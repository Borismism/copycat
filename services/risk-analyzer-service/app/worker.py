"""
Background worker for processing PubSub messages.

Runs in a separate thread to continuously poll for video-discovered messages.
"""

import json
import logging
import threading
import time
from typing import Optional

from google.cloud import firestore, pubsub_v1
from google.api_core import retry

from .config import settings
from .core.risk_analyzer import RiskAnalyzer

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
        self.subscription_path = self.subscriber.subscription_path(
            settings.gcp_project_id,
            settings.pubsub_subscription_video_discovered,
        )

        self.analyzer = RiskAnalyzer(
            firestore_client=self.firestore_client,
            pubsub_subscriber=self.subscriber,
        )

        self.running = False
        self.thread: Optional[threading.Thread] = None

        logger.info(f"PubSubWorker initialized")
        logger.info(f"Subscription: {settings.pubsub_subscription_video_discovered}")

    def _message_callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """
        Process a single PubSub message.

        Args:
            message: PubSub message
        """
        try:
            # Decode message data
            data = json.loads(message.data.decode("utf-8"))

            video_id = data.get("video_id", "unknown")
            logger.info(f"Received message for video {video_id}")

            # Process the video
            self.analyzer.process_discovered_video(data)

            # Acknowledge the message
            message.ack()

            logger.info(f"Successfully processed video {video_id}")

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Nack the message to retry later
            message.nack()

    def start(self) -> None:
        """Start the background worker."""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True

        # Start streaming pull in a separate thread
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        logger.info("PubSubWorker started")

    def _run(self) -> None:
        """Run the subscriber in a loop."""
        while self.running:
            try:
                logger.info(f"Subscribing to {self.subscription_path}")

                # Pull messages with timeout
                streaming_pull_future = self.subscriber.subscribe(
                    self.subscription_path,
                    callback=self._message_callback,
                    flow_control=pubsub_v1.types.FlowControl(max_messages=10),
                )

                logger.info("Listening for messages...")

                # Keep the subscriber running
                while self.running:
                    time.sleep(1)

                # Cancel the streaming pull when stopping
                streaming_pull_future.cancel()
                streaming_pull_future.result(timeout=5)

            except Exception as e:
                logger.error(f"Subscriber error: {e}", exc_info=True)
                if self.running:
                    logger.info("Restarting subscriber in 5 seconds...")
                    time.sleep(5)

    def stop(self) -> None:
        """Stop the background worker."""
        if not self.running:
            logger.warning("Worker not running")
            return

        logger.info("Stopping PubSubWorker...")
        self.running = False

        if self.thread:
            self.thread.join(timeout=10)

        logger.info("PubSubWorker stopped")


# Global worker instance
_worker: Optional[PubSubWorker] = None


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


def get_worker() -> Optional[PubSubWorker]:
    """Get the global worker instance."""
    return _worker
