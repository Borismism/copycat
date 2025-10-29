"""
Risk-based rescanning scheduler.

Determines which videos need rescanning based on risk tier and elapsed time.
Higher risk = more frequent scans = more Gemini budget allocated.
"""

import logging
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from ..config import settings

logger = logging.getLogger(__name__)


class ScanScheduler:
    """
    Risk-based rescanning scheduler.

    Scan Frequency by Tier:
    - CRITICAL (90-100): Every 6 hours
    - HIGH (70-89): Every 24 hours (daily)
    - MEDIUM (40-69): Every 3 days
    - LOW (20-39): Every 7 days (weekly)
    - VERY_LOW (0-19): Every 30 days (monthly)

    This ensures Gemini budget is focused on highest-risk content.
    """

    # Scan intervals by risk tier (in seconds)
    SCAN_INTERVALS = {
        "CRITICAL": settings.scan_frequency_critical,
        "HIGH": settings.scan_frequency_high,
        "MEDIUM": settings.scan_frequency_medium,
        "LOW": settings.scan_frequency_low,
        "VERY_LOW": settings.scan_frequency_very_low,
    }

    def __init__(self, firestore_client: firestore.Client):
        """
        Initialize scan scheduler.

        Args:
            firestore_client: Firestore client for data access
        """
        self.firestore = firestore_client
        self.videos_collection = "videos"

        logger.info("ScanScheduler initialized")

    def get_videos_due_for_scan(self, limit: int = 100) -> list[dict]:
        """
        Get videos due for rescanning, prioritized by risk tier.

        Query strategy:
        1. Get videos where next_scan_at <= now
        2. Order by risk_tier (CRITICAL first) then next_scan_at
        3. Limit to batch size

        Args:
            limit: Maximum number of videos to return

        Returns:
            List of video documents due for scanning
        """
        now = datetime.now(timezone.utc)

        try:
            # Query videos due for scan
            query = (
                self.firestore.collection(self.videos_collection)
                .where("next_scan_at", "<=", now)
                .order_by("next_scan_at")
                .limit(limit)
            )

            videos = []
            for doc in query.stream():
                video_data = doc.to_dict()
                video_data["video_id"] = doc.id
                videos.append(video_data)

            # Sort by risk tier priority (CRITICAL > HIGH > MEDIUM > LOW > VERY_LOW)
            tier_priority = {
                "CRITICAL": 0,
                "HIGH": 1,
                "MEDIUM": 2,
                "LOW": 3,
                "VERY_LOW": 4,
            }

            videos.sort(key=lambda v: tier_priority.get(v.get("risk_tier", "VERY_LOW"), 4))

            logger.info(f"Found {len(videos)} videos due for scanning")

            return videos

        except Exception as e:
            logger.error(f"Error getting videos due for scan: {e}")
            return []

    def calculate_next_scan_time(self, risk_tier: str, last_scan: datetime | None = None) -> datetime:
        """
        Calculate next scan time based on risk tier.

        Args:
            risk_tier: Risk tier (CRITICAL/HIGH/MEDIUM/LOW/VERY_LOW)
            last_scan: Last scan timestamp (defaults to now)

        Returns:
            Next scheduled scan datetime
        """
        if last_scan is None:
            last_scan = datetime.now(timezone.utc)

        # Get interval for this tier
        interval_seconds = self.SCAN_INTERVALS.get(risk_tier, self.SCAN_INTERVALS["VERY_LOW"])

        # Calculate next scan time
        next_scan = last_scan + timedelta(seconds=interval_seconds)

        logger.debug(f"Risk tier {risk_tier}: next scan at {next_scan}")

        return next_scan

    def update_next_scan_time(self, video_id: str, risk_tier: str) -> None:
        """
        Update next_scan_at field for a video.

        Args:
            video_id: Video ID to update
            risk_tier: Current risk tier
        """
        try:
            next_scan = self.calculate_next_scan_time(risk_tier)

            doc_ref = self.firestore.collection(self.videos_collection).document(video_id)
            doc_ref.update({
                "next_scan_at": next_scan,
                "updated_at": datetime.now(timezone.utc),
            })

            logger.info(f"Video {video_id}: next scan scheduled for {next_scan}")

        except Exception as e:
            logger.error(f"Error updating next scan time for {video_id}: {e}")

    def get_scan_queue_stats(self) -> dict:
        """
        Get statistics about the scan queue.

        Returns:
            Dictionary with queue statistics by tier
        """
        now = datetime.now(timezone.utc)

        stats = {
            "total_due": 0,
            "by_tier": {
                "CRITICAL": 0,
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
                "VERY_LOW": 0,
            },
        }

        try:
            # Count videos due for scan by tier
            for tier in stats["by_tier"].keys():
                query = (
                    self.firestore.collection(self.videos_collection)
                    .where("risk_tier", "==", tier)
                    .where("next_scan_at", "<=", now)
                )

                count = sum(1 for _ in query.stream())
                stats["by_tier"][tier] = count
                stats["total_due"] += count

            logger.info(f"Scan queue: {stats['total_due']} videos due, {stats['by_tier']}")

            return stats

        except Exception as e:
            logger.error(f"Error getting scan queue stats: {e}")
            return stats

    def get_next_scan_batch(self, batch_size: int = 100) -> list[str]:
        """
        Get next batch of video IDs to scan, prioritized by risk.

        This is the main method used by the continuous scanning loop.

        Args:
            batch_size: Number of videos to return

        Returns:
            List of video IDs to scan
        """
        videos = self.get_videos_due_for_scan(limit=batch_size)
        video_ids = [v["video_id"] for v in videos]

        if video_ids:
            logger.info(
                f"Next scan batch: {len(video_ids)} videos "
                f"(tiers: {[v.get('risk_tier', 'UNKNOWN') for v in videos[:5]]})"
            )

        return video_ids
