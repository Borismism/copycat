"""View velocity tracking for identifying viral videos."""

import logging
from datetime import datetime, timezone

from google.cloud import firestore

from ..models import ViewVelocity

logger = logging.getLogger(__name__)


class ViewVelocityTracker:
    """
    Tracks view count changes over time to identify viral videos.

    View velocity = views per hour, used to prioritize high-impact
    videos for scanning. Viral videos get scanned first.

    Trending score logic:
    - >10k views/hour = 100 (extremely viral)
    - 1k-10k views/hour = 50-99 (viral)
    - 100-1k views/hour = 10-49 (trending)
    - <100 views/hour = 0-9 (slow growth)
    """

    def __init__(
        self,
        firestore_client: firestore.Client,
        snapshots_collection: str = "view_snapshots",
    ):
        """
        Initialize view velocity tracker.

        Args:
            firestore_client: Firestore client for persistence
            snapshots_collection: Collection name for view snapshots
        """
        self.firestore = firestore_client
        self.snapshots_collection = snapshots_collection

        logger.info("ViewVelocityTracker initialized")

    def record_view_snapshot(self, video_id: str, view_count: int) -> None:
        """
        Store current view count with timestamp.

        Creates a subcollection under each video with timestamped snapshots:
        view_snapshots/{video_id}/snapshots/{timestamp}

        Args:
            video_id: YouTube video ID
            view_count: Current view count
        """
        try:
            now = datetime.now(timezone.utc)
            timestamp_key = now.strftime("%Y%m%d_%H%M%S")

            snapshot_ref = (
                self.firestore.collection(self.snapshots_collection)
                .document(video_id)
                .collection("snapshots")
                .document(timestamp_key)
            )

            snapshot_ref.set(
                {
                    "video_id": video_id,
                    "view_count": view_count,
                    "timestamp": now,
                }
            )

            logger.debug(f"Recorded view snapshot for {video_id}: {view_count} views")

        except Exception as e:
            logger.error(f"Error recording view snapshot for {video_id}: {e}")

    def calculate_velocity(self, video_id: str) -> ViewVelocity | None:
        """
        Calculate views per hour from historical snapshots.

        Compares most recent snapshot with previous snapshot to calculate
        velocity. Requires at least 2 snapshots.

        Args:
            video_id: YouTube video ID

        Returns:
            ViewVelocity object, or None if insufficient data
        """
        try:
            # Get last 2 snapshots
            snapshots_ref = (
                self.firestore.collection(self.snapshots_collection)
                .document(video_id)
                .collection("snapshots")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(2)
            )

            snapshots = list(snapshots_ref.stream())

            if len(snapshots) < 2:
                logger.debug(
                    f"Insufficient snapshots for {video_id} ({len(snapshots)}/2)"
                )
                return None

            # Parse snapshots (newest first)
            current_snap = snapshots[0].to_dict()
            previous_snap = snapshots[1].to_dict()

            current_views = current_snap["view_count"]
            previous_views = previous_snap["view_count"]
            current_time = current_snap["timestamp"]
            previous_time = previous_snap["timestamp"]

            # Calculate time elapsed
            time_delta = current_time - previous_time
            hours_elapsed = time_delta.total_seconds() / 3600.0

            if hours_elapsed == 0:
                logger.warning(
                    f"Zero hours elapsed for {video_id}, cannot calculate velocity"
                )
                return None

            # Calculate velocity
            views_gained = max(0, current_views - previous_views)
            views_per_hour = views_gained / hours_elapsed

            # Calculate trending score
            trending_score = self.get_trending_score_from_velocity(views_per_hour)

            velocity = ViewVelocity(
                video_id=video_id,
                current_views=current_views,
                previous_views=previous_views,
                views_gained=views_gained,
                hours_elapsed=hours_elapsed,
                views_per_hour=views_per_hour,
                trending_score=trending_score,
            )

            logger.info(
                f"Calculated velocity for {video_id}: "
                f"{views_per_hour:.1f} views/hr (score: {trending_score:.1f})"
            )

            return velocity

        except Exception as e:
            logger.error(f"Error calculating velocity for {video_id}: {e}")
            return None

    def get_trending_score_from_velocity(self, views_per_hour: float) -> float:
        """
        Calculate trending score (0-100) from views per hour.

        Scoring logic:
        - >10,000 views/hour = 100 (extremely viral, e.g., major release)
        - 5,000-10,000 = 90-99 (very viral)
        - 1,000-5,000 = 50-89 (viral)
        - 100-1,000 = 10-49 (trending)
        - <100 = 0-9 (slow growth)

        Args:
            views_per_hour: View velocity in views/hour

        Returns:
            Trending score between 0.0 and 100.0
        """
        if views_per_hour >= 10_000:
            return 100.0
        elif views_per_hour >= 5_000:
            # 90-99
            return 90.0 + ((views_per_hour - 5_000) / 5_000) * 9.0
        elif views_per_hour >= 1_000:
            # 50-89
            return 50.0 + ((views_per_hour - 1_000) / 4_000) * 39.0
        elif views_per_hour >= 100:
            # 10-49
            return 10.0 + ((views_per_hour - 100) / 900) * 39.0
        else:
            # 0-9
            return (views_per_hour / 100) * 9.0

    def update_all_velocities(
        self, video_ids: list[str]
    ) -> dict[str, ViewVelocity | None]:
        """
        Batch update velocities for multiple videos.

        Efficiently calculates velocity for many videos at once.
        Used for periodic velocity updates across discovered videos.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            Dictionary mapping video_id to ViewVelocity (or None if insufficient data)
        """
        results = {}

        for video_id in video_ids:
            try:
                velocity = self.calculate_velocity(video_id)
                results[video_id] = velocity
            except Exception as e:
                logger.error(f"Error updating velocity for {video_id}: {e}")
                results[video_id] = None
                continue

        successful = sum(1 for v in results.values() if v is not None)
        logger.info(f"Updated velocities for {successful}/{len(video_ids)} videos")

        return results

    def get_high_velocity_videos(
        self, min_score: float = 50.0, limit: int = 100
    ) -> list[str]:
        """
        Get video IDs with high trending scores.

        Queries recent snapshots to find videos with velocity above threshold.
        Used to prioritize viral videos for scanning.

        Args:
            min_score: Minimum trending score (default: 50.0 = viral)
            limit: Maximum videos to return

        Returns:
            List of video IDs sorted by trending score (highest first)

        Note:
            This is a simplified implementation. In production, you'd want
            to maintain a separate collection with computed velocities
            for efficient querying.
        """
        try:
            # Get all video snapshots (this is simplified - in production,
            # maintain a separate velocities collection for efficient queries)
            videos_ref = self.firestore.collection(self.snapshots_collection).limit(
                limit * 2
            )

            video_docs = videos_ref.stream()

            # Calculate velocities and filter
            high_velocity = []
            for video_doc in video_docs:
                video_id = video_doc.id
                velocity = self.calculate_velocity(video_id)

                if velocity and velocity.trending_score >= min_score:
                    high_velocity.append((video_id, velocity.trending_score))

            # Sort by score (highest first)
            high_velocity.sort(key=lambda x: x[1], reverse=True)

            # Extract video IDs
            video_ids = [vid for vid, _ in high_velocity[:limit]]

            logger.info(f"Found {len(video_ids)} videos with score >= {min_score}")
            return video_ids

        except Exception as e:
            logger.error(f"Error getting high velocity videos: {e}")
            return []

    def get_statistics(self) -> dict:
        """
        Get view velocity tracking statistics.

        Returns:
            Dictionary with velocity tracking metrics
        """
        try:
            # Count total videos being tracked
            videos_ref = self.firestore.collection(self.snapshots_collection)
            video_docs = list(videos_ref.stream())

            total_videos = len(video_docs)
            videos_with_velocity = 0
            avg_velocity = 0.0
            max_velocity = 0.0

            for video_doc in video_docs:
                velocity = self.calculate_velocity(video_doc.id)
                if velocity:
                    videos_with_velocity += 1
                    avg_velocity += velocity.views_per_hour
                    max_velocity = max(max_velocity, velocity.views_per_hour)

            if videos_with_velocity > 0:
                avg_velocity = avg_velocity / videos_with_velocity

            return {
                "total_videos_tracked": total_videos,
                "videos_with_velocity": videos_with_velocity,
                "avg_velocity": avg_velocity,
                "max_velocity": max_velocity,
            }

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {
                "total_videos_tracked": 0,
                "videos_with_velocity": 0,
                "avg_velocity": 0.0,
                "max_velocity": 0.0,
                "error": str(e),
            }
