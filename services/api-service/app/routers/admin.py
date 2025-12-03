"""Admin endpoints for background jobs and system maintenance."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user, require_role
from app.core.firestore_client import firestore_client
from app.models import DailyStats, UserInfo, UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/jobs/aggregate-daily-stats", response_model=DailyStats)
@require_role(UserRole.ADMIN)
async def aggregate_daily_stats_job(
    date_offset_days: int = 1,
    user: UserInfo = Depends(get_current_user)
):
    """
    Aggregate daily statistics for a specific date.

    This endpoint is typically called by Cloud Scheduler to aggregate yesterday's stats.
    Only ADMIN users can trigger this job.

    Args:
        date_offset_days: Number of days ago to aggregate (default: 1 = yesterday)

    Returns:
        DailyStats object with aggregated statistics
    """
    try:
        # Calculate target date (typically yesterday)
        target_date = (datetime.now() - timedelta(days=date_offset_days)).date()

        logger.info(f"Starting daily stats aggregation for {target_date}")

        # Run aggregation
        stats_dict = await firestore_client.aggregate_daily_stats(target_date)

        logger.info(f"Successfully aggregated stats for {target_date}: {stats_dict}")

        return DailyStats(**stats_dict)

    except Exception as e:
        logger.error(f"Failed to aggregate daily stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to aggregate daily stats: {str(e)}"
        )
