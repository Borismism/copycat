"""Analytics and reporting endpoints (placeholder for future implementation)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/overview")
async def get_analytics_overview():
    """Get high-level analytics overview (future implementation)."""
    return {
        "message": "Analytics dashboard coming soon",
        "features": [
            "Discovery efficiency trends",
            "Channel risk distribution over time",
            "Top trending videos",
            "Cost projections",
        ],
    }


@router.get("/trends")
async def get_analytics_trends(days: int = 7):
    """Get historical analytics trends (future implementation)."""
    return {
        "message": f"Analytics trends for last {days} days coming soon",
        "data_source": "BigQuery metrics table",
    }
