"""HTTP client for communicating with discovery-service."""

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.core.config import settings


class DiscoveryClient:
    """Client for making authenticated requests to discovery-service."""

    def __init__(self):
        self.base_url = settings.discovery_service_url
        self.timeout = 600.0  # 10 minutes for discovery runs (accounts for cold starts)

    def _get_id_token(self) -> str | None:
        """
        Fetch ID token for service-to-service authentication.

        Returns None in local/dev environments (no IAM auth needed).
        """
        if not self.base_url:
            raise ValueError("DISCOVERY_SERVICE_URL not configured")

        # Skip IAM authentication in local/dev environments
        if settings.environment in ["local", "dev"]:
            return None

        auth_req = Request()
        return id_token.fetch_id_token(auth_req, self.base_url)

    async def trigger_discovery(self, max_quota: int = 1000) -> dict:
        """
        Trigger a discovery run.

        Args:
            max_quota: Maximum YouTube API quota to use

        Returns:
            Discovery statistics
        """
        if not self.base_url:
            # For local dev without discovery service
            return {
                "videos_discovered": 0,
                "videos_with_ip_match": 0,
                "videos_skipped_duplicate": 0,
                "quota_used": 0,
                "channels_tracked": 0,
                "duration_seconds": 0.0,
            }

        token = self._get_id_token()
        headers = {}
        if token:
            headers["authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/discover/run",
                params={"max_quota": max_quota},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_quota_status(self) -> dict:
        """
        Get current YouTube API quota status.

        Returns:
            Quota information
        """
        if not self.base_url:
            return {
                "daily_quota": 10000,
                "used_quota": 0,
                "remaining_quota": 10000,
                "utilization": 0.0,
            }

        token = self._get_id_token()
        headers = {}
        if token:
            headers["authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.base_url}/discover/quota",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Map discovery service response to expected format
            return {
                "daily_quota": data.get("daily_quota", 10000),
                "used_quota": data.get("used", 0),
                "remaining_quota": data.get("remaining", 10000),
                "utilization": data.get("utilization_percent", 0.0),
                "last_reset": data.get("last_reset"),
                "next_reset": data.get("next_reset"),
            }

    async def get_analytics(self) -> dict:
        """
        Get discovery performance analytics.

        Returns:
            Analytics data
        """
        if not self.base_url:
            return {
                "quota_stats": {
                    "daily_quota": 10000,
                    "used_quota": 0,
                    "remaining_quota": 10000,
                    "utilization": 0.0,
                },
                "channel_statistics": {"total_channels": 0},
            }

        token = self._get_id_token()
        headers = {}
        if token:
            headers["authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.base_url}/discover/analytics/discovery",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> dict:
        """
        Check health of discovery service.

        Returns:
            Health status
        """
        if not self.base_url:
            return {"status": "unknown", "error": "DISCOVERY_SERVICE_URL not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


discovery_client = DiscoveryClient()
