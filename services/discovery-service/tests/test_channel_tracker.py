"""Tests for ChannelTracker class."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.core.channel_tracker import ChannelTracker
from app.models import ChannelProfile


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    return MagicMock()


@pytest.fixture
def channel_tracker(mock_firestore):
    """ChannelTracker instance with mocked Firestore."""
    return ChannelTracker(
        firestore_client=mock_firestore, channels_collection="test_channels"
    )


class TestChannelTrackerInit:
    """Tests for ChannelTracker initialization."""

    def test_initialization_success(self, mock_firestore):
        """Test ChannelTracker initializes correctly."""
        tracker = ChannelTracker(
            firestore_client=mock_firestore, channels_collection="channels"
        )

        assert tracker.firestore == mock_firestore
        assert tracker.channels_collection == "channels"

    def test_scan_frequency_constants(self):
        """Test scan frequency constants are correct."""
        assert ChannelTracker.SCAN_FREQUENCY_HOURS["critical"] == 6
        assert ChannelTracker.SCAN_FREQUENCY_HOURS["high"] == 24
        assert ChannelTracker.SCAN_FREQUENCY_HOURS["medium"] == 72
        assert ChannelTracker.SCAN_FREQUENCY_HOURS["low"] == 168
        assert ChannelTracker.SCAN_FREQUENCY_HOURS["minimal"] == 720


class TestGetOrCreateProfile:
    """Tests for get_or_create_profile method."""

    def test_get_existing_profile(self, channel_tracker, mock_firestore):
        """Test retrieving existing channel profile."""
        now = datetime.now(timezone.utc)
        existing_data = {
            "channel_id": "UC_test_channel",
            "channel_title": "Test AI Channel",
            "total_videos_found": 20,
            "confirmed_infringements": 8,
            "videos_cleared": 12,
            "last_infringement_date": now - timedelta(days=10),
            "risk_score": 60,
            "is_newly_discovered": False,
            "last_scanned_at": now,
            "next_scan_at": now + timedelta(days=3),
            "deep_scan_completed": True,
            "deep_scan_at": now - timedelta(days=1),
            "last_upload_date": now - timedelta(days=2),
            "posting_frequency_days": 2.5,
            "discovered_at": now - timedelta(days=30),
        }

        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = existing_data
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        profile = channel_tracker.get_or_create_profile(
            "UC_test_channel", "Test AI Channel"
        )

        assert profile.channel_id == "UC_test_channel"
        assert profile.tier == "high"  # 60 risk_score = high tier
        assert profile.infringement_rate == pytest.approx(8 / 20)

    def test_create_new_profile(self, channel_tracker, mock_firestore):
        """Test creating new channel profile."""
        doc_mock = MagicMock()
        doc_mock.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        profile = channel_tracker.get_or_create_profile(
            "UC_new_channel", "New Channel"
        )

        assert profile.channel_id == "UC_new_channel"
        assert profile.channel_title == "New Channel"
        assert profile.tier == "minimal"  # Default risk_score=0 = minimal tier
        assert profile.total_videos_found == 0
        assert profile.infringement_rate == 0.0
        assert profile.is_newly_discovered is True

        # Should save to Firestore
        doc_ref = mock_firestore.collection.return_value.document.return_value
        doc_ref.set.assert_called_once()


class TestCalculateRiskScore:
    """Tests for calculate_risk_score method."""

    def test_calculate_risk_critical(self, channel_tracker):
        """Test CRITICAL risk score (80-100) for high infringement rate."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_critical",
            channel_title="High Infringer",
            total_videos_found=20,
            confirmed_infringements=15,
            videos_cleared=5,
            last_infringement_date=now - timedelta(days=5),
            risk_score=0,
            is_newly_discovered=False,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        risk = channel_tracker.calculate_risk_score(profile)
        assert risk >= 80  # Should be critical

        # Update profile with calculated risk to check tier
        profile.risk_score = risk
        assert profile.tier == "critical"

    def test_calculate_risk_high(self, channel_tracker):
        """Test HIGH risk score (60-79) for moderate infringement rate."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_high",
            channel_title="Moderate Infringer",
            total_videos_found=20,
            confirmed_infringements=10,
            videos_cleared=10,
            last_infringement_date=now - timedelta(days=10),
            risk_score=0,
            is_newly_discovered=False,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        risk = channel_tracker.calculate_risk_score(profile)
        # 50% infringement rate + 10 violations = 70 + 5 = 75 or more with recent activity
        assert 60 <= risk <= 100  # Should be high or critical

    def test_calculate_risk_medium(self, channel_tracker):
        """Test MEDIUM risk score (40-59) for low-moderate infringement rate."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_medium",
            channel_title="Low-Moderate Infringer",
            total_videos_found=20,
            confirmed_infringements=6,
            videos_cleared=14,
            last_infringement_date=now - timedelta(days=20),
            risk_score=0,
            is_newly_discovered=False,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        risk = channel_tracker.calculate_risk_score(profile)
        assert 40 <= risk < 60  # Should be medium

    def test_calculate_risk_minimal_clean_channel(self, channel_tracker):
        """Test MINIMAL risk score (0-19) for clean channels."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_clean",
            channel_title="Clean Channel",
            total_videos_found=15,
            confirmed_infringements=0,
            videos_cleared=15,
            risk_score=0,
            is_newly_discovered=False,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        risk = channel_tracker.calculate_risk_score(profile)
        assert risk < 20  # Should be minimal
        assert profile.tier == "minimal"

    def test_calculate_risk_newly_discovered(self, channel_tracker):
        """Test newly discovered channels get medium risk."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_new",
            channel_title="New Channel",
            total_videos_found=8,
            confirmed_infringements=0,
            videos_cleared=0,
            risk_score=0,
            is_newly_discovered=True,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        risk = channel_tracker.calculate_risk_score(profile)
        assert 40 <= risk <= 55  # Newly discovered = medium risk

    def test_calculate_risk_time_decay(self, channel_tracker):
        """Test time decay reduces risk for old infringements."""
        now = datetime.now(timezone.utc)
        profile = ChannelProfile(
            channel_id="UC_old",
            channel_title="Old Infringer",
            total_videos_found=20,
            confirmed_infringements=10,
            videos_cleared=10,
            last_infringement_date=now - timedelta(days=200),  # >180 days
            risk_score=0,
            is_newly_discovered=False,
            last_scanned_at=now,
            next_scan_at=now,
            discovered_at=now,
        )

        risk = channel_tracker.calculate_risk_score(profile)
        # Old infringement with 50% rate = 70 base, but 60% decay = 28
        assert risk < 40  # Should be reduced significantly


class TestCalculateNextScanTime:
    """Tests for calculate_next_scan_time method."""

    def test_next_scan_critical(self, channel_tracker):
        """Test next scan time for CRITICAL risk (80-100) - 6 hours."""
        next_scan = channel_tracker.calculate_next_scan_time(risk_score=85)
        now = datetime.now(timezone.utc)
        expected = now + timedelta(hours=6)

        # Allow 1 second tolerance for test execution time
        assert abs((next_scan - expected).total_seconds()) < 1

    def test_next_scan_high(self, channel_tracker):
        """Test next scan time for HIGH risk (60-79) - 24 hours."""
        next_scan = channel_tracker.calculate_next_scan_time(risk_score=70)
        now = datetime.now(timezone.utc)
        expected = now + timedelta(hours=24)

        assert abs((next_scan - expected).total_seconds()) < 1

    def test_next_scan_medium(self, channel_tracker):
        """Test next scan time for MEDIUM risk (40-59) - 72 hours."""
        next_scan = channel_tracker.calculate_next_scan_time(risk_score=50)
        now = datetime.now(timezone.utc)
        expected = now + timedelta(hours=72)

        assert abs((next_scan - expected).total_seconds()) < 1

    def test_next_scan_low(self, channel_tracker):
        """Test next scan time for LOW risk (20-39) - 168 hours."""
        next_scan = channel_tracker.calculate_next_scan_time(risk_score=30)
        now = datetime.now(timezone.utc)
        expected = now + timedelta(hours=168)  # 7 days

        assert abs((next_scan - expected).total_seconds()) < 1

    def test_next_scan_minimal(self, channel_tracker):
        """Test next scan time for MINIMAL risk (0-19) - 720 hours."""
        next_scan = channel_tracker.calculate_next_scan_time(risk_score=10)
        now = datetime.now(timezone.utc)
        expected = now + timedelta(hours=720)  # 30 days

        assert abs((next_scan - expected).total_seconds()) < 1


class TestUpdateAfterScan:
    """Tests for update_after_scan method."""

    def test_update_after_scan_with_videos(self, channel_tracker, mock_firestore):
        """Test updating profile after scan with videos found."""
        now = datetime.now(timezone.utc)
        latest_upload = now - timedelta(days=2)
        existing_data = {
            "channel_id": "UC_test",
            "channel_title": "Test",
            "total_videos_found": 10,
            "confirmed_infringements": 2,
            "videos_cleared": 5,
            "last_infringement_date": now - timedelta(days=10),
            "risk_score": 30,
            "is_newly_discovered": True,
            "last_scanned_at": now - timedelta(days=1),
            "next_scan_at": now - timedelta(days=1),
            "deep_scan_completed": False,
            "deep_scan_at": None,
            "last_upload_date": None,
            "posting_frequency_days": 7.0,
            "discovered_at": now - timedelta(days=30),
        }

        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = existing_data
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        profile = channel_tracker.update_after_scan(
            "UC_test", found_videos=True, latest_upload_date=latest_upload
        )

        assert profile.is_newly_discovered is False
        assert profile.last_upload_date == latest_upload

    def test_update_after_scan_no_videos(self, channel_tracker, mock_firestore):
        """Test updating profile after scan without videos found."""
        now = datetime.now(timezone.utc)
        existing_data = {
            "channel_id": "UC_test",
            "channel_title": "Test",
            "total_videos_found": 10,
            "confirmed_infringements": 2,
            "videos_cleared": 5,
            "last_infringement_date": now - timedelta(days=10),
            "risk_score": 30,
            "is_newly_discovered": True,
            "last_scanned_at": now - timedelta(days=1),
            "next_scan_at": now - timedelta(days=1),
            "deep_scan_completed": False,
            "deep_scan_at": None,
            "last_upload_date": None,
            "posting_frequency_days": 7.0,
            "discovered_at": now - timedelta(days=30),
        }

        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = existing_data
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        profile = channel_tracker.update_after_scan("UC_test", found_videos=False)

        assert profile.is_newly_discovered is False
        assert profile.last_upload_date is None

    def test_update_recalculates_risk_score(self, channel_tracker, mock_firestore):
        """Test risk score is recalculated after update."""
        now = datetime.now(timezone.utc)
        existing_data = {
            "channel_id": "UC_test",
            "channel_title": "Test",
            "total_videos_found": 20,
            "confirmed_infringements": 15,
            "videos_cleared": 5,
            "last_infringement_date": now - timedelta(days=5),
            "risk_score": 50,  # Old value
            "is_newly_discovered": False,
            "last_scanned_at": now - timedelta(days=1),
            "next_scan_at": now - timedelta(days=1),
            "deep_scan_completed": True,
            "deep_scan_at": now - timedelta(days=1),
            "last_upload_date": now - timedelta(days=2),
            "posting_frequency_days": 7.0,
            "discovered_at": now - timedelta(days=30),
        }

        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = existing_data
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        profile = channel_tracker.update_after_scan("UC_test", found_videos=True)

        # High infringement rate (75%) should result in high/critical risk
        assert profile.risk_score >= 70

    def test_update_nonexistent_channel_raises_error(
        self, channel_tracker, mock_firestore
    ):
        """Test updating nonexistent channel raises error."""
        doc_mock = MagicMock()
        doc_mock.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        with pytest.raises(ValueError, match="Channel .* does not exist"):
            channel_tracker.update_after_scan("UC_nonexistent", found_videos=True)


class TestGetChannelsDueForScan:
    """Tests for get_channels_due_for_scan method."""

    def test_get_channels_due_for_scan(self, channel_tracker, mock_firestore):
        """Test retrieving channels due for scan, sorted by risk score."""
        now = datetime.now(timezone.utc)

        # Mock 3 channels due for scan with different risk scores
        channel_data = [
            {
                "channel_id": "UC_1",
                "channel_title": "Channel 1",
                "total_videos_found": 20,
                "confirmed_infringements": 15,
                "videos_cleared": 5,
                "last_infringement_date": now - timedelta(days=5),
                "risk_score": 85,  # Critical
                "is_newly_discovered": False,
                "last_scanned_at": now - timedelta(days=2),
                "next_scan_at": now - timedelta(hours=1),
                "deep_scan_completed": True,
                "deep_scan_at": now - timedelta(days=1),
                "last_upload_date": now - timedelta(days=1),
                "posting_frequency_days": 3.0,
                "discovered_at": now - timedelta(days=30),
            },
            {
                "channel_id": "UC_2",
                "channel_title": "Channel 2",
                "total_videos_found": 15,
                "confirmed_infringements": 6,
                "videos_cleared": 9,
                "last_infringement_date": now - timedelta(days=10),
                "risk_score": 65,  # High
                "is_newly_discovered": False,
                "last_scanned_at": now - timedelta(days=4),
                "next_scan_at": now - timedelta(hours=2),
                "deep_scan_completed": True,
                "deep_scan_at": now - timedelta(days=2),
                "last_upload_date": now - timedelta(days=3),
                "posting_frequency_days": 5.0,
                "discovered_at": now - timedelta(days=20),
            },
        ]

        mock_docs = [MagicMock(to_dict=lambda d=data: d) for data in channel_data]
        mock_firestore.collection.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = mock_docs

        channels = channel_tracker.get_channels_due_for_scan(limit=10)

        assert len(channels) == 2
        # Should be sorted by risk score (highest first)
        assert channels[0].risk_score == 85
        assert channels[0].tier == "critical"
        assert channels[1].risk_score == 65
        assert channels[1].tier == "high"

    def test_get_channels_empty_result(self, channel_tracker, mock_firestore):
        """Test returns empty list when no channels due."""
        mock_firestore.collection.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = []

        channels = channel_tracker.get_channels_due_for_scan()

        assert channels == []


class TestGetStatistics:
    """Tests for get_statistics method."""

    def test_get_statistics(self, channel_tracker, mock_firestore):
        """Test calculating channel statistics."""
        now = datetime.now(timezone.utc)

        channel_data = [
            {
                "channel_id": "UC_1",
                "channel_title": "Channel 1",
                "total_videos_found": 20,
                "confirmed_infringements": 15,
                "videos_cleared": 5,
                "last_infringement_date": now - timedelta(days=5),
                "risk_score": 85,  # Critical
                "is_newly_discovered": False,
                "last_scanned_at": now,
                "next_scan_at": now,
                "deep_scan_completed": True,
                "deep_scan_at": now - timedelta(days=1),
                "last_upload_date": now - timedelta(days=1),
                "posting_frequency_days": 3.0,
                "discovered_at": now,
            },
            {
                "channel_id": "UC_2",
                "channel_title": "Channel 2",
                "total_videos_found": 10,
                "confirmed_infringements": 5,
                "videos_cleared": 5,
                "last_infringement_date": now - timedelta(days=10),
                "risk_score": 65,  # High
                "is_newly_discovered": False,
                "last_scanned_at": now,
                "next_scan_at": now,
                "deep_scan_completed": True,
                "deep_scan_at": now - timedelta(days=1),
                "last_upload_date": now - timedelta(days=2),
                "posting_frequency_days": 5.0,
                "discovered_at": now,
            },
            {
                "channel_id": "UC_3",
                "channel_title": "Channel 3",
                "total_videos_found": 15,
                "confirmed_infringements": 1,
                "videos_cleared": 14,
                "last_infringement_date": now - timedelta(days=20),
                "risk_score": 15,  # Minimal
                "is_newly_discovered": False,
                "last_scanned_at": now,
                "next_scan_at": now,
                "deep_scan_completed": False,
                "deep_scan_at": None,
                "last_upload_date": now - timedelta(days=3),
                "posting_frequency_days": 7.0,
                "discovered_at": now,
            },
        ]

        mock_docs = [MagicMock(to_dict=lambda d=data: d) for data in channel_data]
        mock_firestore.collection.return_value.stream.return_value = mock_docs

        stats = channel_tracker.get_statistics()

        assert stats["total_channels"] == 3
        assert stats["by_risk_level"]["critical"] == 1
        assert stats["by_risk_level"]["high"] == 1
        assert stats["by_risk_level"]["minimal"] == 1
        assert stats["confirmed_infringements"] == 21  # 15 + 5 + 1
        assert stats["total_videos"] == 45  # 20 + 10 + 15
        assert stats["deep_scan_completed"] == 2
        assert stats["deep_scan_pending"] == 1
        assert stats["avg_risk_score"] == pytest.approx((85 + 65 + 15) / 3)

    def test_get_statistics_empty(self, channel_tracker, mock_firestore):
        """Test statistics with no channels."""
        mock_firestore.collection.return_value.stream.return_value = []

        stats = channel_tracker.get_statistics()

        assert stats["total_channels"] == 0
        assert stats["avg_risk_score"] == 0.0
