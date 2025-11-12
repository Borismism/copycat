"""Tests for budget_manager.py"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from app.core.budget_manager import BudgetManager


class TestBudgetManager:
    """Test BudgetManager class."""

    @pytest.fixture
    def budget_manager(self, mock_firestore):
        """Create budget manager instance."""
        return BudgetManager(mock_firestore)

    def test_initialization(self, budget_manager):
        """Test budget manager initialization."""
        assert budget_manager.DAILY_BUDGET_EUR > 0  # Just check it's set
        assert budget_manager._cached_total == 0.0
        assert budget_manager._video_count == 0

    def test_can_afford_with_sufficient_budget(self, budget_manager):
        """Test can_afford when budget is available."""
        budget_manager._cached_date = budget_manager._get_today_key()
        budget_manager._cached_total = 0.0
        # Ask for half the daily budget - should always work
        cost = budget_manager.DAILY_BUDGET_EUR / 2
        assert budget_manager.can_afford(cost) is True

    def test_can_afford_insufficient_budget(self, budget_manager):
        """Test can_afford when budget would be exceeded."""
        # Set to 99% of budget
        budget_manager._cached_date = budget_manager._get_today_key()
        budget_manager._cached_total = budget_manager.DAILY_BUDGET_EUR * 0.99
        # Ask for 10% more - should fail
        cost = budget_manager.DAILY_BUDGET_EUR * 0.10
        assert budget_manager.can_afford(cost) is False

    def test_can_afford_exact_budget(self, budget_manager):
        """Test can_afford at exact budget limit."""
        # Use 90% of budget
        budget_manager._cached_date = budget_manager._get_today_key()
        budget_manager._cached_total = budget_manager.DAILY_BUDGET_EUR * 0.90
        # Ask for 10% - should work (exactly at limit)
        assert budget_manager.can_afford(budget_manager.DAILY_BUDGET_EUR * 0.10) is True
        # Ask for 10.01% - should fail
        assert budget_manager.can_afford(budget_manager.DAILY_BUDGET_EUR * 0.1001) is False

    def test_record_usage(self, budget_manager, mock_firestore):
        """Test recording budget usage."""
        budget_manager.record_usage("video_123", 5.0)

        # Check Firestore was called
        mock_firestore.collection.assert_called()
        assert budget_manager._cached_total == 5.0
        assert budget_manager._video_count == 1

    def test_record_multiple_usages(self, budget_manager, mock_firestore):
        """Test recording multiple budget usages."""
        budget_manager.record_usage("video_1", 3.0)
        budget_manager.record_usage("video_2", 2.5)
        budget_manager.record_usage("video_3", 1.5)

        assert budget_manager._cached_total == 7.0
        assert budget_manager._video_count == 3

    def test_get_daily_total_from_cache(self, budget_manager):
        """Test getting daily total from cache."""
        budget_manager._cached_date = budget_manager._get_today_key()
        budget_manager._cached_total = 100.0

        total = budget_manager.get_daily_total()
        assert total == 100.0

    def test_get_daily_total_from_firestore(self, budget_manager, mock_firestore):
        """Test getting daily total from Firestore when cache is stale."""
        # Mock Firestore response
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "total_spent_usd": 75.5,
            "video_count": 10,
        }
        mock_firestore.collection().document().get.return_value = mock_doc

        total = budget_manager.get_daily_total()
        assert total == 75.5
        assert budget_manager._video_count == 10

    def test_get_daily_total_no_data(self, budget_manager, mock_firestore):
        """Test getting daily total when no data exists."""
        mock_doc = Mock()
        mock_doc.exists = False
        mock_firestore.collection().document().get.return_value = mock_doc

        total = budget_manager.get_daily_total()
        assert total == 0.0
        assert budget_manager._video_count == 0

    def test_get_remaining_budget(self, budget_manager):
        """Test getting remaining budget."""
        budget_manager._cached_total = 100.0
        budget_manager._cached_date = budget_manager._get_today_key()

        remaining = budget_manager.get_remaining_budget()
        assert remaining == 160.0  # 260 - 100

    def test_get_remaining_budget_zero(self, budget_manager):
        """Test remaining budget when budget is exhausted."""
        budget_manager._cached_total = 270.0
        budget_manager._cached_date = budget_manager._get_today_key()

        remaining = budget_manager.get_remaining_budget()
        assert remaining == 0.0  # Should not go negative

    def test_get_utilization_percent(self, budget_manager):
        """Test budget utilization calculation."""
        budget_manager._cached_total = 130.0  # 50% of 260
        budget_manager._cached_date = budget_manager._get_today_key()

        utilization = budget_manager.get_utilization_percent()
        assert utilization == 50.0

    def test_get_utilization_percent_over_100(self, budget_manager):
        """Test utilization caps at 100%."""
        budget_manager._cached_total = 300.0
        budget_manager._cached_date = budget_manager._get_today_key()

        utilization = budget_manager.get_utilization_percent()
        assert utilization == 100.0  # Capped at 100

    def test_get_video_count_today(self, budget_manager):
        """Test getting video count."""
        budget_manager._video_count = 25
        budget_manager._cached_date = budget_manager._get_today_key()

        count = budget_manager.get_video_count_today()
        assert count == 25

    @pytest.mark.asyncio
    async def test_enforce_rate_limit_no_op(self, budget_manager):
        """Test that enforce_rate_limit is a no-op (no pre-emptive rate limiting)."""
        # Should complete instantly without error
        await budget_manager.enforce_rate_limit()
        # If it returns without exception, test passes

    def test_reset_session(self, budget_manager, mock_firestore):
        """Test session reset."""
        # Set up existing session
        budget_manager._video_count = 10
        budget_manager._start_time = 0.0

        # Mock Firestore for get_video_count_today
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "total_spent_usd": 50.0,
            "video_count": 15,
        }
        mock_firestore.collection().document().get.return_value = mock_doc

        budget_manager.reset_session()

        # Should load video count from Firestore
        assert budget_manager._video_count == 15
        assert budget_manager._start_time > 0  # Should be reset to now

    def test_get_stats(self, budget_manager):
        """Test getting budget statistics."""
        budget_manager._cached_total = 100.0
        budget_manager._video_count = 20
        budget_manager._cached_date = budget_manager._get_today_key()

        stats = budget_manager.get_stats()

        assert stats["daily_budget_usd"] == 260.0
        assert stats["total_spent_usd"] == 100.0
        assert stats["remaining_usd"] == 160.0
        assert stats["utilization_percent"] == 38.5  # 100/260 * 100
        assert stats["videos_analyzed"] == 20
        assert stats["avg_cost_per_video"] == 5.0  # 100/20

    def test_get_stats_no_videos(self, budget_manager):
        """Test stats when no videos analyzed."""
        budget_manager._cached_total = 0.0
        budget_manager._video_count = 0
        budget_manager._cached_date = budget_manager._get_today_key()

        stats = budget_manager.get_stats()

        assert stats["videos_analyzed"] == 0
        assert stats["avg_cost_per_video"] == 0.0  # Should not divide by zero

    def test_today_key_format(self, budget_manager):
        """Test that today key is in correct format."""
        today = budget_manager._get_today_key()

        # Should be YYYY-MM-DD format
        assert len(today) == 10
        assert today[4] == "-"
        assert today[7] == "-"

        # Should be parseable as date
        datetime.strptime(today, "%Y-%m-%d")

    def test_budget_tracking_across_day_boundary(self, budget_manager, mock_firestore):
        """Test that budget resets across day boundary."""
        # Set cached data for yesterday
        with patch.object(budget_manager, "_get_today_key", return_value="2025-10-29"):
            budget_manager._cached_date = "2025-10-29"
            budget_manager._cached_total = 100.0

        # Mock Firestore for new day (empty)
        mock_doc = Mock()
        mock_doc.exists = False
        mock_firestore.collection().document().get.return_value = mock_doc

        # Get total for new day
        with patch.object(budget_manager, "_get_today_key", return_value="2025-10-30"):
            total = budget_manager.get_daily_total()

        # Should fetch fresh data and reset to 0
        assert total == 0.0

    def test_concurrent_usage_recording(self, budget_manager, mock_firestore):
        """Test that multiple videos can be recorded in quick succession."""
        videos_and_costs = [
            ("video_1", 2.5),
            ("video_2", 3.0),
            ("video_3", 1.8),
            ("video_4", 4.2),
            ("video_5", 2.1),
        ]

        for video_id, cost in videos_and_costs:
            budget_manager.record_usage(video_id, cost)

        expected_total = sum(cost for _, cost in videos_and_costs)
        assert abs(budget_manager._cached_total - expected_total) < 0.01
        assert budget_manager._video_count == 5

    def test_firestore_error_handling(self, budget_manager, mock_firestore):
        """Test handling of Firestore errors."""
        mock_firestore.collection().document().get.side_effect = Exception(
            "Firestore error"
        )

        # Should return cached value instead of crashing
        budget_manager._cached_total = 50.0
        budget_manager._cached_date = budget_manager._get_today_key()

        total = budget_manager.get_daily_total()
        assert total == 50.0  # Returns cached fallback
