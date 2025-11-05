"""Pydantic models for the risk-analyzer service."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Risk tiers for scan prioritization (priority queue, no scheduling)."""

    CRITICAL = "CRITICAL"  # Highest priority (90-100 pts)
    HIGH = "HIGH"  # High priority (70-89 pts)
    MEDIUM = "MEDIUM"  # Medium priority (50-69 pts)
    LOW = "LOW"  # Low priority (30-49 pts)
    VERY_LOW = "VERY_LOW"  # Lowest priority (0-29 pts)


class VideoRiskAnalysis(BaseModel):
    """Risk analysis result for a video."""

    video_id: str = Field(..., description="YouTube video ID")
    initial_risk: int = Field(..., ge=0, le=100, description="Initial risk score")
    current_risk: int = Field(..., ge=0, le=100, description="Current risk score")
    risk_tier: RiskTier = Field(..., description="Risk tier for prioritization")
    view_velocity: float = Field(default=0.0, description="Views per hour")
    trending_score: int = Field(default=0, ge=0, le=100, description="Viral detection score")
    channel_risk: int = Field(default=0, ge=0, le=100, description="Channel reputation score")
    last_analyzed_at: datetime = Field(..., description="Last analysis timestamp")


class RiskRescoringResult(BaseModel):
    """Result of risk rescoring operation."""

    video_id: str
    old_risk: int
    new_risk: int
    old_tier: str
    new_tier: str
    factors: dict[str, int] = Field(default_factory=dict, description="Risk factor breakdown")


class ViewVelocity(BaseModel):
    """View velocity tracking for trend detection."""

    video_id: str = Field(..., description="YouTube video ID")
    current_views: int = Field(..., description="Current view count")
    previous_views: int = Field(default=0, description="Previous view count")
    views_gained: int = Field(default=0, description="Views gained since last check")
    hours_elapsed: float = Field(
        default=0.0, description="Hours since last measurement"
    )
    views_per_hour: float = Field(default=0.0, description="View velocity (views/hour)")
    trending_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Trending score (0-100)"
    )


class AnalysisStats(BaseModel):
    """Statistics for risk analysis run."""

    videos_analyzed: int = 0
    videos_upgraded: int = 0  # Risk increased
    videos_downgraded: int = 0  # Risk decreased
    videos_unchanged: int = 0
    trending_detected: int = 0
    duration_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
