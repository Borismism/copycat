"""Pydantic models for the discovery service."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    """Status of a discovered video."""

    DISCOVERED = "discovered"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class VideoMetadata(BaseModel):
    """YouTube video metadata."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    channel_id: str = Field(..., description="Channel ID")
    channel_title: str = Field(..., description="Channel name")
    published_at: datetime = Field(..., description="Video publish date")
    description: str = Field(default="", description="Video description")
    view_count: int = Field(default=0, description="Number of views")
    like_count: int = Field(default=0, description="Number of likes")
    comment_count: int = Field(default=0, description="Number of comments")
    duration_seconds: int = Field(default=0, description="Video duration in seconds")
    tags: list[str] = Field(default_factory=list, description="Video tags")
    category_id: str = Field(default="", description="YouTube category ID")
    thumbnail_url: str = Field(default="", description="Video thumbnail URL")
    matched_ips: list[str] = Field(
        default_factory=list, description="Names of matched IPs"
    )
    view_velocity: float = Field(
        default=0.0, description="Views per hour (trending metric)"
    )

    # Risk scoring fields (Epic 001: Two-Service Architecture)
    initial_risk: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Initial risk score assigned by discovery-service (0-100)"
    )
    current_risk: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Current risk score updated by risk-analyzer-service (0-100)"
    )
    risk_tier: str = Field(
        default="VERY_LOW",
        description="Risk tier: CRITICAL, HIGH, MEDIUM, LOW, VERY_LOW"
    )
    next_scan_at: datetime | None = Field(
        default=None,
        description="Next scheduled rescan time (managed by risk-analyzer-service)"
    )
    last_risk_update: datetime | None = Field(
        default=None,
        description="Last time risk was recalculated by risk-analyzer-service"
    )


class DiscoveryTarget(str, Enum):
    """Discovery target types."""

    SMART = "smart"  # Intelligent orchestrated discovery (all methods)
    TRENDING = "trending"  # Trending videos only
    CHANNEL_TRACKING = "channel_tracking"  # Track specific channels
    KEYWORDS = "keywords"  # Keyword-based discovery


class DiscoveryRequest(BaseModel):
    """Request to discover videos."""

    target: DiscoveryTarget = Field(..., description="Discovery target type")
    query: str | None = Field(
        default=None,
        description="Search query (for SEARCH_QUERY) or comma-separated channel IDs (for CHANNEL_TRACKING)",
    )
    max_results: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum results to fetch (default: 50 for quota efficiency)",
    )
    region_code: str = Field(
        default="US", description="Region code for trending videos"
    )


class DiscoveryResponse(BaseModel):
    """Response from discovery endpoint."""

    videos_discovered: int = Field(..., description="Number of videos discovered")
    videos_published: int = Field(
        ..., description="Number of videos published to PubSub"
    )
    target: DiscoveryTarget = Field(..., description="Discovery target used")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Discovery timestamp"
    )


class IPTargetType(str, Enum):
    """Types of intellectual property."""

    GAME = "game"
    GAME_FRANCHISE = "game_franchise"
    MOVIE = "movie"
    MOVIE_FRANCHISE = "movie_franchise"
    TV_SHOW = "tv_show"
    CHARACTER = "character"
    CHARACTER_FRANCHISE = "character_franchise"
    LOGO = "logo"
    BRAND = "brand"
    MUSIC_ARTIST = "music_artist"
    MUSIC_ALBUM = "music_album"
    OTHER = "other"


class IPPriority(str, Enum):
    """Priority levels for IP monitoring."""

    HIGH = "high"  # Check daily, high-value IPs
    MEDIUM = "medium"  # Check regularly
    LOW = "low"  # Check occasionally


class IPTarget(BaseModel):
    """Configuration for a specific IP to monitor."""

    name: str = Field(..., description="Name of the IP (e.g., 'Fortnite', 'Star Wars')")
    type: IPTargetType = Field(..., description="Type of IP")
    keywords: list[str] = Field(..., description="Keywords to search for this IP")
    description: str = Field(default="", description="Description of the IP")
    owner: str = Field(default="", description="IP owner/rights holder")
    enabled: bool = Field(
        default=True, description="Whether to actively monitor this IP"
    )
    priority: IPPriority = Field(
        default=IPPriority.MEDIUM, description="Monitoring priority level"
    )


class IPMatch(BaseModel):
    """Represents a matched IP in video content."""

    ip_name: str = Field(..., description="Name of the matched IP")
    ip_type: IPTargetType = Field(..., description="Type of IP")
    matched_keywords: list[str] = Field(
        default_factory=list, description="Keywords that matched"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Match confidence (0-1)"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", description="Service health status")
    service: str = Field(default="discovery-service", description="Service name")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Current timestamp"
    )
    version: str = Field(default="0.1.0", description="Service version")
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Status of dependencies (Firestore, PubSub, etc.)",
    )


# ============================================================================
# Channel Intelligence Models
# ============================================================================


class ChannelProfile(BaseModel):
    """
    Channel profile with smart risk scoring.

    Risk is calculated based on:
    - How many videos matched our keywords (volume = risk)
    - Confirmed infringements from Gemini (confirmed = MAX risk)
    - How active the channel is (recent uploads = higher risk)
    """

    channel_id: str = Field(..., description="YouTube channel ID")
    channel_title: str = Field(..., description="Channel name")

    # Discovery metrics
    total_videos_found: int = Field(
        default=0, description="Total videos matching our keywords"
    )
    confirmed_infringements: int = Field(
        default=0, description="Videos confirmed as infringement by Gemini"
    )
    videos_cleared: int = Field(
        default=0, description="Videos confirmed as NOT infringing (false positives cleared)"
    )
    last_infringement_date: datetime | None = Field(
        default=None, description="Date of most recent confirmed infringement"
    )

    # Risk scoring (0-100)
    risk_score: int = Field(
        default=0,
        description="Risk score: 0-100 (higher = scan more frequently)"
    )
    is_newly_discovered: bool = Field(
        default=True,
        description="True if found via keyword search but not yet scanned"
    )

    # Scan scheduling
    last_scanned_at: datetime = Field(..., description="Last channel scan")
    next_scan_at: datetime = Field(..., description="Next scheduled scan")

    # Deep scan tracking
    deep_scan_completed: bool = Field(
        default=False,
        description="True if deep keyword scan has been performed on this channel"
    )
    deep_scan_at: datetime | None = Field(
        default=None,
        description="When deep scan was last performed"
    )

    # Channel activity
    last_upload_date: datetime | None = Field(
        default=None, description="When they last uploaded"
    )
    posting_frequency_days: float = Field(
        default=7.0, description="Days between uploads (estimated)"
    )

    # Metadata
    discovered_at: datetime = Field(..., description="First discovered")

    @property
    def infringement_rate(self) -> float:
        """Calculate infringement rate (0.0 to 1.0)."""
        total_reviewed = self.confirmed_infringements + self.videos_cleared
        if total_reviewed == 0:
            return 0.0
        return self.confirmed_infringements / total_reviewed

    @property
    def tier(self) -> str:
        """Get risk tier based on risk score."""
        if self.risk_score >= 80:
            return "critical"
        elif self.risk_score >= 60:
            return "high"
        elif self.risk_score >= 40:
            return "medium"
        elif self.risk_score >= 20:
            return "low"
        else:
            return "minimal"


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


class DiscoveryStats(BaseModel):
    """Discovery operation statistics."""

    videos_discovered: int = Field(default=0, description="Total videos discovered")
    videos_with_ip_match: int = Field(
        default=0, description="Videos matching IP targets"
    )
    videos_skipped_duplicate: int = Field(
        default=0, description="Videos skipped as duplicates"
    )
    quota_used: int = Field(default=0, description="YouTube API quota units used")
    channels_tracked: int = Field(default=0, description="Channels processed")
    duration_seconds: float = Field(default=0.0, description="Operation duration")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Operation timestamp"
    )
