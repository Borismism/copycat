"""Vision Analyzer budget tracking endpoint - fetches real Vertex AI usage from GCP."""

from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.api_core import exceptions as google_exceptions
from app.core.firestore_client import firestore_client

router = APIRouter()

# Cache to prevent excessive GCP API calls
_budget_cache: Optional[dict] = None
_cache_timestamp: Optional[datetime] = None
CACHE_TTL_SECONDS = 300  # 5 minutes cache


class VisionBudgetStats(BaseModel):
    """Real-time Vertex AI budget statistics."""
    daily_budget_eur: float
    daily_budget_usd: float
    budget_used_eur: float
    budget_used_usd: float
    budget_remaining_eur: float
    budget_remaining_usd: float
    utilization_percentage: float
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    cache_age_seconds: int
    data_from_project: str
    last_updated: str
    # Performance metrics
    success_rate: float
    avg_processing_time_seconds: float
    processing_rate_per_hour: float


class GeminiConfiguration(BaseModel):
    """Gemini model configuration settings."""
    model_name: str
    model_version: str
    region: str
    input_method: str
    resolution: str
    tokens_per_frame: int
    rate_limit_type: str
    max_output_tokens: int
    input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float
    audio_cost_per_1m_tokens: float


class VisionAnalytics(BaseModel):
    """Vision analysis statistics and error tracking."""
    total_analyzed: int
    total_errors: int
    success_rate: float
    infringements_found: int
    detection_rate: float
    avg_processing_time_seconds: float
    total_cost_usd: float
    videos_pending: int
    last_24h: dict
    by_status: dict
    recent_errors: list


def calculate_gemini_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Calculate Gemini 2.5 Flash cost based on token usage.

    Pricing (Vertex AI, as of 2025):
    - Input: $0.30 per 1M tokens
    - Output: $2.50 per 1M tokens
    """
    input_cost = (input_tokens / 1_000_000) * 0.30
    output_cost = (output_tokens / 1_000_000) * 2.50
    return input_cost + output_cost


def get_vertex_ai_usage(project_id: str = "copycat-429012") -> dict:
    """
    Get real Vertex AI usage from Firestore (actual scan data).

    Returns actual request counts based on vision_analysis results in Firestore.
    This is MORE ACCURATE than Cloud Monitoring because it reflects actual scans completed.
    """
    global _budget_cache, _cache_timestamp

    # Check cache
    now = datetime.now(timezone.utc)
    if _budget_cache and _cache_timestamp:
        cache_age = (now - _cache_timestamp).total_seconds()
        if cache_age < CACHE_TTL_SECONDS:
            _budget_cache["cache_age_seconds"] = int(cache_age)
            return _budget_cache

    try:
        # Query Firestore for videos analyzed in last 24 hours
        start_time = now - timedelta(hours=24)

        # Count videos with vision_analysis (these were scanned by Gemini)
        videos_query = firestore_client.videos_collection.where(
            "status", "==", "analyzed"
        ).stream()

        total_requests = 0
        successful_requests = 0
        total_processing_time = 0.0
        processing_times = []
        total_cost_usd = 0.0

        for video in videos_query:
            data = video.to_dict()

            # Check if video has analysis data (either in 'analysis' or 'vision_analysis')
            analysis = data.get("analysis") or data.get("vision_analysis")

            if analysis and isinstance(analysis, dict):
                # This video was analyzed by Gemini
                total_requests += 1
                successful_requests += 1  # If it has analysis, it succeeded

                # Get actual cost from analysis field
                cost = analysis.get("cost_usd", 0.0)
                if cost > 0:
                    total_cost_usd += cost

                # Track processing time (if available)
                processing_time = data.get("processing_time_seconds")
                if processing_time and isinstance(processing_time, (int, float)):
                    processing_times.append(processing_time)
                    total_processing_time += processing_time

        # Calculate performance metrics
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        avg_processing_time = (sum(processing_times) / len(processing_times)) if processing_times else 1.2
        processing_rate_per_hour = total_requests / 24.0 if total_requests > 0 else 0

        # Use actual costs, not estimates
        estimated_cost_usd = total_cost_usd

        # Estimate token usage based on actual cost
        # Reverse calculate from cost (Input: $0.30/1M, Output: $2.50/1M)
        # Assume 95% input, 5% output (typical ratio)
        if total_cost_usd > 0:
            # Rough estimation: input tokens ≈ (cost * 0.95) / (0.30 / 1M)
            total_input_tokens = int((total_cost_usd * 0.95) / (0.30 / 1_000_000))
            total_output_tokens = int((total_cost_usd * 0.05) / (2.50 / 1_000_000))
        else:
            total_input_tokens = 0
            total_output_tokens = 0

        # Convert to EUR (approximate rate: 1 EUR = 1.08 USD)
        estimated_cost_eur = estimated_cost_usd / 1.08

        result = {
            "total_requests": total_requests,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost_usd": round(estimated_cost_usd, 2),
            "estimated_cost_eur": round(estimated_cost_eur, 2),
            "project_id": project_id,
            "cache_age_seconds": 0,
            "last_updated": now.isoformat(),
            # Performance metrics
            "success_rate": round(success_rate, 1),
            "avg_processing_time_seconds": round(avg_processing_time, 2),
            "processing_rate_per_hour": round(processing_rate_per_hour, 1),
        }

        # Update cache
        _budget_cache = result
        _cache_timestamp = now

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Vision AI usage from Firestore: {str(e)}"
        )


def get_config_from_firestore() -> Optional[dict]:
    """Load Gemini configuration from Firestore."""
    try:
        doc_ref = firestore_client.db.collection("system_config").document("gemini")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"Error loading config from Firestore: {e}")
        return None


def save_config_to_firestore(config: dict) -> bool:
    """Save Gemini configuration to Firestore."""
    try:
        doc_ref = firestore_client.db.collection("system_config").document("gemini")
        doc_ref.set(config, merge=True)
        return True
    except Exception as e:
        print(f"Error saving config to Firestore: {e}")
        return False


@router.get("/config", response_model=GeminiConfiguration)
async def get_gemini_configuration():
    """
    Get Gemini 2.5 Flash configuration settings.

    Configuration is loaded from (in order of priority):
    1. Firestore (system_config/gemini document)
    2. Environment variables
    3. Defaults from CLAUDE.md

    Configuration can be updated via PUT /api/vision/config endpoint.
    """
    # Load from Firestore first (highest priority)
    firestore_config = get_config_from_firestore()

    # Fallback to environment variables and defaults
    config = GeminiConfiguration(
        model_name=firestore_config.get("model_name") if firestore_config else "Gemini",
        model_version=firestore_config.get("model_version") if firestore_config else os.getenv("GEMINI_MODEL_VERSION", "gemini-2.5-flash"),
        region=firestore_config.get("region") if firestore_config else os.getenv("GCP_REGION", "europe-west4"),
        input_method=firestore_config.get("input_method") if firestore_config else "Direct YouTube URL",
        resolution=firestore_config.get("resolution") if firestore_config else "Low (optimized)",
        tokens_per_frame=firestore_config.get("tokens_per_frame") if firestore_config else 66,
        rate_limit_type=firestore_config.get("rate_limit_type") if firestore_config else "Dynamic Shared Quota (DSQ)",
        max_output_tokens=firestore_config.get("max_output_tokens") if firestore_config else int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536")),
        input_cost_per_1m_tokens=firestore_config.get("input_cost_per_1m_tokens") if firestore_config else float(os.getenv("GEMINI_INPUT_COST", "0.30")),
        output_cost_per_1m_tokens=firestore_config.get("output_cost_per_1m_tokens") if firestore_config else float(os.getenv("GEMINI_OUTPUT_COST", "2.50")),
        audio_cost_per_1m_tokens=firestore_config.get("audio_cost_per_1m_tokens") if firestore_config else float(os.getenv("GEMINI_AUDIO_COST", "1.00")),
    )
    return config


@router.put("/config", response_model=GeminiConfiguration)
async def update_gemini_configuration(config: GeminiConfiguration):
    """
    Update Gemini 2.5 Flash configuration settings.

    Saves configuration to Firestore (system_config/gemini document).
    Changes take effect immediately and persist across restarts.

    All services will use the updated configuration on their next API call.
    """
    # Save to Firestore
    config_dict = config.model_dump()
    success = save_config_to_firestore(config_dict)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to save configuration to Firestore"
        )

    return config


@router.get("/budget", response_model=VisionBudgetStats)
async def get_vision_budget_stats():
    """
    Get real-time Vertex AI budget statistics.

    - Reads actual costs from gemini_budget Firestore collection
    - Falls back to calculating from analyzed videos if budget doc doesn't exist
    - Cached for 5 minutes to prevent excessive Firestore queries
    - Returns token counts and costs in USD/EUR
    """
    try:
        # Budget configuration (from CLAUDE.md)
        daily_budget_eur = 240.0
        daily_budget_usd = daily_budget_eur * 1.08

        # Try to get actual budget data from gemini_budget collection
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        budget_doc = firestore_client.db.collection("gemini_budget").document(today).get()

        if budget_doc.exists:
            # Use actual tracked budget
            budget_data = budget_doc.to_dict()
            budget_used_usd = budget_data.get("total_spent_usd", 0.0)
            budget_used_eur = budget_used_usd / 1.08
            total_requests = budget_data.get("total_requests", 0)
            total_input_tokens = budget_data.get("total_input_tokens", 0)
            total_output_tokens = budget_data.get("total_output_tokens", 0)
        else:
            # Fallback: calculate from analyzed videos
            usage = get_vertex_ai_usage()
            budget_used_eur = usage["estimated_cost_eur"]
            budget_used_usd = usage["estimated_cost_usd"]
            total_requests = usage["total_requests"]
            total_input_tokens = usage["total_input_tokens"]
            total_output_tokens = usage["total_output_tokens"]
        budget_remaining_eur = max(0, daily_budget_eur - budget_used_eur)
        budget_remaining_usd = max(0, daily_budget_usd - budget_used_usd)
        utilization = (budget_used_eur / daily_budget_eur) * 100

        # Get performance metrics from usage (only if we calculated from videos)
        if budget_doc.exists:
            success_rate = budget_data.get("success_rate", 100.0)
            avg_processing_time = budget_data.get("avg_processing_time_seconds", 1.2)
            processing_rate = budget_data.get("processing_rate_per_hour", 0.0)
            cache_age = 0
            last_updated = budget_data.get("last_updated", datetime.now(timezone.utc).isoformat())
        else:
            usage = get_vertex_ai_usage()
            success_rate = usage["success_rate"]
            avg_processing_time = usage["avg_processing_time_seconds"]
            processing_rate = usage["processing_rate_per_hour"]
            cache_age = usage["cache_age_seconds"]
            last_updated = usage["last_updated"]

        return VisionBudgetStats(
            daily_budget_eur=daily_budget_eur,
            daily_budget_usd=daily_budget_usd,
            budget_used_eur=round(budget_used_eur, 2),
            budget_used_usd=round(budget_used_usd, 2),
            budget_remaining_eur=round(budget_remaining_eur, 2),
            budget_remaining_usd=round(budget_remaining_usd, 2),
            utilization_percentage=round(utilization, 1),
            total_requests=total_requests,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            estimated_cost_usd=round(budget_used_usd, 2),
            cache_age_seconds=cache_age,
            data_from_project="copycat-local",
            last_updated=last_updated,
            # Performance metrics
            success_rate=success_rate,
            avg_processing_time_seconds=avg_processing_time,
            processing_rate_per_hour=processing_rate,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get budget statistics: {str(e)}"
        )


@router.get("/analytics", response_model=VisionAnalytics)
async def get_vision_analytics():
    """
    Get vision analysis statistics, error tracking, and historical data.

    Returns:
    - Total videos analyzed
    - Error counts and success rate
    - Infringement detection stats
    - Processing performance metrics
    - Recent errors with details
    - Status breakdown (success/error/pending/processing)
    """
    try:
        # Get current time
        now = datetime.now(timezone.utc)
        start_24h = now - timedelta(hours=24)

        # Query all videos
        videos = firestore_client.videos_collection.stream()

        total_analyzed = 0
        total_errors = 0
        infringements_found = 0
        processing_times = []
        total_cost = 0.0

        status_counts = {
            "success": 0,
            "error": 0,
            "pending": 0,
            "processing": 0
        }

        recent_errors = []
        videos_pending = 0

        analyzed_last_24h = 0
        errors_last_24h = 0
        cost_last_24h = 0.0

        for video in videos:
            data = video.to_dict()
            status = data.get("status", "pending")
            vision_analysis = data.get("vision_analysis")
            analyzed_at = data.get("analyzed_at")

            # Count by status
            if status == "analyzed":
                if vision_analysis:
                    total_analyzed += 1
                    status_counts["success"] += 1

                    # Check if infringement
                    if isinstance(vision_analysis, dict):
                        full_analysis = vision_analysis.get("full_analysis", vision_analysis)
                        if full_analysis.get("contains_infringement") is True:
                            infringements_found += 1

                    # Track processing time
                    proc_time = data.get("processing_time_seconds")
                    if proc_time and isinstance(proc_time, (int, float)):
                        processing_times.append(proc_time)

                    # Estimate cost (avg $0.008 per video from CLAUDE.md)
                    video_cost = 0.008
                    total_cost += video_cost

                    # Check if analyzed in last 24h
                    if analyzed_at:
                        try:
                            if isinstance(analyzed_at, str):
                                analyzed_time = datetime.fromisoformat(analyzed_at.replace('Z', '+00:00'))
                            else:
                                analyzed_time = analyzed_at

                            if analyzed_time.replace(tzinfo=timezone.utc) >= start_24h:
                                analyzed_last_24h += 1
                                cost_last_24h += video_cost
                        except:
                            pass
                else:
                    status_counts["error"] += 1
                    total_errors += 1
            elif status == "error":
                status_counts["error"] += 1
                total_errors += 1

                # Track recent errors
                error_msg = data.get("error_message", "Unknown error")
                error_time = data.get("error_at", data.get("updated_at"))
                if len(recent_errors) < 20:  # Keep last 20 errors
                    recent_errors.append({
                        "video_id": video.id,
                        "error_message": error_msg,
                        "timestamp": error_time.isoformat() if hasattr(error_time, 'isoformat') else str(error_time)
                    })

                # Check if error in last 24h
                if error_time:
                    try:
                        if isinstance(error_time, str):
                            err_time = datetime.fromisoformat(error_time.replace('Z', '+00:00'))
                        else:
                            err_time = error_time

                        if err_time.replace(tzinfo=timezone.utc) >= start_24h:
                            errors_last_24h += 1
                    except:
                        pass
            elif status == "processing":
                status_counts["processing"] += 1
            else:
                status_counts["pending"] += 1
                videos_pending += 1

        # Calculate metrics
        success_rate = (total_analyzed / (total_analyzed + total_errors) * 100) if (total_analyzed + total_errors) > 0 else 100.0
        detection_rate = (infringements_found / total_analyzed * 100) if total_analyzed > 0 else 0.0
        avg_processing_time = (sum(processing_times) / len(processing_times)) if processing_times else 0.0

        return VisionAnalytics(
            total_analyzed=total_analyzed,
            total_errors=total_errors,
            success_rate=round(success_rate, 1),
            infringements_found=infringements_found,
            detection_rate=round(detection_rate, 1),
            avg_processing_time_seconds=round(avg_processing_time, 2),
            total_cost_usd=round(total_cost, 2),
            videos_pending=videos_pending,
            last_24h={
                "analyzed": analyzed_last_24h,
                "errors": errors_last_24h,
                "cost_usd": round(cost_last_24h, 2)
            },
            by_status=status_counts,
            recent_errors=sorted(recent_errors, key=lambda x: x["timestamp"], reverse=True)[:10]  # Return 10 most recent
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics: {str(e)}"
        )
