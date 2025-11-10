"""Analytics and reporting endpoints for homepage dashboard."""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from google.cloud import firestore

from app.core.firestore_client import firestore_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory cache with TTL
_cache: Dict[str, tuple[Any, datetime]] = {}
_CACHE_TTL_SECONDS = 60  # 60 second cache for expensive queries


def get_cached(key: str) -> Optional[Any]:
    """Get value from cache if still valid."""
    if key in _cache:
        value, expires_at = _cache[key]
        if datetime.now() < expires_at:
            return value
        else:
            del _cache[key]
    return None


def set_cache(key: str, value: Any, ttl_seconds: int = _CACHE_TTL_SECONDS):
    """Set value in cache with TTL."""
    expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
    _cache[key] = (value, expires_at)


@router.get("/hourly-stats")
async def get_hourly_stats(hours: int = 24, start_date: Optional[str] = None):
    """
    Get hourly activity statistics for timeline chart.

    Args:
        hours: Number of hours to fetch (default: 24)
        start_date: Optional start date in ISO format (YYYY-MM-DD). If not provided, uses current time.

    Returns:
        List of hourly buckets with discoveries and infringements (in UTC)
    """
    # Check cache first
    cache_key = f"hourly_stats_{hours}_{start_date or 'now'}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from datetime import timezone
        from dateutil import parser as date_parser

        # Use UTC for consistency
        if start_date:
            # Parse the provided start date and set to beginning of day in UTC
            start = date_parser.isoparse(start_date)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            else:
                start = start.astimezone(timezone.utc)
            # Set to start of day
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Use current day (midnight to now/midnight)
            now = datetime.now(timezone.utc)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Initialize hourly buckets (UTC)
        hourly_data = {}
        for i in range(hours):
            hour = start + timedelta(hours=i)
            hour_key = hour.replace(minute=0, second=0, microsecond=0).isoformat()
            hourly_data[hour_key] = {
                "timestamp": hour_key,
                "discoveries": 0,
                "analyses": 0,
                "infringements": 0,
            }

        # Query pre-aggregated hourly_stats collection (FAST!)
        # This reads only ~24 small documents instead of thousands of videos
        hourly_stats = (
            firestore_client.db.collection("hourly_stats")
            .where("hour", ">=", start)
            .stream()
        )

        for stat_doc in hourly_stats:
            data = stat_doc.to_dict()
            hour = data.get("hour")

            # Parse hour timestamp
            if isinstance(hour, str):
                from dateutil import parser
                hour_dt = parser.isoparse(hour)
            else:
                hour_dt = hour

            # Ensure timezone-aware
            if hour_dt.tzinfo is None:
                hour_dt = hour_dt.replace(tzinfo=timezone.utc)
            else:
                hour_dt = hour_dt.astimezone(timezone.utc)

            hour_key = hour_dt.isoformat()

            # Update hourly data with pre-aggregated stats
            if hour_key in hourly_data:
                hourly_data[hour_key]["discoveries"] = data.get("discoveries", 0)
                hourly_data[hour_key]["analyses"] = data.get("analyses", 0)
                hourly_data[hour_key]["infringements"] = data.get("infringements", 0)

        result = {
            "hours": sorted(hourly_data.values(), key=lambda x: x["timestamp"])
        }

        # Cache the result
        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Failed to get hourly stats: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get hourly stats: {str(e)}")


@router.get("/daily-stats")
async def get_daily_stats(days: int = 30, start_date: Optional[str] = None):
    """
    Get daily activity statistics for monthly chart view.

    Args:
        days: Number of days to fetch (default: 30)
        start_date: Optional start date in ISO format (YYYY-MM-DD). If not provided, uses current time.

    Returns:
        List of daily buckets with discoveries and infringements (in UTC)
    """
    # Check cache first
    cache_key = f"daily_stats_{days}_{start_date or 'now'}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from datetime import timezone
        from dateutil import parser as date_parser

        # Use UTC for consistency
        if start_date:
            # Parse the provided start date and set to beginning of month in UTC
            start = date_parser.isoparse(start_date)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            else:
                start = start.astimezone(timezone.utc)
            # Set to start of month (day 1)
            start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calculate days in this specific month
            if start.month == 12:
                next_month = start.replace(year=start.year + 1, month=1)
            else:
                next_month = start.replace(month=start.month + 1)
            days = (next_month - start).days
        else:
            # Current month: start from 1st of current month
            now = datetime.now(timezone.utc)
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calculate days in current month
            if start.month == 12:
                next_month = start.replace(year=start.year + 1, month=1)
            else:
                next_month = start.replace(month=start.month + 1)
            days = (next_month - start).days

        # Initialize daily buckets
        daily_data = {}
        for i in range(days):
            day = start + timedelta(days=i)
            day_key = day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            daily_data[day_key] = {
                "timestamp": day_key,
                "discoveries": 0,
                "analyses": 0,
                "infringements": 0,
            }

        # Query hourly_stats and aggregate by day
        hourly_stats = (
            firestore_client.db.collection("hourly_stats")
            .where("hour", ">=", start)
            .stream()
        )

        for stat_doc in hourly_stats:
            data = stat_doc.to_dict()
            hour = data.get("hour")

            # Parse hour timestamp
            if isinstance(hour, str):
                hour_dt = date_parser.isoparse(hour)
            else:
                hour_dt = hour

            # Ensure timezone-aware
            if hour_dt.tzinfo is None:
                hour_dt = hour_dt.replace(tzinfo=timezone.utc)
            else:
                hour_dt = hour_dt.astimezone(timezone.utc)

            # Get day key (truncate to day)
            day_dt = hour_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_key = day_dt.isoformat()

            # Aggregate into daily buckets
            if day_key in daily_data:
                daily_data[day_key]["discoveries"] += data.get("discoveries", 0)
                daily_data[day_key]["analyses"] += data.get("analyses", 0)
                daily_data[day_key]["infringements"] += data.get("infringements", 0)

        result = {
            "days": sorted(daily_data.values(), key=lambda x: x["timestamp"])
        }

        # Cache the result
        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Failed to get daily stats: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get daily stats: {str(e)}")


@router.get("/system-health")
async def get_system_health():
    """
    Get aggregated system health metrics with alerts and warnings.

    Returns:
        alerts: Critical issues requiring immediate action
        warnings: Issues that need attention soon
        info: Informational messages
    """
    try:
        alerts = []
        warnings = []
        info = []

        # Check quota usage
        try:
            summary = await firestore_client.get_24h_summary()
            quota_used = summary.get("quota_used", 0)
            quota_total = summary.get("quota_total", 10000)
            quota_utilization = quota_used / quota_total if quota_total > 0 else 0

            if quota_utilization >= 0.95:
                alerts.append({
                    "id": "quota_critical",
                    "type": "critical",
                    "title": f"YouTube quota at {quota_utilization*100:.1f}%",
                    "message": f"{quota_used:,} / {quota_total:,} units used",
                    "action": "Reduce discovery frequency or request quota increase",
                    "timestamp": datetime.now().isoformat(),
                })
            elif quota_utilization >= 0.85:
                warnings.append({
                    "id": "quota_warning",
                    "type": "warning",
                    "title": f"YouTube quota at {quota_utilization*100:.1f}%",
                    "message": f"{quota_used:,} / {quota_total:,} units used",
                    "action": "Monitor usage closely",
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            warnings.append({
                "id": "quota_error",
                "type": "warning",
                "title": "Unable to check quota status",
                "message": str(e),
                "action": "Check quota manually in GCP Console",
                "timestamp": datetime.now().isoformat(),
            })

        # Check budget usage (if vision analyzer is running)
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            budget_doc = firestore_client.db.collection("gemini_budget").document(today).get()

            if budget_doc.exists:
                budget_data = budget_doc.to_dict()
                total_spent = budget_data.get("total_spent_usd", 0)
                daily_budget = 240.0  # $240 daily budget
                budget_utilization = total_spent / daily_budget

                if budget_utilization >= 0.95:
                    alerts.append({
                        "id": "budget_critical",
                        "type": "critical",
                        "title": f"Gemini budget at {budget_utilization*100:.1f}%",
                        "message": f"${total_spent:.2f} / ${daily_budget:.2f} spent",
                        "action": "Analysis will pause at limit. Consider increasing budget.",
                        "timestamp": datetime.now().isoformat(),
                    })
                elif budget_utilization >= 0.85:
                    warnings.append({
                        "id": "budget_warning",
                        "type": "warning",
                        "title": f"Gemini budget at {budget_utilization*100:.1f}%",
                        "message": f"${total_spent:.2f} / ${daily_budget:.2f} spent",
                        "action": "Monitor spending closely",
                        "timestamp": datetime.now().isoformat(),
                    })
        except Exception:
            # Budget collection may not exist yet (vision analyzer not deployed)
            pass

        # Add info messages for recent activity
        try:
            last_run = summary.get("last_run")
            if last_run:
                videos_discovered = last_run.get("videos_discovered", 0)
                if videos_discovered > 0:
                    info.append({
                        "id": "discovery_complete",
                        "type": "info",
                        "title": "Discovery run completed",
                        "message": f"{videos_discovered} new videos found",
                        "action": None,
                        "timestamp": last_run.get("timestamp", datetime.now()).isoformat(),
                    })
        except Exception:
            pass

        return {
            "alerts": alerts,
            "warnings": warnings,
            "info": info,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get system health: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/performance-metrics")
async def get_performance_metrics():
    """
    Get system performance metrics for gauges and KPI cards.

    Returns:
        Discovery efficiency, analysis throughput, budget utilization, queue health
    """
    # Check cache first
    cache_key = "performance_metrics"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        summary = await firestore_client.get_24h_summary()

        # Discovery efficiency (videos per quota unit)
        quota_used = summary.get("quota_used", 0)
        videos_discovered = summary.get("videos_discovered", 0)
        discovery_efficiency = videos_discovered / quota_used if quota_used > 0 else 0

        # Analysis throughput (videos per hour)
        videos_analyzed = summary.get("videos_analyzed", 0)
        analysis_throughput = videos_analyzed / 24.0  # Average over 24 hours

        # Budget utilization - fetch from Firestore
        # Note: Direct service-to-service calls don't work in Cloud Run (not Kubernetes)
        # Vision analyzer updates budget_tracking collection in Firestore
        try:
            from datetime import timezone as tz
            today = datetime.now(tz.utc).strftime("%Y-%m-%d")
            budget_doc = firestore_client.db.collection("budget_tracking").document(today).get()
            if budget_doc.exists:
                budget_data = budget_doc.to_dict()
                total_spent = budget_data.get("total_spent_eur", 0)
                # Get daily budget from document (vision-analyzer stores this)
                daily_budget = budget_data.get("daily_budget_eur", 260.0)
                budget_utilization = total_spent / daily_budget if daily_budget > 0 else 0
                logger.info(f"Budget data: spent=€{total_spent:.2f}, budget=€{daily_budget}, util={budget_utilization:.2%}")
            else:
                logger.warning(f"No budget_tracking document found for {today}")
                total_spent = 0
                budget_utilization = 0
                daily_budget = 260.0  # Fallback to configured default (EUR)
        except Exception as e:
            logger.error(f"Failed to get budget data: {e}", exc_info=True)
            total_spent = 0
            budget_utilization = 0
            daily_budget = 260.0

        # Queue health (pending videos) - use aggregation query for efficiency
        try:
            from google.cloud.firestore_v1.aggregation import AggregationQuery, Count

            # Use Firestore aggregation query (much faster than streaming)
            query = firestore_client.videos_collection.where("status", "==", "discovered")
            aggregation_query = AggregationQuery(query)
            aggregation_query.count(alias="pending_count")

            result = aggregation_query.get()
            pending_videos = result[0][0].value if result else 0
        except Exception as count_error:
            logger.warning(f"Failed to count pending videos: {count_error}, falling back to estimate")
            # Fallback: use cached value from summary if available
            pending_videos = summary.get("videos_pending", 0)

        # Calculate scores (0-100)
        discovery_score = min(100, (discovery_efficiency / 0.5) * 100) if discovery_efficiency > 0 else 0
        throughput_score = min(100, (analysis_throughput / 250.0) * 100) if analysis_throughput > 0 else 0
        budget_score = budget_utilization * 100
        queue_score = 100 if pending_videos < 5000 else 50 if pending_videos < 10000 else 25

        result = {
            "discovery_efficiency": {
                "value": round(discovery_efficiency, 2),
                "target": 0.5,
                "score": round(discovery_score, 1),
                "status": "excellent" if discovery_score >= 90 else "good" if discovery_score >= 70 else "fair",
            },
            "analysis_throughput": {
                "value": round(analysis_throughput, 1),
                "target": 250.0,
                "score": round(throughput_score, 1),
                "status": "excellent" if throughput_score >= 90 else "good" if throughput_score >= 70 else "fair",
            },
            "budget_utilization": {
                "value": round(budget_utilization, 3),
                "spent": round(total_spent, 2),
                "total": daily_budget,
                "score": round(budget_score, 1),
                "status": "excellent" if 85 <= budget_score <= 95 else "good" if budget_score >= 75 else "low",
            },
            "queue_health": {
                "pending": pending_videos,
                "threshold": 5000,
                "score": round(queue_score, 1),
                "status": "excellent" if pending_videos < 5000 else "good" if pending_videos < 10000 else "warning",
            },
        }

        # Cache the result
        set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Failed to get performance metrics: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/recent-events")
async def get_recent_events(limit: int = 20):
    """
    Get recent system events for activity feed.

    Args:
        limit: Maximum number of events to return (default: 20)

    Returns:
        List of recent events (discoveries, analyses, infringements)
    """
    try:
        events = []

        # Get recent discovery metrics
        try:
            discovery_metrics = (
                firestore_client.db.collection("discovery_metrics")
                .order_by("timestamp", direction=firestore_client.db.collection("discovery_metrics").DESCENDING)
                .limit(5)
                .stream()
            )

            for doc in discovery_metrics:
                data = doc.to_dict()
                events.append({
                    "id": doc.id,
                    "type": "discovery",
                    "title": "Discovery run completed",
                    "message": f"{data.get('videos_discovered', 0)} videos discovered, {data.get('quota_used', 0)} quota used",
                    "timestamp": data.get("timestamp", datetime.now()).isoformat(),
                    "icon": "🔍",
                })
        except Exception:
            pass

        # Get recent high-confidence infringements
        try:
            recent_infringements = (
                firestore_client.videos_collection
                .where("status", "==", "analyzed")
                .order_by("updated_at", direction=firestore_client.db.collection("videos").DESCENDING)
                .limit(10)
                .stream()
            )

            for video_doc in recent_infringements:
                video = video_doc.to_dict()
                vision_analysis = video.get("vision_analysis", {})
                if isinstance(vision_analysis, dict):
                    full_analysis = vision_analysis.get("full_analysis", vision_analysis)
                    contains_infringement = full_analysis.get("contains_infringement", False)
                    confidence = full_analysis.get("confidence_score", 0)

                    if contains_infringement and confidence >= 80:
                        events.append({
                            "id": video.get("video_id"),
                            "type": "infringement",
                            "title": f"Infringement detected: {video.get('title', 'Unknown')[:50]}...",
                            "message": f"{confidence}% confidence",
                            "timestamp": video.get("updated_at", datetime.now()).isoformat(),
                            "icon": "⚠️",
                            "video_id": video.get("video_id"),
                        })
        except Exception:
            pass

        # Sort by timestamp and limit
        events.sort(key=lambda x: x["timestamp"], reverse=True)
        events = events[:limit]

        return {
            "events": events,
            "total": len(events),
        }

    except Exception as e:
        logger.error(f"Failed to get recent events: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get recent events: {str(e)}")


@router.get("/character-stats")
async def get_character_detection_stats():
    """
    Get character detection statistics from analyzed videos.

    Returns:
        Character counts and percentages based on real vision_analysis data
    """
    try:
        # Query all analyzed videos with vision_analysis
        analyzed_videos = firestore_client.videos_collection.where(
            "status", "==", "analyzed"
        ).stream()

        # Count character detections from actual Gemini results
        character_counts = {}
        total_infringements = 0

        for video in analyzed_videos:
            data = video.to_dict()
            vision_analysis = data.get("vision_analysis", {})

            if isinstance(vision_analysis, dict):
                full_analysis = vision_analysis.get("full_analysis", vision_analysis)
                contains_infringement = full_analysis.get("contains_infringement", False)

                if contains_infringement:
                    total_infringements += 1

                    # Extract characters_detected from Gemini response
                    characters_detected = full_analysis.get("characters_detected", [])

                    if isinstance(characters_detected, list):
                        for char_data in characters_detected:
                            if isinstance(char_data, dict):
                                char_name = char_data.get("name", "Unknown")
                                if char_name not in character_counts:
                                    character_counts[char_name] = 0
                                character_counts[char_name] += 1

        # Format response
        character_stats = []
        for char_name, count in character_counts.items():
            percentage = (count / total_infringements * 100) if total_infringements > 0 else 0
            character_stats.append({
                "name": char_name,
                "count": count,
                "percentage": round(percentage, 1),
            })

        # Sort by count descending
        character_stats.sort(key=lambda x: x["count"], reverse=True)

        return {
            "characters": character_stats,
            "total_infringements": total_infringements,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get character stats: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get character stats: {str(e)}")


@router.get("/overview")
async def get_analytics_overview():
    """
    Get comprehensive analytics overview (legacy endpoint).

    This endpoint combines data from multiple sources for backward compatibility.
    """
    try:
        summary = await firestore_client.get_24h_summary()
        health = await get_system_health()
        metrics = await get_performance_metrics()

        return {
            "summary": summary,
            "health": health,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get overview: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get overview: {str(e)}")
