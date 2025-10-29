"""Tests for new channel intelligence models."""

import pytest
from datetime import datetime, timedelta, timezone

from app.models import (
    ChannelProfile,
    ViewVelocity,
    DiscoveryStats,
    VideoMetadata,
    DiscoveryTarget,
)


class TestChannelTier:
    """Tests for channel tier calculation (now a computed property)."""

    def test_channel_tier_critical(self):
        """Test critical tier (80-100 risk score)."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="test",
            channel_title="Test",
            risk_score=85,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )
        assert profile.tier == "critical"

    def test_channel_tier_high(self):
        """Test high tier (60-79 risk score)."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="test",
            channel_title="Test",
            risk_score=65,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )
        assert profile.tier == "high"

    def test_channel_tier_medium(self):
        """Test medium tier (40-59 risk score)."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="test",
            channel_title="Test",
            risk_score=50,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )
        assert profile.tier == "medium"

    def test_channel_tier_low(self):
        """Test low tier (20-39 risk score)."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="test",
            channel_title="Test",
            risk_score=30,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )
        assert profile.tier == "low"

    def test_channel_tier_minimal(self):
        """Test minimal tier (0-19 risk score)."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="test",
            channel_title="Test",
            risk_score=10,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )
        assert profile.tier == "minimal"


class TestChannelProfile:
    """Tests for ChannelProfile model."""

    def test_channel_profile_creation(self):
        """Test creating a channel profile."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_test_123",
            channel_title="AI Content Creator",
            total_videos_found=25,
            confirmed_infringements=10,
            videos_cleared=15,
            risk_score=60,
            last_scanned_at=now,
            next_scan_at=now + timedelta(days=3),
            posting_frequency_days=2.5,
            discovered_at=now - timedelta(days=30),
        )

        assert profile.channel_id == "UC_test_123"
        assert profile.tier == "high"  # 60 risk_score = high tier
        assert profile.infringement_rate == 0.40  # 10/(10+15)
        assert profile.total_videos_found == 25
        assert profile.confirmed_infringements == 10

    def test_channel_profile_defaults(self):
        """Test channel profile with default values."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_minimal",
            channel_title="Minimal Channel",
            risk_score=10,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        assert profile.total_videos_found == 0
        assert profile.confirmed_infringements == 0
        assert profile.videos_cleared == 0
        assert profile.infringement_rate == 0.0
        assert profile.posting_frequency_days == 7.0  # Default value
        assert profile.tier == "minimal"  # 10 risk_score = minimal tier

    def test_channel_profile_serialization(self):
        """Test channel profile can be serialized."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_test",
            channel_title="Test",
            risk_score=90,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        data = profile.model_dump()
        assert data["channel_id"] == "UC_test"
        assert data["risk_score"] == 90
        # Note: tier is a @property so not in model_dump()
        assert profile.tier == "critical"  # 90 risk_score = critical tier


class TestViewVelocity:
    """Tests for ViewVelocity model."""

    def test_view_velocity_creation(self):
        """Test creating a view velocity record."""
        velocity = ViewVelocity(
            video_id="test_video_123",
            current_views=50000,
            previous_views=40000,
            views_gained=10000,
            hours_elapsed=24.0,
            views_per_hour=416.67,
            trending_score=75.5,
        )

        assert velocity.video_id == "test_video_123"
        assert velocity.current_views == 50000
        assert velocity.views_gained == 10000
        assert velocity.views_per_hour == 416.67
        assert velocity.trending_score == 75.5

    def test_view_velocity_defaults(self):
        """Test view velocity with default values."""
        velocity = ViewVelocity(video_id="test_video_456", current_views=1000)

        assert velocity.previous_views == 0
        assert velocity.views_gained == 0
        assert velocity.hours_elapsed == 0.0
        assert velocity.views_per_hour == 0.0
        assert velocity.trending_score == 0.0

    def test_view_velocity_trending_score_validation(self):
        """Test trending score is between 0-100."""
        # Valid scores
        ViewVelocity(video_id="test", current_views=100, trending_score=0.0)
        ViewVelocity(video_id="test", current_views=100, trending_score=50.0)
        ViewVelocity(video_id="test", current_views=100, trending_score=100.0)

        # Invalid scores should fail validation
        with pytest.raises(ValueError):
            ViewVelocity(video_id="test", current_views=100, trending_score=101.0)

        with pytest.raises(ValueError):
            ViewVelocity(video_id="test", current_views=100, trending_score=-1.0)


class TestDiscoveryStats:
    """Tests for DiscoveryStats model."""

    def test_discovery_stats_creation(self):
        """Test creating discovery stats."""
        stats = DiscoveryStats(
            videos_discovered=100,
            videos_with_ip_match=25,
            videos_skipped_duplicate=50,
            quota_used=150,
            channels_tracked=10,
            duration_seconds=45.5,
        )

        assert stats.videos_discovered == 100
        assert stats.videos_with_ip_match == 25
        assert stats.videos_skipped_duplicate == 50
        assert stats.quota_used == 150
        assert stats.channels_tracked == 10
        assert stats.duration_seconds == 45.5

    def test_discovery_stats_defaults(self):
        """Test discovery stats with default values."""
        stats = DiscoveryStats()

        assert stats.videos_discovered == 0
        assert stats.videos_with_ip_match == 0
        assert stats.videos_skipped_duplicate == 0
        assert stats.quota_used == 0
        assert stats.channels_tracked == 0
        assert stats.duration_seconds == 0.0
        assert isinstance(stats.timestamp, datetime)

    def test_discovery_stats_serialization(self):
        """Test discovery stats can be serialized."""
        stats = DiscoveryStats(videos_discovered=50, quota_used=200)

        data = stats.model_dump()
        assert data["videos_discovered"] == 50
        assert data["quota_used"] == 200
        assert "timestamp" in data


class TestVideoMetadataUpdates:
    """Tests for VideoMetadata view_velocity field."""

    def test_video_metadata_with_view_velocity(self):
        """Test VideoMetadata includes view_velocity field."""
        metadata = VideoMetadata(
            video_id="test_123",
            title="Test Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.utcnow(),
            view_velocity=125.5,
        )

        assert metadata.view_velocity == 125.5

    def test_video_metadata_view_velocity_default(self):
        """Test view_velocity defaults to 0.0."""
        metadata = VideoMetadata(
            video_id="test_456",
            title="Test Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.utcnow(),
        )

        assert metadata.view_velocity == 0.0


class TestDiscoveryTargetUpdates:
    """Tests for updated DiscoveryTarget enum."""

    def test_discovery_target_values(self):
        """Test DiscoveryTarget enum values."""
        assert DiscoveryTarget.SMART == "smart"
        assert DiscoveryTarget.TRENDING == "trending"
        assert DiscoveryTarget.CHANNEL_TRACKING == "channel_tracking"
        assert DiscoveryTarget.KEYWORDS == "keywords"

    def test_discovery_target_count(self):
        """Test expected number of discovery targets."""
        # Should have exactly 4 values (removed GAMING, VIRAL, SEARCH_QUERY)
        assert len(DiscoveryTarget) == 4

    def test_removed_targets_not_present(self):
        """Test old discovery targets were removed."""
        target_values = [t.value for t in DiscoveryTarget]
        assert "gaming" not in target_values
        assert "viral" not in target_values
        assert "search_query" not in target_values
