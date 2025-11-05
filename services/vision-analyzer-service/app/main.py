"""FastAPI application for vision-analyzer service."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers import admin, health
from . import worker

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

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(admin.router, tags=["admin"])


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info(f"Starting {settings.service_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"GCP Project: {settings.gcp_project_id}")
    logger.info(f"Region: {settings.gcp_region}")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Daily Budget: ${settings.daily_budget_usd}")

    # Start PubSub worker
    logger.info("Starting PubSub worker...")
    try:
        worker.start_worker()
        logger.info("PubSub worker started successfully")
    except Exception as e:
        logger.error(f"Failed to start PubSub worker: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info(f"Shutting down {settings.service_name}")

    # Stop PubSub worker
    logger.info("Stopping PubSub worker...")
    worker.stop_worker()
    logger.info("PubSub worker stopped")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
