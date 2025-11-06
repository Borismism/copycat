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


@router.get("/scan-history")
async def get_scan_history(limit: int = 50):
    """Get recent scan history."""
    try:
        from google.cloud import firestore as fs

        scans = (
            firestore_client.db.collection("scan_history")
            .order_by("started_at", direction=fs.Query.DESCENDING)
            .limit(limit)
            .stream()
        )

        history = []
        for scan in scans:
            data = scan.to_dict()
            history.append(data)

        return {"scans": history, "total": len(history)}

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
