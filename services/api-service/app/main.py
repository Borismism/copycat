"""Copycat API Gateway - Central API for managing and monitoring Copycat services."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import (
    analytics,
    channels,
    config,
    config_ai_assistant,
    config_manager,
    config_validate_characters,
    discovery,
    keyword_stats,
    status,
    users,
    videos,
    vision_budget,
)
from app.utils.logging_utils import log_exception_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for FastAPI app."""
    # Startup
    print(f"Starting API Service in {settings.environment} environment")
    print(f"Project: {settings.gcp_project_id}, Region: {settings.gcp_region}")
    yield
    # Shutdown
    print("Shutting down API Service")


app = FastAPI(
    title="Copycat API Gateway",
    description="Central API for managing and monitoring Copycat services",
    version="0.1.0",
    lifespan=lifespan,
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and responses."""
    logger.info(f"🔵 {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"✅ {request.method} {request.url.path} → {response.status_code}")
        return response
    except Exception as e:
        log_exception_json(
            logger,
            f"Middleware error on {request.method} {request.url.path}",
            e,
            severity="ERROR",
            service="api-service",
            path=str(request.url.path),
            method=request.method
        )
        raise

# Global exception handler for 500 errors with structured JSON logging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log all unhandled exceptions as structured JSON (single Cloud Run log entry)."""
    log_exception_json(
        logger,
        f"Unhandled exception on {request.method} {request.url.path}",
        exc,
        severity="ERROR",
        service="api-service",
        path=str(request.url.path),
        method=request.method
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"}
    )

# CORS middleware (allow frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(status.router, prefix="/api/status", tags=["Status"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["Discovery"])
app.include_router(channels.router, prefix="/api/channels", tags=["Channels"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(vision_budget.router, prefix="/api/vision", tags=["Vision Analyzer"])
app.include_router(config.router, prefix="/api", tags=["Configuration"])
app.include_router(config_manager.router, prefix="/api/config", tags=["Configuration Manager"])
app.include_router(config_ai_assistant.router, prefix="/api/config/ai", tags=["AI Configuration Assistant"])
app.include_router(config_validate_characters.router, tags=["AI Configuration Assistant"])
app.include_router(keyword_stats.router, prefix="/api/keywords", tags=["Keyword Statistics"])
app.include_router(users.router, prefix="/api/users", tags=["Users & Roles"])


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "api-service",
        "version": "0.1.0",
        "environment": settings.environment,
        "status": "healthy",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "api-service"}
# test
