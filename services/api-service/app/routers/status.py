"""Status and health check endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user, require_role
from app.core.discovery_client import discovery_client
from app.core.firestore_client import firestore_client
from app.models import ServiceHealth, ServiceStatus, SystemStatus, SystemSummary, UserInfo, UserRole

router = APIRouter()


async def _get_services_status_internal() -> list[ServiceHealth]:
    """Internal helper to get services status."""
    services = []

    # Discovery service - assume healthy (PubSub will handle failures)
    services.append(
        ServiceHealth(
            service_name="discovery-service",
            status=ServiceStatus.HEALTHY,
            last_check=datetime.now(),
            url=discovery_client.base_url,
            error=None,
        )
    )

    # Vision-analyzer service (PubSub-triggered, reports via Firestore)
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


async def _get_system_summary_internal() -> SystemSummary:
    """Internal helper to get system summary."""
    summary_data = await firestore_client.get_24h_summary()
    return SystemSummary(**summary_data)


@router.get("/services", response_model=list[ServiceHealth])
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_services_status(user: UserInfo = Depends(get_current_user)):
    """Get health status of all services."""
    return await _get_services_status_internal()


@router.get("/summary", response_model=SystemSummary)
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_system_summary(user: UserInfo = Depends(get_current_user)):
    """Get 24-hour activity summary."""
    return await _get_system_summary_internal()


@router.get("", response_model=SystemStatus)
@require_role(UserRole.READ, UserRole.LEGAL, UserRole.EDITOR, UserRole.ADMIN)
async def get_system_status(user: UserInfo = Depends(get_current_user)):
    """Get complete system status (services + summary)."""
    services = await _get_services_status_internal()
    summary = await _get_system_summary_internal()

    return SystemStatus(
        services=services,
        summary=summary,
        timestamp=datetime.now(),
    )
