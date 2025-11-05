"""Admin endpoints for manual operations and monitoring."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    cost_usd: Optional[float] = None


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
        firestore_client = firestore.Client(project=worker.settings.gcp_project_id)
        doc_ref = firestore_client.collection(worker.settings.firestore_videos_collection).document(
            request.video_id
        )
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found")

        # Parse video data
        data = doc.to_dict()

        # Build VideoMetadata
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
            matched_characters=data.get("matched_ips", []),
            discovered_at=data.get("discovered_at") or datetime.now(),
            last_risk_update=data.get("last_risk_update") or data.get("discovered_at") or datetime.now(),
        )

        # Analyze video
        logger.info(f"Triggering manual analysis for video {request.video_id}")
        result = await worker.video_analyzer.analyze_video(video_metadata, queue_size=1)

        return TriggerAnalysisResponse(
            success=True,
            message=f"Analysis complete: infringement={result.analysis.contains_infringement}, confidence={result.analysis.confidence_score}%",
            video_id=request.video_id,
            cost_usd=result.metrics.cost_usd,
        )

    except Exception as e:
        logger.error(f"Failed to trigger analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/status")
async def get_status():
    """
    Get service status and health.

    Returns:
        Service status
    """
    from .. import worker

    return {
        "service": "vision-analyzer-service",
        "worker_running": worker.worker_thread is not None,
        "components_initialized": {
            "video_analyzer": worker.video_analyzer is not None,
            "budget_manager": worker.budget_manager is not None,
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
        firestore_client = firestore.Client(project=worker.settings.gcp_project_id)
        doc_ref = firestore_client.collection(worker.settings.firestore_videos_collection).document(
            request.video_id
        )
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found")

        data = doc.to_dict()

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
        result = AnalysisResult(
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
        logger.error(f"Failed to trigger mock analysis: {e}", exc_info=True)
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
        firestore_client = firestore.Client(project=worker.settings.gcp_project_id)
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
        logger.error(f"Failed to trigger batch scan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
