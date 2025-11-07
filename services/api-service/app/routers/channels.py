"""Channel management endpoints."""

import json
from fastapi import APIRouter, HTTPException, Query

from app.core.firestore_client import firestore_client
from app.models import ChannelListResponse, ChannelProfile, ChannelStats, ChannelTier, VideoStatus
from app.core.config import settings

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
async def list_channels(
    min_risk: int | None = Query(None, ge=0, le=100, description="Minimum risk score filter"),
    tier: ChannelTier | None = Query(None, description="Filter by channel tier"),
    action_status: str | None = Query(None, description="Filter by action status"),
    sort_by: str = Query("last_seen_at", description="Field to sort by"),
    sort_desc: bool = Query(True, description="Sort descending"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    List channels with filters and pagination.

    Args:
        min_risk: Minimum risk score (0-100)
        tier: Channel tier filter
        action_status: Filter by action status (urgent, pending, etc.)
        sort_by: Sort field (risk_score, last_scanned_at, etc.)
        sort_desc: Sort descending
        limit: Results per page
        offset: Results to skip

    Returns:
        Paginated channel list
    """
    try:
        channels, total = await firestore_client.list_channels(
            min_risk=min_risk,
            tier=tier,
            action_status=action_status,
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

        return ChannelListResponse(
            channels=channels,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(channels)) < total,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list channels: {str(e)}")


@router.get("/stats", response_model=ChannelStats)
async def get_channel_statistics():
    """Get channel tier distribution statistics."""
    try:
        return await firestore_client.get_channel_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get channel stats: {str(e)}")


@router.get("/scan-history-with-processing")
async def get_scan_history_with_processing(limit: int = 50, offset: int = 0):
    """
    OPTIMIZED: Get scan history AND processing videos in one call.

    Combines two endpoints to reduce round trips:
    - /api/channels/scan-history
    - /api/videos/processing/list

    Returns both scan history and currently processing videos.
    """
    try:
        from google.cloud import firestore as fs
        from collections import defaultdict

        # Execute both queries in parallel using asyncio
        import asyncio

        async def get_processing_videos():
            query = firestore_client.videos_collection.where("status", "==", "processing").limit(50)
            docs = list(query.stream())
            videos = []
            for doc in docs:
                data = doc.to_dict()
                if data.get("analysis"):
                    data["vision_analysis"] = data["analysis"]
                from app.models import VideoMetadata
                videos.append(VideoMetadata(**data))
            return videos

        async def get_scan_hist():
            fetch_multiplier = 3
            fetch_limit = (limit + offset) * fetch_multiplier
            scans = (
                firestore_client.db.collection("scan_history")
                .order_by("started_at", direction=fs.Query.DESCENDING)
                .limit(fetch_limit)
                .stream()
            )
            return list(scans)

        # Run both queries in parallel
        processing_videos, scan_docs = await asyncio.gather(
            get_processing_videos(),
            get_scan_hist()
        )

        # Process scan history (existing logic)
        videos = defaultdict(list)
        for scan in scan_docs:
            data = scan.to_dict()
            video_id = data.get("video_id")
            if video_id:
                videos[video_id].append(data)

        grouped_scans = []
        for video_id, attempts in videos.items():
            attempts_sorted = sorted(
                attempts,
                key=lambda x: x.get("started_at") or "",
                reverse=True
            )
            latest = attempts_sorted[0]
            statuses = [a.get("status") for a in attempts_sorted]

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

        grouped_scans.sort(key=lambda x: x.get("started_at") or "", reverse=True)
        paginated_scans = grouped_scans[offset:offset + limit]
        has_more = len(grouped_scans) > offset + limit

        return {
            "scan_history": {
                "scans": paginated_scans,
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            },
            "processing_videos": processing_videos,
            "processing_count": len(processing_videos)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scan data: {str(e)}")


@router.get("/scan-history")
async def get_scan_history(limit: int = 50, offset: int = 0):
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
        from google.cloud import firestore as fs
        from collections import defaultdict

        # Calculate how many scans to fetch
        # Assume average 1.5 attempts per video (some have retries)
        # Fetch extra to account for grouping reducing the count
        fetch_multiplier = 3  # Fetch 3x to handle retries + pagination
        fetch_limit = (limit + offset) * fetch_multiplier

        # Fetch scans with smart limit
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
        raise HTTPException(status_code=500, detail=f"Failed to get scan history: {str(e)}")


@router.get("/{channel_id}", response_model=ChannelProfile)
async def get_channel(channel_id: str):
    """Get detailed channel profile."""
    try:
        channel = await firestore_client.get_channel(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
        return channel
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get channel: {str(e)}")


@router.post("/{channel_id}/scan-all-videos")
async def scan_all_videos(channel_id: str):
    """
    Queue all discovered videos for a channel for vision analysis.

    Publishes all videos to the scan-ready PubSub topic for processing by vision-analyzer-service.

    Args:
        channel_id: Channel ID to scan all videos for

    Returns:
        Stats about queued videos
    """
    from datetime import datetime, timezone

    # Get channel info
    channel = await firestore_client.get_channel(channel_id)
    channel_title = channel.channel_title if channel else channel_id

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
            # Skip already analyzed videos
            if video.status == VideoStatus.ANALYZED:
                videos_already_analyzed += 1
                continue

            # Skip videos currently processing
            if video.status == VideoStatus.PROCESSING:
                videos_skipped += 1
                continue

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
        raise HTTPException(status_code=500, detail=f"Failed to queue videos: {str(e)}")
