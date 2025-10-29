"""Discovery service endpoints."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import httpx

from app.core.discovery_client import discovery_client
from app.core.firestore_client import firestore_client
from app.core.config import settings
from app.models import DiscoveryAnalytics, DiscoveryStats, DiscoveryTriggerRequest, QuotaStatus

router = APIRouter()


@router.post("/trigger", response_model=DiscoveryStats)
async def trigger_discovery(request: DiscoveryTriggerRequest):
    """
    Trigger a discovery run.

    Args:
        request: Discovery trigger parameters

    Returns:
        Discovery statistics
    """
    try:
        result = await discovery_client.trigger_discovery(max_quota=request.max_quota)

        return DiscoveryStats(
            videos_discovered=result.get("videos_discovered", 0),
            videos_with_ip_match=result.get("videos_with_ip_match", 0),
            videos_skipped_duplicate=result.get("videos_skipped_duplicate", 0),
            quota_used=result.get("quota_used", 0),
            channels_tracked=result.get("channels_tracked", 0),
            duration_seconds=result.get("duration_seconds", 0.0),
            timestamp=datetime.now(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger discovery: {str(e)}")


@router.get("/trigger/stream")
async def trigger_discovery_stream(max_quota: int = 1000):
    """
    Trigger discovery with real-time SSE progress updates.

    Proxies SSE events from discovery service to frontend.
    """
    async def event_generator():
        url = f"{settings.discovery_service_url}/discover/run/stream?max_quota={max_quota}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("GET", url) as response:
                async for chunk in response.aiter_raw():
                    if chunk:
                        yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/quota", response_model=QuotaStatus)
async def get_quota_status():
    """Get current YouTube API quota status."""
    try:
        quota_data = await discovery_client.get_quota_status()

        return QuotaStatus(
            daily_quota=quota_data.get("daily_quota", 10000),
            used_quota=quota_data.get("used_quota", 0),
            remaining_quota=quota_data.get("remaining_quota", 10000),
            utilization=quota_data.get("utilization", 0.0),
            last_reset=quota_data.get("last_reset"),
            next_reset=quota_data.get("next_reset"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quota status: {str(e)}")


@router.get("/analytics", response_model=DiscoveryAnalytics)
async def get_discovery_analytics():
    """Get discovery performance analytics."""
    try:
        analytics_data = await discovery_client.get_analytics()
        channel_stats = await firestore_client.get_channel_stats()

        # Extract quota stats
        quota_stats_data = analytics_data.get("quota_stats", {})
        quota_stats = QuotaStatus(
            daily_quota=quota_stats_data.get("daily_quota", 10000),
            used_quota=quota_stats_data.get("used_quota", 0),
            remaining_quota=quota_stats_data.get("remaining_quota", 10000),
            utilization=quota_stats_data.get("utilization", 0.0),
        )

        # Create a dummy discovery stats (in production, query from metrics)
        discovery_stats = DiscoveryStats(
            videos_discovered=0,
            videos_with_ip_match=0,
            videos_skipped_duplicate=0,
            quota_used=quota_stats.used_quota,
            channels_tracked=channel_stats.total,
            duration_seconds=0.0,
            timestamp=datetime.now(),
        )

        # Calculate efficiency
        efficiency = (
            discovery_stats.videos_discovered / discovery_stats.quota_used
            if discovery_stats.quota_used > 0
            else 0.0
        )

        return DiscoveryAnalytics(
            quota_stats=quota_stats,
            discovery_stats=discovery_stats,
            efficiency=efficiency,
            channel_count_by_tier=channel_stats,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")
