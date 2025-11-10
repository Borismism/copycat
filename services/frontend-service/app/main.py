"""Frontend Service - FastAPI proxy for React SPA with IAM authentication."""
# Force rebuild for favicon

import logging
import os
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from pydantic_settings import BaseSettings
from sse_starlette.sse import EventSourceResponse
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings."""

    api_service_url: str | None = None
    environment: str = "dev"


settings = Settings()

app = FastAPI(title="Copycat Frontend")

# Global exception handler with full stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log all unhandled exceptions with full stack trace."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_api(path: str, request: Request) -> Response:
    """
    Proxy all /api/* requests to api-service with IAM authentication.

    This enables the frontend to call the backend with service account credentials,
    avoiding CORS issues and handling IAM auth transparently.

    In local development, IAM authentication is skipped.
    """
    if not settings.api_service_url:
        return Response(
            content='{"error": "API_SERVICE_URL not configured"}',
            status_code=503,
            media_type="application/json",
        )

    # Build target URL (add /api prefix back)
    url = f"{settings.api_service_url}/api/{path}"

    # Prepare headers
    headers = {
        "content-type": request.headers.get("content-type", "application/json"),
    }

    # Forward IAP headers to API service (for user authentication)
    iap_email = request.headers.get("X-Goog-Authenticated-User-Email")
    iap_jwt = request.headers.get("X-Goog-IAP-JWT-Assertion")

    if iap_email:
        headers["X-Goog-Authenticated-User-Email"] = iap_email
    if iap_jwt:
        headers["X-Goog-IAP-JWT-Assertion"] = iap_jwt

    # Forward "Act As" header for admin impersonation
    act_as = request.headers.get("X-Act-As")
    if act_as:
        headers["X-Act-As"] = act_as

    # For local dev without IAP, check for dev user header
    dev_user = request.headers.get("X-Dev-User")
    if dev_user and settings.environment == "local":
        headers["X-Dev-User"] = dev_user

    # Add IAM authentication for service-to-service auth (skip only in local development)
    if settings.environment != "local":
        try:
            # Fetch service account ID token for api-service audience
            auth_req = GoogleAuthRequest()
            token = id_token.fetch_id_token(auth_req, settings.api_service_url)
            headers["authorization"] = f"Bearer {token}"
        except Exception as e:
            return Response(
                content=f'{{"error": "Failed to fetch IAM token: {str(e)}"}}',
                status_code=500,
                media_type="application/json",
            )

    # Get request body if present
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Forward request
    try:
        # For SSE streams, use StreamingResponse (NOT EventSourceResponse - data is already formatted)
        if "stream" in path:
            from fastapi.responses import StreamingResponse
            # Keep client alive for the duration of the stream (10 minutes for cold starts)
            client = httpx.AsyncClient(timeout=600.0)

            async def event_generator():
                try:
                    async with client.stream(
                        method=request.method,
                        url=url,
                        params=request.query_params,
                        content=body,
                        headers=headers,
                    ) as response:
                        async for chunk in response.aiter_raw():
                            # Forward raw chunks with minimal buffering
                            if chunk:
                                yield chunk
                finally:
                    await client.aclose()

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Credentials": "true",
                }
            )
        else:
            # Regular request (10 minutes timeout for cold starts)
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    content=body,
                    headers=headers,
                )

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
    except Exception as e:
        return Response(
            content=f'{{"error": "Failed to proxy request: {str(e)}"}}',
            status_code=502,
            media_type="application/json",
        )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "frontend-service"}


# Serve static files (React SPA)
static_dir = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(static_dir):
    # Mount static directory for assets
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve React SPA for all non-API routes (client-side routing)."""
        # Check if the requested file exists
        file_path = os.path.join(static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Otherwise serve index.html (SPA routing)
        return FileResponse(os.path.join(static_dir, "index.html"))
else:
    @app.get("/")
    async def no_frontend() -> dict[str, str]:
        """Fallback when frontend is not built."""
        return {
            "message": "Frontend not built yet",
            "hint": "Run 'npm run build' in app/web/ to build the React SPA",
        }
