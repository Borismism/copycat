"""Admin endpoints for manual rescoring operations."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_risk_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class BulkRescoreRequest(BaseModel):
    """Request to rescore all videos."""

    limit: int = 1000


class BulkRescoreResponse(BaseModel):
    """Response from bulk rescore operation."""

    videos_processed: int
    risks_increased: int
    risks_decreased: int
    risks_unchanged: int


@router.post("/rescore-all", response_model=BulkRescoreResponse)
async def rescore_all_videos(
    request: BulkRescoreRequest,
    risk_analyzer=Depends(get_risk_analyzer),
):
    """
    Rescore ALL videos with the latest 6-factor risk model.

    This endpoint:
    1. Fetches all videos from Firestore
    2. Applies the 6-factor risk scoring algorithm
    3. Updates scan_priority and priority_tier
    4. Videos are immediately available in priority queue

    Use this after deploying risk model changes.
    """
    logger.info(f"Starting bulk rescore (limit={request.limit})")

    # Get all video IDs
    videos_col = risk_analyzer.firestore.collection("videos")
    query = videos_col.limit(request.limit)
    video_ids = [doc.id for doc in query.stream()]

    logger.info(f"Found {len(video_ids)} videos to rescore")

    # Rescore batch
    stats = await risk_analyzer.rescore_video_batch(video_ids)

    logger.info(
        f"Bulk rescore complete: {stats['videos_processed']} videos, "
        f"{stats['risks_increased']} increased, "
        f"{stats['risks_decreased']} decreased"
    )

    return BulkRescoreResponse(
        videos_processed=stats["videos_processed"],
        risks_increased=stats["risks_increased"],
        risks_decreased=stats["risks_decreased"],
        risks_unchanged=stats["risks_unchanged"],
    )
