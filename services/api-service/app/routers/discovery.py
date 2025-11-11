"""Discovery service endpoints."""

from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.cloud import firestore

from app.core.auth import get_current_user, require_role
from app.core.config import settings
from app.core.discovery_client import discovery_client
from app.core.firestore_client import FirestoreClient, firestore_client, get_firestore_client
from app.models import DiscoveryAnalytics, DiscoveryStats, DiscoveryTriggerRequest, QuotaStatus, UserInfo, UserRole

router = APIRouter()


@router.post("/trigger", response_model=DiscoveryStats)
@require_role(UserRole.ADMIN, UserRole.EDITOR)
async def trigger_discovery(request: DiscoveryTriggerRequest, user: UserInfo = Depends(get_current_user)):
    """
    Trigger a discovery run (admin/editor only).

    Args:
        request: Discovery trigger parameters
        user: Current user (from IAP)

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
        raise HTTPException(status_code=500, detail=f"Failed to trigger discovery: {e!s}")


@router.get("/trigger/stream")
@require_role(UserRole.ADMIN, UserRole.EDITOR)
async def trigger_discovery_stream(max_quota: int = 1000, user: UserInfo = Depends(get_current_user)):
    """
    Trigger discovery with real-time SSE progress updates.

    Proxies SSE events from discovery service to frontend.

    Requires: EDITOR or ADMIN role
    """
    async def event_generator():
        url = f"{settings.discovery_service_url}/discover/run/stream?max_quota={max_quota}"

        # Get ID token for authentication (same as discovery_client)
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        headers = {}
        if settings.environment != "local":
            auth_req = Request()
            token = id_token.fetch_id_token(auth_req, settings.discovery_service_url)
            headers["authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("GET", url, headers=headers) as response:
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
async def get_quota_status(
    firestore_client: FirestoreClient = Depends(get_firestore_client),
):
    """
    Get current YouTube API quota status from Firestore.

    Reads from quota_usage collection (single source of truth).
    Updated automatically after discovery runs and on-demand via /quota/refresh.
    """
    try:
        from datetime import datetime, UTC
        from zoneinfo import ZoneInfo

        # Get today's date in Pacific Time (YouTube API quota resets at midnight PT)
        pacific_tz = ZoneInfo("America/Los_Angeles")
        now_pacific = datetime.now(UTC).astimezone(pacific_tz)
        today_key = now_pacific.strftime("%Y-%m-%d")

        # Read from Firestore quota_usage collection
        doc = firestore_client.db.collection("quota_usage").document(today_key).get()

        if doc.exists:
            data = doc.to_dict()
            used_quota = data.get("units_used", 0)
            daily_quota = data.get("daily_quota", 10000)
        else:
            # No usage record for today - quota is fresh
            used_quota = 0
            daily_quota = 10000

        remaining_quota = max(0, daily_quota - used_quota)
        utilization = (used_quota / daily_quota) if daily_quota > 0 else 0.0

        return QuotaStatus(
            daily_quota=daily_quota,
            used_quota=used_quota,
            remaining_quota=remaining_quota,
            utilization=utilization,
            last_reset=None,  # Not tracked yet
            next_reset=None,  # Not tracked yet
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quota status: {e!s}")


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
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {e!s}")


@router.post("/discover/channel/{channel_id}/scan")
@require_role(UserRole.ADMIN, UserRole.EDITOR)
async def scan_channel(channel_id: str, max_videos: int = 50, user: UserInfo = Depends(get_current_user)):
    """
    Scan a specific channel for videos.
    Proxies request to discovery service.

    Requires: EDITOR or ADMIN role
    """

    # NOTE: No scan_history tracking for discovery operations
    # Only per-video scans are tracked in scan_history

    try:
        url = f"{settings.discovery_service_url}/discover/channel/{channel_id}/scan?max_videos={max_videos}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url)
            response.raise_for_status()
            result = response.json()

        return result

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan channel: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan channel: {e!s}")


@router.get("/history")
async def get_discovery_history(
    limit: int = 20,
    offset: int = 0,
    firestore_client: FirestoreClient = Depends(get_firestore_client),
):
    """
    Get discovery run history with pagination.

    Args:
        limit: Number of runs to return
        offset: Number of runs to skip

    Returns:
        List of discovery runs
    """
    try:
        # Fetch from Firestore
        query = firestore_client.db.collection("discovery_history").order_by(
            "started_at", direction=firestore.Query.DESCENDING
        )

        all_runs = list(query.stream())
        total = len(all_runs)

        # Apply pagination
        paginated_runs = all_runs[offset:offset+limit]

        runs = []
        for doc in paginated_runs:
            data = doc.to_dict()
            runs.append(data)

        return {
            "runs": runs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch discovery history: {e!s}")
