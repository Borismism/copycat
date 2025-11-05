"""Budget management for daily Gemini API spending.

This module tracks daily budget usage, enforces limits, and implements
the budget exhaustion algorithm that maximizes daily spend utilization.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from google.cloud import firestore

from ..config import settings

logger = logging.getLogger(__name__)


class BudgetManager:
    """
    Manage daily Gemini API budget and enforce spending limits.

    Features:
    - Track daily spend in Firestore
    - Automatic midnight UTC reset
    - Cost estimation before scanning
    - Budget exhaustion algorithm

    NOTE: Gemini 2.5 Flash on Vertex AI uses Dynamic Shared Quota (DSQ).
    No hard rate limits! System scales automatically based on availability.
    """

    DAILY_BUDGET_USD = settings.daily_budget_usd

    def __init__(self, firestore_client: firestore.Client):
        """
        Initialize budget manager.

        Args:
            firestore_client: Firestore client for persistence
        """
        self.firestore = firestore_client
        self.budget_collection = settings.firestore_budget_collection

        # In-memory cache for current day
        self._cached_date: Optional[str] = None
        self._cached_total: float = 0.0
        self._video_count: int = 0
        self._start_time: float = datetime.now(timezone.utc).timestamp()

        logger.info(f"Budget manager initialized: daily_budget=${self.DAILY_BUDGET_USD}")

    def can_afford(self, estimated_cost_usd: float) -> bool:
        """
        Check if we can afford to analyze a video.

        Args:
            estimated_cost_usd: Estimated cost for the video

        Returns:
            True if within budget, False if would exceed
        """
        current_total = self.get_daily_total()
        would_exceed = (current_total + estimated_cost_usd) > self.DAILY_BUDGET_USD

        if would_exceed:
            logger.info(
                f"Budget check failed: current=${current_total:.2f}, "
                f"estimated=${estimated_cost_usd:.4f}, "
                f"would_total=${current_total + estimated_cost_usd:.2f}, "
                f"limit=${self.DAILY_BUDGET_USD}"
            )

        return not would_exceed

    def record_usage(self, video_id: str, actual_cost_usd: float):
        """
        Record actual cost after video analysis.

        Args:
            video_id: Video that was analyzed
            actual_cost_usd: Actual cost incurred
        """
        today = self._get_today_key()

        # Update Firestore
        doc_ref = self.firestore.collection(self.budget_collection).document(today)

        try:
            # Atomic increment
            doc_ref.set(
                {
                    "date": today,
                    "total_spent_usd": firestore.Increment(actual_cost_usd),
                    "video_count": firestore.Increment(1),
                    "last_updated": datetime.now(timezone.utc),
                },
                merge=True,
            )

            # Update cache
            self._cached_total += actual_cost_usd
            self._video_count += 1

            logger.info(
                f"Recorded usage: video={video_id}, cost=${actual_cost_usd:.4f}, "
                f"daily_total=${self._cached_total:.2f}/{self.DAILY_BUDGET_USD}"
            )

        except Exception as e:
            logger.error(f"Failed to record budget usage: {e}")
            raise

    def get_daily_total(self) -> float:
        """
        Get total spent today.

        Returns:
            Total spent in USD
        """
        today = self._get_today_key()

        # Return cached value if same day
        if self._cached_date == today:
            return self._cached_total

        # Fetch from Firestore
        try:
            doc_ref = self.firestore.collection(self.budget_collection).document(today)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                total = data.get("total_spent_usd", 0.0)
                video_count = data.get("video_count", 0)
            else:
                total = 0.0
                video_count = 0

            # Update cache
            self._cached_date = today
            self._cached_total = total
            self._video_count = video_count

            return total

        except Exception as e:
            logger.error(f"Failed to get daily total: {e}")
            # Return cached value as fallback
            return self._cached_total

    def get_remaining_budget(self) -> float:
        """
        Get remaining budget for today.

        Returns:
            Remaining budget in USD
        """
        remaining = max(0, self.DAILY_BUDGET_USD - self.get_daily_total())
        return remaining

    def get_utilization_percent(self) -> float:
        """
        Get budget utilization percentage.

        Returns:
            Utilization as percentage (0-100)
        """
        total = self.get_daily_total()
        utilization = (total / self.DAILY_BUDGET_USD) * 100
        return min(100, utilization)

    def get_video_count_today(self) -> int:
        """
        Get number of videos analyzed today.

        Returns:
            Video count
        """
        # Ensure cache is fresh
        self.get_daily_total()
        return self._video_count

    async def enforce_rate_limit(self):
        """
        No-op for Vertex AI DSQ (no hard rate limits).

        Kept for API compatibility but does nothing.
        Vertex AI Dynamic Shared Quota scales automatically.
        """
        # No rate limiting needed with Vertex AI DSQ
        pass

    def reset_session(self):
        """
        Reset session tracking (call at start of new scanning session).
        """
        self._start_time = datetime.now(timezone.utc).timestamp()
        self._video_count = self.get_video_count_today()
        logger.info(f"Session reset: starting with {self._video_count} videos analyzed today")

    def get_stats(self) -> dict:
        """
        Get budget statistics for monitoring.

        Returns:
            Dict with budget stats
        """
        total = self.get_daily_total()
        remaining = self.get_remaining_budget()
        utilization = self.get_utilization_percent()
        video_count = self.get_video_count_today()
        avg_cost = total / video_count if video_count > 0 else 0.0

        return {
            "date": self._get_today_key(),
            "daily_budget_usd": self.DAILY_BUDGET_USD,
            "total_spent_usd": round(total, 2),
            "remaining_usd": round(remaining, 2),
            "utilization_percent": round(utilization, 1),
            "videos_analyzed": video_count,
            "avg_cost_per_video": round(avg_cost, 4),
        }

    def _get_today_key(self) -> str:
        """
        Get today's date key (UTC).

        Returns:
            Date string in YYYY-MM-DD format
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
