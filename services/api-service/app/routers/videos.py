"""Video library endpoints."""

import asyncio
import json
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.firestore_client import firestore_client
from app.models import UserInfo, UserRole, VideoListResponse, VideoMetadata, VideoStatus
from app.utils.logging_utils import log_exception_json

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


@router.get("", response_model=VideoListResponse)
async def list_videos(
    status: VideoStatus | None = Query(None, description="Filter by video status"),
    has_ip_match: bool | None = Query(None, description="Filter by IP match presence"),
    channel_id: str | None = Query(None, description="Filter by channel ID"),
    sort_by: str = Query("discovered_at", description="Field to sort by"),
    sort_desc: bool = Query(True, description="Sort descending"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    List videos with filters and pagination.

    Args:
        status: Filter by processing status
        has_ip_match: Filter by IP match presence
        channel_id: Filter by channel
        sort_by: Sort field (discovered_at, view_count, etc.)
        sort_desc: Sort descending
        limit: Results per page
        offset: Results to skip

    Returns:
        Paginated video list
    """
    try:
        videos, total = await firestore_client.list_videos(
            status=status,
            has_ip_match=has_ip_match,
            channel_id=channel_id,
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

        return VideoListResponse(
            videos=videos,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(videos)) < total,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {e!s}")


@router.get("/processing/list")
async def list_processing_videos():
    """
    Get all currently processing videos (OPTIMIZED).

    Returns list of videos that are actively being scanned by Gemini.
    Useful for showing progress indicators and allowing users to reopen progress modals.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        # OPTIMIZED: Direct Firestore query without pagination overhead
        # Only fetch processing videos (should be 0-10 typically)
        query = firestore_client.videos_collection.where("status", "==", "processing").limit(50)

        docs = list(query.stream())

        videos = []
        for doc in docs:
            data = doc.to_dict()

            # Map analysis field to vision_analysis for API response
            if data.get("analysis"):
                data["vision_analysis"] = data["analysis"]

            # Import here to avoid circular dependency
            from app.models import VideoMetadata
            videos.append(VideoMetadata(**data))

        return {
            "processing_videos": videos,
            "count": len(videos)
        }
    except Exception as e:
        log_exception_json(logger, "Failed to list processing videos", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=f"Failed to list processing videos: {e!s}")


@router.get("/{video_id}", response_model=VideoMetadata)
async def get_video(video_id: str):
    """Get detailed video metadata."""
    try:
        video = await firestore_client.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
        return video
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video: {e!s}")


@router.post("/{video_id}/scan")
async def scan_video(
    video_id: str,
    user: UserInfo = Depends(get_current_user)
):
    """
    Manually trigger vision analysis for a video.

    Publishes the video to the scan-ready PubSub topic for immediate analysis.

    Requires: EDITOR or ADMIN role

    Args:
        video_id: Video ID to scan

    Returns:
        Success message
    """
    # Check permissions - only EDITOR, LEGAL, and ADMIN can trigger scans
    if user.role not in [UserRole.EDITOR, UserRole.LEGAL, UserRole.ADMIN]:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions. Role '{user.role.value}' cannot trigger scans. Required: editor, legal, or admin."
        )

    try:
        # Get video metadata
        video = await firestore_client.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

        # NOTE: scan_history entry will be created by vision-analyzer worker
        # No need to create it here - avoids duplicates

        # Build scan message
        scan_message = {
            "video_id": video_id,
            "priority": 100,  # High priority for manual scans
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

        # Publish to scan-ready topic
        publisher = get_publisher()
        topic_path = publisher.topic_path(settings.gcp_project_id, "scan-ready")
        message_data = json.dumps(scan_message).encode("utf-8")

        future = publisher.publish(topic_path, message_data)
        message_id = future.result()  # Wait for publish to complete

        return {
            "success": True,
            "message": f"Video {video_id} queued for analysis (message_id: {message_id})",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger scan: {e!s}")


@router.get("/{video_id}/scan/stream")
async def scan_video_stream(video_id: str):
    """
    Scan a video with real-time SSE progress updates.

    Monitors Firestore for status changes and sends progress updates.
    """
    async def event_generator():
        try:
            # Get video metadata
            video = await firestore_client.get_video(video_id)
            if not video:
                yield f"data: {json.dumps({'status': 'error', 'message': f'Video {video_id} not found'})}\n\n"
                return

            # NEVER auto-trigger scans - only monitor existing scans
            if video.status == "analyzed":
                yield f"data: {json.dumps({'status': 'completed', 'message': 'Video already analyzed', 'elapsed': 0})}\n\n"
                return

            if video.status == "processing":
                # Monitor existing scan
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Monitoring scan progress...'})}\n\n"
            else:
                # Video not queued - don't trigger, just inform user
                yield f"data: {json.dumps({'status': 'error', 'message': 'Video not queued for scanning. Use batch scan to queue videos.'})}\n\n"
                return

            # Poll Firestore for status updates
            max_wait = 180  # 3 minutes (increased for longer videos)
            poll_interval = 2  # 2 seconds
            elapsed = 0
            last_status = None

            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                # Check video status
                video = await firestore_client.get_video(video_id)
                if not video:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Video not found'})}\n\n"
                    return

                # Calculate real elapsed time from when processing started
                real_elapsed = elapsed
                if video.status == "processing" and hasattr(video, 'processing_started_at') and video.processing_started_at:
                    from datetime import datetime
                    now = datetime.now(UTC)
                    start_time = video.processing_started_at
                    # Ensure start_time is timezone-aware
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=UTC)
                    real_elapsed = int((now - start_time).total_seconds())

                # Only send update if status changed or every 10 seconds
                if video.status != last_status or elapsed % 10 == 0:
                    if video.status == "processing":
                        # Include processing_started_at timestamp for accurate progress synchronization
                        processing_started_at = None
                        if hasattr(video, 'processing_started_at') and video.processing_started_at:
                            processing_started_at = int(video.processing_started_at.timestamp())

                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Analyzing video with Gemini AI...', 'elapsed': real_elapsed, 'processing_started_at': processing_started_at})}\n\n"
                        last_status = "processing"

                    elif video.status == "analyzed":
                        # Get analysis results
                        analysis_data = video.vision_analysis.full_analysis if hasattr(video.vision_analysis, 'full_analysis') else video.vision_analysis

                        result = {
                            'status': 'completed',
                            'message': 'Analysis complete!',
                            'elapsed': elapsed,
                            'infringement': analysis_data.get('contains_infringement', False) if analysis_data else False,
                            'confidence': analysis_data.get('confidence_score', 0) if analysis_data else 0,
                            'characters': [c.get('name') for c in analysis_data.get('characters_detected', [])] if analysis_data else []
                        }
                        yield f"data: {json.dumps(result)}\n\n"

                        # Wait a bit before closing to ensure message is received
                        await asyncio.sleep(1)
                        return

                    elif video.status == "failed":
                        error_msg = getattr(video, 'error_message', 'Unknown error')
                        error_type = getattr(video, 'error_type', 'Error')
                        yield f"data: {json.dumps({'status': 'failed', 'message': 'Analysis failed', 'elapsed': elapsed, 'error_type': error_type, 'error_message': error_msg})}\n\n"
                        return

            # Timeout - but analysis might still complete
            yield f"data: {json.dumps({'status': 'timeout', 'message': 'Analysis is taking longer than expected. It will continue in the background. Check the video list in a few minutes.', 'elapsed': elapsed})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
