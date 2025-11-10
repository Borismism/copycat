"""
Channel risk profile updater.

Updates channel risk scores based on Gemini analysis results.
Learns which channels are serial infringers to prioritize their content.
"""

import logging
from datetime import datetime, UTC

from google.cloud import firestore
from .channel_risk_calculator import ChannelRiskCalculator
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)


class ChannelUpdater:
    """
    Updates channel risk profiles based on video analysis results.

    When Gemini confirms infringement, boost channel risk.
    When Gemini confirms clean, reduce channel risk.

    This creates a learning system that adapts to actual infringement patterns.
    """

    def __init__(self, firestore_client: firestore.Client):
        """
        Initialize channel updater.

        Args:
            firestore_client: Firestore client for data access
        """
        self.firestore = firestore_client
        self.channels_collection = "channels"
        self.videos_collection = "videos"
        self.risk_calculator = ChannelRiskCalculator()

        logger.info("ChannelUpdater initialized")

    def update_after_analysis(
        self,
        channel_id: str,
        video_id: str,
        contains_infringement: bool
    ) -> dict:
        """
        Update channel risk after Gemini analysis.

        IMPORTANT: For rescans, DON'T increment counters - vision-analyzer already handles this.

        Args:
            channel_id: Channel ID
            video_id: Video ID that was analyzed
            contains_infringement: Whether Gemini confirmed infringement

        Returns:
            Updated channel stats
        """
        try:
            # Check if this is a rescan by checking scan_history collection
            # (videos don't have scan_history field, it's a separate collection)
            scan_history_query = self.firestore.collection('scan_history').where(
                filter=firestore.FieldFilter('video_id', '==', video_id)
            ).limit(2).stream()

            scan_count = len(list(scan_history_query))
            is_rescan = scan_count > 1

            logger.debug(f"Processing feedback for video {video_id}: is_rescan={is_rescan}, scan_count={scan_count}")

            doc_ref = self.firestore.collection(self.channels_collection).document(channel_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.warning(f"Channel {channel_id} not found, creating profile")
                # Create basic channel profile
                channel_data = {
                    "channel_id": channel_id,
                    "total_videos_analyzed": 0,
                    "confirmed_infringements": 0,
                    "videos_cleared": 0,
                    "risk_score": 0,
                    "created_at": datetime.now(UTC),
                }
            else:
                channel_data = doc.to_dict()

            # Update counts ONLY if not a rescan
            # (vision-analyzer already handles rescan counter updates correctly)
            if not is_rescan:
                channel_data["total_videos_analyzed"] = channel_data.get("total_videos_analyzed", 0) + 1

                if contains_infringement:
                    channel_data["confirmed_infringements"] = channel_data.get("confirmed_infringements", 0) + 1
                    channel_data["last_infringement_date"] = datetime.now(UTC)
                else:
                    channel_data["videos_cleared"] = channel_data.get("videos_cleared", 0) + 1
            else:
                logger.info(f"Skipping counter increments for rescan of video {video_id}")

            # Recalculate risk score
            risk_result = self.risk_calculator.calculate_channel_risk(channel_data)
            new_risk = risk_result["channel_risk"]
            old_risk = channel_data.get("channel_risk", 0)

            # Store risk score
            channel_data["channel_risk"] = new_risk
            channel_data["channel_risk_factors"] = risk_result["factors"]
            channel_data["updated_at"] = datetime.now(UTC)

            # Save to Firestore
            doc_ref.set(channel_data, merge=True)

            logger.info(
                f"Channel {channel_id}: risk updated {old_risk}→{new_risk} "
                f"({'infringement' if contains_infringement else 'cleared'})"
            )

            # Calculate infringement rate for return stats
            total = channel_data.get("total_videos_analyzed", channel_data.get("total_videos_found", 0))
            confirmed = channel_data.get("confirmed_infringements", 0)
            infringement_rate = confirmed / total if total > 0 else 0.0

            return {
                "channel_id": channel_id,
                "old_risk": old_risk,
                "new_risk": new_risk,
                "infringement_rate": infringement_rate,
            }

        except Exception as e:
            log_exception_json(logger, "Error updating channel", e, severity="ERROR", channel_id=channel_id)
            return {}


    def batch_update_from_videos(self, video_ids: list[str]) -> dict:
        """
        Update channel risks based on analyzed videos.

        Used to batch-update channels after Gemini analysis runs.

        Args:
            video_ids: List of video IDs that were analyzed

        Returns:
            Statistics about updates
        """
        stats = {
            "channels_updated": 0,
            "infringements_found": 0,
            "videos_cleared": 0,
        }

        try:
            # Get videos with Gemini results
            for video_id in video_ids:
                doc_ref = self.firestore.collection(self.videos_collection).document(video_id)
                doc = doc_ref.get()

                if not doc.exists:
                    continue

                video_data = doc.to_dict()
                gemini_result = video_data.get("gemini_result")

                if not gemini_result:
                    continue  # Not analyzed yet

                channel_id = video_data.get("channel_id")
                if not channel_id:
                    continue

                contains_infringement = gemini_result.get("contains_infringement", False)

                # Update channel
                self.update_after_analysis(channel_id, video_id, contains_infringement)

                stats["channels_updated"] += 1
                if contains_infringement:
                    stats["infringements_found"] += 1
                else:
                    stats["videos_cleared"] += 1

            logger.info(f"Batch channel update: {stats}")

            return stats

        except Exception as e:
            logger.error(f"Error in batch channel update: {e}")
            return stats

    def get_high_risk_channels(self, min_risk: int = 70, limit: int = 100) -> list[dict]:
        """
        Get high-risk channels for monitoring.

        Args:
            min_risk: Minimum risk score
            limit: Maximum channels to return

        Returns:
            List of high-risk channel documents
        """
        try:
            query = (
                self.firestore.collection(self.channels_collection)
                .where("channel_risk", ">=", min_risk)
                .order_by("channel_risk", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )

            channels = []
            for doc in query.stream():
                channel_data = doc.to_dict()
                channel_data["channel_id"] = doc.id
                channels.append(channel_data)

            logger.info(f"Found {len(channels)} high-risk channels (risk >= {min_risk})")

            return channels

        except Exception as e:
            logger.error(f"Error getting high-risk channels: {e}")
            return []
