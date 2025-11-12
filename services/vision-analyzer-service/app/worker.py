"""PubSub worker for processing scan-ready messages."""

import json
import logging
import threading
from concurrent.futures import TimeoutError

from google.cloud import firestore, bigquery, pubsub_v1

from .config import settings
from .models import ScanReadyMessage
from .core.video_config_calculator import VideoConfigCalculator
from .core.prompt_builder import PromptBuilder
from .core.gemini_client import GeminiClient
from .core.budget_manager import BudgetManager
from .core.result_processor import ResultProcessor
from .core.video_analyzer import VideoAnalyzer
from .core.config_loader import ConfigLoader
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)

# Configuration constants
MINIMUM_SCAN_PRIORITY = 0  # Scan everything from top to bottom until budget depleted

# Global instances (initialized in start_worker)
video_analyzer: VideoAnalyzer | None = None
budget_manager: BudgetManager | None = None
config_loader: ConfigLoader | None = None
worker_thread: threading.Thread | None = None
subscriber: pubsub_v1.SubscriberClient | None = None
subscription_path: str | None = None


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
        log_exception_json(logger, "Failed to start PubSub worker", e, severity="ERROR")
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
        log_exception_json(logger, "Error querying videos by priority", e, severity="ERROR")
        return []


def message_callback(message: pubsub_v1.subscriber.message.Message):
    """
    Process incoming scan-ready message.

    Args:
        message: PubSub message from scan-ready topic
    """
    scan_id = None  # Initialize scan_id for error handling
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

        # Initialize Firestore client (needed for all checks below)
        firestore_client = firestore.Client(project=settings.gcp_project_id)

        # Deduplication: Check if video is already being scanned
        try:
            existing_scans = (
                firestore_client.collection("scan_history")
                .where("video_id", "==", video_id)
                .where("status", "==", "running")
                .limit(1)
                .stream()
            )

            if list(existing_scans):
                logger.info(
                    f"Skipping video {video_id}: already has a running scan. "
                    "This prevents duplicate concurrent scans."
                )
                message.ack()
                return
        except Exception as e:
            logger.warning(f"Failed to check for existing scans: {e}")
            # Continue anyway - better to have duplicate scan than miss one

        # Check scan priority threshold
        if scan_priority is not None and scan_priority < MINIMUM_SCAN_PRIORITY:
            logger.info(
                f"Skipping video {video_id}: scan_priority {scan_priority} < "
                f"minimum {MINIMUM_SCAN_PRIORITY} (tier: {scan_message.priority})"
            )

            # Update video status to skipped
            try:
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

        # Create scan history entry
        import uuid
        scan_id = str(uuid.uuid4())

        scan_history = {
            "scan_id": scan_id,
            "scan_type": "video_single",
            "video_id": scan_message.video_id,
            "video_title": scan_message.metadata.title,
            "channel_id": scan_message.metadata.channel_id,
            "channel_title": scan_message.metadata.channel_title,
            "status": "running",
            "started_at": firestore.SERVER_TIMESTAMP,
            "matched_ips": scan_message.metadata.matched_ips,
        }

        try:
            firestore_client.collection("scan_history").document(scan_id).set(scan_history)
            logger.info(f"Created scan history: {scan_id} for video {scan_message.video_id}")
        except Exception as e:
            logger.warning(f"Failed to create scan history: {e}")
            # Continue anyway - not critical

        # Update video status to "processing"
        try:
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

        # If no IPs matched, scan against ALL IPs to catch potential infringements
        if not matched_ips:
            logger.info(
                f"⚠️  No matched_ips for video {scan_message.video_id}. "
                "Loading ALL IP configs for comprehensive scan."
            )
            configs = config_loader.get_all_configs()
            if configs:
                logger.info(f"✅ Loaded {len(configs)} IP configs for comprehensive scan")
            else:
                logger.error("❌ No IP configs available in system!")
                # Update scan history to failed
                try:
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": "No IP configs available in system",
                    })
                except Exception as e:
                    logger.error(f"Failed to update scan history: {e}")

                # Update video status to failed
                try:
                    doc_ref = firestore_client.collection(
                        settings.firestore_videos_collection
                    ).document(scan_message.video_id)
                    doc_ref.update({
                        "status": "failed",
                        "error_message": "No IP configs available in system",
                        "error_type": "ConfigurationError",
                        "failed_at": firestore.SERVER_TIMESTAMP,
                    })
                except Exception as e:
                    logger.error(f"Failed to update video status: {e}")

                message.ack()  # Don't retry - this is a system configuration problem
                return
        else:
            # Load specific IP configs that matched
            logger.info(f"Loading configs for matched IPs: {matched_ips}")
            configs = []
            for ip_id in matched_ips:
                config = config_loader.get_config(ip_id)
                if config:
                    configs.append(config)
                    logger.info(f"✅ Loaded config: {config.name}")
                else:
                    logger.error(f"❌ Config not found for IP: {ip_id}")

            if not configs:
                logger.error(
                    f"❌ No valid configs for video {scan_message.video_id}. "
                    f"matched_ips={matched_ips}."
                )
                # Update scan history to failed
                try:
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": f"No IP configs found for matched_ips={matched_ips}",
                    })
                except Exception as e:
                    logger.error(f"Failed to update scan history: {e}")

                # Update video status to failed
                try:
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

        # Update scan history to completed
        try:
            firestore_client.collection("scan_history").document(scan_id).update({
                "status": "completed",
                "completed_at": firestore.SERVER_TIMESTAMP,
                "result": {
                    "success": True,
                    "has_infringement": has_infringement,
                    "overall_recommendation": result.analysis.overall_recommendation,
                    "cost_usd": result.metrics.cost_usd,
                    "ip_count": len(result.analysis.ip_results),
                }
            })
            logger.info(f"Updated scan history {scan_id} to completed")
        except Exception as e:
            log_exception_json(logger, "Failed to update scan history", e, severity="ERROR")

    except ValueError as e:
        # Check if it's a PERMISSION_DENIED error (video not accessible)
        if "PERMISSION_DENIED" in str(e):
            logger.warning(
                f"Video {scan_message.video_id} not accessible (PERMISSION_DENIED), "
                f"marking as skipped: {e}"
            )

            # Update scan history to skipped
            if scan_id:
                try:
                    firestore_client = firestore.Client(project=settings.gcp_project_id)
                    firestore_client.collection("scan_history").document(scan_id).update({
                        "status": "skipped",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": "Video not accessible (private/restricted)",
                        "error_type": "PERMISSION_DENIED",
                    })
                    logger.info(f"Updated scan history {scan_id} to skipped")
                except Exception as update_error:
                    log_exception_json(logger, "Failed to update scan history for PERMISSION_DENIED video", update_error, severity="WARNING", scan_id=scan_id)

            # Update video status to skipped (not failed)
            try:
                doc_ref = firestore_client.collection(settings.firestore_videos_collection).document(
                    scan_message.video_id
                )
                doc_ref.update({
                    "status": "skipped",
                    "error_message": "Video not accessible (private/restricted)",
                    "error_type": "PERMISSION_DENIED",
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"Updated video {scan_message.video_id} status to 'skipped' (not accessible)")
            except Exception as update_error:
                logger.error(f"Failed to update video status: {update_error}")

            # Ack message - don't retry inaccessible videos
            message.ack()
            logger.info("Message acked after marking video as skipped (PERMISSION_DENIED)")
            return

        # Re-raise other ValueErrors
        raise

    except Exception as e:
        log_exception_json(logger, "Failed to process message", e, severity="ERROR")

        # Update scan history to failed (only if scan_id was created)
        if scan_id:
            try:
                firestore_client = firestore.Client(project=settings.gcp_project_id)
                firestore_client.collection("scan_history").document(scan_id).update({
                    "status": "failed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "error_message": str(e),
                })
                logger.info(f"Updated scan history {scan_id} to failed")
            except Exception as update_error:
                log_exception_json(logger, "Failed to update scan history after worker failure", update_error, severity="WARNING", scan_id=scan_id)

        # Update video status to failed with error details
        try:
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
