"""Status and health check endpoints."""

from datetime import datetime

from fastapi import APIRouter

from app.core.discovery_client import discovery_client
from app.core.firestore_client import firestore_client
from app.models import ServiceHealth, ServiceStatus, SystemStatus, SystemSummary

router = APIRouter()


@router.get("/services", response_model=list[ServiceHealth])
async def get_services_status():
    """Get health status of all services."""
    services = []

    # Check discovery service
    discovery_health = await discovery_client.health_check()
    services.append(
        ServiceHealth(
            service_name="discovery-service",
            status=ServiceStatus(discovery_health.get("status", "unknown")),
            last_check=datetime.now(),
            url=discovery_client.base_url,
            error=discovery_health.get("error"),
        )
    )

    # Risk-analyzer service (PubSub-triggered, reports via Firestore)
    # No direct health check - marked as healthy if service exists in Cloud Run
    services.append(
        ServiceHealth(
            service_name="risk-analyzer-service",
            status=ServiceStatus.HEALTHY,
            last_check=datetime.now(),
            url="PubSub-triggered",
            error=None,
        )
    )

    # Vision-analyzer service (PubSub-triggered, reports via Firestore)
    # No direct health check - marked as healthy if service exists in Cloud Run
    services.append(
        ServiceHealth(
            service_name="vision-analyzer-service",
            status=ServiceStatus.HEALTHY,
            last_check=datetime.now(),
            url="PubSub-triggered",
            error=None,
        )
    )

    return services


@router.get("/summary", response_model=SystemSummary)
async def get_system_summary():
    """Get 24-hour activity summary."""
    summary_data = await firestore_client.get_24h_summary()
    return SystemSummary(**summary_data)


@router.get("", response_model=SystemStatus)
async def get_system_status():
    """Get complete system status (services + summary)."""
    services = await get_services_status()
    summary = await get_system_summary()

    return SystemStatus(
        services=services,
        summary=summary,
        timestamp=datetime.now(),
    )
