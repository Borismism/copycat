"""Simple channel tracking - saves channel metadata to Firestore."""

import logging
from datetime import datetime, UTC

from google.cloud import firestore

logger = logging.getLogger(__name__)


class ChannelTracker:
    """Tracks YouTube channels and saves metadata to Firestore."""

    def __init__(self, firestore_client: firestore.Client, youtube_client=None):
        """
        Initialize channel tracker.

        Args:
            firestore_client: Firestore client for database operations
            youtube_client: Optional YouTubeClient for fetching channel details
        """
        self.firestore = firestore_client
        self.youtube_client = youtube_client
        logger.info("ChannelTracker initialized")

    def get_or_create_profile(self, channel_id: str, channel_title: str) -> dict:
        """
        Get or create a channel profile in Firestore and increment video count.

        Args:
            channel_id: YouTube channel ID
            channel_title: Channel display name

        Returns:
            Channel profile dict
        """
        try:
            from google.cloud.firestore_v1 import Increment

            # Use channel_id as document ID
            doc_ref = self.firestore.collection("channels").document(channel_id)
            doc = doc_ref.get()

            if doc.exists:
                # Channel exists, update last_seen and increment video count
                doc_ref.update({
                    "channel_title": channel_title,  # Update title in case it changed
                    "last_seen_at": datetime.now(UTC),
                    "video_count": Increment(1),  # Increment video count!
                })
                logger.debug(f"Updated channel: {channel_id} (video_count++)")
                return doc.to_dict()
            else:
                # Create new channel with initial count of 1
                channel_data = {
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "discovered_at": datetime.now(UTC),
                    "last_seen_at": datetime.now(UTC),
                    "video_count": 1,  # First video!
                    "channel_risk": 40,  # Default risk for unknown channels (updated by risk-analyzer after scans)
                    "infringing_videos_count": 0,
                    "total_videos_found": 1,
                }

                # Try to fetch real thumbnail from YouTube API if available
                if self.youtube_client:
                    try:
                        details = self.youtube_client.get_channel_details(channel_id)
                        if details and details.get("thumbnail_high"):
                            channel_data["thumbnail_url"] = details.get("thumbnail_high")
                            channel_data["subscriber_count"] = details.get("subscriber_count", 0)
                            channel_data["video_count"] = details.get("video_count", 0)
                            logger.info(f"📺 Fetched thumbnail for {channel_id}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch channel thumbnail: {e}")
                        # Continue without thumbnail
                else:
                    logger.debug(f"No youtube_client available for channel {channel_id}")

                doc_ref.set(channel_data)
                logger.info(f"📺 Created channel: {channel_id} ({channel_title}) with 1 video")

                # Increment global channel count
                self._increment_global_stat("total_channels", 1)

                return channel_data

        except Exception as e:
            logger.error(f"Failed to create/update channel {channel_id}: {e}")
            raise

    def _increment_global_stat(self, stat_name: str, increment: int = 1):
        """
        Atomically increment global statistics counter.

        Args:
            stat_name: Name of the stat to increment
            increment: Amount to increment by
        """
        try:
            stats_ref = self.firestore.collection("system_stats").document("global")
            stats_ref.set({
                stat_name: firestore.Increment(increment),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)
        except Exception as e:
            logger.warning(f"Failed to increment global stat {stat_name}: {e}")
