"""Copycat API Gateway - Central API for managing and monitoring Copycat services."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import analytics, channels, discovery, status, videos


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
