"""Channel management endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user, require_role
from app.core.config import settings
from app.core.firestore_client import firestore_client
from app.models import ChannelListResponse, ChannelProfile, ChannelStats, ChannelTier, UserInfo, UserRole, VideoStatus

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
