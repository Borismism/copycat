"""Admin endpoints for manual operations and monitoring."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.logging_utils import log_exception_json

router = APIRouter()
logger = logging.getLogger(__name__)


class BudgetStatsResponse(BaseModel):
    """Budget statistics response."""

    date: str
    daily_budget_usd: float
    total_spent_usd: float
    remaining_usd: float
    utilization_percent: float
    videos_analyzed: int
    avg_cost_per_video: float


class TriggerAnalysisRequest(BaseModel):
    """Manual analysis trigger request."""

    video_id: str
    force: bool = False  # Force analysis even if budget low


class TriggerAnalysisResponse(BaseModel):
    """Manual analysis trigger response."""

    success: bool
    message: str
    video_id: str
    cost_usd: float | None = None


class BatchScanRequest(BaseModel):
    """Batch scan trigger request."""

    limit: int = 10  # Number of videos to scan
    min_priority: int = 50  # Minimum scan_priority score
    force: bool = False  # Force even if budget low


class BatchScanResponse(BaseModel):
    """Batch scan trigger response."""

    success: bool
    message: str
    videos_queued: int
    estimated_cost_usd: float
    budget_remaining_usd: float


@router.get("/admin/budget", response_model=BudgetStatsResponse)
async def get_budget_stats():
    """
    Get current budget statistics.

    Returns:
        Budget stats
    """
    from .. import worker

    if not worker.budget_manager:
        raise HTTPException(status_code=503, detail="Budget manager not initialized")

    stats = worker.budget_manager.get_stats()
    return BudgetStatsResponse(**stats)


@router.post("/admin/analyze", response_model=TriggerAnalysisResponse)
async def trigger_analysis(request: TriggerAnalysisRequest):
    """
    Manually trigger analysis for a specific video (for testing).

    Args:
        request: Video ID and options

    Returns:
        Analysis result
    """
    from .. import worker
    from ..models import VideoMetadata
    from google.cloud import firestore
    from datetime import datetime

    if not worker.video_analyzer:
        raise HTTPException(status_code=503, detail="Video analyzer not initialized")

    try:
        # Fetch video metadata from Firestore
        firestore_client = firestore.Client(
            project=worker.settings.gcp_project_id,
            database=worker.settings.firestore_database_id,
        )
        doc_ref = firestore_client.collection(worker.settings.firestore_videos_collection).document(
            request.video_id
        )
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found")

        # Parse video data
        data = doc.to_dict()

        # Build VideoMetadata
        matched_ips = data.get("matched_ips", [])
        video_metadata = VideoMetadata(
            video_id=request.video_id,
            youtube_url=f"https://youtube.com/watch?v={request.video_id}",
            title=data.get("title", "Unknown"),
            duration_seconds=data.get("duration_seconds", 300),
            view_count=data.get("view_count", 0),
            channel_id=data.get("channel_id", ""),
            channel_title=data.get("channel_title", "Unknown"),
            risk_score=data.get("risk_score", 50.0),
            risk_tier=data.get("risk_tier", "MEDIUM"),
            matched_characters=matched_ips,
            matched_ips=matched_ips,
            discovered_at=data.get("discovered_at") or datetime.now(),
            last_risk_update=data.get("last_risk_update") or data.get("discovered_at") or datetime.now(),
        )

        # Load IP configs (same logic as worker.py)
        if not matched_ips:
            logger.info(f"No matched_ips for video {request.video_id}. Loading ALL IP configs.")
            configs = worker.config_loader.get_all_configs()
            if not configs:
                raise HTTPException(status_code=500, detail="No IP configs available in system")
        else:
            logger.info(f"Loading configs for matched IPs: {matched_ips}")
            configs = []
            for ip_id in matched_ips:
                config = worker.config_loader.get_config(ip_id)
                if config:
                    configs.append(config)
                else:
                    logger.error(f"Config not found for IP: {ip_id}")

            if not configs:
                raise HTTPException(
                    status_code=500,
                    detail=f"No valid configs found for matched_ips={matched_ips}"
                )

        # Analyze video with configs
        logger.info(f"Triggering manual analysis for video {request.video_id} with {len(configs)} IP configs")
        result = await worker.video_analyzer.analyze_video(video_metadata, configs=configs, queue_size=1)

        return TriggerAnalysisResponse(
            success=True,
            message=f"Analysis complete: infringement={result.analysis.contains_infringement}, confidence={result.analysis.confidence_score}%",
            video_id=request.video_id,
            cost_usd=result.metrics.cost_usd,
        )

    except Exception as e:
        log_exception_json(logger, "Failed to trigger analysis", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/status")
async def get_status():
    """
    Get service status and health.

    Returns:
        Service status
    """
    from ..routers import analyze

    return {
        "service": "vision-analyzer-service",
        "mode": "push_subscription",
        "components_initialized": {
            "video_analyzer": analyze.video_analyzer is not None,
            "budget_manager": analyze.budget_manager is not None,
            "config_loader": analyze.config_loader is not None,
        },
    }


@router.post("/admin/analyze-mock", response_model=TriggerAnalysisResponse)
async def trigger_mock_analysis(request: TriggerAnalysisRequest):
    """
    Manually trigger a MOCK analysis (for testing UI without hitting Gemini).

    Args:
        request: Video ID and options

    Returns:
        Mock analysis result
    """
    from .. import worker
    from ..models import GeminiAnalysisResult, AnalysisResult, AnalysisMetrics
    from google.cloud import firestore
    from datetime import datetime
    import random

    if not worker.video_analyzer:
        raise HTTPException(status_code=503, detail="Video analyzer not initialized")

    try:
        # Fetch video metadata from Firestore
        firestore_client = firestore.Client(
            project=worker.settings.gcp_project_id,
            database=worker.settings.firestore_database_id,
        )
        doc_ref = firestore_client.collection(worker.settings.firestore_videos_collection).document(
            request.video_id
        )
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found")

        doc.to_dict()

        # Create mock analysis result
        mock_infringement = random.choice([True, False])
        mock_confidence = random.randint(70, 95)
        mock_cost = round(random.uniform(0.003, 0.012), 4)

        gemini_result = GeminiAnalysisResult(
            contains_infringement=mock_infringement,
            confidence_score=mock_confidence,
            infringement_type="ai_clips" if mock_infringement else "fair_use",
            ai_generated={
                "is_ai": True,
                "confidence": 85,
                "tools_detected": ["Sora AI"],
                "evidence": "MOCK: AI-generated content detected"
            },
            characters_detected=[
                {
                    "name": "Superman",
                    "screen_time_seconds": 5,
                    "prominence": "primary",
                    "timestamps": ["0:00-0:05"],
                    "description": "MOCK: Character appearance"
                }
            ],
            copyright_assessment={
                "infringement_likelihood": mock_confidence,
                "reasoning": "MOCK ANALYSIS - This is a test result, not real Gemini output",
                "fair_use_applies": not mock_infringement,
                "fair_use_factors": {}
            },
            video_characteristics={
                "duration_category": "short",
                "content_type": "clips",
                "monetization_detected": False,
                "professional_quality": False
            },
            recommended_action="monitor" if mock_infringement else "safe_harbor",
            legal_notes="MOCK RESULT - For testing only"
        )

        metrics = AnalysisMetrics(
            cost_usd=mock_cost,
            input_tokens=5000,
            output_tokens=500,
            processing_time_seconds=2.5,
            fps_used=0.5,
            frames_analyzed=100
        )

        # Store result in Firestore
        AnalysisResult(
            analysis=gemini_result,
            metrics=metrics
        )

        # Update Firestore with mock result
        doc_ref.update({
            "vision_analysis": gemini_result.model_dump(),
            "analysis_cost_usd": mock_cost,
            "analyzed_at": datetime.now(),
            "status": "analyzed",
        })

        logger.info(f"Mock analysis stored for video {request.video_id}")

        return TriggerAnalysisResponse(
            success=True,
            message=f"MOCK Analysis complete: infringement={mock_infringement}, confidence={mock_confidence}%",
            video_id=request.video_id,
            cost_usd=mock_cost,
        )

    except Exception as e:
        log_exception_json(logger, "Failed to trigger mock analysis", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/batch-scan", response_model=BatchScanResponse)
async def trigger_batch_scan(request: BatchScanRequest):
    """
    Trigger batch scanning of high-priority videos (OPTIMIZED).

    Calculates max affordable videos upfront, queries and publishes in batch.
    Up to 100x faster than one-by-one processing!

    Args:
        request: Batch scan parameters

    Returns:
        Batch scan result with stats
    """
    from .. import worker
    from google.cloud import firestore, pubsub_v1
    import json
    from datetime import datetime

    if not worker.budget_manager:
        raise HTTPException(status_code=503, detail="Budget manager not initialized")

    try:
        # Check budget and calculate max affordable videos
        budget_remaining = worker.budget_manager.get_remaining_budget()
        avg_cost_per_video = 0.008  # Average $0.008 per video
        firestore_client = firestore.Client(
            project=worker.settings.gcp_project_id,
            database=worker.settings.firestore_database_id,
        )

        if not request.force:
            # Calculate how many videos we can afford
            max_affordable = int(budget_remaining / avg_cost_per_video)

            if max_affordable < 1:
                raise HTTPException(
                    status_code=402,
                    detail=f"Insufficient budget: ${budget_remaining:.2f} remaining (need ~${avg_cost_per_video} per video)"
                )

            # Limit to budget OR requested limit, whichever is lower
            effective_limit = min(request.limit, max_affordable)
            logger.info(
                f"Budget allows {max_affordable} videos, requesting {request.limit}, "
                f"will query {effective_limit} videos"
            )
        else:
            effective_limit = request.limit
            logger.info(f"Force mode: ignoring budget, querying {effective_limit} videos")

        # Query Firestore for ALL videos needing analysis (discovered OR failed)
        # Process from highest to lowest priority
        videos_ref = firestore_client.collection(worker.settings.firestore_videos_collection)

        # Fetch all discovered videos (need first scan)
        query_discovered = (
            videos_ref
            .where("scan_priority", ">=", request.min_priority)
            .where("status", "==", "discovered")
            .order_by("scan_priority", direction=firestore.Query.DESCENDING)
        )

        # Fetch all failed videos (need retry)
        query_failed = (
            videos_ref
            .where("scan_priority", ">=", request.min_priority)
            .where("status", "==", "failed")
            .order_by("scan_priority", direction=firestore.Query.DESCENDING)
        )

        # Fetch both and merge, sort by priority (highest first)
        videos_discovered = list(query_discovered.stream())
        videos_failed = list(query_failed.stream())
        all_videos = videos_discovered + videos_failed

        # Sort by scan_priority descending (try highest priority first)
        all_videos.sort(key=lambda doc: doc.to_dict().get("scan_priority", 0), reverse=True)

        # Limit to budget/batch size
        videos = all_videos[:effective_limit]

        if not videos:
            return BatchScanResponse(
                success=True,
                message=f"No videos found with priority >= {request.min_priority}",
                videos_queued=0,
                estimated_cost_usd=0.0,
                budget_remaining_usd=budget_remaining
            )

        # Publish ALL messages in batch (way faster!)
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(worker.settings.gcp_project_id, "scan-ready")

        # Batch publish with futures
        publish_futures = []

        for doc in videos:
            data = doc.to_dict()
            video_id = doc.id

            # Build scan message
            scan_message = {
                "video_id": video_id,
                "priority": data.get("scan_priority", 50),
                "metadata": {
                    "video_id": video_id,
                    "youtube_url": f"https://youtube.com/watch?v={video_id}",
                    "title": data.get("title", "Unknown"),
                    "duration_seconds": data.get("duration_seconds", 300),
                    "view_count": data.get("view_count", 0),
                    "channel_id": data.get("channel_id", ""),
                    "channel_title": data.get("channel_title", "Unknown"),
                    "risk_score": data.get("scan_priority", 50.0),
                    "risk_tier": data.get("priority_tier", "MEDIUM"),
                    "matched_ips": data.get("matched_ips", []),
                    "discovered_at": data.get("discovered_at", datetime.now()).isoformat() if isinstance(data.get("discovered_at"), datetime) else str(data.get("discovered_at", datetime.now())),
                    "last_risk_update": data.get("discovered_at", datetime.now()).isoformat() if isinstance(data.get("discovered_at"), datetime) else str(data.get("discovered_at", datetime.now())),
                }
            }

            # Publish (non-blocking, returns future)
            message_data = json.dumps(scan_message).encode("utf-8")
            future = publisher.publish(topic_path, message_data)
            publish_futures.append((video_id, data.get("scan_priority"), future))

        # Wait for all publishes to complete
        queued_count = 0
        for video_id, priority, future in publish_futures:
            try:
                message_id = future.result(timeout=10)  # 10s timeout per message
                queued_count += 1
                logger.debug(f"Queued {video_id} (priority={priority}, msg={message_id})")
            except Exception as e:
                logger.error(f"Failed to publish {video_id}: {e}")

        # Calculate estimated cost
        estimated_cost = queued_count * avg_cost_per_video

        logger.info(
            f"Batch scan complete: queued {queued_count}/{len(videos)} videos, "
            f"estimated_cost=${estimated_cost:.2f}"
        )

        return BatchScanResponse(
            success=True,
            message=f"Queued {queued_count} videos for scanning",
            videos_queued=queued_count,
            estimated_cost_usd=round(estimated_cost, 2),
            budget_remaining_usd=round(budget_remaining, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        log_exception_json(logger, "Failed to trigger batch scan", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=str(e))


class CleanupResponse(BaseModel):
    """Cleanup stuck videos response."""

    success: bool
    message: str
    videos_marked_failed: int
    scan_history_updated: int


@router.post("/admin/cleanup-stuck-videos", response_model=CleanupResponse)
async def cleanup_stuck_videos():
    """
    Cleanup videos stuck in 'processing' status.

    This endpoint is called by Cloud Scheduler every 10 minutes to catch videos
    that got stuck due to:
    - Gemini API hanging
    - Instance crashes
    - Cloud Run scale-down
    - Network issues

    Returns:
        CleanupResponse with statistics
    """
    from datetime import datetime, timedelta, timezone
    from google.cloud import firestore
    from ..config import settings

    STUCK_THRESHOLD_MINUTES = 20  # Videos processing >20 minutes are stuck

    try:
        logger.info("🔍 Cleanup cron: Checking for stuck videos...")

        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id,
        )

        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)

        # Query videos in processing status
        videos_ref = firestore_client.collection(settings.firestore_videos_collection)
        stuck_videos = videos_ref.where("status", "==", "processing").stream()

        marked_count = 0
        scan_history_count = 0

        for video in stuck_videos:
            video_data = video.to_dict()
            video_id = video.id

            # Check processing_started_at timestamp
            processing_started = video_data.get("processing_started_at")

            should_mark = False
            if not processing_started:
                # No timestamp - definitely stuck
                logger.warning(f"Video {video_id} has no processing_started_at, marking as failed")
                should_mark = True
            else:
                # Convert to datetime if needed
                if hasattr(processing_started, "timestamp"):
                    started_dt = datetime.fromtimestamp(processing_started.timestamp(), tz=timezone.utc)
                else:
                    started_dt = processing_started

                # Ensure timezone-aware
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)

                # Check if stuck
                if started_dt < cutoff_time:
                    stuck_duration_mins = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
                    logger.warning(f"Video {video_id} stuck for {stuck_duration_mins:.1f}m, marking as failed")
                    should_mark = True

            if should_mark:
                # Mark video as failed
                video.reference.update({
                    "status": "failed",
                    "error_message": f"Video stuck in processing for >{STUCK_THRESHOLD_MINUTES} minutes - likely Gemini timeout or instance crash",
                    "error_type": "ProcessingTimeout",
                    "failed_at": firestore.SERVER_TIMESTAMP,
                    "processing_started_at": firestore.DELETE_FIELD,
                })

                marked_count += 1

                # Mark related scan history as failed
                scan_history_query = firestore_client.collection("scan_history") \
                    .where("video_id", "==", video_id) \
                    .where("status", "==", "running")

                for scan_doc in scan_history_query.stream():
                    scan_doc.reference.update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": "Video stuck in processing (cleanup cron)",
                    })
                    scan_history_count += 1

        logger.info(
            f"Cleanup complete: marked {marked_count} videos as failed, "
            f"updated {scan_history_count} scan history entries"
        )

        return CleanupResponse(
            success=True,
            message=f"Marked {marked_count} stuck videos as failed",
            videos_marked_failed=marked_count,
            scan_history_updated=scan_history_count
        )

    except Exception as e:
        log_exception_json(logger, "Failed to cleanup stuck videos", e, severity="ERROR")
        raise HTTPException(status_code=500, detail=str(e))
