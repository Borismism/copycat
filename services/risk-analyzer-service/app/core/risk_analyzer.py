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
from .scan_priority_calculator import ScanPriorityCalculator
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
        self.channel_updater = ChannelUpdater(firestore_client)
        self.velocity_tracker = ViewVelocityTracker(firestore_client)
        self.priority_calculator = ScanPriorityCalculator(firestore_client)

        logger.info("RiskAnalyzer initialized")

    async def process_video_discovered(self, message_data: dict) -> None:
        """
        Process a newly discovered video from PubSub (async version for webhooks).

        Workflow:
        1. Extract video metadata
        2. Calculate scan priority (Channel 40% + Video 60%)
        3. Set initial next_scan_at based on priority tier
        4. Update Firestore

        Args:
            message_data: Video metadata from discovery-service
        """
        try:
            video_id = message_data.get("video_id", "")

            logger.info(f"Processing discovered video {video_id}")

            # Get video data from Firestore (discovery-service already saved it)
            doc_ref = self.firestore.collection("videos").document(video_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.error(f"Video {video_id} not found in Firestore")
                return

            video_data = doc.to_dict()

            # Calculate comprehensive scan priority
            priority_result = await self.priority_calculator.calculate_priority(video_data)

            scan_priority = priority_result["scan_priority"]
            priority_tier = priority_result["priority_tier"]
            channel_risk = priority_result["channel_risk"]
            video_risk = priority_result["video_risk"]

            logger.info(
                f"Video {video_id}: scan_priority={scan_priority}, tier={priority_tier}, "
                f"channel_risk={channel_risk}, video_risk={video_risk}"
            )

            # Update video with scan priority (no scheduling - just priority queue)
            doc_ref.update({
                "scan_priority": scan_priority,
                "priority_tier": priority_tier,
                "channel_risk": channel_risk,
                "video_risk": video_risk,
                "updated_at": datetime.now(timezone.utc),
            })

            logger.info(
                f"Video {video_id}: priority={scan_priority}, tier={priority_tier}"
            )

        except Exception as e:
            logger.error(f"Error processing discovered video: {e}", exc_info=True)

    def process_discovered_video(self, message_data: dict) -> None:
        """
        Process a newly discovered video from PubSub (sync version).

        Workflow:
        1. Extract video metadata
        2. Calculate scan priority (Channel 40% + Video 60%)
        3. Set initial next_scan_at based on priority tier
        4. Update Firestore

        Args:
            message_data: Video metadata from discovery-service
        """
        try:
            video_id = message_data.get("video_id", "")

            logger.info(f"Processing discovered video {video_id}")

            # Get video data from Firestore (discovery-service already saved it)
            doc_ref = self.firestore.collection("videos").document(video_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.error(f"Video {video_id} not found in Firestore")
                return

            video_data = doc.to_dict()

            # Calculate comprehensive scan priority
            import asyncio
            priority_result = asyncio.run(
                self.priority_calculator.calculate_priority(video_data)
            )

            scan_priority = priority_result["scan_priority"]
            priority_tier = priority_result["priority_tier"]
            channel_risk = priority_result["channel_risk"]
            video_risk = priority_result["video_risk"]

            logger.info(
                f"Video {video_id}: scan_priority={scan_priority}, tier={priority_tier}, "
                f"channel_risk={channel_risk}, video_risk={video_risk}"
            )

            # Update video with scan priority (no scheduling - just priority queue)
            doc_ref.update({
                "scan_priority": scan_priority,
                "priority_tier": priority_tier,
                "channel_risk": channel_risk,
                "video_risk": video_risk,
                "updated_at": datetime.now(timezone.utc),
            })

            logger.info(
                f"Video {video_id}: priority={scan_priority}, tier={priority_tier}"
            )

        except Exception as e:
            logger.error(f"Error processing discovered video: {e}", exc_info=True)

    async def rescore_video_batch(self, video_ids: list[str]) -> dict:
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

            # Rescore each video using scan_priority_calculator (recalculates channel_risk!)
            for video_id in video_ids:
                try:
                    # Get video data
                    doc_ref = self.firestore.collection("videos").document(video_id)
                    doc = doc_ref.get()
                    if not doc.exists:
                        continue

                    video_data = doc.to_dict()
                    old_scan_priority = video_data.get("scan_priority", 0)
                    old_channel_risk = video_data.get("channel_risk", 0)

                    # Recalculate scan priority (also recalculates channel_risk!)
                    priority_result = await self.priority_calculator.calculate_priority(video_data)

                    new_scan_priority = priority_result["scan_priority"]
                    new_channel_risk = priority_result["channel_risk"]
                    new_video_risk = priority_result["video_risk"]

                    # Update video with new scores
                    doc_ref.update({
                        "scan_priority": new_scan_priority,
                        "priority_tier": priority_result["priority_tier"],
                        "channel_risk": new_channel_risk,
                        "video_risk": new_video_risk,
                    })

                    stats["videos_processed"] += 1

                    # Track changes
                    if new_scan_priority > old_scan_priority:
                        stats["risks_increased"] += 1
                    elif new_scan_priority < old_scan_priority:
                        stats["risks_decreased"] += 1
                    else:
                        stats["risks_unchanged"] += 1

                    # Check if trending
                    view_velocity = video_data.get("view_velocity", 0)
                    if view_velocity > 1000:
                        stats["trending_detected"] += 1

                    logger.info(
                        f"Video {video_id}: priority {old_scan_priority}→{new_scan_priority}, "
                        f"channel_risk {old_channel_risk}→{new_channel_risk}"
                    )

                except Exception as e:
                    logger.error(f"Error rescoring video {video_id}: {e}")
                    continue

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
            # Get videos by priority (no scheduling)
            video_ids = []  # Not implemented - use process_video directly

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

    async def process_vision_feedback(self, message_data: dict) -> None:
        """
        Process vision analysis feedback (async version for webhooks).

        When vision analyzer finds an infringement, it updates channel data.
        This triggers recalculation of ALL pending videos from that channel.

        Args:
            message_data: Feedback from vision-analyzer-service
        """
        try:
            video_id = message_data.get("video_id", "")
            channel_id = message_data.get("channel_id", "")
            contains_infringement = message_data.get("contains_infringement", False)

            logger.info(
                f"Received vision feedback for video {video_id} from channel {channel_id}: "
                f"infringement={contains_infringement}"
            )

            # Update channel infringement counts
            self.channel_updater.update_after_analysis(
                channel_id=channel_id,
                video_id=video_id,
                contains_infringement=contains_infringement
            )

            # Always recalculate - both positive (infringement) and negative (clean) feedback matters!
            # Clean videos should LOWER channel risk over time

            # Find all pending/discovered videos from this channel
            videos_query = (
                self.firestore.collection("videos")
                .where("channel_id", "==", channel_id)
                .where("status", "in", ["discovered", "pending"])
                .limit(100)
            )

            videos = list(videos_query.stream())
            video_ids = [v.id for v in videos]

            if not video_ids:
                logger.info(f"No pending videos found for channel {channel_id}")
                return

            logger.info(
                f"Recalculating priorities for {len(video_ids)} videos from channel {channel_id}"
            )

            # Recalculate priorities for all videos from this channel
            import asyncio

            for video_doc in videos:
                video_data = video_doc.to_dict()

                # Recalculate priority with updated channel data
                priority_result = await self.priority_calculator.calculate_priority(video_data)

                scan_priority = priority_result["scan_priority"]
                priority_tier = priority_result["priority_tier"]
                channel_risk = priority_result["channel_risk"]
                video_risk = priority_result["video_risk"]

                # Update video (now higher priority based on updated channel risk)
                self.firestore.collection("videos").document(video_doc.id).update(
                    {
                        "scan_priority": scan_priority,
                        "priority_tier": priority_tier,
                        "channel_risk": channel_risk,
                        "video_risk": video_risk,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

                logger.info(
                    f"Video {video_doc.id}: priority recalculated to {priority_tier} "
                    f"(priority={scan_priority}, channel_risk={channel_risk}, infringement_feedback={contains_infringement})"
                )

            logger.info(
                f"Successfully recalculated priorities for {len(video_ids)} videos "
                f"from channel {channel_id}"
            )

        except Exception as e:
            logger.error(f"Error processing vision feedback: {e}", exc_info=True)

    def get_system_stats(self) -> dict:
        """
        Get system-wide statistics.

        Returns:
            Dictionary with system stats
        """
        try:
            queue_stats = {}  # No scheduler

            stats = {
                "scan_queue": queue_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
