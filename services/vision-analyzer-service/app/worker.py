"""PubSub worker for processing scan-ready messages."""

import json
import logging
import threading
from concurrent.futures import TimeoutError
from typing import Optional

from google.cloud import firestore, bigquery, pubsub_v1

from .config import settings
from .models import ScanReadyMessage, VideoMetadata
from .core.video_config_calculator import VideoConfigCalculator
from .core.prompt_builder import PromptBuilder
from .core.gemini_client import GeminiClient
from .core.budget_manager import BudgetManager
from .core.result_processor import ResultProcessor
from .core.video_analyzer import VideoAnalyzer
from .core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Configuration constants
MINIMUM_SCAN_PRIORITY = 0  # Scan everything from top to bottom until budget depleted

# Global instances (initialized in start_worker)
video_analyzer: Optional[VideoAnalyzer] = None
budget_manager: Optional[BudgetManager] = None
config_loader: Optional[ConfigLoader] = None
worker_thread: Optional[threading.Thread] = None
subscriber: Optional[pubsub_v1.SubscriberClient] = None
subscription_path: Optional[str] = None


def start_worker():
    """Start PubSub worker to process scan-ready messages."""
    global video_analyzer, budget_manager, config_loader, worker_thread, subscriber, subscription_path

    logger.info("Initializing PubSub worker...")

    try:
        # Initialize GCP clients
        firestore_client = firestore.Client(project=settings.gcp_project_id)
        bigquery_client = bigquery.Client(project=settings.gcp_project_id)
        pubsub_publisher = pubsub_v1.PublisherClient()
        subscriber = pubsub_v1.SubscriberClient()

        # Initialize core components
        config_calculator = VideoConfigCalculator()
        prompt_builder = PromptBuilder()
        gemini_client = GeminiClient()
        budget_manager = BudgetManager(firestore_client)
        config_loader = ConfigLoader(firestore_client)
        result_processor = ResultProcessor(
            firestore_client, bigquery_client, pubsub_publisher
        )

        # Initialize video analyzer (orchestrator)
        video_analyzer = VideoAnalyzer(
            config_calculator=config_calculator,
            prompt_builder=prompt_builder,
            gemini_client=gemini_client,
            budget_manager=budget_manager,
            result_processor=result_processor,
        )

        logger.info("✅ Initialized config loader for IP-specific analysis")

        # Subscribe to scan-ready topic
        subscription_path = subscriber.subscription_path(
            settings.gcp_project_id, settings.pubsub_scan_ready_subscription
        )

        logger.info(f"Subscribing to: {subscription_path}")

        # Start streaming pull
        streaming_pull_future = subscriber.subscribe(
            subscription_path, callback=message_callback
        )

        logger.info("PubSub worker started successfully")

        # Keep thread alive (non-blocking)
        def await_shutdown():
            try:
                streaming_pull_future.result()
            except TimeoutError:
                streaming_pull_future.cancel()
                streaming_pull_future.result()

        worker_thread = threading.Thread(target=await_shutdown, daemon=True)
        worker_thread.start()

    except Exception as e:
        logger.error(f"Failed to start PubSub worker: {e}", exc_info=True)
        raise


def stop_worker():
    """Stop PubSub worker gracefully."""
    global subscriber, subscription_path

    logger.info("Stopping PubSub worker...")

    try:
        if subscriber and subscription_path:
            subscriber.close()
            logger.info("PubSub worker stopped")

    except Exception as e:
        logger.error(f"Error stopping worker: {e}")


def get_videos_by_priority(limit: int = 100, min_priority: int = MINIMUM_SCAN_PRIORITY) -> list[dict]:
    """
    Query Firestore for ALL unscanned videos sorted by scan_priority (descending).

    Budget-exhaustion mode: Scan from highest to lowest priority until budget depleted.
    No time-based scheduling, no 7-day delays - just pure priority queue.

    Args:
        limit: Maximum number of videos to return
        min_priority: Minimum scan_priority threshold (default 0 = scan ALL)

    Returns:
        List of video documents sorted by scan_priority DESC
    """
    try:
        firestore_client = firestore.Client(project=settings.gcp_project_id)

        # Query ALL videos that haven't been scanned yet
        # Sort by scan_priority descending (highest first)
        query = (
            firestore_client.collection(settings.firestore_videos_collection)
            .where("status", "in", ["discovered"])  # Only unscanned videos
            .where("scan_priority", ">=", min_priority)
            .order_by("scan_priority", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        docs = query.stream()
        videos = [doc.to_dict() for doc in docs]

        logger.info(
            f"Found {len(videos)} unscanned videos "
            f"(top priority: {videos[0].get('scan_priority') if videos else 'N/A'})"
        )

        return videos

    except Exception as e:
        logger.error(f"Error querying videos by priority: {e}", exc_info=True)
        return []


def message_callback(message: pubsub_v1.subscriber.message.Message):
    """
    Process incoming scan-ready message.

    Args:
        message: PubSub message from scan-ready topic
    """
    try:
        # Parse message
        data = json.loads(message.data.decode("utf-8"))
        scan_message = ScanReadyMessage(**data)

        video_id = scan_message.video_id
        scan_priority = getattr(scan_message.metadata, 'scan_priority', None)

        logger.info(
            f"Received scan-ready message: video={video_id}, "
            f"priority={scan_message.priority}, scan_priority={scan_priority}"
        )

        # Check scan priority threshold
        if scan_priority is not None and scan_priority < MINIMUM_SCAN_PRIORITY:
            logger.info(
                f"Skipping video {video_id}: scan_priority {scan_priority} < "
                f"minimum {MINIMUM_SCAN_PRIORITY} (tier: {scan_message.priority})"
            )

            # Update video status to skipped
            try:
                firestore_client = firestore.Client(project=settings.gcp_project_id)
                doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                    video_id
                )
                doc_ref.update({
                    "status": "skipped_low_priority",
                    "skip_reason": f"scan_priority {scan_priority} < minimum {MINIMUM_SCAN_PRIORITY}",
                    "skipped_at": firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                logger.warning(f"Failed to update skipped video status: {e}")

            # Ack message (don't reprocess)
            message.ack()
            return

        # Update video status to "processing"
        try:
            firestore_client = firestore.Client(project=settings.gcp_project_id)
            doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                scan_message.video_id
            )
            doc_ref.update({
                "status": "processing",
                "processing_started_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Updated video {scan_message.video_id} status to 'processing'")
        except Exception as e:
            logger.warning(f"Failed to update video status to processing: {e}")
            # Continue anyway - not critical

        # Load IP configs for this video
        matched_ips = scan_message.metadata.matched_ips
        logger.info(f"Loading configs for IPs: {matched_ips}")

        configs = []
        for ip_id in matched_ips:
            config = config_loader.get_config(ip_id)
            if config:
                configs.append(config)
                logger.info(f"✅ Loaded config: {config.name}")
            else:
                logger.error(f"❌ Config not found for IP: {ip_id}")

        # No fallback - matched_ips MUST be present from discovery-service
        if not configs:
            logger.error(
                f"❌ No valid configs for video {scan_message.video_id}. "
                f"matched_ips={matched_ips}. This should never happen!"
            )
            # Update video status to failed
            try:
                firestore_client = firestore.Client(project=settings.gcp_project_id)
                doc_ref = firestore_client.collection(
                    settings.firestore_videos_collection
                ).document(scan_message.video_id)
                doc_ref.update({
                    "status": "failed",
                    "error_message": f"No IP configs found for matched_ips={matched_ips}",
                    "error_type": "ConfigurationError",
                    "failed_at": firestore.SERVER_TIMESTAMP,
                })
            except Exception as e:
                logger.error(f"Failed to update video status: {e}")

            message.ack()  # Don't retry - this is a data problem
            return

        # Process video analysis with configs
        import asyncio

        result = asyncio.run(
            video_analyzer.analyze_video(
                video_metadata=scan_message.metadata, configs=configs, queue_size=1
            )
        )

        # Ack message on success
        message.ack()

        has_infringement = any(ip.contains_infringement for ip in result.analysis.ip_results)
        logger.info(
            f"Successfully processed video {scan_message.video_id}: "
            f"infringement={has_infringement}, "
            f"action={result.analysis.overall_recommendation}"
        )

    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)

        # Update video status to failed with error details
        try:
            firestore_client = firestore.Client(project=settings.gcp_project_id)
            doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                scan_message.video_id
            )
            doc_ref.update({
                "status": "failed",
                "error_message": str(e),
                "error_type": type(e).__name__,
                "failed_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Updated video {scan_message.video_id} status to 'failed' with error: {e}")
        except Exception as update_error:
            logger.error(f"Failed to update video status to failed: {update_error}")

        # Ack message to prevent infinite retries (we marked it as failed)
        message.ack()

        logger.info("Message acked after marking video as failed")
