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
from ..core.quota_manager import QuotaManager
from ..core.search_randomizer import SearchRandomizer
from ..core.video_processor import VideoProcessor
from ..core.youtube_client import YouTubeClient
from ..models import DiscoveryStats

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
    topic_path = pubsub_publisher.topic_path(
        settings.gcp_project_id, settings.pubsub_topic_discovered_videos
    )
    # Create channel tracker to save channel metadata
    channel_tracker = ChannelTracker(firestore_client=firestore_client)

    return VideoProcessor(
        firestore_client=firestore_client,
        pubsub_publisher=pubsub_publisher,
        topic_path=topic_path,
        channel_tracker=channel_tracker,
    )


# Cached instances to avoid recreating on every request
_quota_manager_cache: QuotaManager | None = None
_search_randomizer_cache: SearchRandomizer | None = None


def get_quota_manager(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> QuotaManager:
    """Get quota manager (cached singleton)."""
    global _quota_manager_cache
    if _quota_manager_cache is None:
        _quota_manager_cache = QuotaManager(
            firestore_client=firestore_client, daily_quota=10_000
        )
    return _quota_manager_cache


def get_search_randomizer(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> SearchRandomizer:
    """Get search randomizer (cached singleton)."""
    global _search_randomizer_cache
    if _search_randomizer_cache is None:
        _search_randomizer_cache = SearchRandomizer(firestore_client=firestore_client)
    return _search_randomizer_cache


def get_discovery_engine(
    youtube_client: YouTubeClient = Depends(get_youtube_client),
    video_processor: VideoProcessor = Depends(get_video_processor),
    quota_manager: QuotaManager = Depends(get_quota_manager),
    search_randomizer: SearchRandomizer = Depends(get_search_randomizer),
) -> DiscoveryEngine:
    """Get discovery engine."""
    return DiscoveryEngine(
        youtube_client=youtube_client,
        video_processor=video_processor,
        quota_manager=quota_manager,
        search_randomizer=search_randomizer,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/run", response_model=DiscoveryStats)
async def discover(
    max_quota: int = 10_000,  # Full daily quota by default
    engine: DiscoveryEngine = Depends(get_discovery_engine),
) -> DiscoveryStats:
    """
    Run smart query-based discovery.

    Strategy:
    - Deep pagination (5 pages per keyword)
    - Daily order rotation (date/viewCount/rating/relevance)
    - Daily time window rotation (last_7d/last_30d/30-90d_ago)
    - Smart deduplication (skip scanned, update unscanned for virality)

    Capacity:
    - 10k quota = ~100 queries = ~5,000 videos/day

    Args:
        max_quota: Maximum quota limit for this run (default: 10,000 units)

    Returns:
        Discovery statistics
    """
    logger.info(f"Starting smart discovery with max_quota={max_quota}")

    try:
        stats = await engine.discover(max_quota=max_quota)
        return stats

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/run/stream")
async def run_discovery_stream(
    max_quota: int = 10_000,
    engine: DiscoveryEngine = Depends(get_discovery_engine),
):
    """
    Run discovery with real-time SSE progress updates.

    Streams progress events as discovery executes queries.
    """
    async def event_generator():
        try:
            # Send initial status
            yield f"data: {json.dumps({'status': 'starting', 'quota': max_quota, 'message': f'🚀 Initializing discovery with {max_quota:,} quota units'})}\n\n"
            await asyncio.sleep(0.1)

            # Send planning phase
            yield f"data: {json.dumps({'status': 'planning', 'message': '📋 Loading keywords and planning search strategy...'})}\n\n"
            await asyncio.sleep(0.1)

            # Send search strategy details
            yield f"data: {json.dumps({'status': 'strategy', 'message': '🎯 Strategy: 20 keywords × 5 pages deep with order rotation'})}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'status': 'strategy', 'message': '📅 Time window: all-time (comprehensive coverage)'})}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'status': 'strategy', 'message': '🔀 Order: rotating through date/viewCount/rating/relevance'})}\n\n"
            await asyncio.sleep(0.1)

            # Start discovery
            yield f"data: {json.dumps({'status': 'searching', 'message': '🔍 Executing YouTube API queries...'})}\n\n"
            await asyncio.sleep(0.1)

            # Run actual discovery
            stats = await engine.discover(max_quota=max_quota)

            # Send processing status
            yield f"data: {json.dumps({'status': 'processing', 'message': f'⚙️ Processing {stats.videos_discovered} videos for IP matches...'})}\n\n"
            await asyncio.sleep(0.1)

            # Send final results (convert pydantic model to dict)
            result = {
                'status': 'complete',
                'videos_discovered': stats.videos_discovered,
                'videos_with_ip_match': stats.videos_with_ip_match,
                'videos_skipped_duplicate': stats.videos_skipped_duplicate,
                'quota_used': stats.quota_used,
                'duration_seconds': stats.duration_seconds,
                'message': f'✅ Complete! Found {stats.videos_discovered:,} videos ({stats.videos_with_ip_match:,} with IP match) using {stats.quota_used:,} quota units in {stats.duration_seconds:.1f}s'
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


@router.get("/analytics/discovery")
async def get_discovery_analytics(
    quota_manager: QuotaManager = Depends(get_quota_manager),
) -> dict:
    """
    Get discovery performance metrics.

    Refreshes quota from Firestore to ensure up-to-date values.

    Returns:
        Analytics data including quota usage
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

        return {
            "quota": quota_stats,
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


@router.get("/keywords/performance")
async def get_keyword_performance(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> dict:
    """
    Get keyword performance statistics with tiers and cooldowns.

    Returns:
        Keyword performance data grouped by tier
    """
    try:
        # Get all keyword searches, latest per keyword
        all_searches = (
            firestore_client.collection("keyword_searches")
            .order_by("searched_at", direction="DESCENDING")
            .stream()
        )

        keyword_stats = {}
        seen_keywords = set()

        for doc in all_searches:
            data = doc.to_dict()
            keyword = data.get("keyword")

            # Only track latest search per keyword
            if keyword in seen_keywords:
                continue
            seen_keywords.add(keyword)

            # Calculate days since last search
            searched_at = data.get("searched_at")
            days_since = (datetime.now(timezone.utc) - searched_at).days if searched_at else 999

            # Get cooldown status
            cooldown_days = data.get("cooldown_days", 1)
            in_cooldown = days_since < cooldown_days
            days_until_ready = max(0, cooldown_days - days_since)

            keyword_stats[keyword] = {
                "keyword": keyword,
                "tier": data.get("tier", "UNKNOWN"),
                "efficiency_pct": data.get("efficiency_pct", 0),
                "new_videos": data.get("new_videos", 0),
                "total_results": data.get("total_results", 0),
                "last_searched": searched_at.isoformat() if searched_at else None,
                "days_since_search": days_since,
                "cooldown_days": cooldown_days,
                "in_cooldown": in_cooldown,
                "days_until_ready": days_until_ready,
                "search_date": data.get("search_date"),
            }

        # Group by tier (1, 2, 3 matching config tier system)
        by_tier = {
            "1": [],
            "2": [],
            "3": [],
        }

        for stats in keyword_stats.values():
            tier = stats["tier"]
            if tier in by_tier:
                by_tier[tier].append(stats)

        # Sort each tier by efficiency descending
        for tier in by_tier:
            by_tier[tier].sort(key=lambda x: x["efficiency_pct"], reverse=True)

        # Calculate tier summaries
        tier_summary = {}
        for tier, keywords in by_tier.items():
            if keywords:
                tier_summary[tier] = {
                    "count": len(keywords),
                    "avg_efficiency": sum(k["efficiency_pct"] for k in keywords) / len(keywords),
                    "in_cooldown": sum(1 for k in keywords if k["in_cooldown"]),
                    "ready_to_search": sum(1 for k in keywords if not k["in_cooldown"]),
                }

        return {
            "keywords": list(keyword_stats.values()),
            "by_tier": by_tier,
            "tier_summary": tier_summary,
            "total_keywords": len(keyword_stats),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get keyword performance: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get keyword performance: {str(e)}"
        )


@router.get("/analytics/performance")
async def get_performance_metrics(
    days: int = 7,
    firestore_client: firestore.Client = Depends(get_firestore_client),
    quota_manager: QuotaManager = Depends(get_quota_manager),
) -> dict:
    """
    Get discovery performance metrics over time.

    Tracks KPIs to measure discovery efficiency:
    - Videos discovered per API unit spent
    - Quota usage trends
    - Deduplication effectiveness
    - Discovery efficiency over time

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
                "allocation_strategy": "Smart query-based with deep pagination",
            },
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
