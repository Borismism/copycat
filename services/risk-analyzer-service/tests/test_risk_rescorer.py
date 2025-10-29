"""Test adaptive risk rescoring algorithm."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.core.risk_rescorer import RiskRescorer


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    return Mock()


@pytest.fixture
def rescorer(mock_firestore):
    """Create risk rescorer instance."""
    return RiskRescorer(mock_firestore)


class TestCalculateVelocityBoost:
    """Test view velocity bonus calculation."""

    def test_extremely_viral(self, rescorer):
        """Test extremely viral video (>10k views/hour)."""
        video_data = {"view_velocity": 15_000.0}
        boost = rescorer._calculate_velocity_boost(video_data)
        assert boost == 30

    def test_very_viral(self, rescorer):
        """Test very viral video (>1k views/hour)."""
        video_data = {"view_velocity": 5_000.0}
        boost = rescorer._calculate_velocity_boost(video_data)
        assert boost == 20

    def test_viral(self, rescorer):
        """Test viral video (>100 views/hour)."""
        video_data = {"view_velocity": 500.0}
        boost = rescorer._calculate_velocity_boost(video_data)
        assert boost == 10

    def test_normal_growth(self, rescorer):
        """Test normal growth video."""
        video_data = {"view_velocity": 50.0}
        boost = rescorer._calculate_velocity_boost(video_data)
        assert boost == 0


class TestCalculateChannelBoost:
    """Test channel reputation bonus calculation."""

    def test_serial_infringer(self, rescorer):
        """Test channel with 100% infringement."""
        video_data = {"channel_risk": 100}
        boost = rescorer._calculate_channel_boost(video_data)
        assert boost == 20

    def test_frequent_infringer(self, rescorer):
        """Test channel with 50% infringement."""
        video_data = {"channel_risk": 50}
        boost = rescorer._calculate_channel_boost(video_data)
        assert boost == 10

    def test_clean_channel(self, rescorer):
        """Test clean channel."""
        video_data = {"channel_risk": 0}
        boost = rescorer._calculate_channel_boost(video_data)
        assert boost == 0


class TestCalculateEngagementBoost:
    """Test engagement rate bonus calculation."""

    def test_high_engagement(self, rescorer):
        """Test high engagement (>5%)."""
        video_data = {
            "view_count": 10_000,
            "like_count": 400,
            "comment_count": 200,
        }
        boost = rescorer._calculate_engagement_boost(video_data)
        assert boost == 10  # 600/10000 = 6% > 5%

    def test_medium_engagement(self, rescorer):
        """Test medium engagement (>2%)."""
        video_data = {
            "view_count": 10_000,
            "like_count": 200,
            "comment_count": 100,
        }
        boost = rescorer._calculate_engagement_boost(video_data)
        assert boost == 5  # 300/10000 = 3%

    def test_low_engagement(self, rescorer):
        """Test low engagement (<2%)."""
        video_data = {
            "view_count": 10_000,
            "like_count": 50,
            "comment_count": 50,
        }
        boost = rescorer._calculate_engagement_boost(video_data)
        assert boost == 0

    def test_zero_views(self, rescorer):
        """Test video with zero views."""
        video_data = {
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
        }
        boost = rescorer._calculate_engagement_boost(video_data)
        assert boost == 0


class TestCalculateAgeDecay:
    """Test age decay penalty calculation."""

    def test_very_old_video(self, rescorer):
        """Test video >6 months old."""
        video_data = {
            "published_at": datetime.now(timezone.utc) - timedelta(days=200)
        }
        penalty = rescorer._calculate_age_decay(video_data)
        assert penalty == -15

    def test_old_video(self, rescorer):
        """Test video >3 months old."""
        video_data = {
            "published_at": datetime.now(timezone.utc) - timedelta(days=100)
        }
        penalty = rescorer._calculate_age_decay(video_data)
        assert penalty == -10

    def test_month_old_video(self, rescorer):
        """Test video >1 month old."""
        video_data = {
            "published_at": datetime.now(timezone.utc) - timedelta(days=40)
        }
        penalty = rescorer._calculate_age_decay(video_data)
        assert penalty == -5

    def test_recent_video(self, rescorer):
        """Test recent video (<1 month)."""
        video_data = {
            "published_at": datetime.now(timezone.utc) - timedelta(days=10)
        }
        penalty = rescorer._calculate_age_decay(video_data)
        assert penalty == 0


class TestCalculateResultsAdjustment:
    """Test prior analysis results adjustment."""

    def test_confirmed_infringement(self, rescorer):
        """Test confirmed infringement."""
        video_data = {
            "gemini_result": {
                "contains_infringement": True,
            }
        }
        adjustment = rescorer._calculate_results_adjustment(video_data)
        assert adjustment == 20

    def test_confirmed_clean(self, rescorer):
        """Test confirmed clean video."""
        video_data = {
            "gemini_result": {
                "contains_infringement": False,
            }
        }
        adjustment = rescorer._calculate_results_adjustment(video_data)
        assert adjustment == -10

    def test_no_analysis(self, rescorer):
        """Test video with no analysis."""
        video_data = {}
        adjustment = rescorer._calculate_results_adjustment(video_data)
        assert adjustment == 0


class TestCalculateTier:
    """Test risk tier calculation."""

    def test_critical_tier(self, rescorer):
        """Test CRITICAL tier (90-100)."""
        assert rescorer.calculate_tier(100) == "CRITICAL"
        assert rescorer.calculate_tier(95) == "CRITICAL"
        assert rescorer.calculate_tier(90) == "CRITICAL"

    def test_high_tier(self, rescorer):
        """Test HIGH tier (70-89)."""
        assert rescorer.calculate_tier(89) == "HIGH"
        assert rescorer.calculate_tier(75) == "HIGH"
        assert rescorer.calculate_tier(70) == "HIGH"

    def test_medium_tier(self, rescorer):
        """Test MEDIUM tier (40-69)."""
        assert rescorer.calculate_tier(69) == "MEDIUM"
        assert rescorer.calculate_tier(50) == "MEDIUM"
        assert rescorer.calculate_tier(40) == "MEDIUM"

    def test_low_tier(self, rescorer):
        """Test LOW tier (20-39)."""
        assert rescorer.calculate_tier(39) == "LOW"
        assert rescorer.calculate_tier(25) == "LOW"
        assert rescorer.calculate_tier(20) == "LOW"

    def test_very_low_tier(self, rescorer):
        """Test VERY_LOW tier (0-19)."""
        assert rescorer.calculate_tier(19) == "VERY_LOW"
        assert rescorer.calculate_tier(10) == "VERY_LOW"
        assert rescorer.calculate_tier(0) == "VERY_LOW"


class TestRecalculateRisk:
    """Test full risk recalculation."""

    def test_viral_new_video(self, rescorer):
        """Test viral new video from unknown channel."""
        video_data = {
            "video_id": "viral_123",
            "initial_risk": 30,
            "view_velocity": 5_000.0,  # +20
            "channel_risk": 0,  # +0
            "view_count": 100_000,
            "like_count": 3_000,  # 3% engagement
            "comment_count": 2_000,
            "published_at": datetime.now(timezone.utc) - timedelta(days=2),  # +0
        }

        result = rescorer.recalculate_risk(video_data)

        # 30 (initial) + 20 (velocity) + 0 (channel) + 5 (engagement) + 0 (age) + 0 (results) = 55
        assert result["new_risk"] == 55
        assert result["new_tier"] == "MEDIUM"

    def test_confirmed_infringer_channel(self, rescorer):
        """Test video from confirmed serial infringer."""
        video_data = {
            "video_id": "infringer_456",
            "initial_risk": 40,
            "view_velocity": 150.0,  # +10 (>100, <1000)
            "channel_risk": 80,  # +16 (80 * 0.2 = 16)
            "view_count": 50_000,
            "like_count": 1_000,  # 2% engagement = 0 (needs >2%)
            "comment_count": 0,
            "published_at": datetime.now(timezone.utc) - timedelta(days=5),  # +0
            "gemini_result": {"contains_infringement": True},  # +20
        }

        result = rescorer.recalculate_risk(video_data)

        # 40 + 10 + 16 + 0 + 0 + 20 = 86
        # But velocity 100 is >100 which gives +10, so we should get 86
        # If getting 76, then velocity is only giving 0 instead of 10
        # 100.0 is exactly at boundary - let's adjust
        assert result["new_risk"] == 86
        assert result["new_tier"] == "HIGH"

    def test_old_clean_video(self, rescorer):
        """Test old video confirmed clean."""
        video_data = {
            "video_id": "old_clean_789",
            "initial_risk": 30,
            "view_velocity": 0.0,  # +0
            "channel_risk": 0,  # +0
            "view_count": 10_000,
            "like_count": 100,  # 1% engagement
            "comment_count": 0,
            "published_at": datetime.now(timezone.utc) - timedelta(days=200),  # -15
            "gemini_result": {"contains_infringement": False},  # -10
        }

        result = rescorer.recalculate_risk(video_data)

        # 30 + 0 + 0 + 0 - 15 - 10 = 5
        assert result["new_risk"] == 5
        assert result["new_tier"] == "VERY_LOW"

    def test_risk_clamping(self, rescorer):
        """Test risk is clamped to 0-100."""
        # Test upper bound
        video_data = {
            "video_id": "max_risk",
            "initial_risk": 90,
            "view_velocity": 15_000.0,  # +30
            "channel_risk": 100,  # +20
            "view_count": 1_000_000,
            "like_count": 60_000,  # 6% engagement
            "comment_count": 0,
            "published_at": datetime.now(timezone.utc) - timedelta(days=1),
            "gemini_result": {"contains_infringement": True},  # +20
        }

        result = rescorer.recalculate_risk(video_data)

        # Would be 90 + 30 + 20 + 10 + 0 + 20 = 170, clamped to 100
        assert result["new_risk"] == 100
        assert result["new_tier"] == "CRITICAL"

        # Test lower bound
        video_data_low = {
            "video_id": "min_risk",
            "initial_risk": 5,
            "view_velocity": 0.0,
            "channel_risk": 0,
            "view_count": 100,
            "like_count": 0,
            "comment_count": 0,
            "published_at": datetime.now(timezone.utc) - timedelta(days=200),  # -15
            "gemini_result": {"contains_infringement": False},  # -10
        }

        result_low = rescorer.recalculate_risk(video_data_low)

        # Would be 5 + 0 + 0 + 0 - 15 - 10 = -20, clamped to 0
        assert result_low["new_risk"] == 0
        assert result_low["new_tier"] == "VERY_LOW"
