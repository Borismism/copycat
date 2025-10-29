"""Discovery router - Clean, simplified API endpoints."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.cloud import firestore, pubsub_v1

from ..config import settings
from ..core.channel_tracker import ChannelTracker
from ..core.discovery_engine import DiscoveryEngine
from ..core.ip_loader import IPTargetManager
from ..core.keyword_tracker import KeywordTracker
from ..core.quota_manager import QuotaManager
from ..core.video_processor import VideoProcessor
from ..core.youtube_client import YouTubeClient
from ..models import (
    ChannelProfile,
    DiscoveryStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover", tags=["discovery"])


# ============================================================================
# Dependency Injection
# ============================================================================


def get_firestore_client() -> firestore.Client:
    """Get Firestore client."""
    return firestore.Client(
        project=settings.gcp_project_id, database=settings.firestore_database_id
    )


def get_pubsub_publisher() -> pubsub_v1.PublisherClient:
    """Get PubSub publisher client."""
    return pubsub_v1.PublisherClient()


def get_youtube_client() -> YouTubeClient:
    """Get YouTube API client."""
    if not settings.youtube_api_key:
        raise HTTPException(status_code=500, detail="No YouTube API key configured")
    return YouTubeClient(api_key=settings.youtube_api_key)


def get_video_processor(
    firestore_client: firestore.Client = Depends(get_firestore_client),
    pubsub_publisher: pubsub_v1.PublisherClient = Depends(get_pubsub_publisher),
) -> VideoProcessor:
    """Get video processor."""
    ip_manager = IPTargetManager()
    topic_path = pubsub_publisher.topic_path(
        settings.gcp_project_id, settings.pubsub_topic_discovered_videos
    )
    return VideoProcessor(
        firestore_client=firestore_client,
        pubsub_publisher=pubsub_publisher,
        ip_manager=ip_manager,
        topic_path=topic_path,
    )


def get_channel_tracker(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ChannelTracker:
    """Get channel tracker."""
    return ChannelTracker(firestore_client=firestore_client)


# Cached instances to avoid recreating on every request
_quota_manager_cache: QuotaManager | None = None

def get_quota_manager(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> QuotaManager:
    """Get quota manager (cached singleton)."""
    global _quota_manager_cache
    if _quota_manager_cache is None:
        _quota_manager_cache = QuotaManager(firestore_client=firestore_client, daily_quota=10_000)
    return _quota_manager_cache


def get_keyword_tracker(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> KeywordTracker:
    """Get keyword tracker."""
    return KeywordTracker(firestore_client=firestore_client)


def get_discovery_engine(
    youtube_client: YouTubeClient = Depends(get_youtube_client),
    video_processor: VideoProcessor = Depends(get_video_processor),
    channel_tracker: ChannelTracker = Depends(get_channel_tracker),
    quota_manager: QuotaManager = Depends(get_quota_manager),
    keyword_tracker: KeywordTracker = Depends(get_keyword_tracker),
) -> DiscoveryEngine:
    """Get discovery engine."""
    return DiscoveryEngine(
        youtube_client=youtube_client,
        video_processor=video_processor,
        channel_tracker=channel_tracker,
        quota_manager=quota_manager,
        keyword_tracker=keyword_tracker,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/run", response_model=DiscoveryStats)
async def discover(
    max_quota: int = 100,
    engine: DiscoveryEngine = Depends(get_discovery_engine),
) -> DiscoveryStats:
    """
    Run intelligent discovery until quota exhausted.

    Automatically uses best strategy:
    1. Channel tracking (70% quota) - most efficient
    2. Trending videos (20% quota) - cheap and broad
    3. Targeted keywords (10% quota) - expensive but precise

    Args:
        max_quota: Maximum quota limit for this run (default: 100 units)

    Returns:
        Discovery statistics
    """
    logger.info(f"Starting discovery run with max_quota={max_quota}")

    try:
        stats = await engine.discover(max_quota=max_quota)
        return stats

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/run/stream")
async def run_discovery_stream(
    max_quota: int = 100,
    engine: DiscoveryEngine = Depends(get_discovery_engine),
):
    """
    Run discovery with real-time SSE progress updates.

    Streams progress events as discovery runs through each tier.
    """
    async def event_generator():
        try:
            # Send initial status
            yield f"data: {json.dumps({'status': 'starting', 'quota': max_quota})}\n\n"
            await asyncio.sleep(0.1)

            # Run discovery (this will take a few seconds)
            # We'll send progress updates by checking intermediate state
            yield f"data: {json.dumps({'status': 'tier1', 'message': 'Scanning fresh content...'})}\n\n"
            await asyncio.sleep(0.1)

            # Start discovery
            stats = await engine.discover(max_quota=max_quota)

            # Send tier updates (stats is DiscoveryStats pydantic model, not dict)
            yield f"data: {json.dumps({'status': 'tier2', 'message': 'Tracking channels...'})}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'status': 'tier3', 'message': 'Keyword rotation...'})}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'status': 'tier4', 'message': 'Rescanning videos...'})}\n\n"
            await asyncio.sleep(0.1)

            # Send final results (convert pydantic model to dict)
            result = {
                'status': 'complete',
                'videos_discovered': stats.videos_discovered,
                'videos_with_ip_match': stats.videos_with_ip_match,
                'videos_skipped_duplicate': stats.videos_skipped_duplicate,
                'quota_used': stats.quota_used,
                'channels_tracked': stats.channels_tracked,
                'duration_seconds': stats.duration_seconds,
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            logger.error(f"Discovery stream failed: {e}")
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


@router.get("/channels", response_model=list[ChannelProfile])
async def list_channels(
    min_risk: int | None = None,
    limit: int = 50,
    tracker: ChannelTracker = Depends(get_channel_tracker),
) -> list[ChannelProfile]:
    """
    List tracked channels with optional risk score filter.

    Args:
        min_risk: Minimum risk score (0-100, optional)
        limit: Maximum channels to return

    Returns:
        List of channel profiles ordered by risk score (highest first)
    """
    try:
        channels = tracker.get_all_channels(min_risk=min_risk, limit=limit)
        return channels

    except Exception as e:
        logger.error(f"Failed to list channels: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list channels: {str(e)}"
        )


@router.get("/analytics/discovery")
async def get_discovery_analytics(
    quota_manager: QuotaManager = Depends(get_quota_manager),
    channel_tracker: ChannelTracker = Depends(get_channel_tracker),
) -> dict:
    """
    Get discovery performance metrics.

    Refreshes quota from Firestore to ensure up-to-date values.

    Returns:
        Analytics data including quota usage and channel statistics
    """
    try:
        # Refresh quota from Firestore to get latest usage
        quota_manager.reload_usage()

        # Get quota stats
        quota_stats = {
            "total_quota": quota_manager.daily_quota,
            "used_quota": quota_manager.used_quota,
            "remaining_quota": quota_manager.get_remaining(),
            "utilization": quota_manager.get_utilization(),
        }

        # Get channel stats
        channel_stats = channel_tracker.get_statistics()

        return {
            "quota": quota_stats,
            "channels": channel_stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get analytics: {str(e)}"
        )


@router.get("/quota")
async def get_quota_status(
    quota_manager: QuotaManager = Depends(get_quota_manager),
) -> dict:
    """
    Get current YouTube API quota status.

    Refreshes from Firestore to ensure up-to-date values.

    Returns:
        Quota usage information
    """
    # Refresh quota from Firestore to get latest usage
    quota_manager.reload_usage()

    return {
        "daily_quota": quota_manager.daily_quota,
        "used": quota_manager.used_quota,
        "remaining": quota_manager.get_remaining(),
        "utilization_percent": quota_manager.get_utilization(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/performance")
async def get_performance_metrics(
    days: int = 7,
    firestore_client: firestore.Client = Depends(get_firestore_client),
    quota_manager: QuotaManager = Depends(get_quota_manager),
    channel_tracker: ChannelTracker = Depends(get_channel_tracker),
) -> dict:
    """
    Get discovery performance metrics over time.

    Tracks KPIs to measure discovery efficiency:
    - Videos discovered per API unit spent
    - Channel tier distribution over time
    - Infringement rate by channel tier
    - Quota usage by discovery method
    - Deduplication effectiveness

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        Performance metrics and trends
    """
    logger.info(f"Getting performance metrics for last {days} days")

    try:
        from datetime import timedelta

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Query discovery metrics from Firestore
        metrics_ref = firestore_client.collection("discovery_metrics")
        query = (
            metrics_ref.where("timestamp", ">=", start_date)
            .where("timestamp", "<=", end_date)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
        )

        metrics_docs = list(query.stream())

        # Aggregate metrics
        total_videos = 0
        total_quota = 0
        total_channels = 0
        total_duplicates = 0
        quota_by_method = {"channel_tracking": 0, "trending": 0, "keywords": 0}

        daily_metrics = []
        for doc in metrics_docs:
            data = doc.to_dict()
            total_videos += data.get("videos_discovered", 0)
            total_quota += data.get("quota_used", 0)
            total_channels += data.get("channels_tracked", 0)
            total_duplicates += data.get("videos_skipped_duplicate", 0)

            # Aggregate by method
            method_usage = data.get("quota_by_method", {})
            for method, usage in method_usage.items():
                if method in quota_by_method:
                    quota_by_method[method] += usage

            daily_metrics.append(
                {
                    "date": data.get("timestamp").date().isoformat()
                    if isinstance(data.get("timestamp"), datetime)
                    else data.get("timestamp"),
                    "videos_discovered": data.get("videos_discovered", 0),
                    "quota_used": data.get("quota_used", 0),
                    "efficiency": (
                        data.get("videos_discovered", 0) / data.get("quota_used", 1)
                        if data.get("quota_used", 0) > 0
                        else 0
                    ),
                }
            )

        # Calculate efficiency metrics
        avg_efficiency = total_videos / total_quota if total_quota > 0 else 0
        dedup_rate = (
            total_duplicates / (total_videos + total_duplicates)
            if (total_videos + total_duplicates) > 0
            else 0
        )

        # Get current channel tier distribution
        channel_stats = channel_tracker.get_statistics()

        # Build response
        return {
            "period": {
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "days": days,
            },
            "totals": {
                "videos_discovered": total_videos,
                "quota_used": total_quota,
                "channels_tracked": total_channels,
                "duplicates_skipped": total_duplicates,
            },
            "efficiency": {
                "avg_videos_per_quota_unit": round(avg_efficiency, 2),
                "deduplication_rate": round(dedup_rate * 100, 2),
                "target_efficiency": 0.5,  # Target: <0.5 units per video
                "status": "excellent"
                if avg_efficiency > 2.0
                else "good"
                if avg_efficiency > 1.0
                else "needs_improvement",
            },
            "quota_distribution": {
                "by_method": quota_by_method,
                "allocation_strategy": {
                    "channel_tracking": "70%",
                    "trending": "20%",
                    "keywords": "10%",
                },
            },
            "channel_tiers": channel_stats.get("by_tier", {}),
            "daily_metrics": daily_metrics[:days],  # Limit to requested days
            "current_quota": {
                "daily_limit": quota_manager.daily_quota,
                "used_today": quota_manager.used_quota,
                "remaining_today": quota_manager.get_remaining(),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance metrics: {str(e)}"
        )
