"""FastAPI application for risk-analyzer service."""

import logging

from fastapi import FastAPI
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
    title="Risk Analyzer Service",
    description="Continuous risk analysis and adaptive rescanning prioritization",
    version=settings.version,
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

    # Start PubSub worker
    logger.info("Starting PubSub worker...")
    worker.start_worker()
    logger.info("PubSub worker started")


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
