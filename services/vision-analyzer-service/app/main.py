"""FastAPI application for vision-analyzer service."""

import asyncio
import logging
import signal
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from google.cloud import firestore, bigquery, pubsub_v1

from .config import settings
from .routers import admin, health, analyze
from .core.video_config_calculator import VideoConfigCalculator
from .core.prompt_builder import PromptBuilder
from .core.gemini_client import GeminiClient
from .core.budget_manager import BudgetManager
from .core.result_processor import ResultProcessor
from .core.video_analyzer import VideoAnalyzer
from .core.config_loader import ConfigLoader
from .utils.logging_utils import log_exception_json

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Vision Analyzer Service",
    description="AI-powered copyright infringement detection using Gemini 2.5 Flash",
    version=settings.version,
)

# Global exception handler with structured JSON logging for Cloud Run
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log all unhandled exceptions as structured JSON (single Cloud Run log entry)."""
    log_exception_json(
        logger,
        f"Unhandled exception on {request.method} {request.url.path}",
        exc,
        severity="ERROR",
        service="vision-analyzer",
        path=str(request.url.path),
        method=request.method
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"}
    )

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (frontend can be localhost or deployed)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(admin.router, tags=["admin"])
app.include_router(analyze.router, tags=["analyze"])


async def _cleanup_stuck_videos(firestore_client: firestore.Client):
    """
    Clean up videos stuck in 'processing' state from previous instance crashes.

    This is the RESILIENT approach - check scan_history for incomplete scans
    instead of relying on timestamps, making the system idempotent.

    This handles cases where Cloud Run killed the instance (deployment, crash,
    autoscaling) before the background task could complete.
    """

    try:
        logger.info("🔧 Checking for incomplete scans from previous instance...")

        # RESILIENT APPROACH: Find ALL scan_history entries still in 'running' state
        # These were killed mid-processing when the instance was terminated
        stuck_scans = firestore_client.collection('scan_history') \
            .where('status', '==', 'running') \
            .stream()

        reset_count = 0
        stuck_scan_list = list(stuck_scans)

        if not stuck_scan_list:
            logger.info("✅ No stuck scans found")
            return

        logger.warning(f"Found {len(stuck_scan_list)} stuck scans from previous instance")

        for scan_doc in stuck_scan_list:
            scan_data = scan_doc.to_dict()
            scan_id = scan_doc.id
            video_id = scan_data.get('video_id')

            if not video_id:
                logger.warning(f"Scan {scan_id} has no video_id, skipping")
                continue

            logger.warning(
                f"🔧 Resetting stuck scan {scan_id[:8]}... for video {video_id}"
            )

            # Mark scan as failed (instance was killed mid-processing)
            try:
                scan_doc.reference.update({
                    'status': 'failed',
                    'completed_at': firestore.SERVER_TIMESTAMP,
                    'error_message': 'Instance terminated during processing (deployment/crash/autoscale)',
                    'reset_at': firestore.SERVER_TIMESTAMP,
                })
            except Exception as e:
                logger.error(f"Failed to update scan_history {scan_id}: {e}")

            # Reset video to 'discovered' so it can be reprocessed
            try:
                video_ref = firestore_client.collection(settings.firestore_videos_collection).document(video_id)
                video_doc = video_ref.get()

                if video_doc.exists:
                    video_data = video_doc.to_dict()
                    current_status = video_data.get('status')

                    # Only reset if still in 'processing' state
                    # (it might have been updated by another instance)
                    if current_status == 'processing':
                        video_ref.update({
                            'status': 'discovered',
                            'processing_started_at': None,
                            'error_message': 'Reset from incomplete scan (instance terminated)',
                            'reset_at': firestore.SERVER_TIMESTAMP,
                            'updated_at': firestore.SERVER_TIMESTAMP,
                        })
                        logger.info(f"✅ Reset video {video_id} to 'discovered'")
                        reset_count += 1
                    else:
                        logger.info(f"Video {video_id} already in '{current_status}' state, skipping reset")
                else:
                    logger.warning(f"Video {video_id} not found for scan {scan_id}")

            except Exception as e:
                logger.error(f"Failed to reset video {video_id}: {e}")

        if reset_count > 0:
            logger.warning(f"⚠️  Reset {reset_count} stuck video(s) from {len(stuck_scan_list)} incomplete scans")
        else:
            logger.info(f"✅ Processed {len(stuck_scan_list)} stuck scans (videos already processed)")

    except Exception as e:
        # Don't fail startup if cleanup fails
        log_exception_json(
            logger,
            "Failed to cleanup stuck videos (non-fatal)",
            e,
            severity="WARNING"
        )


# Track active processing to prevent premature shutdown
active_processing_count = 0
shutdown_requested = False

# Global queue for video analysis requests (populated by /analyze endpoint)
analysis_queue: asyncio.Queue = None
worker_tasks: list[asyncio.Task] = []


def signal_handler(signum, frame):
    """
    Handle SIGTERM from Cloud Run deployments.

    CRITICAL: This prevents Cloud Run from killing instances mid-processing.
    When a deployment happens, Cloud Run sends SIGTERM and waits up to
    terminationGracePeriodSeconds (default 30s) before SIGKILL.

    We block shutdown until all active processing completes.
    """
    global shutdown_requested

    signal_name = "SIGTERM" if signum == signal.SIGTERM else f"signal {signum}"
    logger.warning(f"⚠️  Received {signal_name} - graceful shutdown initiated")
    logger.warning(f"⚠️  Active processing: {active_processing_count} videos")

    if active_processing_count > 0:
        logger.warning(
            f"⚠️  Waiting for {active_processing_count} active video(s) to complete before shutdown"
        )
        shutdown_requested = True
        # Don't exit - let processing complete
        # Cloud Run will wait up to terminationGracePeriodSeconds before SIGKILL
    else:
        logger.info("✅ No active processing, exiting gracefully")
        sys.exit(0)


# Register signal handlers BEFORE startup
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


async def video_analysis_worker(
    worker_id: int,
    video_analyzer,
    firestore_client: firestore.Client,
):
    """
    Worker task that continuously processes videos from the queue.

    This enables TRUE parallel processing - multiple workers run concurrently,
    each processing different videos at the same time.
    """
    global active_processing_count, shutdown_requested

    logger.info(f"🔧 Worker {worker_id} started")

    while not shutdown_requested:
        try:
            # Wait for video from queue (with timeout to check shutdown periodically)
            try:
                job = await asyncio.wait_for(analysis_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No video available, loop back to check shutdown
                continue

            scan_message, scan_id, configs = job

            video_id = scan_message.video_id
            active_processing_count += 1

            logger.info(
                f"🎬 Worker {worker_id} processing {video_id} "
                f"(active: {active_processing_count}, queue: {analysis_queue.qsize()})"
            )

            try:
                # Import here to avoid circular dependency
                from .routers.analyze import process_video_analysis

                # Process the video (this is the actual work)
                await process_video_analysis(
                    scan_message=scan_message,
                    scan_id=scan_id,
                    configs=configs,
                    video_analyzer=video_analyzer,
                    firestore_client=firestore_client,
                )

            except Exception as e:
                log_exception_json(
                    logger,
                    f"Worker {worker_id} failed to process video {video_id}",
                    e,
                    severity="ERROR",
                    worker_id=worker_id,
                    video_id=video_id
                )

            finally:
                active_processing_count -= 1
                analysis_queue.task_done()

                logger.info(
                    f"✅ Worker {worker_id} completed {video_id} "
                    f"(active: {active_processing_count}, queue: {analysis_queue.qsize()})"
                )

        except Exception as e:
            log_exception_json(
                logger,
                f"Worker {worker_id} encountered unexpected error",
                e,
                severity="ERROR",
                worker_id=worker_id
            )
            await asyncio.sleep(1)  # Brief pause before retrying

    logger.info(f"🛑 Worker {worker_id} shutting down")


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    global analysis_queue, worker_tasks

    logger.info(f"Starting {settings.service_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"GCP Project: {settings.gcp_project_id}")
    logger.info(f"Region: {settings.gcp_region}")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Daily Budget: €{settings.daily_budget_eur}")
    logger.info(f"Worker Pool Size: {settings.worker_pool_size}")

    # Initialize GCP clients
    logger.info("Initializing GCP clients...")
    try:
        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id,
        )
        bigquery_client = bigquery.Client(project=settings.gcp_project_id)
        pubsub_publisher = pubsub_v1.PublisherClient()

        # Clean up stuck videos from previous instance crashes/kills
        await _cleanup_stuck_videos(firestore_client)

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

        # Make components available to analyze router
        analyze.video_analyzer = video_analyzer
        analyze.budget_manager = budget_manager
        analyze.config_loader = config_loader

        # Also make available to admin router (for backward compatibility)
        import sys
        worker_module = type(sys)('worker')
        worker_module.video_analyzer = video_analyzer
        worker_module.budget_manager = budget_manager
        worker_module.config_loader = config_loader
        worker_module.settings = settings
        sys.modules['app.worker'] = worker_module

        # Initialize analysis queue (unbounded - can hold all incoming messages)
        analysis_queue = asyncio.Queue()
        logger.info("✅ Analysis queue initialized")

        # Launch worker pool for parallel video processing
        logger.info(f"🚀 Launching {settings.worker_pool_size} worker tasks...")
        for worker_id in range(settings.worker_pool_size):
            task = asyncio.create_task(
                video_analysis_worker(
                    worker_id=worker_id,
                    video_analyzer=video_analyzer,
                    firestore_client=firestore_client,
                )
            )
            worker_tasks.append(task)

        logger.info("✅ All components initialized successfully")
        logger.info(f"✅ {settings.worker_pool_size} workers ready for parallel processing")
        logger.info("✅ Ready to receive PubSub push messages at /analyze")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown - mark any videos currently processing as failed."""
    logger.info(f"Shutting down {settings.service_name}")

    try:
        # Get firestore client
        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id,
        )

        # Find videos this instance was processing
        # CRITICAL: Mark them as failed so they don't stay stuck
        videos_ref = firestore_client.collection(settings.firestore_videos_collection)
        processing_videos = videos_ref.where('status', '==', 'processing').limit(10).stream()

        marked_count = 0
        for video_doc in processing_videos:
            video_id = video_doc.id
            try:
                video_doc.reference.update({
                    'status': 'failed',
                    'error_message': 'Instance shutdown during processing (Cloud Run scale-down or health check failure)',
                    'error_type': 'InstanceShutdown',
                    'failed_at': firestore.SERVER_TIMESTAMP,
                })

                # Also mark scan history as failed
                scan_histories = firestore_client.collection('scan_history') \
                    .where('video_id', '==', video_id) \
                    .where('status', '==', 'running') \
                    .stream()

                for scan_doc in scan_histories:
                    scan_doc.reference.update({
                        'status': 'failed',
                        'completed_at': firestore.SERVER_TIMESTAMP,
                        'error_message': 'Instance shutdown during scan',
                    })

                marked_count += 1
                logger.warning(f"Marked video {video_id} as failed due to shutdown")
            except Exception as e:
                logger.error(f"Failed to mark video {video_id} as failed during shutdown: {e}")

        if marked_count > 0:
            logger.info(f"Marked {marked_count} processing video(s) as failed on shutdown")

    except Exception as e:
        # Don't fail shutdown if cleanup fails
        logger.error(f"Error during shutdown cleanup: {e}")

    logger.info("Service shutdown complete")
