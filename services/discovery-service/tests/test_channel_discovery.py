"""Tests for ChannelDiscovery class."""

import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock

from app.core.channel_discovery import ChannelDiscovery
from app.models import ChannelProfile, VideoMetadata


@pytest.fixture
def mock_youtube():
    """Mock YouTubeClient."""
    return MagicMock()


@pytest.fixture
def mock_video_processor():
    """Mock VideoProcessor."""
    return MagicMock()


@pytest.fixture
def mock_channel_tracker():
    """Mock ChannelTracker."""
    return MagicMock()


@pytest.fixture
def mock_quota_manager():
    """Mock QuotaManager."""
    manager = MagicMock()
    manager.can_afford.return_value = True  # Default: always has quota
    return manager


@pytest.fixture
def channel_discovery(
    mock_youtube, mock_video_processor, mock_channel_tracker, mock_quota_manager
):
    """ChannelDiscovery instance with all mocks."""
    return ChannelDiscovery(
        youtube_client=mock_youtube,
        video_processor=mock_video_processor,
        channel_tracker=mock_channel_tracker,
        quota_manager=mock_quota_manager,
    )


@pytest.fixture
def sample_channel_profile():
    """Sample channel profile."""
    now = datetime.now(UTC)
    return ChannelProfile(
        channel_id="UC_test_123",
        channel_title="Test AI Channel",
        risk_score=65,  # High tier (60-79)
        total_videos_found=20,
        confirmed_infringements=8,
        videos_cleared=12,
        last_scanned_at=now,
        next_scan_at=now,
        discovered_at=now,
    )


@pytest.fixture
def sample_video_data():
    """Sample YouTube API video data."""
    return {
        "id": "video_123",
        "snippet": {
            "title": "Superman AI Movie",
            "channelId": "UC_test_123",
            "channelTitle": "Test AI Channel",
            "publishedAt": "2024-01-15T10:30:00Z",
            "description": "AI-generated content",
            "tags": ["Superman", "AI"],
            "categoryId": "20",
            "thumbnails": {"high": {"url": "https://example.com/thumb.jpg"}},
        },
        "statistics": {"viewCount": "50000", "likeCount": "1000"},
        "contentDetails": {"duration": "PT5M30S"},
    }


class TestChannelDiscoveryInit:
    """Tests for ChannelDiscovery initialization."""

    def test_initialization_success(
        self,
        mock_youtube,
        mock_video_processor,
        mock_channel_tracker,
        mock_quota_manager,
    ):
        """Test ChannelDiscovery initializes correctly."""
        discovery = ChannelDiscovery(
            youtube_client=mock_youtube,
            video_processor=mock_video_processor,
            channel_tracker=mock_channel_tracker,
            quota_manager=mock_quota_manager,
        )

        assert discovery.youtube == mock_youtube
        assert discovery.video_processor == mock_video_processor
        assert discovery.channel_tracker == mock_channel_tracker
        assert discovery.quota_manager == mock_quota_manager

    def test_cost_per_channel_constant(self):
        """Test COST_PER_CHANNEL is 3 units."""
        assert ChannelDiscovery.COST_PER_CHANNEL == 3


class TestDiscoverFromChannels:
    """Tests for discover_from_channels method."""

    def test_discover_from_channels_success(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        mock_video_processor,
        mock_quota_manager,
        sample_channel_profile,
        sample_video_data,
    ):
        """Test successful channel-based discovery."""
        # Mock channels due for scan
        mock_channel_tracker.get_channels_due_for_scan.return_value = [
            sample_channel_profile
        ]

        # Mock YouTube channel uploads
        mock_youtube.get_channel_uploads.return_value = [sample_video_data]

        # Mock processed videos
        processed_video = VideoMetadata(
            video_id="video_123",
            title="Superman AI Movie",
            channel_id="UC_test_123",
            channel_title="Test AI Channel",
            published_at=datetime.now(UTC),
            matched_ips=["Superman"],
        )
        mock_video_processor.process_batch.return_value = [processed_video]

        # Run discovery
        videos = channel_discovery.discover_from_channels(max_channels=10)

        # Assertions
        assert len(videos) == 1
        assert videos[0].video_id == "video_123"

        # Verify interactions
        mock_channel_tracker.get_channels_due_for_scan.assert_called_once_with(limit=10)
        mock_youtube.get_channel_uploads.assert_called_once()
        mock_video_processor.process_batch.assert_called_once()
        mock_quota_manager.record_usage.assert_called()
        mock_channel_tracker.update_after_scan.assert_called_once_with(
            "UC_test_123", True
        )

    def test_discover_no_channels_due(self, channel_discovery, mock_channel_tracker):
        """Test discovery with no channels due for scanning."""
        mock_channel_tracker.get_channels_due_for_scan.return_value = []

        videos = channel_discovery.discover_from_channels()

        assert videos == []
        mock_channel_tracker.get_channels_due_for_scan.assert_called_once()

    def test_discover_insufficient_quota(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_quota_manager,
        sample_channel_profile,
    ):
        """Test discovery stops when quota exhausted."""
        mock_channel_tracker.get_channels_due_for_scan.return_value = [
            sample_channel_profile
        ]
        mock_quota_manager.can_afford.return_value = False  # No quota

        videos = channel_discovery.discover_from_channels()

        assert videos == []

    def test_discover_multiple_channels(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        mock_video_processor,
        sample_video_data,
    ):
        """Test discovering from multiple channels."""
        now = datetime.now(UTC)

        # Mock 3 channels
        channels = [
            ChannelProfile(
                channel_id=f"UC_channel_{i}",
                channel_title=f"Channel {i}",
                risk_score=65,  # High tier
                total_videos_found=10,
                confirmed_infringements=4,
                videos_cleared=6,
                last_scanned_at=now,
                next_scan_at=now,
                discovered_at=now,
            )
            for i in range(3)
        ]

        mock_channel_tracker.get_channels_due_for_scan.return_value = channels

        # Each channel returns 1 video
        mock_youtube.get_channel_uploads.return_value = [sample_video_data]

        # Each video gets processed
        mock_video_processor.process_batch.return_value = [
            VideoMetadata(
                video_id="video_1",
                title="Test",
                channel_id="UC_test",
                channel_title="Test",
                published_at=now,
                matched_ips=["Superman"],
            )
        ]

        videos = channel_discovery.discover_from_channels(max_channels=10)

        # Should discover from all 3 channels
        assert len(videos) == 3
        assert mock_youtube.get_channel_uploads.call_count == 3

    def test_discover_channel_no_uploads(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        sample_channel_profile,
    ):
        """Test handling channel with no recent uploads."""
        mock_channel_tracker.get_channels_due_for_scan.return_value = [
            sample_channel_profile
        ]
        mock_youtube.get_channel_uploads.return_value = []  # No uploads

        videos = channel_discovery.discover_from_channels()

        assert videos == []

    def test_discover_updates_channel_with_infringement(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        mock_video_processor,
        sample_channel_profile,
        sample_video_data,
    ):
        """Test channel updated correctly when infringement found."""
        mock_channel_tracker.get_channels_due_for_scan.return_value = [
            sample_channel_profile
        ]
        mock_youtube.get_channel_uploads.return_value = [sample_video_data]

        # Mock processed video WITH infringement
        now = datetime.now(UTC)
        mock_video_processor.process_batch.return_value = [
            VideoMetadata(
                video_id="video_1",
                title="Test",
                channel_id="UC_test_123",
                channel_title="Test",
                published_at=now,
                matched_ips=["Superman"],
            )
        ]

        channel_discovery.discover_from_channels()

        # Should update with had_infringement=True
        mock_channel_tracker.update_after_scan.assert_called_once_with(
            "UC_test_123", True
        )

    def test_discover_updates_channel_without_infringement(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        mock_video_processor,
        sample_channel_profile,
        sample_video_data,
    ):
        """Test channel updated correctly when NO infringement found."""
        mock_channel_tracker.get_channels_due_for_scan.return_value = [
            sample_channel_profile
        ]
        mock_youtube.get_channel_uploads.return_value = [sample_video_data]

        # Mock NO processed videos (no IP match)
        mock_video_processor.process_batch.return_value = []

        channel_discovery.discover_from_channels()

        # Should update with had_infringement=False
        mock_channel_tracker.update_after_scan.assert_called_once_with(
            "UC_test_123", False
        )

    def test_discover_handles_channel_error(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        sample_channel_profile,
    ):
        """Test discovery continues after channel error."""
        now = datetime.now(UTC)

        # Two channels - first will error
        channels = [
            sample_channel_profile,
            ChannelProfile(
                channel_id="UC_channel_2",
                channel_title="Channel 2",
                risk_score=45,  # Medium tier
                total_videos_found=5,
                confirmed_infringements=1,
                videos_cleared=4,
                last_scanned_at=now,
                next_scan_at=now,
                discovered_at=now,
            ),
        ]

        mock_channel_tracker.get_channels_due_for_scan.return_value = channels

        # First channel errors, second succeeds
        mock_youtube.get_channel_uploads.side_effect = [
            Exception("API error"),
            [],  # Second channel returns empty
        ]

        videos = channel_discovery.discover_from_channels()

        # Should continue despite error
        assert videos == []
        assert mock_youtube.get_channel_uploads.call_count == 2

    def test_discover_respects_max_channels(
        self, channel_discovery, mock_channel_tracker
    ):
        """Test max_channels parameter is respected."""
        channel_discovery.discover_from_channels(max_channels=25)

        mock_channel_tracker.get_channels_due_for_scan.assert_called_once_with(limit=25)

    def test_discover_respects_videos_per_channel(
        self,
        channel_discovery,
        mock_channel_tracker,
        mock_youtube,
        sample_channel_profile,
    ):
        """Test videos_per_channel parameter is respected."""
        mock_channel_tracker.get_channels_due_for_scan.return_value = [
            sample_channel_profile
        ]
        mock_youtube.get_channel_uploads.return_value = []

        channel_discovery.discover_from_channels(videos_per_channel=30)

        mock_youtube.get_channel_uploads.assert_called_once_with(
            "UC_test_123", max_results=30
        )


class TestCountByTier:
    """Tests for _count_by_tier helper method."""

    def test_count_by_tier(self, channel_discovery):
        """Test counting channels by tier."""
        now = datetime.now(UTC)

        channels = [
            ChannelProfile(
                channel_id="UC_1",
                channel_title="Channel 1",
                risk_score=85,  # Critical tier (>= 80)
                total_videos_found=20,
                confirmed_infringements=15,
                videos_cleared=5,
                last_scanned_at=now,
                next_scan_at=now,
                discovered_at=now,
            ),
            ChannelProfile(
                channel_id="UC_2",
                channel_title="Channel 2",
                risk_score=65,  # High tier (60-79)
                total_videos_found=15,
                confirmed_infringements=6,
                videos_cleared=9,
                last_scanned_at=now,
                next_scan_at=now,
                discovered_at=now,
            ),
            ChannelProfile(
                channel_id="UC_3",
                channel_title="Channel 3",
                risk_score=70,  # High tier (60-79)
                total_videos_found=10,
                confirmed_infringements=3,
                videos_cleared=7,
                last_scanned_at=now,
                next_scan_at=now,
                discovered_at=now,
            ),
        ]

        counts = channel_discovery._count_by_tier(channels)

        assert counts["critical"] == 1
        assert counts["high"] == 2

    def test_count_by_tier_empty(self, channel_discovery):
        """Test counting empty channel list."""
        counts = channel_discovery._count_by_tier([])

        assert counts == {}


class TestGetEfficiencyMetrics:
    """Tests for get_efficiency_metrics method."""

    def test_get_efficiency_metrics_structure(self, channel_discovery):
        """Test efficiency metrics structure."""
        metrics = channel_discovery.get_efficiency_metrics()

        assert "cost_per_channel" in metrics
        assert "cost_per_video_estimate" in metrics
        assert "vs_search_cost" in metrics
        assert "efficiency_multiplier" in metrics
        assert "method" in metrics

    def test_get_efficiency_metrics_values(self, channel_discovery):
        """Test efficiency metrics values."""
        metrics = channel_discovery.get_efficiency_metrics()

        assert metrics["cost_per_channel"] == 3
        assert metrics["vs_search_cost"] == 100
        assert metrics["efficiency_multiplier"] == pytest.approx(33.3)
        assert metrics["method"] == "channel_tracking"
