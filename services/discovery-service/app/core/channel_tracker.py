"""Simple channel tracking - saves channel metadata to Firestore."""

import logging
from datetime import datetime, timezone

from google.cloud import firestore

logger = logging.getLogger(__name__)


class ChannelTracker:
    """Tracks YouTube channels and saves metadata to Firestore."""

    def __init__(self, firestore_client: firestore.Client):
        """
        Initialize channel tracker.

        Args:
            firestore_client: Firestore client for database operations
        """
        self.firestore = firestore_client
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
                    "last_seen_at": datetime.now(timezone.utc),
                    "video_count": Increment(1),  # Increment video count!
                })
                logger.debug(f"Updated channel: {channel_id} (video_count++)")
                return doc.to_dict()
            else:
                # Create new channel with initial count of 1
                channel_data = {
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "discovered_at": datetime.now(timezone.utc),
                    "last_seen_at": datetime.now(timezone.utc),
                    "video_count": 1,  # First video!
                }
                doc_ref.set(channel_data)
                logger.info(f"📺 Created channel: {channel_id} ({channel_title}) with 1 video")
                return channel_data

        except Exception as e:
            logger.error(f"Failed to create/update channel {channel_id}: {e}")
            raise
