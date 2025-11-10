"""
Background worker for processing PubSub messages.

Runs in a separate thread to continuously poll for video-discovered messages.
"""

import json
import logging
import threading
import time

from google.cloud import firestore, pubsub_v1

from .config import settings
from .core.risk_analyzer import RiskAnalyzer
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)


class PubSubWorker:
    """Background worker for processing PubSub messages."""

    def __init__(self):
        """Initialize the worker."""
        self.firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id,
        )
        self.subscriber = pubsub_v1.SubscriberClient()
        self.video_discovered_subscription = self.subscriber.subscription_path(
            settings.gcp_project_id,
            settings.pubsub_subscription_video_discovered,
        )
        self.vision_feedback_subscription = self.subscriber.subscription_path(
            settings.gcp_project_id,
            settings.pubsub_subscription_vision_feedback,
        )

        self.analyzer = RiskAnalyzer(
            firestore_client=self.firestore_client,
            pubsub_subscriber=self.subscriber,
        )

        self.running = False
        self.video_thread: threading.Thread | None = None
        self.feedback_thread: threading.Thread | None = None

        logger.info("PubSubWorker initialized")
        logger.info(f"Video discovered subscription: {settings.pubsub_subscription_video_discovered}")
        logger.info(f"Vision feedback subscription: {settings.pubsub_subscription_vision_feedback}")

    def _video_discovered_callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """
        Process a video-discovered PubSub message.

        Args:
            message: PubSub message
        """
        try:
            # Decode message data
            data = json.loads(message.data.decode("utf-8"))

            video_id = data.get("video_id", "unknown")
            logger.info(f"Received video-discovered message for video {video_id}")

            # Process the video
            self.analyzer.process_discovered_video(data)

            # Acknowledge the message
            message.ack()

            logger.info(f"Successfully processed video {video_id}")

        except Exception as e:
            log_exception_json(logger, "Error processing video-discovered message", e, severity="ERROR")
            # Nack the message to retry later
            message.nack()

    def _vision_feedback_callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """
        Process a vision-feedback PubSub message.

        Args:
            message: PubSub message
        """
        try:
            # Decode message data
            data = json.loads(message.data.decode("utf-8"))

            video_id = data.get("video_id", "unknown")
            channel_id = data.get("channel_id", "unknown")
            logger.info(f"Received vision-feedback message for video {video_id} (channel {channel_id})")

            # Process the feedback
            self.analyzer.process_vision_feedback(data)

            # Acknowledge the message
            message.ack()

            logger.info(f"Successfully processed vision feedback for {video_id}")

        except Exception as e:
            log_exception_json(logger, "Error processing vision-feedback message", e, severity="ERROR")
            # Nack the message to retry later
            message.nack()

    def start(self) -> None:
        """Start the background worker."""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True

        # Start video-discovered subscriber in separate thread
        self.video_thread = threading.Thread(
            target=self._run_video_discovered, daemon=True
        )
        self.video_thread.start()

        # Start vision-feedback subscriber in separate thread
        self.feedback_thread = threading.Thread(
            target=self._run_vision_feedback, daemon=True
        )
        self.feedback_thread.start()

        logger.info("PubSubWorker started (2 subscriptions)")

    def _run_video_discovered(self) -> None:
        """Run the video-discovered subscriber in a loop."""
        while self.running:
            try:
                logger.info(f"Subscribing to {self.video_discovered_subscription}")

                # Pull messages with timeout
                streaming_pull_future = self.subscriber.subscribe(
                    self.video_discovered_subscription,
                    callback=self._video_discovered_callback,
                    flow_control=pubsub_v1.types.FlowControl(max_messages=10),
                )

                logger.info("Listening for video-discovered messages...")

                # Keep the subscriber running
                while self.running:
                    time.sleep(1)

                # Cancel the streaming pull when stopping
                streaming_pull_future.cancel()
                streaming_pull_future.result(timeout=5)

            except Exception as e:
                log_exception_json(logger, "Video-discovered subscriber error", e, severity="ERROR")
                if self.running:
                    logger.info("Restarting video-discovered subscriber in 5 seconds...")
                    time.sleep(5)

    def _run_vision_feedback(self) -> None:
        """Run the vision-feedback subscriber in a loop."""
        while self.running:
            try:
                logger.info(f"Subscribing to {self.vision_feedback_subscription}")

                # Pull messages with timeout
                streaming_pull_future = self.subscriber.subscribe(
                    self.vision_feedback_subscription,
                    callback=self._vision_feedback_callback,
                    flow_control=pubsub_v1.types.FlowControl(max_messages=10),
                )

                logger.info("Listening for vision-feedback messages...")

                # Keep the subscriber running
                while self.running:
                    time.sleep(1)

                # Cancel the streaming pull when stopping
                streaming_pull_future.cancel()
                streaming_pull_future.result(timeout=5)

            except Exception as e:
                log_exception_json(logger, "Vision-feedback subscriber error", e, severity="ERROR")
                if self.running:
                    logger.info("Restarting vision-feedback subscriber in 5 seconds...")
                    time.sleep(5)

    def stop(self) -> None:
        """Stop the background worker."""
        if not self.running:
            logger.warning("Worker not running")
            return

        logger.info("Stopping PubSubWorker...")
        self.running = False

        if self.video_thread:
            self.video_thread.join(timeout=10)

        if self.feedback_thread:
            self.feedback_thread.join(timeout=10)

        logger.info("PubSubWorker stopped")


# Global worker instance
_worker: PubSubWorker | None = None


def start_worker() -> PubSubWorker:
    """Start the global worker instance."""
    global _worker

    if _worker is None:
        _worker = PubSubWorker()

    _worker.start()
    return _worker


def stop_worker() -> None:
    """Stop the global worker instance."""
    global _worker

    if _worker:
        _worker.stop()
        _worker = None


def get_worker() -> PubSubWorker | None:
    """Get the global worker instance."""
    return _worker
