"""Video library endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.core.firestore_client import firestore_client
from app.models import VideoListResponse, VideoMetadata, VideoStatus

router = APIRouter()


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
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to get video: {str(e)}")
