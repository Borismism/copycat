"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "service": "risk-analyzer-service",
        "version": "0.1.0",
    }


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "risk-analyzer-service",
        "description": "Continuous risk analysis and adaptive rescanning prioritization",
        "version": "0.1.0",
    }
