"""Channel management endpoints."""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user, require_role
from app.core.config import settings
from app.core.firestore_client import firestore_client
from app.models import ChannelListResponse, ChannelProfile, ChannelStats, ChannelTier, UserInfo, UserRole, VideoStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize PubSub publisher (lazy import)
_publisher = None


def get_publisher():
    """Get or create PubSub publisher client."""
    global _publisher
    if _publisher is None:
        from google.cloud import pubsub_v1
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


@router.get("", response_model=ChannelListResponse)
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def list_channels(
    user: UserInfo = Depends(get_current_user),
    min_risk: int | None = Query(None, ge=0, le=100, description="Minimum risk score filter"),
    tier: ChannelTier | None = Query(None, description="Filter by channel tier"),
    action_status: str | None = Query(None, description="Filter by action status"),
    sort_by: str = Query("last_seen_at", description="Field to sort by"),
    sort_desc: bool = Query(True, description="Sort descending"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per page"),
    cursor: str | None = Query(None, description="Cursor for pagination (channel_id)"),
):
    """
    List channels with cursor-based pagination (FAST!).

    Args:
        min_risk: Minimum risk score (0-100)
        tier: Channel tier filter
        action_status: Filter by action status (urgent, pending, etc.)
        sort_by: Sort field (risk_score, last_scanned_at, etc.)
        sort_desc: Sort descending
        limit: Results per page
        cursor: Cursor (channel_id of last item from previous page)

    Returns:
        Paginated channel list with next_cursor
    """
    try:
        channels, total, next_cursor = await firestore_client.list_channels(
            min_risk=min_risk,
            tier=tier,
            action_status=action_status,
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=limit,
            cursor=cursor,
        )

        return {
            "channels": channels,
            "total": total,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list channels: {e!s}")


@router.get("/stats", response_model=ChannelStats)
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_channel_statistics(user: UserInfo = Depends(get_current_user)):
    """Get channel tier distribution statistics."""
    try:
        return await firestore_client.get_channel_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get channel stats: {e!s}")


@router.get("/scan-history-with-processing")
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_scan_history_with_processing(
    user: UserInfo = Depends(get_current_user),
    limit: int = 50,
    cursor: str | None = None
):
    """
    BLAZING FAST: Cursor-based pagination (no offset!).

    Instead of offset, use cursor (the last scan_id from previous page).
    Firestore .start_after() is O(1) instead of O(n) like offset!

    Performance: <200ms regardless of page number!
    """
    import logging
    import time
    logger = logging.getLogger(__name__)

    start_time = time.time()

    try:
        from google.cloud import firestore as fs

        async def get_scan_hist():
            query_start = time.time()

            # CURSOR-BASED PAGINATION - The FAST way!
            query = (
                firestore_client.db.collection("scan_history")
                .order_by("started_at", direction=fs.Query.DESCENDING)
                .limit(limit + 1)  # Fetch one extra to check if there's more
            )

            # Use cursor for pagination (FAST!)
            if cursor:
                cursor_lookup_start = time.time()
                # Get the cursor document to start after
                cursor_doc = firestore_client.db.collection("scan_history").document(cursor).get()
                cursor_lookup_time = (time.time() - cursor_lookup_start) * 1000
                logger.info(f"⏱️  Cursor lookup: {cursor_lookup_time:.2f}ms")

                if cursor_doc.exists:
                    query = query.start_after(cursor_doc)

            stream_start = time.time()
            result = list(query.stream())
            stream_time = (time.time() - stream_start) * 1000

            query_time = (time.time() - query_start) * 1000
            logger.info(f"⏱️  Firestore query total: {query_time:.2f}ms (stream: {stream_time:.2f}ms)")

            return result

        # ONLY fetch scan history - processing videos removed (too slow!)
        # Fetch MORE docs to account for grouping reducing count
        query_exec_start = time.time()
        scan_docs = await get_scan_hist()
        query_exec_time = (time.time() - query_exec_start) * 1000
        logger.info(f"⏱️  Query execution: {query_exec_time:.2f}ms")

        # Fetch queued/processing videos (lightweight - just first 10 with matched_ips)
        # Show both pending (queued) and processing (currently analyzing)
        pending_query_start = time.time()
        queued_videos = []
        try:
            # Get pending videos with high priority (queued for analysis)
            pending_docs = (
                firestore_client.videos_collection
                .where("status", "==", "pending")
                .where("matched_ips", "!=", [])
                .order_by("scan_priority", direction=fs.Query.DESCENDING)
                .limit(10)
                .stream()
            )
            for doc in pending_docs:
                data = doc.to_dict()
                queued_videos.append({
                    "video_id": doc.id,
                    "title": data.get("title", "Unknown"),
                    "channel_title": data.get("channel_title"),
                    "matched_ips": data.get("matched_ips", []),
                    "scan_priority": data.get("scan_priority", 0),
                    "status": "queued",
                })

            # Also get processing videos (currently being analyzed)
            processing_docs = (
                firestore_client.videos_collection
                .where("status", "==", "processing")
                .limit(10)
                .stream()
            )
            for doc in processing_docs:
                data = doc.to_dict()
                queued_videos.append({
                    "video_id": doc.id,
                    "title": data.get("title", "Unknown"),
                    "channel_title": data.get("channel_title"),
                    "matched_ips": data.get("matched_ips", []),
                    "scan_priority": data.get("scan_priority", 0),
                    "status": "processing",
                })

            # Sort by priority (processing first, then by priority)
            queued_videos.sort(key=lambda x: (0 if x["status"] == "processing" else 1, -x.get("scan_priority", 0)))
            queued_videos = queued_videos[:10]  # Limit to 10 total

        except Exception as e:
            logger.warning(f"Failed to fetch queued videos: {e}")

        pending_query_time = (time.time() - pending_query_start) * 1000
        logger.info(f"⏱️  Queued videos query: {pending_query_time:.2f}ms")


        # GROUP scans by video_id - show latest status per video
        processing_start = time.time()
        from collections import defaultdict

        video_scans = defaultdict(list)
        for scan_doc in scan_docs:
            data = scan_doc.to_dict()
            data["scan_id"] = scan_doc.id
            video_id = data.get("video_id")
            if video_id:
                video_scans[video_id].append(data)

        grouping_time = (time.time() - processing_start) * 1000
        logger.info(f"⏱️  Grouping by video_id: {grouping_time:.2f}ms")

        # Create grouped scans (one per video, latest status)
        condensing_start = time.time()
        grouped_scans = []
        for video_id, attempts in video_scans.items():
            # Sort by started_at (most recent first)
            attempts_sorted = sorted(
                attempts,
                key=lambda x: x.get("started_at") or "",
                reverse=True
            )
            latest = attempts_sorted[0]
            statuses = [a.get("status") for a in attempts_sorted]

            # Aggregate status logic
            if "running" in statuses:
                aggregate_status = "running"
            elif all(s == "failed" for s in statuses):
                aggregate_status = "failed"
            elif "completed" in statuses:
                aggregate_status = "completed"
            else:
                aggregate_status = latest.get("status", "unknown")

            grouped_scan = {
                **latest,
                "status": aggregate_status,
                "attempt_count": len(attempts_sorted),
                "attempts": attempts_sorted if len(attempts_sorted) > 1 else None,
            }
            grouped_scans.append(grouped_scan)

        # Sort by started_at
        grouped_scans.sort(key=lambda x: x.get("started_at") or "", reverse=True)

        condensing_time = (time.time() - condensing_start) * 1000
        logger.info(f"⏱️  Condensing scans: {condensing_time:.2f}ms")

        # Paginate grouped results
        # IMPORTANT: Check if we have MORE than limit (because we fetched limit+1 from Firestore)
        # But after grouping, we might have fewer unique videos
        scans = grouped_scans[:limit]
        # has_more = did we fetch limit+1 raw docs? (means there's more in Firestore)
        has_more = len(scan_docs) > limit
        next_cursor = scans[-1]["scan_id"] if (scans and has_more) else None

        processing_time = (time.time() - processing_start) * 1000
        logger.info(f"⏱️  Data processing total: {processing_time:.2f}ms (grouped {len(scan_docs)} scans into {len(grouped_scans)} videos)")

        total_time = (time.time() - start_time) * 1000
        logger.info(f"⏱️  TOTAL request time: {total_time:.2f}ms (cursor={cursor}, limit={limit}, results={len(scans)})")

        return {
            "scan_history": {
                "scans": scans,
                "limit": limit,
                "cursor": cursor,
                "next_cursor": next_cursor if has_more else None,
                "has_more": has_more
            },
            "processing_videos": [],  # Removed - use /api/videos/processing/list if needed
            "processing_count": 0,  # Frontend can get this from analytics
            "_debug": {
                "total_time_ms": round(total_time, 2),
                "query_time_ms": round(query_exec_time, 2),
                "processing_time_ms": round(processing_time, 2),
                "docs_fetched": len(scan_docs),
                "docs_returned": len(scans)
            }
        }

    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Request failed after {total_time:.2f}ms: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to get scan data: {e!s}")


@router.get("/scan-updates-stream")
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def scan_updates_stream(user: UserInfo = Depends(get_current_user)):
    """
    SSE (Server-Sent Events) stream for real-time scan updates.

    Streams scan status changes for running scans and new scans.
    Frontend should use this to update records in place instead of polling.

    Event types:
    - scan_started: New scan has started
    - scan_updated: Scan status changed (running -> completed/failed)
    - scan_completed: Scan finished successfully
    - scan_failed: Scan failed with error
    - processing_video: Video moved to processing status
    - heartbeat: Keep-alive ping every 15s
    """
    async def event_generator():
        """Generate SSE events from Firestore snapshots."""
        from google.cloud import firestore as fs

        try:
            # Track last seen timestamps to avoid duplicates
            last_check = datetime.utcnow()

            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"

            while True:
                try:
                    # Query for recent scans (last 30 seconds)
                    current_time = datetime.utcnow()
                    time_window = (current_time - last_check).total_seconds()

                    # Get running scans and recently completed/failed scans
                    recent_scans = []

                    # Running scans
                    running_query = (
                        firestore_client.db.collection("scan_history")
                        .where("status", "==", "running")
                        .order_by("started_at", direction=fs.Query.DESCENDING)
                        .limit(50)
                        .stream()
                    )

                    for doc in running_query:
                        data = doc.to_dict()
                        data["scan_id"] = doc.id
                        recent_scans.append({
                            "type": "scan_updated",
                            "scan": data
                        })

                    # Recently completed scans (last 30s)
                    if time_window > 0:
                        completed_query = (
                            firestore_client.db.collection("scan_history")
                            .where("status", "in", ["completed", "failed"])
                            .order_by("completed_at", direction=fs.Query.DESCENDING)
                            .limit(20)
                            .stream()
                        )

                        for doc in completed_query:
                            data = doc.to_dict()
                            completed_at = data.get("completed_at")

                            # Check if completed recently
                            if completed_at:
                                if isinstance(completed_at, datetime):
                                    # Make timezone-naive for comparison
                                    completed_time = completed_at.replace(tzinfo=None) if completed_at.tzinfo else completed_at
                                elif hasattr(completed_at, 'seconds'):
                                    # Firestore timestamp - always timezone-naive
                                    completed_time = datetime.fromtimestamp(completed_at.seconds)
                                else:
                                    continue

                                # Only send if completed after last check
                                if completed_time > last_check:
                                    data["scan_id"] = doc.id
                                    event_type = "scan_completed" if data["status"] == "completed" else "scan_failed"
                                    recent_scans.append({
                                        "type": event_type,
                                        "scan": data
                                    })

                    # Send events
                    for event in recent_scans:
                        event_data = json.dumps(event["scan"], default=str)
                        yield f"event: {event['type']}\ndata: {event_data}\n\n"

                    # Get processing videos
                    processing_videos = []
                    processing_query = (
                        firestore_client.videos_collection
                        .where("status", "in", ["pending", "processing"])
                        .where("matched_ips", "!=", [])
                        .order_by("scan_priority", direction=fs.Query.DESCENDING)
                        .limit(10)
                        .stream()
                    )

                    for doc in processing_query:
                        data = doc.to_dict()
                        processing_videos.append({
                            "video_id": doc.id,
                            "title": data.get("title", "Unknown"),
                            "channel_title": data.get("channel_title"),
                            "matched_ips": data.get("matched_ips", []),
                            "status": data.get("status")
                        })

                    # Send processing videos update
                    if processing_videos:
                        yield f"event: processing_videos\ndata: {json.dumps(processing_videos)}\n\n"

                    last_check = current_time

                    # Wait before next check (5 seconds)
                    await asyncio.sleep(5)

                    # Send heartbeat every iteration
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"

                except Exception as e:
                    logger.error(f"Error in SSE event loop: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("SSE stream cancelled by client")
            raise
        except Exception as e:
            logger.error(f"Fatal error in SSE stream: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/scan-history")
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_scan_history(user: UserInfo = Depends(get_current_user), limit: int = 50, offset: int = 0):
    """
    Get recent scan history with smart grouping by video_id.

    For efficiency with large datasets:
    - Fetches enough scans to fill the requested page
    - Groups by video_id dynamically
    - If grouping reduces results below limit, fetches more

    Status logic:
    - If ANY scan is "running" → status = "running"
    - If ALL scans failed → status = "failed"
    - If ANY scan completed → status = "completed"
    """
    try:
        from collections import defaultdict

        from google.cloud import firestore as fs

        # OPTIMIZED: Fetch only what we need
        # Most videos have 1-2 scan attempts, reduced from 3x to 2x multiplier
        fetch_multiplier = 2  # Reduced from 3 to 2
        fetch_limit = (limit + offset) * fetch_multiplier

        # Fetch scans with optimized limit
        scans = (
            firestore_client.db.collection("scan_history")
            .order_by("started_at", direction=fs.Query.DESCENDING)
            .limit(fetch_limit)
            .stream()
        )

        # Group scans by video_id
        videos = defaultdict(list)
        seen_video_ids = set()

        for scan in scans:
            data = scan.to_dict()
            video_id = data.get("video_id")
            if video_id:
                videos[video_id].append(data)
                seen_video_ids.add(video_id)

        # Process each video group
        grouped_scans = []
        for video_id, attempts in videos.items():
            # Sort attempts by started_at (most recent first)
            attempts_sorted = sorted(
                attempts,
                key=lambda x: x.get("started_at") or "",
                reverse=True
            )

            # Get the most recent attempt as the primary scan
            latest = attempts_sorted[0]

            # Determine aggregate status
            statuses = [a.get("status") for a in attempts_sorted]

            if "running" in statuses:
                aggregate_status = "running"
            elif all(s == "failed" for s in statuses):
                aggregate_status = "failed"
            elif "completed" in statuses:
                aggregate_status = "completed"
            else:
                aggregate_status = latest.get("status", "unknown")

            # Create grouped scan entry
            grouped_scan = {
                **latest,  # Use latest scan data as base
                "status": aggregate_status,  # Override with aggregate status
                "attempt_count": len(attempts_sorted),
                "attempts": attempts_sorted if len(attempts_sorted) > 1 else None,
            }

            grouped_scans.append(grouped_scan)

        # Sort by most recent started_at
        grouped_scans.sort(
            key=lambda x: x.get("started_at") or "",
            reverse=True
        )

        # Apply pagination AFTER grouping
        paginated_scans = grouped_scans[offset:offset + limit]

        # Check if we have more results
        # If we fetched more than we're returning, there are definitely more
        has_more = len(grouped_scans) > offset + limit

        return {
            "scans": paginated_scans,
            "limit": limit,
            "offset": offset,
            "has_more": has_more
            # Note: No "total" field - we don't know the exact total without fetching everything
            # Frontend should use has_more for pagination
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scan history: {e!s}")


@router.get("/{channel_id}", response_model=ChannelProfile)
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_channel(channel_id: str, user: UserInfo = Depends(get_current_user)):
    """Get detailed channel profile."""
    try:
        channel = await firestore_client.get_channel(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
        return channel
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get channel: {e!s}")


@router.post("/{channel_id}/scan-all-videos")
async def scan_all_videos(
    channel_id: str,
    user: UserInfo = Depends(get_current_user)
):
    """
    Queue all discovered videos for a channel for vision analysis.

    Publishes all videos to the scan-ready PubSub topic for processing by vision-analyzer-service.

    Requires: EDITOR or ADMIN role

    Args:
        channel_id: Channel ID to scan all videos for

    Returns:
        Stats about queued videos
    """
    # Check permissions - only EDITOR, LEGAL, and ADMIN can trigger scans
    if user.role not in [UserRole.EDITOR, UserRole.LEGAL, UserRole.ADMIN]:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions. Role '{user.role.value}' cannot trigger scans. Required: editor, legal, or admin."
        )

    # Get channel info
    await firestore_client.get_channel(channel_id)

    # NOTE: scan_history entries will be created per-video by vision-analyzer worker
    # No batch operation tracking - only individual video scans

    try:
        # Get all videos for this channel
        videos, total = await firestore_client.list_videos(
            channel_id=channel_id,
            limit=1000,  # Max videos to queue at once
            offset=0,
        )

        if not videos:
            return {
                "success": True,
                "message": f"No videos found for channel {channel_id}",
                "videos_queued": 0,
                "videos_already_analyzed": 0,
                "videos_skipped": 0,
            }

        # Publish each video to scan-ready topic
        publisher = get_publisher()
        topic_path = publisher.topic_path(settings.gcp_project_id, "scan-ready")

        videos_queued = 0
        videos_already_analyzed = 0
        videos_skipped = 0

        for video in videos:
            # Skip videos currently processing (to avoid duplicate scans)
            if video.status == VideoStatus.PROCESSING:
                videos_skipped += 1
                continue

            # Track already analyzed videos (but still rescan them)
            if video.status == VideoStatus.ANALYZED:
                videos_already_analyzed += 1

            # Build scan message
            scan_message = {
                "video_id": video.video_id,
                "priority": 80,  # Medium-high priority for bulk scans
                "metadata": {
                    "video_id": video.video_id,
                    "youtube_url": f"https://youtube.com/watch?v={video.video_id}",
                    "title": video.title,
                    "duration_seconds": video.duration_seconds or 300,
                    "view_count": video.view_count,
                    "channel_id": video.channel_id,
                    "channel_title": video.channel_title,
                    "risk_score": getattr(video, "risk_score", 50.0),
                    "risk_tier": getattr(video, "risk_tier", "MEDIUM"),
                    "matched_ips": video.matched_ips or [],
                    "discovered_at": video.discovered_at.isoformat(),
                    "last_risk_update": video.discovered_at.isoformat(),
                }
            }

            # Publish to PubSub
            message_data = json.dumps(scan_message).encode("utf-8")
            future = publisher.publish(topic_path, message_data)
            future.result()  # Wait for publish to complete
            videos_queued += 1

        return {
            "success": True,
            "message": f"Queued {videos_queued} videos for analysis",
            "videos_queued": videos_queued,
            "videos_already_analyzed": videos_already_analyzed,
            "videos_skipped": videos_skipped,
            "total_videos": total,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue videos: {e!s}")
