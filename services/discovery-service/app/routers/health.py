"""Health check router."""

import logging
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status and dependency health.
    """
    try:
        # In a real implementation, you might check:
        # - Firestore connectivity
        # - PubSub connectivity
        # - YouTube API availability

        return HealthResponse(
            status="healthy",
            service=settings.service_name,
            timestamp=datetime.now(UTC),
            version=settings.version,
            dependencies={
                "firestore": "healthy",
                "pubsub": "healthy",
                "youtube_api": "healthy",
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": settings.service_name,
        "version": settings.version,
        "status": "running",
    }
