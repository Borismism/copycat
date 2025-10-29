"""Main FastAPI application for the discovery service."""
# Force rebuild with packaging dependency

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .middleware import RequestLoggingMiddleware, setup_logging
from .routers import discover, health

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Discovery Service",
    description="YouTube video discovery service with smart targeting and quota management",
    version=settings.version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(health.router)
app.include_router(discover.router)


@app.on_event("startup")
async def startup_event() -> None:
    """Run on application startup."""
    logger.info(
        f"Starting {settings.service_name} v{settings.version}",
        extra={
            "environment": settings.environment,
            "project_id": settings.gcp_project_id,
            "region": settings.gcp_region,
        },
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Run on application shutdown."""
    logger.info(f"Shutting down {settings.service_name}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
