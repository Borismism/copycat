"""Analytics and reporting endpoints for homepage dashboard."""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.firestore_client import firestore_client

router = APIRouter()


@router.get("/hourly-stats")
async def get_hourly_stats(hours: int = 24):
    """
    Get hourly activity statistics for timeline chart.

    Args:
        hours: Number of hours to look back (default: 24)

    Returns:
        List of hourly buckets with discoveries and infringements (in UTC)
    """
    try:
        from datetime import timezone

        # Use UTC for consistency
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)

        # Initialize hourly buckets (UTC) - include current hour
        hourly_data = {}
        for i in range(hours + 1):  # +1 to include current hour
            hour = start + timedelta(hours=i)
            hour_key = hour.replace(minute=0, second=0, microsecond=0).isoformat()
            hourly_data[hour_key] = {
                "timestamp": hour_key,
                "discoveries": 0,
                "analyses": 0,
                "infringements": 0,
            }

        # Query ALL videos and filter in memory
        # Note: We need all videos because analyses/infringements may happen days after discovery
        all_video_docs = firestore_client.videos_collection.stream()

        for video in all_video_docs:
            data = video.to_dict()

            # Use discovered_at, fall back to created_at
            timestamp_raw = data.get("discovered_at") or data.get("created_at")
            if not timestamp_raw:
                continue

            # Parse timestamp (could be string or datetime)
            if isinstance(timestamp_raw, str):
                # Parse ISO format string
                from dateutil import parser
                timestamp = parser.isoparse(timestamp_raw)
            else:
                timestamp = timestamp_raw

            # Ensure timezone-aware datetime
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)

            # Skip if outside our time range
            if timestamp < start:
                continue

            # Round to hour
            hour = timestamp.replace(minute=0, second=0, microsecond=0)
            hour_key = hour.isoformat()

            if hour_key in hourly_data:
                hourly_data[hour_key]["discoveries"] += 1

                # Count analyses
                if data.get("status") == "analyzed":
                    hourly_data[hour_key]["analyses"] += 1

                    # Count infringements (new structure: analysis.contains_infringement)
                    analysis = data.get("analysis", {})
                    if isinstance(analysis, dict) and analysis.get("contains_infringement"):
                        hourly_data[hour_key]["infringements"] += 1

        return {
            "hours": sorted(hourly_data.values(), key=lambda x: x["timestamp"])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get hourly stats: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/performance-metrics")
async def get_performance_metrics():
    """
    Get system performance metrics for gauges and KPI cards.

    Returns:
        Discovery efficiency, analysis throughput, budget utilization, queue health
    """
    try:
        summary = await firestore_client.get_24h_summary()

        # Discovery efficiency (videos per quota unit)
        quota_used = summary.get("quota_used", 0)
        videos_discovered = summary.get("videos_discovered", 0)
        discovery_efficiency = videos_discovered / quota_used if quota_used > 0 else 0

        # Analysis throughput (videos per hour)
        videos_analyzed = summary.get("videos_analyzed", 0)
        analysis_throughput = videos_analyzed / 24.0  # Average over 24 hours

        # Budget utilization - fetch from vision analyzer service
        try:
            import httpx
            # Try to fetch from vision analyzer service first
            async with httpx.AsyncClient() as client:
                response = await client.get("http://vision-analyzer-service:8080/admin/budget", timeout=5.0)
                if response.status_code == 200:
                    budget_data = response.json()
                    total_spent = budget_data.get("total_spent_usd", 0)
                    daily_budget = budget_data.get("daily_budget_usd", 260.0)
                    budget_utilization = total_spent / daily_budget if daily_budget > 0 else 0
                else:
                    raise Exception("Vision analyzer not available")
        except Exception as e:
            # Fallback to Firestore
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                budget_doc = firestore_client.db.collection("budget_tracking").document(today).get()
                if budget_doc.exists:
                    budget_data = budget_doc.to_dict()
                    total_spent = budget_data.get("total_spent_usd", 0)
                    daily_budget = 260.0
                    budget_utilization = total_spent / daily_budget
                else:
                    total_spent = 0
                    budget_utilization = 0
            except Exception:
                total_spent = 0
                budget_utilization = 0

        # Queue health (pending videos) - use count aggregation for performance
        from google.cloud.firestore_v1.aggregation import CountAggregation
        pending_videos = firestore_client.videos_collection.where("status", "==", "discovered").count().get()[0][0].value

        # Calculate scores (0-100)
        discovery_score = min(100, (discovery_efficiency / 0.5) * 100) if discovery_efficiency > 0 else 0
        throughput_score = min(100, (analysis_throughput / 25.0) * 100) if analysis_throughput > 0 else 0
        budget_score = budget_utilization * 100
        queue_score = 100 if pending_videos < 5000 else 50 if pending_videos < 10000 else 25

        return {
            "discovery_efficiency": {
                "value": round(discovery_efficiency, 2),
                "target": 0.5,
                "score": round(discovery_score, 1),
                "status": "excellent" if discovery_score >= 90 else "good" if discovery_score >= 70 else "fair",
            },
            "analysis_throughput": {
                "value": round(analysis_throughput, 1),
                "target": 25.0,
                "score": round(throughput_score, 1),
                "status": "excellent" if throughput_score >= 90 else "good" if throughput_score >= 70 else "fair",
            },
            "budget_utilization": {
                "value": round(budget_utilization, 3),
                "spent": round(total_spent, 2),
                "total": 240.0,
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

    except Exception as e:
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
        raise HTTPException(status_code=500, detail=f"Failed to get overview: {str(e)}")
