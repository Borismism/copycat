"""YouTube API quota management and optimization."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore
from google.cloud import monitoring_v3

logger = logging.getLogger(__name__)


class QuotaManager:
    """
    YouTube API quota optimization.

    Tracks daily quota usage, prevents quota exhaustion, and provides
    visibility into API consumption patterns.

    YouTube API v3 quota costs:
    - search.list: 100 units
    - videos.list: 1 unit
    - channels.list: 1 unit
    - playlistItems.list: 1 unit
    """

    # YouTube API v3 operation costs
    COSTS = {
        "search": 100,  # search.list - EXPENSIVE
        "video_details": 1,  # videos.list
        "trending": 1,  # videos.list (chart parameter)
        "channel_details": 1,  # channels.list
        "playlist_items": 1,  # playlistItems.list (channel uploads pagination)
    }

    # Warning threshold (percentage)
    WARNING_THRESHOLD = 0.80  # 80%

    def __init__(
        self,
        firestore_client: firestore.Client,
        daily_quota: int = 10_000,
        quota_collection: str = "quota_usage",
        project_id: str | None = None,
    ):
        """
        Initialize quota manager.

        Args:
            firestore_client: Firestore client for persistence
            daily_quota: Daily quota limit in units (default: 10,000)
            quota_collection: Firestore collection name for quota tracking
            project_id: GCP project ID for monitoring API
        """
        self.firestore = firestore_client
        self.daily_quota = daily_quota
        self.quota_collection = quota_collection
        self.project_id = project_id or firestore_client.project
        self.monitoring_client = monitoring_v3.MetricServiceClient()
        self._warning_logged = False
        self._operations_since_reload = 0
        self._reload_interval = 10  # Reload from Google every 10 operations

        # Load REAL quota from Google Monitoring API on startup
        self.used_quota = self.fetch_actual_quota_from_google()
        if self.used_quota == 0:
            # Fallback to Firestore if Google API fails
            self.used_quota = self._load_today_usage()

        logger.info(
            f"QuotaManager initialized: {self.used_quota}/{self.daily_quota} units used (from Google)"
        )

    def _get_today_key(self) -> str:
        """
        Get today's date key for Firestore document.

        Returns:
            Date string in YYYY-MM-DD format (UTC)
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_today_usage(self) -> int:
        """
        Load today's quota usage from Firestore.

        Returns:
            Number of quota units used today (0 if no record)
        """
        today_key = self._get_today_key()
        doc_ref = self.firestore.collection(self.quota_collection).document(today_key)

        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                used = data.get("units_used", 0)
                logger.debug(f"Loaded today's usage: {used} units")
                return used
            else:
                logger.debug("No usage record for today")
                return 0
        except Exception as e:
            logger.error(f"Failed to load quota usage: {e}")
            return 0

    def can_afford(self, operation: str, count: int = 1) -> bool:
        """
        Check if we can afford this operation without exceeding quota.

        Args:
            operation: Operation type (search, video_details, etc.)
            count: Number of operations (default: 1)

        Returns:
            True if operation is affordable, False otherwise

        Raises:
            ValueError: If operation type is unknown
        """
        if operation not in self.COSTS:
            raise ValueError(
                f"Unknown operation: {operation}. "
                f"Valid operations: {list(self.COSTS.keys())}"
            )

        cost = self.COSTS[operation] * count
        affordable = (self.used_quota + cost) <= self.daily_quota

        if not affordable:
            logger.warning(
                f"Cannot afford {operation} (cost: {cost}, "
                f"used: {self.used_quota}/{self.daily_quota})"
            )

        return affordable

    def fetch_actual_quota_from_google(self) -> int:
        """
        Fetch actual quota usage directly from Google Cloud Monitoring API.

        This queries the real YouTube API quota consumed according to Google's metrics,
        not our estimates.

        Returns:
            Actual quota units used today according to Google
        """
        try:
            project_name = f"projects/{self.project_id}"

            # Query for YouTube API quota usage in the last 24 hours
            now = datetime.now(timezone.utc)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

            interval = monitoring_v3.TimeInterval({
                "end_time": now,
                "start_time": start_of_day,
            })

            # YouTube Data API v3 quota metric - CORRECT METRIC!
            # Source: https://stackoverflow.com/questions/65886976/
            metric_filter = (
                'metric.type = "serviceruntime.googleapis.com/quota/rate/net_usage" '
                'AND resource.labels.service = "youtube.googleapis.com"'
            )

            results = self.monitoring_client.list_time_series(
                request={
                    "name": project_name,
                    "filter": metric_filter,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            # Sum up quota usage
            total_quota = 0
            for result in results:
                for point in result.points:
                    total_quota += point.value.int64_value or point.value.double_value or 0

            if total_quota > 0:
                logger.info(f"Fetched actual quota from Google (quota metric): {total_quota} units")
                return int(total_quota)

            # Fallback: Use Firestore tracking (our estimates are more accurate than request count)
            logger.warning("Could not fetch quota metric from Google, using Firestore")
            return self._load_today_usage()

        except Exception as e:
            logger.error(f"Failed to fetch quota from Google Cloud Monitoring: {e}")
            # Fall back to Firestore value if monitoring API fails
            return self._load_today_usage()

    def reload_usage(self) -> None:
        """
        Reload quota usage from Google Cloud Monitoring (actual usage).

        Fetches real quota consumption from Google's monitoring API and
        updates both in-memory and Firestore values.
        """
        previous_usage = self.used_quota

        # Fetch actual usage from Google
        actual_usage = self.fetch_actual_quota_from_google()
        self.used_quota = actual_usage

        # Update Firestore with actual value
        self._save_actual_usage_to_firestore(actual_usage)

        if self.used_quota != previous_usage:
            logger.info(
                f"Reloaded quota usage: {previous_usage} → {self.used_quota} units (from Google)"
            )

    def _save_actual_usage_to_firestore(self, actual_usage: int) -> None:
        """Save actual quota usage from Google to Firestore."""
        today_key = self._get_today_key()
        doc_ref = self.firestore.collection(self.quota_collection).document(today_key)

        try:
            doc_ref.set({
                "units_used": actual_usage,
                "last_updated": datetime.now(timezone.utc),
                "source": "google_monitoring_api",
            }, merge=True)
            logger.debug(f"Saved actual usage to Firestore: {actual_usage} units")
        except Exception as e:
            logger.error(f"Failed to save actual usage to Firestore: {e}")

    def record_usage(self, operation: str, count: int = 1) -> None:
        """
        Record API usage and persist to Firestore.

        Updates both in-memory counter and Firestore document.
        Logs warning if quota utilization exceeds 80%.

        Args:
            operation: Operation type (search, video_details, etc.)
            count: Number of operations (default: 1)

        Raises:
            ValueError: If operation type is unknown
        """
        if operation not in self.COSTS:
            raise ValueError(
                f"Unknown operation: {operation}. "
                f"Valid operations: {list(self.COSTS.keys())}"
            )

        # Reload from Google periodically (not every operation - too slow!)
        self._operations_since_reload += 1
        if self._operations_since_reload >= self._reload_interval:
            self.reload_usage()
            self._operations_since_reload = 0

        cost = self.COSTS[operation] * count
        self.used_quota += cost

        logger.info(
            f"Recorded {operation} usage: {cost} units "
            f"(total: {self.used_quota}/{self.daily_quota})"
        )

        # Check warning threshold
        utilization = self.get_utilization()
        if utilization >= self.WARNING_THRESHOLD and not self._warning_logged:
            logger.warning(
                f"⚠️  QUOTA WARNING: {utilization:.1%} utilization "
                f"({self.used_quota}/{self.daily_quota} units used)"
            )
            self._warning_logged = True

        # Persist to Firestore
        self._save_to_firestore()

    def _save_to_firestore(self) -> None:
        """
        Save current quota usage to Firestore with atomic update.

        Uses Firestore transactions to ensure quota updates are atomic
        and prevent race conditions when multiple service instances run.
        """
        today_key = self._get_today_key()
        doc_ref = self.firestore.collection(self.quota_collection).document(today_key)

        try:
            # Use set with merge to update atomically
            doc_ref.set(
                {
                    "date": today_key,
                    "units_used": self.used_quota,
                    "daily_quota": self.daily_quota,
                    "updated_at": datetime.now(timezone.utc),
                },
                merge=True,
            )
            logger.debug(f"Saved quota usage to Firestore: {self.used_quota} units")
        except Exception as e:
            logger.error(f"Failed to save quota usage to Firestore: {e}")

    def get_remaining(self) -> int:
        """
        Get remaining quota for today.

        Returns:
            Number of quota units remaining (0 if quota exceeded)
        """
        remaining = max(0, self.daily_quota - self.used_quota)
        return remaining

    def get_utilization(self) -> float:
        """
        Get quota utilization percentage.

        Returns:
            Utilization as float between 0.0 and 1.0
        """
        if self.daily_quota == 0:
            return 0.0

        utilization = self.used_quota / self.daily_quota
        return min(1.0, utilization)  # Cap at 100%

    def get_status(self) -> dict[str, Any]:
        """
        Get comprehensive quota status.

        Returns:
            Dictionary with quota metrics:
            - used: Units used today
            - remaining: Units remaining
            - daily_quota: Daily limit
            - utilization: Usage percentage (0-100)
            - date: Current date (UTC)
        """
        return {
            "used": self.used_quota,
            "remaining": self.get_remaining(),
            "daily_quota": self.daily_quota,
            "utilization": self.get_utilization() * 100,
            "date": self._get_today_key(),
        }

    def reset_daily_quota(self) -> None:
        """
        Reset daily quota counter.

        Used primarily for testing. In production, quota automatically
        resets when date changes (new Firestore document).
        """
        self.used_quota = 0
        self._warning_logged = False
        logger.info("Daily quota reset to 0")
