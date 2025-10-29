"""
Channel risk profile updater.

Updates channel risk scores based on Gemini analysis results.
Learns which channels are serial infringers to prioritize their content.
"""

import logging
from datetime import datetime, timezone

from google.cloud import firestore

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

        logger.info("ChannelUpdater initialized")

    def update_after_analysis(
        self,
        channel_id: str,
        video_id: str,
        contains_infringement: bool
    ) -> dict:
        """
        Update channel risk after Gemini analysis.

        Args:
            channel_id: Channel ID
            video_id: Video ID that was analyzed
            contains_infringement: Whether Gemini confirmed infringement

        Returns:
            Updated channel stats
        """
        try:
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
                    "created_at": datetime.now(timezone.utc),
                }
            else:
                channel_data = doc.to_dict()

            # Update counts
            channel_data["total_videos_analyzed"] = channel_data.get("total_videos_analyzed", 0) + 1

            if contains_infringement:
                channel_data["confirmed_infringements"] = channel_data.get("confirmed_infringements", 0) + 1
                channel_data["last_infringement_date"] = datetime.now(timezone.utc)
            else:
                channel_data["videos_cleared"] = channel_data.get("videos_cleared", 0) + 1

            # Recalculate risk score
            new_risk = self._calculate_channel_risk(channel_data)
            old_risk = channel_data.get("risk_score", 0)
            channel_data["risk_score"] = new_risk
            channel_data["updated_at"] = datetime.now(timezone.utc)

            # Save to Firestore
            doc_ref.set(channel_data, merge=True)

            logger.info(
                f"Channel {channel_id}: risk updated {old_risk}→{new_risk} "
                f"({'infringement' if contains_infringement else 'cleared'})"
            )

            return {
                "channel_id": channel_id,
                "old_risk": old_risk,
                "new_risk": new_risk,
                "infringement_rate": self._calculate_infringement_rate(channel_data),
            }

        except Exception as e:
            logger.error(f"Error updating channel {channel_id}: {e}")
            return {}

    def _calculate_channel_risk(self, channel_data: dict) -> int:
        """
        Calculate channel risk score (0-100).

        Factors:
        - Infringement rate (0-70 points): % of videos confirmed as infringing
        - Volume (0-20 points): Total number of infringements
        - Recency (0-10 points): How recent was last infringement

        Args:
            channel_data: Channel document data

        Returns:
            Risk score 0-100
        """
        risk = 0

        # Factor 1: Infringement rate (70 points max)
        infringement_rate = self._calculate_infringement_rate(channel_data)
        risk += int(infringement_rate * 70)

        # Factor 2: Volume (20 points max)
        confirmed = channel_data.get("confirmed_infringements", 0)
        if confirmed >= 10:
            risk += 20
        elif confirmed >= 5:
            risk += 15
        elif confirmed >= 3:
            risk += 10
        elif confirmed >= 1:
            risk += 5

        # Factor 3: Recency (10 points max)
        last_infringement = channel_data.get("last_infringement_date")
        if last_infringement:
            if isinstance(last_infringement, datetime):
                days_since = (datetime.now(timezone.utc) - last_infringement).days
            else:
                days_since = 999  # Firestore timestamp, assume old

            if days_since <= 7:
                risk += 10
            elif days_since <= 30:
                risk += 5

        return min(risk, 100)

    def _calculate_infringement_rate(self, channel_data: dict) -> float:
        """
        Calculate infringement rate (0.0-1.0).

        Args:
            channel_data: Channel document data

        Returns:
            Infringement rate as decimal
        """
        total = channel_data.get("total_videos_analyzed", 0)
        if total == 0:
            return 0.0

        confirmed = channel_data.get("confirmed_infringements", 0)
        return confirmed / total

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
                .where("risk_score", ">=", min_risk)
                .order_by("risk_score", direction=firestore.Query.DESCENDING)
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
