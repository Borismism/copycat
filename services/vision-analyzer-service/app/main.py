"""FastAPI application for vision-analyzer service."""

import logging

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


# Track active processing to reject new requests when at capacity
active_request_count = 0
MAX_CONCURRENT_REQUESTS = 490  # Reserve 10 slots for health checks

# Note: No SIGTERM handler needed - if instance dies, PubSub will redeliver message to another instance
# Cloud Run keeps HTTP connections alive until timeout (1 hour) or completion


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info(f"Starting {settings.service_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"GCP Project: {settings.gcp_project_id}")
    logger.info(f"Region: {settings.gcp_region}")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Daily Budget: €{settings.daily_budget_eur}")
    logger.info(f"Max Concurrent Requests: {MAX_CONCURRENT_REQUESTS}")

    # Initialize GCP clients
    logger.info("Initializing GCP clients...")
    try:
        firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database_id,
        )
        bigquery_client = bigquery.Client(project=settings.gcp_project_id)
        pubsub_publisher = pubsub_v1.PublisherClient()

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
        analyze.firestore_client = firestore_client

        # Also make available to admin router (for backward compatibility)
        import sys
        worker_module = type(sys)('worker')
        worker_module.video_analyzer = video_analyzer
        worker_module.budget_manager = budget_manager
        worker_module.config_loader = config_loader
        worker_module.settings = settings
        sys.modules['app.worker'] = worker_module

        logger.info("✅ All components initialized successfully")
        logger.info("✅ Ready to receive PubSub push messages at /analyze (synchronous processing)")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info(f"Shutting down {settings.service_name}")
    logger.info(f"Active requests at shutdown: {active_request_count}")
    logger.info("Service shutdown complete")
