"""Tests for ViewVelocityTracker class."""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock

from app.core.view_velocity_tracker import ViewVelocityTracker


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    return MagicMock()


@pytest.fixture
def velocity_tracker(mock_firestore):
    """ViewVelocityTracker instance with mocked Firestore."""
    return ViewVelocityTracker(
        firestore_client=mock_firestore, snapshots_collection="test_snapshots"
    )


class TestViewVelocityTrackerInit:
    """Tests for ViewVelocityTracker initialization."""

    def test_initialization_success(self, mock_firestore):
        """Test ViewVelocityTracker initializes correctly."""
        tracker = ViewVelocityTracker(
            firestore_client=mock_firestore, snapshots_collection="snapshots"
        )

        assert tracker.firestore == mock_firestore
        assert tracker.snapshots_collection == "snapshots"


class TestRecordViewSnapshot:
    """Tests for record_view_snapshot method."""

    def test_record_snapshot_success(self, velocity_tracker, mock_firestore):
        """Test recording view snapshot."""
        velocity_tracker.record_view_snapshot("test_video_123", 50000)

        # Should call Firestore set
        mock_firestore.collection.assert_called()

    def test_record_multiple_snapshots(self, velocity_tracker, mock_firestore):
        """Test recording multiple snapshots for same video."""
        velocity_tracker.record_view_snapshot("test_video_123", 10000)
        velocity_tracker.record_view_snapshot("test_video_123", 15000)
        velocity_tracker.record_view_snapshot("test_video_123", 20000)

        # Should be called 3 times
        assert mock_firestore.collection.call_count >= 3


class TestCalculateVelocity:
    """Tests for calculate_velocity method."""

    def test_calculate_velocity_insufficient_data(
        self, velocity_tracker, mock_firestore
    ):
        """Test returns None with insufficient snapshots."""
        # Mock only 1 snapshot
        mock_snapshot = MagicMock()
        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            mock_snapshot
        ]

        velocity = velocity_tracker.calculate_velocity("test_video")

        assert velocity is None

    def test_calculate_velocity_success(self, velocity_tracker, mock_firestore):
        """Test successful velocity calculation."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=24)

        # Mock 2 snapshots
        current_snap = MagicMock()
        current_snap.to_dict.return_value = {
            "video_id": "test_123",
            "view_count": 50000,
            "timestamp": now,
        }

        previous_snap = MagicMock()
        previous_snap.to_dict.return_value = {
            "video_id": "test_123",
            "view_count": 40000,
            "timestamp": past,
        }

        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            current_snap,
            previous_snap,
        ]

        velocity = velocity_tracker.calculate_velocity("test_123")

        assert velocity is not None
        assert velocity.video_id == "test_123"
        assert velocity.current_views == 50000
        assert velocity.previous_views == 40000
        assert velocity.views_gained == 10000
        assert velocity.hours_elapsed == pytest.approx(24.0)
        assert velocity.views_per_hour == pytest.approx(10000 / 24)

    def test_calculate_velocity_high_growth(self, velocity_tracker, mock_firestore):
        """Test velocity calculation with high view growth."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=1)

        current_snap = MagicMock()
        current_snap.to_dict.return_value = {
            "video_id": "viral_video",
            "view_count": 100000,
            "timestamp": now,
        }

        previous_snap = MagicMock()
        previous_snap.to_dict.return_value = {
            "video_id": "viral_video",
            "view_count": 80000,
            "timestamp": past,
        }

        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            current_snap,
            previous_snap,
        ]

        velocity = velocity_tracker.calculate_velocity("viral_video")

        assert velocity.views_per_hour == pytest.approx(20000.0)
        assert velocity.trending_score == 100.0  # >10k views/hr

    def test_calculate_velocity_negative_growth(self, velocity_tracker, mock_firestore):
        """Test velocity handles negative growth (views decreased)."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=12)

        current_snap = MagicMock()
        current_snap.to_dict.return_value = {
            "video_id": "test_video",
            "view_count": 5000,
            "timestamp": now,
        }

        previous_snap = MagicMock()
        previous_snap.to_dict.return_value = {
            "video_id": "test_video",
            "view_count": 6000,  # Higher than current (unusual)
            "timestamp": past,
        }

        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            current_snap,
            previous_snap,
        ]

        velocity = velocity_tracker.calculate_velocity("test_video")

        # Should handle as 0 growth
        assert velocity.views_gained == 0
        assert velocity.views_per_hour == 0.0


class TestGetTrendingScoreFromVelocity:
    """Tests for get_trending_score_from_velocity method."""

    def test_trending_score_extremely_viral(self, velocity_tracker):
        """Test score for extremely viral videos (>10k views/hr)."""
        score = velocity_tracker.get_trending_score_from_velocity(15000)
        assert score == 100.0

        score = velocity_tracker.get_trending_score_from_velocity(10000)
        assert score == 100.0

    def test_trending_score_very_viral(self, velocity_tracker):
        """Test score for very viral videos (5k-10k views/hr)."""
        score = velocity_tracker.get_trending_score_from_velocity(7500)
        assert 90.0 <= score < 100.0

        score = velocity_tracker.get_trending_score_from_velocity(5000)
        assert score == pytest.approx(90.0)

    def test_trending_score_viral(self, velocity_tracker):
        """Test score for viral videos (1k-5k views/hr)."""
        score = velocity_tracker.get_trending_score_from_velocity(3000)
        assert 50.0 <= score < 90.0

        score = velocity_tracker.get_trending_score_from_velocity(1000)
        assert score == pytest.approx(50.0)

    def test_trending_score_trending(self, velocity_tracker):
        """Test score for trending videos (100-1k views/hr)."""
        score = velocity_tracker.get_trending_score_from_velocity(500)
        assert 10.0 <= score < 50.0

        score = velocity_tracker.get_trending_score_from_velocity(100)
        assert score == pytest.approx(10.0)

    def test_trending_score_slow_growth(self, velocity_tracker):
        """Test score for slow growth videos (<100 views/hr)."""
        score = velocity_tracker.get_trending_score_from_velocity(50)
        assert 0.0 <= score < 10.0

        score = velocity_tracker.get_trending_score_from_velocity(0)
        assert score == 0.0

    def test_trending_score_edge_cases(self, velocity_tracker):
        """Test score edge cases."""
        # Exact thresholds
        assert velocity_tracker.get_trending_score_from_velocity(10000) == 100.0
        assert velocity_tracker.get_trending_score_from_velocity(5000) == 90.0
        assert velocity_tracker.get_trending_score_from_velocity(1000) == 50.0
        assert velocity_tracker.get_trending_score_from_velocity(100) == 10.0
        assert velocity_tracker.get_trending_score_from_velocity(0) == 0.0


class TestUpdateAllVelocities:
    """Tests for update_all_velocities method."""

    def test_update_all_velocities_success(self, velocity_tracker, mock_firestore):
        """Test batch updating velocities."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=12)

        # Mock snapshots for video 1
        snap1_current = MagicMock()
        snap1_current.to_dict.return_value = {
            "video_id": "video_1",
            "view_count": 10000,
            "timestamp": now,
        }
        snap1_previous = MagicMock()
        snap1_previous.to_dict.return_value = {
            "video_id": "video_1",
            "view_count": 5000,
            "timestamp": past,
        }

        # Mock snapshots for video 2
        snap2_current = MagicMock()
        snap2_current.to_dict.return_value = {
            "video_id": "video_2",
            "view_count": 20000,
            "timestamp": now,
        }
        snap2_previous = MagicMock()
        snap2_previous.to_dict.return_value = {
            "video_id": "video_2",
            "view_count": 15000,
            "timestamp": past,
        }

        # Configure mock to return different snapshots per video
        def mock_stream():
            video_id = mock_firestore.collection.return_value.document.call_args[0][0]
            if video_id == "video_1":
                return [snap1_current, snap1_previous]
            elif video_id == "video_2":
                return [snap2_current, snap2_previous]
            return []

        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.side_effect = mock_stream

        results = velocity_tracker.update_all_velocities(["video_1", "video_2"])

        assert len(results) == 2
        assert "video_1" in results
        assert "video_2" in results

    def test_update_all_velocities_partial_success(
        self, velocity_tracker, mock_firestore
    ):
        """Test batch update with some failures."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=12)

        # video_1 has snapshots
        snap1_current = MagicMock()
        snap1_current.to_dict.return_value = {
            "video_id": "video_1",
            "view_count": 10000,
            "timestamp": now,
        }
        snap1_previous = MagicMock()
        snap1_previous.to_dict.return_value = {
            "video_id": "video_1",
            "view_count": 5000,
            "timestamp": past,
        }

        def mock_stream():
            video_id = mock_firestore.collection.return_value.document.call_args[0][0]
            if video_id == "video_1":
                return [snap1_current, snap1_previous]
            # video_2 has no snapshots
            return []

        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.side_effect = mock_stream

        results = velocity_tracker.update_all_velocities(["video_1", "video_2"])

        assert results["video_1"] is not None
        assert results["video_2"] is None

    def test_update_all_velocities_empty_list(self, velocity_tracker):
        """Test batch update with empty list."""
        results = velocity_tracker.update_all_velocities([])

        assert results == {}


class TestGetHighVelocityVideos:
    """Tests for get_high_velocity_videos method."""

    def test_get_high_velocity_videos(self, velocity_tracker, mock_firestore):
        """Test retrieving high velocity videos."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=1)

        # Mock video documents
        video_doc1 = MagicMock()
        video_doc1.id = "viral_video_1"

        video_doc2 = MagicMock()
        video_doc2.id = "viral_video_2"

        mock_firestore.collection.return_value.limit.return_value.stream.return_value = [
            video_doc1,
            video_doc2,
        ]

        # Mock high velocity snapshots
        high_velocity_snap_current = MagicMock()
        high_velocity_snap_current.to_dict.return_value = {
            "video_id": "viral_video_1",
            "view_count": 20000,
            "timestamp": now,
        }
        high_velocity_snap_previous = MagicMock()
        high_velocity_snap_previous.to_dict.return_value = {
            "video_id": "viral_video_1",
            "view_count": 10000,
            "timestamp": past,
        }

        mock_firestore.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            high_velocity_snap_current,
            high_velocity_snap_previous,
        ]

        video_ids = velocity_tracker.get_high_velocity_videos(min_score=50.0, limit=10)

        # At least one high velocity video should be returned
        assert isinstance(video_ids, list)


class TestGetStatistics:
    """Tests for get_statistics method."""

    def test_get_statistics_structure(self, velocity_tracker, mock_firestore):
        """Test statistics returns correct structure."""
        mock_firestore.collection.return_value.stream.return_value = []

        stats = velocity_tracker.get_statistics()

        assert "total_videos_tracked" in stats
        assert "videos_with_velocity" in stats
        assert "avg_velocity" in stats
        assert "max_velocity" in stats

    def test_get_statistics_empty(self, velocity_tracker, mock_firestore):
        """Test statistics with no tracked videos."""
        mock_firestore.collection.return_value.stream.return_value = []

        stats = velocity_tracker.get_statistics()

        assert stats["total_videos_tracked"] == 0
        assert stats["videos_with_velocity"] == 0
        assert stats["avg_velocity"] == 0.0
        assert stats["max_velocity"] == 0.0
