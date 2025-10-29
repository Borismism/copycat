"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

# ============================================================================
# Enums
# ============================================================================


class VideoStatus(str, Enum):
    """Video processing status."""

    DISCOVERED = "discovered"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class ServiceStatus(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ChannelTier(str, Enum):
    """Channel risk tier based on infringement history."""

    CRITICAL = "critical"  # 80-100
    HIGH = "high"  # 60-79
    MEDIUM = "medium"  # 40-59
    LOW = "low"  # 20-39
    MINIMAL = "minimal"  # 0-19


# ============================================================================
# Video Models
# ============================================================================


class VideoMetadata(BaseModel):
    """Video metadata from Firestore."""

    video_id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: datetime
    description: str | None = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    duration_seconds: int | None = None
    tags: list[str] = Field(default_factory=list)
    category_id: str | None = None
    thumbnail_url: str | None = None
    matched_ips: list[str] = Field(default_factory=list)
    view_velocity: float | None = None
    status: VideoStatus = VideoStatus.DISCOVERED
    discovered_at: datetime
    updated_at: datetime | None = None


class VideoListResponse(BaseModel):
    """Paginated video list response."""

    videos: list[VideoMetadata]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============================================================================
# Channel Models
# ============================================================================


class ChannelProfile(BaseModel):
    """Channel tracking profile from Firestore."""

    channel_id: str
    channel_title: str
    total_videos_found: int = 0
    confirmed_infringements: int = 0
    videos_cleared: int = 0  # Videos confirmed as NOT infringing
    last_infringement_date: datetime | None = None
    infringement_rate: float = 0.0
    risk_score: int = 0  # 0-100
    tier: ChannelTier = ChannelTier.MINIMAL
    is_newly_discovered: bool = True
    last_scanned_at: datetime | None = None
    next_scan_at: datetime | None = None
    last_upload_date: datetime | None = None
    posting_frequency_days: float | None = None
    discovered_at: datetime

    @model_validator(mode="after")
    def compute_tier_and_rate(self) -> "ChannelProfile":
        """Compute tier from risk_score and infringement_rate."""
        # Compute tier from risk_score
        if self.risk_score >= 80:
            self.tier = ChannelTier.CRITICAL
        elif self.risk_score >= 60:
            self.tier = ChannelTier.HIGH
        elif self.risk_score >= 40:
            self.tier = ChannelTier.MEDIUM
        elif self.risk_score >= 20:
            self.tier = ChannelTier.LOW
        else:
            self.tier = ChannelTier.MINIMAL

        # Calculate infringement rate if not set
        total_reviewed = self.confirmed_infringements + self.videos_cleared
        if total_reviewed > 0:
            self.infringement_rate = self.confirmed_infringements / total_reviewed
        else:
            self.infringement_rate = 0.0

        return self


class ChannelListResponse(BaseModel):
    """Paginated channel list response."""

    channels: list[ChannelProfile]
    total: int
    limit: int
    offset: int
    has_more: bool


class ChannelStats(BaseModel):
    """Channel tier distribution statistics."""

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    minimal: int = 0
    total: int = 0


# ============================================================================
# Discovery Models
# ============================================================================


class DiscoveryStats(BaseModel):
    """Discovery run statistics."""

    videos_discovered: int = 0
    videos_with_ip_match: int = 0
    videos_skipped_duplicate: int = 0
    quota_used: int = 0
    channels_tracked: int = 0
    duration_seconds: float = 0.0
    timestamp: datetime


class QuotaStatus(BaseModel):
    """YouTube API quota status."""

    daily_quota: int
    used_quota: int
    remaining_quota: int
    utilization: float  # 0.0 - 1.0
    last_reset: datetime | None = None
    next_reset: datetime | None = None


class DiscoveryTriggerRequest(BaseModel):
    """Request to trigger discovery run."""

    max_quota: int = Field(default=1000, ge=100, le=10000)
    priority: str | None = None


class DiscoveryAnalytics(BaseModel):
    """Discovery performance analytics."""

    quota_stats: QuotaStatus
    discovery_stats: DiscoveryStats
    efficiency: float  # videos per quota unit
    channel_count_by_tier: ChannelStats


# ============================================================================
# System Status Models
# ============================================================================


class ServiceHealth(BaseModel):
    """Individual service health status."""

    service_name: str
    status: ServiceStatus
    last_check: datetime | None = None
    url: str | None = None
    error: str | None = None


class LastDiscoveryRun(BaseModel):
    """Last discovery run statistics."""

    timestamp: datetime
    videos_discovered: int = 0
    quota_used: int = 0
    channels_tracked: int = 0
    duration_seconds: float = 0.0
    tier_breakdown: dict = Field(default_factory=dict)


class SystemSummary(BaseModel):
    """24-hour activity summary."""

    videos_discovered: int = 0
    channels_tracked: int = 0
    quota_used: int = 0
    quota_total: int = 10000
    videos_analyzed: int = 0
    infringements_found: int = 0
    period_start: datetime
    period_end: datetime
    last_run: LastDiscoveryRun | None = None


class SystemStatus(BaseModel):
    """Complete system status."""

    services: list[ServiceHealth]
    summary: SystemSummary
    timestamp: datetime
