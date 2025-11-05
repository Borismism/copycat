"""Channel management endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.core.firestore_client import firestore_client
from app.models import ChannelListResponse, ChannelProfile, ChannelStats, ChannelTier

router = APIRouter()


@router.get("", response_model=ChannelListResponse)
async def list_channels(
    min_risk: int | None = Query(None, ge=0, le=100, description="Minimum risk score filter"),
    tier: ChannelTier | None = Query(None, description="Filter by channel tier"),
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
