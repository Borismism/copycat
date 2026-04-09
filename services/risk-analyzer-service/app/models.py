"""Pydantic models for the risk-analyzer service."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PriorityTier(str, Enum):
    """Pre-scan priority tiers (should we scan this?)."""

    SCAN_NOW = "SCAN_NOW"      # 70-100: Queue immediately
    SCAN_SOON = "SCAN_SOON"    # 40-69: Normal queue
    SCAN_LATER = "SCAN_LATER"  # 20-39: Low priority
    SKIP = "SKIP"              # 0-19: Don't scan


class RiskTier(str, Enum):
    """Post-scan risk tiers (how bad is confirmed infringement?)."""

    CRITICAL = "CRITICAL"  # 80-100: Immediate takedown
    HIGH = "HIGH"          # 60-79: Same-day action
    MEDIUM = "MEDIUM"      # 40-59: This week
    LOW = "LOW"            # 20-39: Monitor
    MINIMAL = "MINIMAL"    # 1-19: Log only
    CLEAR = "CLEAR"        # 0: No infringement
    PENDING = "PENDING"    # Not scanned yet


class VideoRiskAnalysis(BaseModel):
    """Risk analysis result for a video."""

    video_id: str = Field(..., description="YouTube video ID")

    # Pre-scan: Should we scan this?
    scan_priority: int = Field(default=0, ge=0, le=100, description="Scan priority (0-100)")
    priority_tier: str = Field(default="SKIP", description="SCAN_NOW/SCAN_SOON/SCAN_LATER/SKIP")

    # Post-scan: How bad is the infringement?
    infringement_risk: int = Field(default=0, ge=0, le=100, description="Infringement risk (0 if clean)")
    risk_tier: str = Field(default="PENDING", description="CRITICAL/HIGH/MEDIUM/LOW/MINIMAL/CLEAR/PENDING")

    # Channel context
    channel_risk: int = Field(default=0, ge=0, le=100, description="Channel risk score")

    # Metadata
    last_analyzed_at: datetime = Field(..., description="Last analysis timestamp")


class ChannelRiskAnalysis(BaseModel):
    """Risk analysis result for a channel."""

    channel_id: str = Field(..., description="YouTube channel ID")
    channel_risk: int = Field(default=0, ge=0, le=100, description="Channel risk score")

    # Stats
    confirmed_infringements: int = Field(default=0, description="Total confirmed infringements")
    total_videos_scanned: int = Field(default=0, description="Total videos analyzed")
    infringement_rate: float = Field(default=0.0, description="Infringement rate (0-1)")

    # Factors breakdown
    factors: dict[str, int] = Field(default_factory=dict, description="Risk factor breakdown")


class ViewVelocity(BaseModel):
    """View velocity tracking for trend detection."""

    video_id: str = Field(..., description="YouTube video ID")
    current_views: int = Field(..., description="Current view count")
    previous_views: int = Field(default=0, description="Previous view count")
    views_gained: int = Field(default=0, description="Views gained since last check")
    hours_elapsed: float = Field(default=0.0, description="Hours since last measurement")
    views_per_hour: float = Field(default=0.0, description="View velocity (views/hour)")
    trending_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Trending score (0-100)")


class AnalysisStats(BaseModel):
    """Statistics for risk analysis run."""

    videos_analyzed: int = 0
    infringements_found: int = 0
    clean_videos: int = 0
    priorities_recalculated: int = 0
    duration_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
