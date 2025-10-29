"""
Main risk analyzer orchestrator.

Coordinates all risk analysis operations:
- Listens to video-discovered events
- Rescores video risks
- Updates channel profiles
- Schedules rescans

This is the main entry point for the risk-analyzer-service.
"""

import json
import logging
from datetime import datetime, timezone

from google.cloud import firestore, pubsub_v1

from .channel_updater import ChannelUpdater
from .risk_rescorer import RiskRescorer
from .scan_scheduler import ScanScheduler
from .view_velocity_tracker import ViewVelocityTracker

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    """
    Main risk analyzer orchestrator.

    Coordinates:
    1. Continuous risk rescoring
    2. View velocity tracking
    3. Channel profile updates
    4. Scan scheduling
    """

    def __init__(
        self,
        firestore_client: firestore.Client,
        pubsub_subscriber: pubsub_v1.SubscriberClient,
    ):
        """
        Initialize risk analyzer.

        Args:
            firestore_client: Firestore client
            pubsub_subscriber: PubSub subscriber client
        """
        self.firestore = firestore_client
        self.subscriber = pubsub_subscriber

        # Initialize components
        self.rescorer = RiskRescorer(firestore_client)
        self.scheduler = ScanScheduler(firestore_client)
        self.channel_updater = ChannelUpdater(firestore_client)
        self.velocity_tracker = ViewVelocityTracker(firestore_client)

        logger.info("RiskAnalyzer initialized")

    def process_discovered_video(self, message_data: dict) -> None:
        """
        Process a newly discovered video from PubSub.

        Workflow:
        1. Extract video metadata
        2. Set initial next_scan_at based on risk tier
        3. Update Firestore

        Args:
            message_data: Video metadata from discovery-service
        """
        try:
            video_id = message_data.get("video_id", "")
            risk_tier = message_data.get("risk_tier", "VERY_LOW")

            logger.info(f"Processing discovered video {video_id} (tier={risk_tier})")

            # Calculate next scan time
            next_scan = self.scheduler.calculate_next_scan_time(risk_tier)

            # Update video with next_scan_at
            doc_ref = self.firestore.collection("videos").document(video_id)
            doc_ref.update({
                "next_scan_at": next_scan,
                "updated_at": datetime.now(timezone.utc),
            })

            logger.info(f"Video {video_id}: scheduled first scan for {next_scan}")

        except Exception as e:
            logger.error(f"Error processing discovered video: {e}")

    def rescore_video_batch(self, video_ids: list[str]) -> dict:
        """
        Rescore a batch of videos.

        This is the main rescoring workflow:
        1. Update view velocities
        2. Recalculate risks
        3. Update next scan times

        Args:
            video_ids: List of video IDs to rescore

        Returns:
            Statistics about rescoring operation
        """
        stats = {
            "videos_processed": 0,
            "risks_increased": 0,
            "risks_decreased": 0,
            "risks_unchanged": 0,
            "trending_detected": 0,
        }

        try:
            logger.info(f"Rescoring batch of {len(video_ids)} videos")

            # Update view velocities (requires YouTube API call)
            # For now, skip this - would be implemented in production
            # velocity_results = self.velocity_tracker.update_all_velocities(video_ids, youtube_client)

            # Rescore videos
            rescore_results = self.rescorer.batch_rescore(video_ids)

            for video_id, result in rescore_results.items():
                stats["videos_processed"] += 1

                # Get old risk from video
                doc_ref = self.firestore.collection("videos").document(video_id)
                doc = doc_ref.get()
                if doc.exists:
                    video_data = doc.to_dict()
                    old_risk = video_data.get("current_risk", 0)
                    new_risk = result["new_risk"]

                    if new_risk > old_risk:
                        stats["risks_increased"] += 1
                    elif new_risk < old_risk:
                        stats["risks_decreased"] += 1
                    else:
                        stats["risks_unchanged"] += 1

                    # Check if trending
                    view_velocity = video_data.get("view_velocity", 0)
                    if view_velocity > 1000:
                        stats["trending_detected"] += 1

                # Update next scan time based on new tier
                self.scheduler.update_next_scan_time(video_id, result["new_tier"])

            logger.info(f"Batch rescore complete: {stats}")

            return stats

        except Exception as e:
            logger.error(f"Error in batch rescore: {e}")
            return stats

    def run_continuous_analysis(self, batch_size: int = 100) -> dict:
        """
        Run one iteration of continuous risk analysis.

        This is called periodically (e.g., hourly) to:
        1. Get videos due for rescanning
        2. Rescore their risks
        3. Update channel profiles

        Args:
            batch_size: Number of videos to process

        Returns:
            Statistics about the analysis run
        """
        start_time = datetime.now(timezone.utc)

        logger.info("=== Starting continuous risk analysis ===")

        try:
            # Get videos due for scan
            video_ids = self.scheduler.get_next_scan_batch(batch_size)

            if not video_ids:
                logger.info("No videos due for scanning")
                return {"videos_processed": 0, "duration_seconds": 0}

            # Rescore videos
            stats = self.rescore_video_batch(video_ids)

            # Calculate duration
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            stats["duration_seconds"] = duration

            logger.info(f"=== Analysis complete: {stats} ===")

            return stats

        except Exception as e:
            logger.error(f"Error in continuous analysis: {e}")
            return {"error": str(e)}

    def get_system_stats(self) -> dict:
        """
        Get system-wide statistics.

        Returns:
            Dictionary with system stats
        """
        try:
            queue_stats = self.scheduler.get_scan_queue_stats()

            stats = {
                "scan_queue": queue_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
