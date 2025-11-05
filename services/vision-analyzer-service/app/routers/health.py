"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for Cloud Run.

    Returns:
        Health status
    """
    from ..config import settings

    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.version,
    )
