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
from ..core.search_history import SearchHistory
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
    youtube_client: YouTubeClient = Depends(get_youtube_client),
) -> VideoProcessor:
    """Get video processor."""
    topic_path = pubsub_publisher.topic_path(
        settings.gcp_project_id, settings.pubsub_topic_discovered_videos
    )
    # Create channel tracker to save channel metadata (uses YouTube API for thumbnails)
    channel_tracker = ChannelTracker(
        firestore_client=firestore_client,
        youtube_client=youtube_client
    )

    return VideoProcessor(
        firestore_client=firestore_client,
        pubsub_publisher=pubsub_publisher,
        topic_path=topic_path,
        channel_tracker=channel_tracker,
    )


# Cached instances to avoid recreating on every request
_quota_manager_cache: QuotaManager | None = None
# Note: SearchRandomizer is NOT cached - needs to pick up config changes from Firestore


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
    """
    Get search randomizer (fresh instance each time to pick up config changes).

    Note: No caching here because keywords can be updated in Firestore at any time.
    Loading keywords is fast (single Firestore query), so recreating is acceptable.
    """
    return SearchRandomizer(firestore_client=firestore_client)


def get_search_history(
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> SearchHistory:
    """Get search history tracker."""
    return SearchHistory(firestore_client=firestore_client)


def get_discovery_engine(
    youtube_client: YouTubeClient = Depends(get_youtube_client),
    video_processor: VideoProcessor = Depends(get_video_processor),
    quota_manager: QuotaManager = Depends(get_quota_manager),
    search_randomizer: SearchRandomizer = Depends(get_search_randomizer),
    search_history: SearchHistory = Depends(get_search_history),
) -> DiscoveryEngine:
    """Get discovery engine."""
    return DiscoveryEngine(
        youtube_client=youtube_client,
        video_processor=video_processor,
        quota_manager=quota_manager,
        search_randomizer=search_randomizer,
        search_history=search_history,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/run")
async def discover(
    max_quota: int | None = None,  # Auto-calculate if not provided
    engine: DiscoveryEngine = Depends(get_discovery_engine),
    quota_manager: QuotaManager = Depends(get_quota_manager),
    firestore_client: firestore.Client = Depends(get_firestore_client),
):
    """
    Run smart query-based discovery with automatic quota optimization.

    **NON-BLOCKING**: Returns immediately and runs discovery in background.
    This prevents Cloud Scheduler timeouts and health probe kills.

    Strategy:
    - Deep pagination (5 pages per keyword)
    - Daily order rotation (date/viewCount/rating/relevance)
    - Daily time window rotation (last_7d/last_30d/30-90d_ago)
    - Smart deduplication (skip scanned, update unscanned for virality)
    - AUTO QUOTA: If max_quota not specified, calculates optimal quota
      to perfectly deplete remaining daily quota by midnight UTC

    Capacity:
    - 10k quota = ~100 queries = ~5,000 videos/day

    Args:
        max_quota: Maximum quota limit (optional - auto-calculated if not provided)

    Returns:
        Immediate response with run_id (discovery runs in background)
    """
    # Auto-calculate optimal quota if not specified
    if max_quota is None:
        max_quota = quota_manager.calculate_optimal_quota()
        logger.info(f"Auto-calculated optimal quota: {max_quota} units")
    else:
        logger.info(f"Using specified max_quota: {max_quota} units")

    # Create discovery history entry
    import uuid
    import asyncio

    run_id = str(uuid.uuid4())
    history_entry = {
        "run_id": run_id,
        "status": "running",
        "max_quota": max_quota,
        "started_at": firestore.SERVER_TIMESTAMP,
        "quota_auto_calculated": max_quota is None or "auto" in str(max_quota).lower(),
    }

    try:
        firestore_client.collection("discovery_history").document(run_id).set(history_entry)
        logger.info(f"Created discovery history entry: {run_id}")
    except Exception as e:
        logger.warning(f"Failed to create discovery history: {e}")

    # Run discovery in background (fire-and-forget)
    async def run_discovery_background():
        """Background task to run discovery without blocking the HTTP response."""
        all_progress_events = []

        async def progress_callback(data):
            all_progress_events.append(data)

        try:
            stats = await engine.discover(
                max_quota=max_quota,
                progress_callback=progress_callback
            )

            # Extract detailed query information from progress events
            all_keywords = []
            query_details = []

            # Get keywords from plan event
            for event in all_progress_events:
                if event['type'] == 'plan':
                    all_keywords = event['unique_keywords']
                    break

            # Collect actual query results with full details
            for event in all_progress_events:
                if event['type'] == 'query_result':
                    # Get actual time window from event or default to ALL TIME
                    time_window_display = 'ALL TIME'
                    if event.get('time_window'):
                        tw = event['time_window']
                        start = tw['published_after'][:10] if 'published_after' in tw else '?'
                        end = tw['published_before'][:10] if 'published_before' in tw else '?'
                        time_window_display = f"{start} to {end}"

                    query_details.append({
                        'keyword': event['keyword'],
                        'order': event['order'],
                        'results_count': event.get('results_count', 0),
                        'new_count': event.get('new_count', 0),
                        'rediscovered_count': event.get('rediscovered_count', 0),
                        'skipped_count': event.get('skipped_count', 0),
                        'time_window': time_window_display
                    })

            # Update history with complete results and details
            try:
                firestore_client.collection("discovery_history").document(run_id).update({
                    "status": "completed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "videos_discovered": stats.videos_discovered,
                    "videos_with_ip_match": stats.videos_with_ip_match,
                    "videos_skipped_duplicate": stats.videos_skipped_duplicate,
                    "quota_used": stats.quota_used,
                    "channels_tracked": stats.channels_tracked,
                    "duration_seconds": stats.duration_seconds,
                    # Store rich details for popup modal
                    "keywords_searched": all_keywords,
                    "keywords_count": len(all_keywords),
                    "all_query_details": query_details,
                    "time_window": 'ALL TIME',
                    "orders_used": list(set(q['order'] for q in query_details)),
                })
                logger.info(f"Updated discovery history {run_id} to completed with full details")
            except Exception as e:
                logger.error(f"Failed to update discovery history: {e}")

        except Exception as e:
            logger.error(f"Discovery failed: {e}")

            # Mark as failed in history
            try:
                firestore_client.collection("discovery_history").document(run_id).update({
                    "status": "failed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "error_message": str(e),
                })
            except:
                pass

    # Start background task (fire-and-forget)
    asyncio.create_task(run_discovery_background())

    # Return immediately
    return {
        "status": "started",
        "run_id": run_id,
        "max_quota": max_quota,
        "message": f"Discovery job started in background with quota limit {max_quota}"
    }


@router.get("/run/stream")
async def run_discovery_stream(
    max_quota: int | None = None,  # Auto-calculate if not provided
    engine: DiscoveryEngine = Depends(get_discovery_engine),
    quota_manager: QuotaManager = Depends(get_quota_manager),
    firestore_client: firestore.Client = Depends(get_firestore_client),
):
    """
    Run discovery with real-time SSE progress updates.

    Streams progress events as discovery executes queries.
    Auto-calculates optimal quota if not specified.
    """
    # Auto-calculate optimal quota if not specified
    if max_quota is None:
        max_quota = quota_manager.calculate_optimal_quota()
        logger.info(f"Auto-calculated optimal quota for stream: {max_quota} units")

    # Create discovery history entry
    import uuid
    from datetime import datetime, timezone

    run_id = str(uuid.uuid4())
    history_entry = {
        "run_id": run_id,
        "status": "running",
        "max_quota": max_quota,
        "started_at": firestore.SERVER_TIMESTAMP,
        "quota_auto_calculated": max_quota is None or "auto" in str(max_quota).lower(),
    }

    try:
        firestore_client.collection("discovery_history").document(run_id).set(history_entry)
        logger.info(f"Created discovery history entry: {run_id}")
    except Exception as e:
        logger.warning(f"Failed to create discovery history: {e}")

    async def event_generator():
        try:
            import asyncio

            # Send initial status
            yield f"data: {json.dumps({'status': 'starting', 'quota': max_quota, 'message': f'🚀 Initializing discovery with {max_quota:,} quota units'})}\n\n"

            # Create queue for real-time events
            event_queue = asyncio.Queue()
            all_progress_events = []

            # Define async callback that puts events in queue
            async def progress_callback(data):
                all_progress_events.append(data)
                await event_queue.put(data)

            # Run discovery in background task
            async def run_discovery():
                result = await engine.discover(
                    max_quota=max_quota,
                    progress_callback=progress_callback
                )
                await event_queue.put({'type': 'done', 'stats': result})
                return result

            discovery_task = asyncio.create_task(run_discovery())

            # Stream events as they arrive in real-time
            while True:
                try:
                    # Wait for next event with timeout
                    data = await asyncio.wait_for(event_queue.get(), timeout=0.5)

                    if data['type'] == 'done':
                        # Discovery finished
                        stats = data['stats']
                        break
                    elif data['type'] == 'plan':
                        msg1 = f"📋 Plan: {data['keywords_count']} keywords, {data['total_queries']} queries"
                        yield f"data: {json.dumps({'status': 'plan', 'message': msg1, 'keywords': data['unique_keywords']})}\n\n"

                        kw_list = ', '.join(data['unique_keywords'])
                        msg2 = f"🔑 Keywords: {kw_list}"
                        yield f"data: {json.dumps({'status': 'keywords', 'message': msg2, 'all_keywords': data['unique_keywords']})}\n\n"
                    elif data['type'] == 'query_start':
                        msg = f"🔍 Query {data['query_index']}/{data['total_queries']}: '{data['keyword']}' (order={data['order']}, quota={data['quota_used']:,}/{data['max_quota']:,})"
                        yield f"data: {json.dumps({'status': 'query', 'message': msg, 'keyword': data['keyword'], 'order': data['order']})}\n\n"
                    elif data['type'] == 'query_result':
                        msg = f"✓ '{data['keyword']}' → {data['results_count']} videos (cost: {data['quota_used']:,} units)"
                        yield f"data: {json.dumps({'status': 'result', 'message': msg, 'keyword': data['keyword'], 'results': data['results_count']})}\n\n"
                except asyncio.TimeoutError:
                    # No event yet, check if discovery task is done
                    if discovery_task.done():
                        stats = await discovery_task
                        break
                    # Otherwise keep waiting
                    continue

            progress_events = all_progress_events

            # Send final results with full summary (convert pydantic model to dict)
            all_keywords = []
            query_details = []

            # Get keywords from plan event
            for event in progress_events:
                if event['type'] == 'plan':
                    all_keywords = event['unique_keywords']
                    break

            # Collect actual query results with full details
            for event in progress_events:
                if event['type'] == 'query_result':
                    # Get actual time window from event or default to ALL TIME
                    time_window_display = 'ALL TIME'
                    if event.get('time_window'):
                        tw = event['time_window']
                        start = tw['published_after'][:10] if 'published_after' in tw else '?'
                        end = tw['published_before'][:10] if 'published_before' in tw else '?'
                        time_window_display = f"{start} to {end}"

                    query_details.append({
                        'keyword': event['keyword'],
                        'order': event['order'],
                        'results_count': event.get('results_count', 0),
                        'new_count': event.get('new_count', 0),
                        'rediscovered_count': event.get('rediscovered_count', 0),
                        'skipped_count': event.get('skipped_count', 0),
                        'time_window': time_window_display
                    })

            # Group queries by keyword to show what orders were used
            queries_by_keyword = {}
            for q in query_details:
                kw = q['keyword']
                if kw not in queries_by_keyword:
                    queries_by_keyword[kw] = []
                queries_by_keyword[kw].append(q['order'])

            # Update history with completion and full details
            try:
                firestore_client.collection("discovery_history").document(run_id).update({
                    "status": "completed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "videos_discovered": stats.videos_discovered,
                    "videos_with_ip_match": stats.videos_with_ip_match,
                    "videos_skipped_duplicate": stats.videos_skipped_duplicate,
                    "quota_used": stats.quota_used,
                    "channels_tracked": stats.channels_tracked,
                    "duration_seconds": stats.duration_seconds,
                    # Store rich details for popup modal
                    "keywords_searched": all_keywords,
                    "keywords_count": len(all_keywords),
                    "all_query_details": query_details,
                    "time_window": 'ALL TIME',
                    "orders_used": list(set(q['order'] for q in query_details)),
                })
                logger.info(f"Updated discovery history {run_id} to completed with full details")
            except Exception as hist_err:
                logger.warning(f"Failed to update discovery history: {hist_err}")

            result = {
                'status': 'complete',
                'videos_discovered': stats.videos_discovered,
                'videos_with_ip_match': stats.videos_with_ip_match,
                'videos_skipped_duplicate': stats.videos_skipped_duplicate,
                'quota_used': stats.quota_used,
                'duration_seconds': stats.duration_seconds,
                'keywords_searched': all_keywords,
                'keywords_count': len(all_keywords),
                'queries_by_keyword': queries_by_keyword,  # Shows exact keyword+order combinations
                'all_query_details': query_details,  # Full list of every query
                'time_window': 'ALL TIME',
                'orders_used': list(set(q['order'] for q in query_details)),  # Actual orders used
                'message': f'✅ Complete! Found {stats.videos_discovered:,} videos ({stats.videos_with_ip_match:,} with IP match) using {stats.quota_used:,} quota units in {stats.duration_seconds:.1f}s'
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            logger.error(f"Discovery stream failed: {e}")

            # Update history with failure
            try:
                firestore_client.collection("discovery_history").document(run_id).update({
                    "status": "failed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "error_message": str(e),
                })
                logger.info(f"Updated discovery history {run_id} to failed")
            except Exception as hist_err:
                logger.warning(f"Failed to update discovery history: {hist_err}")

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


@router.post("/channel/{channel_id}/scan")
async def scan_channel(
    channel_id: str,
    max_videos: int = 50,
    youtube_client: YouTubeClient = Depends(get_youtube_client),
    video_processor: VideoProcessor = Depends(get_video_processor),
) -> dict:
    """
    Fetch and process videos from a specific channel.

    Args:
        channel_id: YouTube channel ID
        max_videos: Maximum number of videos to fetch (default: 50)

    Returns:
        Statistics about discovered videos
    """
    logger.info(f"Scanning channel {channel_id} for up to {max_videos} videos")

    try:
        # Fetch videos from YouTube
        videos = youtube_client.get_channel_uploads(channel_id, max_results=max_videos)

        if not videos:
            return {
                "channel_id": channel_id,
                "videos_found": 0,
                "videos_new": 0,
                "videos_updated": 0,
                "message": "No videos found for this channel"
            }

        # Process each video
        processed = video_processor.process_batch(videos)

        return {
            "channel_id": channel_id,
            "videos_found": len(videos),
            "videos_new": len(processed),
            "videos_updated": 0,
            "message": f"Successfully scanned {len(videos)} videos, discovered {len(processed)} new"
        }

    except Exception as e:
        logger.error(f"Failed to scan channel {channel_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to scan channel: {str(e)}"
        )
