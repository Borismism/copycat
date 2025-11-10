"""Main FastAPI application for the discovery service."""
# Force rebuild with packaging dependency

import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers import discover, health
from .utils.logging_utils import log_exception_json

# Setup logging with full stack traces
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
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

# Global exception handler with structured JSON logging for Cloud Run
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log all unhandled exceptions as structured JSON (single Cloud Run log entry)."""
    log_exception_json(
        logger,
        f"Unhandled exception on {request.method} {request.url.path}",
        exc,
        severity="ERROR",
        service="discovery",
        path=str(request.url.path),
        method=request.method
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"}
    )

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
# Force rebuild
