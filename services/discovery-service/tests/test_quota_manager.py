"""Tests for QuotaManager class."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.core.quota_manager import QuotaManager


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    return MagicMock()


@pytest.fixture
def quota_manager(mock_firestore):
    """QuotaManager instance with mocked Firestore."""
    return QuotaManager(
        firestore_client=mock_firestore,
        daily_quota=10_000,
        quota_collection="quota_usage",
    )


class TestQuotaManagerInit:
    """Tests for QuotaManager initialization."""

    def test_initialization_success(self, mock_firestore):
        """Test QuotaManager initializes correctly."""
        # Mock no existing usage
        doc_mock = MagicMock()
        doc_mock.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        manager = QuotaManager(
            firestore_client=mock_firestore,
            daily_quota=5000,
            quota_collection="test_quota",
        )

        assert manager.firestore == mock_firestore
        assert manager.daily_quota == 5000
        assert manager.quota_collection == "test_quota"
        assert manager.used_quota == 0

    def test_initialization_loads_existing_usage(self, mock_firestore):
        """Test initialization loads existing usage from Firestore."""
        # Mock existing quota document
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {"units_used": 2500, "daily_quota": 10000}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        manager = QuotaManager(firestore_client=mock_firestore)

        assert manager.used_quota == 2500

    def test_initialization_no_existing_usage(self, mock_firestore):
        """Test initialization with no existing usage."""
        # Mock no document
        doc_mock = MagicMock()
        doc_mock.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        manager = QuotaManager(firestore_client=mock_firestore)

        assert manager.used_quota == 0


class TestGetTodayKey:
    """Tests for _get_today_key method."""

    def test_get_today_key_format(self, quota_manager):
        """Test today key is in YYYY-MM-DD format."""
        today_key = quota_manager._get_today_key()

        # Should be in YYYY-MM-DD format
        assert len(today_key) == 10
        assert today_key.count("-") == 2

        # Should be parseable as date
        datetime.strptime(today_key, "%Y-%m-%d")


class TestCanAfford:
    """Tests for can_afford method."""

    def test_can_afford_search_within_quota(self, quota_manager):
        """Test can afford search operation."""
        quota_manager.used_quota = 0

        result = quota_manager.can_afford("search", count=1)

        assert result is True

    def test_can_afford_multiple_operations(self, quota_manager):
        """Test can afford multiple operations."""
        quota_manager.used_quota = 0

        result = quota_manager.can_afford("video_details", count=50)

        assert result is True  # 50 units within 10,000 quota

    def test_cannot_afford_exceeds_quota(self, quota_manager):
        """Test cannot afford operation that exceeds quota."""
        quota_manager.used_quota = 9950  # Close to limit

        result = quota_manager.can_afford("search", count=1)  # Would cost 100

        assert result is False

    def test_can_afford_exactly_at_quota(self, quota_manager):
        """Test can afford operation that exactly uses remaining quota."""
        quota_manager.used_quota = 9900

        result = quota_manager.can_afford("search", count=1)  # Costs 100, total=10000

        assert result is True

    def test_can_afford_invalid_operation(self, quota_manager):
        """Test error with invalid operation."""
        with pytest.raises(ValueError, match="Unknown operation"):
            quota_manager.can_afford("invalid_operation")

    def test_can_afford_all_operation_types(self, quota_manager):
        """Test can_afford works with all operation types."""
        quota_manager.used_quota = 0

        for operation in QuotaManager.COSTS.keys():
            result = quota_manager.can_afford(operation, count=1)
            assert result is True


class TestRecordUsage:
    """Tests for record_usage method."""

    def test_record_usage_search(self, quota_manager, mock_firestore):
        """Test recording search operation usage."""
        quota_manager.used_quota = 0

        quota_manager.record_usage("search", count=1)

        assert quota_manager.used_quota == 100
        mock_firestore.collection.assert_called()

    def test_record_usage_video_details(self, quota_manager, mock_firestore):
        """Test recording video_details operation usage."""
        quota_manager.used_quota = 0

        quota_manager.record_usage("video_details", count=10)

        assert quota_manager.used_quota == 10

    def test_record_usage_accumulates(self, quota_manager):
        """Test usage accumulates over multiple operations."""
        quota_manager.used_quota = 0

        quota_manager.record_usage("search", count=1)  # +100
        quota_manager.record_usage("video_details", count=5)  # +5
        quota_manager.record_usage("channel_details", count=2)  # +2

        assert quota_manager.used_quota == 107

    def test_record_usage_invalid_operation(self, quota_manager):
        """Test error with invalid operation."""
        with pytest.raises(ValueError, match="Unknown operation"):
            quota_manager.record_usage("invalid_operation")

    def test_record_usage_saves_to_firestore(self, quota_manager, mock_firestore):
        """Test usage is persisted to Firestore."""
        quota_manager.used_quota = 0

        quota_manager.record_usage("search", count=1)

        # Should call Firestore set
        doc_ref = mock_firestore.collection.return_value.document.return_value
        doc_ref.set.assert_called_once()

        # Check saved data structure
        call_args = doc_ref.set.call_args
        saved_data = call_args[0][0]

        assert saved_data["units_used"] == 100
        assert saved_data["daily_quota"] == 10_000
        assert "date" in saved_data
        assert "updated_at" in saved_data

    def test_record_usage_logs_warning_at_80_percent(
        self, quota_manager, mock_firestore
    ):
        """Test warning logged at 80% utilization."""
        quota_manager.used_quota = 0
        quota_manager._warning_logged = False

        # Use 80% of quota
        quota_manager.record_usage("search", count=80)  # 8000 units

        # Warning should be logged (checked via internal flag)
        assert quota_manager._warning_logged is True

    def test_record_usage_no_duplicate_warnings(self, quota_manager):
        """Test warning only logged once."""
        quota_manager.used_quota = 8000
        quota_manager._warning_logged = False

        quota_manager.record_usage("search", count=1)  # First warning
        assert quota_manager._warning_logged is True

        quota_manager.record_usage("search", count=1)  # Should not warn again
        # Still true (no duplicate warning)
        assert quota_manager._warning_logged is True


class TestGetRemaining:
    """Tests for get_remaining method."""

    def test_get_remaining_full_quota(self, quota_manager):
        """Test remaining with no usage."""
        quota_manager.used_quota = 0

        remaining = quota_manager.get_remaining()

        assert remaining == 10_000

    def test_get_remaining_partial_usage(self, quota_manager):
        """Test remaining with partial usage."""
        quota_manager.used_quota = 3000

        remaining = quota_manager.get_remaining()

        assert remaining == 7000

    def test_get_remaining_quota_exceeded(self, quota_manager):
        """Test remaining when quota exceeded returns 0."""
        quota_manager.used_quota = 15000  # Over quota

        remaining = quota_manager.get_remaining()

        assert remaining == 0

    def test_get_remaining_exactly_at_quota(self, quota_manager):
        """Test remaining when exactly at quota."""
        quota_manager.used_quota = 10_000

        remaining = quota_manager.get_remaining()

        assert remaining == 0


class TestGetUtilization:
    """Tests for get_utilization method."""

    def test_get_utilization_no_usage(self, quota_manager):
        """Test utilization with no usage."""
        quota_manager.used_quota = 0

        utilization = quota_manager.get_utilization()

        assert utilization == 0.0

    def test_get_utilization_50_percent(self, quota_manager):
        """Test utilization at 50%."""
        quota_manager.used_quota = 5000

        utilization = quota_manager.get_utilization()

        assert utilization == 0.5

    def test_get_utilization_80_percent(self, quota_manager):
        """Test utilization at 80% (warning threshold)."""
        quota_manager.used_quota = 8000

        utilization = quota_manager.get_utilization()

        assert utilization == 0.80

    def test_get_utilization_100_percent(self, quota_manager):
        """Test utilization at 100%."""
        quota_manager.used_quota = 10_000

        utilization = quota_manager.get_utilization()

        assert utilization == 1.0

    def test_get_utilization_over_100_percent_capped(self, quota_manager):
        """Test utilization capped at 100% when quota exceeded."""
        quota_manager.used_quota = 15000  # 150%

        utilization = quota_manager.get_utilization()

        assert utilization == 1.0  # Capped

    def test_get_utilization_zero_quota(self, mock_firestore):
        """Test utilization with zero daily quota."""
        manager = QuotaManager(firestore_client=mock_firestore, daily_quota=0)

        utilization = manager.get_utilization()

        assert utilization == 0.0


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_structure(self, quota_manager):
        """Test get_status returns correct structure."""
        quota_manager.used_quota = 3000

        status = quota_manager.get_status()

        assert "used" in status
        assert "remaining" in status
        assert "daily_quota" in status
        assert "utilization" in status
        assert "date" in status

    def test_get_status_values(self, quota_manager):
        """Test get_status returns correct values."""
        quota_manager.used_quota = 2500

        status = quota_manager.get_status()

        assert status["used"] == 2500
        assert status["remaining"] == 7500
        assert status["daily_quota"] == 10_000
        assert status["utilization"] == 25.0  # Percentage
        assert isinstance(status["date"], str)


class TestResetDailyQuota:
    """Tests for reset_daily_quota method."""

    def test_reset_daily_quota(self, quota_manager):
        """Test resetting daily quota."""
        quota_manager.used_quota = 5000
        quota_manager._warning_logged = True

        quota_manager.reset_daily_quota()

        assert quota_manager.used_quota == 0
        assert quota_manager._warning_logged is False


class TestCostConstants:
    """Tests for COSTS constants."""

    def test_cost_constants_exist(self):
        """Test all expected cost constants are defined."""
        assert "search" in QuotaManager.COSTS
        assert "video_details" in QuotaManager.COSTS
        assert "trending" in QuotaManager.COSTS
        assert "channel_details" in QuotaManager.COSTS
        assert "playlist_items" in QuotaManager.COSTS

    def test_cost_values_correct(self):
        """Test cost values match YouTube API v3 costs."""
        assert QuotaManager.COSTS["search"] == 100
        assert QuotaManager.COSTS["video_details"] == 1
        assert QuotaManager.COSTS["trending"] == 1
        assert QuotaManager.COSTS["channel_details"] == 1
        assert QuotaManager.COSTS["playlist_items"] == 1

    def test_warning_threshold(self):
        """Test warning threshold is 80%."""
        assert QuotaManager.WARNING_THRESHOLD == 0.80


class TestIntegration:
    """Integration tests for QuotaManager."""

    def test_typical_usage_flow(self, quota_manager):
        """Test typical usage flow."""
        # Start fresh
        quota_manager.used_quota = 0
        assert quota_manager.can_afford("search", count=5)

        # Use quota
        quota_manager.record_usage("search", count=5)  # 500 units
        assert quota_manager.used_quota == 500

        # Check remaining
        assert quota_manager.get_remaining() == 9500
        assert quota_manager.get_utilization() == 0.05

        # Use more quota
        quota_manager.record_usage("video_details", count=100)  # 100 units
        assert quota_manager.used_quota == 600

        # Check status
        status = quota_manager.get_status()
        assert status["used"] == 600
        assert status["remaining"] == 9400

    def test_quota_exhaustion_prevention(self, quota_manager):
        """Test quota exhaustion is prevented."""
        quota_manager.used_quota = 9950

        # Cannot afford expensive search
        assert not quota_manager.can_afford("search", count=1)

        # Can still afford cheap operations
        assert quota_manager.can_afford("video_details", count=10)
