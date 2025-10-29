"""Video rescanning - detect trending videos by tracking view growth."""

import logging
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from ..models import VideoMetadata

logger = logging.getLogger(__name__)


class VideoRescanner:
    """
    Rescan videos to detect trending/viral content.

    Tracks view count growth over time to identify videos that are
    gaining popularity after initial discovery.
    """

    def __init__(self, firestore_client: firestore.Client):
        """Initialize video rescanner."""
        self.firestore = firestore_client
        self.videos_collection = "videos"

    def get_videos_to_rescan(
        self,
        max_age_hours: int = 72,
        max_views: int = 10_000,
        limit: int = 50,
    ) -> list[str]:
        """
        Get video IDs that should be rescanned for view growth.

        Targets recently discovered videos with low-to-medium view counts
        that might be going viral.

        Args:
            max_age_hours: Only rescan videos discovered within this time (default: 72h)
            max_views: Only rescan videos with fewer than this many views (default: 10k)
            limit: Maximum number of videos to rescan

        Returns:
            List of video IDs to rescan
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        try:
            # Query videos that are:
            # 1. Recently discovered (within max_age_hours)
            # 2. Have low-to-medium views (might be trending)
            # 3. Not yet viral (< max_views)
            #
            # Note: Firestore with TWO inequality filters can only order by one field
            # So we order by view_count (primary sort key for trending detection)
            query = (
                self.firestore.collection(self.videos_collection)
                .where("view_count", "<", max_views)
                .where("discovered_at", ">=", cutoff_time)
                .order_by("view_count", direction=firestore.Query.ASCENDING)
                .limit(limit)
            )

            video_ids = []
            for doc in query.stream():
                video_ids.append(doc.id)

            logger.info(
                f"Found {len(video_ids)} videos to rescan "
                f"(age < {max_age_hours}h, views < {max_views})"
            )

            return video_ids

        except Exception as e:
            logger.error(f"Error getting videos to rescan: {e}")
            return []

    def update_video_stats(
        self, video_id: str, new_view_count: int, new_like_count: int
    ) -> dict:
        """
        Update video statistics and calculate view velocity.

        Args:
            video_id: YouTube video ID
            new_view_count: Current view count from YouTube
            new_like_count: Current like count from YouTube

        Returns:
            Dictionary with old/new stats and velocity metrics
        """
        try:
            doc_ref = self.firestore.collection(self.videos_collection).document(
                video_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                logger.warning(f"Video {video_id} not found in database")
                return {}

            video_data = doc.to_dict()
            old_view_count = video_data.get("view_count", 0)
            old_like_count = video_data.get("like_count", 0)
            discovered_at = video_data.get("discovered_at")

            # Calculate view growth
            view_growth = new_view_count - old_view_count
            like_growth = new_like_count - old_like_count

            # Calculate time elapsed since discovery
            if isinstance(discovered_at, datetime):
                elapsed_hours = (
                    datetime.now(timezone.utc) - discovered_at
                ).total_seconds() / 3600
            else:
                elapsed_hours = 1  # Default to 1 hour if no timestamp

            # Calculate view velocity (views per hour)
            views_per_hour = view_growth / elapsed_hours if elapsed_hours > 0 else 0

            # Update document
            updates = {
                "view_count": new_view_count,
                "like_count": new_like_count,
                "view_velocity": views_per_hour,
                "last_rescanned_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            doc_ref.update(updates)

            logger.info(
                f"Rescanned {video_id}: {old_view_count:,} → {new_view_count:,} views "
                f"(+{view_growth:,}, {views_per_hour:.1f} views/hour)"
            )

            return {
                "video_id": video_id,
                "old_view_count": old_view_count,
                "new_view_count": new_view_count,
                "view_growth": view_growth,
                "views_per_hour": views_per_hour,
                "is_trending": views_per_hour > 100,  # >100 views/hour = trending
            }

        except Exception as e:
            logger.error(f"Error updating video stats for {video_id}: {e}")
            return {}

    def rescan_batch(
        self, video_ids: list[str], youtube_client
    ) -> dict[str, dict]:
        """
        Rescan a batch of videos to update their statistics.

        Args:
            video_ids: List of video IDs to rescan
            youtube_client: YouTubeClient instance

        Returns:
            Dictionary mapping video_id to rescan results
        """
        if not video_ids:
            return {}

        try:
            # Fetch current video details from YouTube
            video_details = youtube_client.get_video_details(video_ids)

            results = {}
            for video_data in video_details:
                video_id = video_data.get("id", "")
                statistics = video_data.get("statistics", {})

                new_view_count = int(statistics.get("viewCount", 0))
                new_like_count = int(statistics.get("likeCount", 0))

                result = self.update_video_stats(
                    video_id, new_view_count, new_like_count
                )
                results[video_id] = result

            trending_count = sum(1 for r in results.values() if r.get("is_trending"))

            logger.info(
                f"Rescanned {len(results)} videos, {trending_count} are trending"
            )

            return results

        except Exception as e:
            logger.error(f"Error rescanning batch: {e}")
            return {}
