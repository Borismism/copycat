"""
Scan Priority Calculator - Combines Channel Risk + Video Risk

Final scan priority score (0-100) = (Channel Risk × 0.40) + (Video Risk × 0.60)

This creates a balanced scoring system where:
- Video characteristics matter more (60%) - specific content is most important
- Channel reputation provides context (40%) - past behavior influences priority
"""

import logging
from google.cloud import firestore

from .channel_risk_calculator import ChannelRiskCalculator
from .video_risk_calculator import VideoRiskCalculator
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)


class ScanPriorityCalculator:
    """
    Combines channel and video risk into final scan priority.

    Priority Tiers:
    - CRITICAL (90-100): Scan within 6 hours
    - HIGH (70-89): Scan within 24 hours
    - MEDIUM (50-69): Scan within 3 days
    - LOW (30-49): Scan within 7 days
    - VERY_LOW (0-29): Scan within 30 days (or skip entirely)
    """

    CHANNEL_WEIGHT = 0.40
    VIDEO_WEIGHT = 0.60

    def __init__(self, firestore_client: firestore.Client):
        """
        Initialize scan priority calculator.

        Args:
            firestore_client: Firestore client for data access
        """
        self.firestore = firestore_client
        self.channel_calculator = ChannelRiskCalculator()
        self.video_calculator = VideoRiskCalculator()

        logger.info("ScanPriorityCalculator initialized")

    async def calculate_priority(self, video_data: dict) -> dict:
        """
        Calculate final scan priority for a video.

        Args:
            video_data: Video document from Firestore

        Returns:
            {
                "scan_priority": int (0-100),
                "priority_tier": str,
                "channel_risk": int,
                "video_risk": int,
                "channel_factors": dict,
                "video_factors": dict
            }
        """
        video_id = video_data.get("video_id", "unknown")
        channel_id = video_data.get("channel_id", "unknown")

        # Get channel data
        channel_data = await self._get_channel_data(channel_id)

        # Calculate channel risk (0-100)
        channel_result = self.channel_calculator.calculate_channel_risk(channel_data)
        channel_risk = channel_result["channel_risk"]
        channel_factors = channel_result["factors"]

        # Calculate video risk (0-100)
        video_result = self.video_calculator.calculate_video_risk(video_data)
        video_risk = video_result["video_risk"]
        video_factors = video_result["factors"]

        # Combine: Channel 40% + Video 60%
        scan_priority = int(
            (channel_risk * self.CHANNEL_WEIGHT) +
            (video_risk * self.VIDEO_WEIGHT)
        )
        scan_priority = max(0, min(100, scan_priority))

        # Calculate priority tier
        priority_tier = self._calculate_priority_tier(scan_priority)

        logger.info(
            f"Video {video_id}: scan_priority={scan_priority}, tier={priority_tier}, "
            f"channel_risk={channel_risk}, video_risk={video_risk}"
        )

        return {
            "scan_priority": scan_priority,
            "priority_tier": priority_tier,
            "channel_risk": channel_risk,
            "video_risk": video_risk,
            "channel_factors": channel_factors,
            "video_factors": video_factors,
        }

    async def _get_channel_data(self, channel_id: str) -> dict:
        """
        Fetch channel data from Firestore.

        Args:
            channel_id: Channel ID

        Returns:
            Channel document as dict (or empty dict if not found)
        """
        try:
            channel_ref = self.firestore.collection("channels").document(channel_id)
            channel_doc = channel_ref.get()

            if channel_doc.exists:
                return channel_doc.to_dict()
            else:
                logger.warning(f"Channel {channel_id} not found in Firestore")
                return {
                    "channel_id": channel_id,
                    "infringing_videos_count": 0,
                    "total_videos_found": 0,
                    "total_infringing_views": 0,
                    "subscriber_count": 0,
                    "videos_per_month": 0,
                }
        except Exception as e:
            log_exception_json(logger, "Error fetching channel", e, severity="ERROR", channel_id=channel_id)
            return {
                "channel_id": channel_id,
                "infringing_videos_count": 0,
                "total_videos_found": 0,
                "total_infringing_views": 0,
                "subscriber_count": 0,
                "videos_per_month": 0,
            }

    def _calculate_priority_tier(self, scan_priority: int) -> str:
        """
        Calculate priority tier from scan priority score.

        Args:
            scan_priority: Scan priority score (0-100)

        Returns:
            Priority tier string
        """
        if scan_priority >= 90:
            return "CRITICAL"
        elif scan_priority >= 70:
            return "HIGH"
        elif scan_priority >= 50:
            return "MEDIUM"
        elif scan_priority >= 30:
            return "LOW"
        else:
            return "VERY_LOW"

    def batch_calculate_priority(self, video_ids: list[str]) -> dict[str, dict]:
        """
        Calculate scan priority for multiple videos efficiently.

        Args:
            video_ids: List of video IDs

        Returns:
            Dictionary mapping video_id to priority results
        """
        results = {}

        for video_id in video_ids:
            try:
                # Fetch video from Firestore
                video_ref = self.firestore.collection("videos").document(video_id)
                video_doc = video_ref.get()

                if not video_doc.exists:
                    logger.warning(f"Video {video_id} not found")
                    continue

                video_data = video_doc.to_dict()

                # Calculate priority (async call wrapped)
                import asyncio
                priority_result = asyncio.run(self.calculate_priority(video_data))
                results[video_id] = priority_result

                # Update Firestore with new priority
                video_ref.update({
                    "scan_priority": priority_result["scan_priority"],
                    "priority_tier": priority_result["priority_tier"],
                    "channel_risk": priority_result["channel_risk"],
                    "video_risk": priority_result["video_risk"],
                    "last_priority_update": firestore.SERVER_TIMESTAMP,
                })

                logger.info(
                    f"Video {video_id}: priority updated to {priority_result['scan_priority']} "
                    f"(tier={priority_result['priority_tier']})"
                )

            except Exception as e:
                log_exception_json(logger, "Error calculating priority for video", e, severity="ERROR", video_id=video_id)
                continue

        return results
