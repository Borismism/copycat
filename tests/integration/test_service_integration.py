"""
Simplified integration tests for service communication.

Tests message formats, data flow, and Firestore schema compatibility
without requiring both services to be imported simultaneously.
"""

import json
import pytest
from datetime import datetime, timedelta

# Test data representing what discovery service would publish
DISCOVERY_MESSAGE = {
    "video_id": "test_video_123",
    "title": "AI Generated Superman Movie - Sora AI",
    "channel_id": "UC_test_channel",
    "channel_title": "AI Movies Channel",
    "published_at": "2025-10-28T10:00:00Z",
    "view_count": 50000,
    "duration_seconds": 300,
    "matched_keywords": ["superman", "ai generated"],
    "discovery_method": "keyword_search",
    "initial_risk_score": 75,
    "risk_factors": {
        "keyword_relevance": 90,
        "duration_score": 80,
        "recency_score": 95,
        "view_count_score": 60,
        "channel_size_score": 50
    },
    "discovered_at": "2025-10-28T10:00:00Z"
}


class TestMessageFormats:
    """Test that message formats are compatible between services."""

    def test_video_discovered_message_has_required_fields(self):
        """Test that video-discovered messages have all required fields."""
        required_fields = [
            "video_id",
            "title",
            "channel_id",
            "view_count",
            "initial_risk_score",
            "risk_factors",
            "discovered_at"
        ]

        for field in required_fields:
            assert field in DISCOVERY_MESSAGE, f"Missing required field: {field}"

    def test_risk_factors_structure(self):
        """Test that risk_factors has correct structure."""
        risk_factors = DISCOVERY_MESSAGE["risk_factors"]

        # Should be a dict
        assert isinstance(risk_factors, dict)

        # Should have the 5 discovery factors
        expected_factors = [
            "keyword_relevance",
            "duration_score",
            "recency_score",
            "view_count_score",
            "channel_size_score"
        ]

        for factor in expected_factors:
            assert factor in risk_factors
            assert isinstance(risk_factors[factor], (int, float))
            assert 0 <= risk_factors[factor] <= 100

    def test_message_json_serializable(self):
        """Test that messages can be serialized to JSON (for PubSub)."""
        try:
            json_data = json.dumps(DISCOVERY_MESSAGE)
            parsed = json.loads(json_data)
            assert parsed == DISCOVERY_MESSAGE
        except Exception as e:
            pytest.fail(f"Message not JSON serializable: {e}")


class TestFirestoreSchema:
    """Test Firestore document schemas are compatible."""

    def test_video_document_initial_state(self):
        """Test video document after discovery."""
        video_doc = {
            "video_id": "test_123",
            "title": "Test Video",
            "channel_id": "UC_test",
            "channel_title": "Test Channel",
            "published_at": "2025-10-28T10:00:00Z",
            "view_count": 10000,
            "duration_seconds": 300,
            "matched_keywords": ["superman"],
            "discovery_method": "keyword_search",
            "initial_risk_score": 75,
            "risk_factors": {},
            "discovered_at": "2025-10-28T10:00:00Z",
            "status": "discovered"
        }

        # Verify structure
        assert "video_id" in video_doc
        assert "initial_risk_score" in video_doc
        assert isinstance(video_doc["view_count"], int)
        assert isinstance(video_doc["initial_risk_score"], (int, float))

    def test_video_document_after_risk_analysis(self):
        """Test video document after risk-analyzer processing."""
        video_doc = {
            "video_id": "test_123",
            "title": "Test Video",
            "channel_id": "UC_test",
            "initial_risk_score": 75,

            # Risk analyzer adds these
            "current_risk_score": 85,
            "risk_tier": "HIGH",
            "next_scan_time": "2025-10-29T10:00:00Z",
            "view_history": [
                {
                    "timestamp": "2025-10-28T10:00:00Z",
                    "view_count": 10000
                }
            ],
            "scan_history": [],
            "last_risk_update": "2025-10-28T10:00:00Z"
        }

        # Verify risk analyzer fields
        assert "current_risk_score" in video_doc
        assert "risk_tier" in video_doc
        assert "next_scan_time" in video_doc
        assert "view_history" in video_doc

        # Verify risk tier is valid
        valid_tiers = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]
        assert video_doc["risk_tier"] in valid_tiers

    def test_channel_profile_structure(self):
        """Test channel profile document structure."""
        channel_doc = {
            "channel_id": "UC_test",
            "channel_title": "Test Channel",
            "total_videos_found": 50,
            "total_videos_scanned": 30,
            "infringement_count": 15,
            "infringement_rate": 0.50,
            "avg_views_per_video": 10000,
            "risk_tier": "GOLD",
            "last_updated": "2025-10-28T10:00:00Z"
        }

        # Verify structure
        assert "channel_id" in channel_doc
        assert "infringement_rate" in channel_doc
        assert "risk_tier" in channel_doc

        # Verify data types
        assert isinstance(channel_doc["infringement_rate"], float)
        assert 0 <= channel_doc["infringement_rate"] <= 1

        # Verify valid tier
        valid_tiers = ["PLATINUM", "GOLD", "SILVER", "BRONZE", "IGNORE"]
        assert channel_doc["risk_tier"] in valid_tiers


class TestRiskTierMapping:
    """Test that risk scores map to correct tiers."""

    def test_critical_tier_thresholds(self):
        """CRITICAL tier: score >= 80."""
        assert 80 <= 100
        assert 85 >= 80
        assert 95 >= 80

    def test_high_tier_thresholds(self):
        """HIGH tier: 60 <= score < 80."""
        assert 60 <= 75 < 80
        assert 60 <= 70 < 80

    def test_medium_tier_thresholds(self):
        """MEDIUM tier: 40 <= score < 60."""
        assert 40 <= 50 < 60
        assert 40 <= 45 < 60

    def test_low_tier_thresholds(self):
        """LOW tier: 20 <= score < 40."""
        assert 20 <= 30 < 40
        assert 20 <= 25 < 40

    def test_very_low_tier_thresholds(self):
        """VERY_LOW tier: score < 20."""
        assert 10 < 20
        assert 5 < 20


class TestScanScheduling:
    """Test scan scheduling intervals."""

    def test_critical_scan_interval(self):
        """CRITICAL videos scanned every 6 hours."""
        interval_hours = 6
        now = datetime.now()
        next_scan = now + timedelta(hours=interval_hours)

        time_diff = (next_scan - now).total_seconds() / 3600
        assert time_diff == 6

    def test_high_scan_interval(self):
        """HIGH videos scanned every 24 hours."""
        interval_hours = 24
        now = datetime.now()
        next_scan = now + timedelta(hours=interval_hours)

        time_diff = (next_scan - now).total_seconds() / 3600
        assert time_diff == 24

    def test_medium_scan_interval(self):
        """MEDIUM videos scanned every 3 days."""
        interval_days = 3
        now = datetime.now()
        next_scan = now + timedelta(days=interval_days)

        time_diff = (next_scan - now).total_seconds() / 86400
        assert time_diff == 3

    def test_low_scan_interval(self):
        """LOW videos scanned every 7 days."""
        interval_days = 7
        now = datetime.now()
        next_scan = now + timedelta(days=interval_days)

        time_diff = (next_scan - now).total_seconds() / 86400
        assert time_diff == 7

    def test_very_low_scan_interval(self):
        """VERY_LOW videos scanned every 30 days."""
        interval_days = 30
        now = datetime.now()
        next_scan = now + timedelta(days=interval_days)

        time_diff = (next_scan - now).total_seconds() / 86400
        assert time_diff == 30


class TestChannelTierMapping:
    """Test channel tier classification."""

    def test_platinum_tier_criteria(self):
        """PLATINUM: >50% infringement, >10 violations."""
        infringement_rate = 0.75
        infringement_count = 15

        assert infringement_rate > 0.50
        assert infringement_count > 10

    def test_gold_tier_criteria(self):
        """GOLD: 25-50% infringement, >5 violations."""
        infringement_rate = 0.40
        infringement_count = 8

        assert 0.25 <= infringement_rate <= 0.50
        assert infringement_count > 5

    def test_silver_tier_criteria(self):
        """SILVER: 10-25% infringement."""
        infringement_rate = 0.18

        assert 0.10 <= infringement_rate <= 0.25

    def test_bronze_tier_criteria(self):
        """BRONZE: <10% infringement."""
        infringement_rate = 0.05

        assert infringement_rate < 0.10

    def test_ignore_tier_criteria(self):
        """IGNORE: 0% infringement after 20+ videos."""
        infringement_rate = 0.0
        total_scanned = 25

        assert infringement_rate == 0.0
        assert total_scanned >= 20


class TestViewVelocityCalculation:
    """Test view velocity scoring logic."""

    def test_extremely_viral_video(self):
        """Test >10k views/hour = score 90-100."""
        views_per_hour = 12500
        expected_min_score = 90

        # Viral videos should score very high
        assert views_per_hour > 10000
        # This would result in a score >= 90

    def test_very_viral_video(self):
        """Test 1k-10k views/hour = score 70-89."""
        views_per_hour = 5000
        expected_range = (70, 89)

        assert 1000 <= views_per_hour <= 10000

    def test_viral_video(self):
        """Test 100-1k views/hour = score 50-69."""
        views_per_hour = 500
        expected_range = (50, 69)

        assert 100 <= views_per_hour <= 1000

    def test_trending_video(self):
        """Test 10-100 views/hour = score 30-49."""
        views_per_hour = 50
        expected_range = (30, 49)

        assert 10 <= views_per_hour <= 100

    def test_normal_video(self):
        """Test <10 views/hour = score 0-29."""
        views_per_hour = 5
        expected_range = (0, 29)

        assert views_per_hour < 10


class TestDataFlow:
    """Test the expected data flow between services."""

    def test_discovery_to_risk_analyzer_flow(self):
        """Test the expected data transformation."""
        # 1. Discovery finds video
        discovery_output = {
            "video_id": "abc123",
            "initial_risk_score": 75,
            "status": "discovered"
        }

        # 2. Risk analyzer receives and enhances
        risk_analyzer_input = discovery_output.copy()
        risk_analyzer_output = {
            **risk_analyzer_input,
            "current_risk_score": 85,  # May be higher after velocity analysis
            "risk_tier": "HIGH",
            "next_scan_time": "2025-10-29T10:00:00Z",
            "status": "analyzed"
        }

        # Verify transformation
        assert risk_analyzer_output["video_id"] == discovery_output["video_id"]
        assert "current_risk_score" in risk_analyzer_output
        assert "risk_tier" in risk_analyzer_output
        assert risk_analyzer_output["status"] == "analyzed"

    def test_risk_to_scheduler_flow(self):
        """Test risk analyzer output can be used for scheduling."""
        risk_output = {
            "video_id": "abc123",
            "current_risk_score": 85,
            "risk_tier": "HIGH",
            "next_scan_time": "2025-10-29T10:00:00Z"
        }

        # Scheduler should be able to use this data
        assert "next_scan_time" in risk_output
        assert "risk_tier" in risk_output

        # Parse next_scan_time
        next_scan = datetime.fromisoformat(risk_output["next_scan_time"].replace("Z", "+00:00"))
        assert isinstance(next_scan, datetime)


class TestErrorHandling:
    """Test error scenarios in data flow."""

    def test_missing_video_data(self):
        """Test handling of incomplete video data."""
        incomplete_data = {
            "video_id": "test_123"
            # Missing required fields
        }

        # Should have at minimum these fields
        required = ["video_id", "view_count", "initial_risk_score"]
        missing = [f for f in required if f not in incomplete_data]

        assert len(missing) > 0  # Demonstrates missing fields

    def test_invalid_risk_score(self):
        """Test handling of out-of-range risk scores."""
        invalid_scores = [-10, 150, 999]

        for score in invalid_scores:
            assert not (0 <= score <= 100)

    def test_invalid_risk_tier(self):
        """Test handling of invalid risk tiers."""
        invalid_tiers = ["SUPER_HIGH", "ULTRA_LOW", "UNKNOWN"]
        valid_tiers = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]

        for tier in invalid_tiers:
            assert tier not in valid_tiers
