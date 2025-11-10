"""Tests for video_config_calculator.py"""

import pytest
from app.core.video_config_calculator import VideoConfigCalculator


class TestVideoConfigCalculator:
    """Test VideoConfigCalculator class."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return VideoConfigCalculator()

    def test_short_video_fps(self, calculator):
        """Test FPS for short videos (0-2 min)."""
        config = calculator.calculate_config(
            video_id="test_1",
            duration_seconds=90,  # 1.5 minutes
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        assert config.fps == 1.0  # Should use full 1 FPS
        assert config.estimated_cost_usd > 0

    def test_medium_video_fps(self, calculator):
        """Test FPS for medium videos (2-5 min)."""
        config = calculator.calculate_config(
            video_id="test_2",
            duration_seconds=300,  # 5 minutes
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        assert config.fps == 0.5  # 2-5 min should be 0.5 FPS
        assert 0.007 <= config.estimated_cost_usd <= 0.012  # Expected range

    def test_long_video_fps(self, calculator):
        """Test FPS for long videos (10-20 min)."""
        config = calculator.calculate_config(
            video_id="test_3",
            duration_seconds=1200,  # 20 minutes
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        assert config.fps == 0.25  # 10-20 min should be 0.25 FPS
        assert config.frames_analyzed > 0

    def test_very_long_video_fps(self, calculator):
        """Test FPS for very long videos (60+ min)."""
        config = calculator.calculate_config(
            video_id="test_4",
            duration_seconds=3900,  # 65 minutes
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        assert config.fps == 0.05  # 60+ min should be 0.05 FPS (extreme optimization)

    def test_critical_risk_tier_multiplier(self, calculator):
        """Test CRITICAL risk tier gets 2x FPS."""
        config = calculator.calculate_config(
            video_id="test_5",
            duration_seconds=300,
            risk_tier="CRITICAL",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # CRITICAL = 2.0x multiplier, 5min base = 0.5, so 0.5 * 2.0 = 1.0
        assert config.fps == 1.0

    def test_high_risk_tier_multiplier(self, calculator):
        """Test HIGH risk tier gets 1.5x FPS."""
        config = calculator.calculate_config(
            video_id="test_6",
            duration_seconds=300,
            risk_tier="HIGH",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # HIGH = 1.5x multiplier, 5min base = 0.5, so 0.5 * 1.5 = 0.75
        assert config.fps == 0.75

    def test_low_risk_tier_multiplier(self, calculator):
        """Test LOW risk tier gets 0.75x FPS."""
        config = calculator.calculate_config(
            video_id="test_7",
            duration_seconds=300,
            risk_tier="LOW",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # LOW = 0.75x multiplier, 5min base = 0.5, so 0.5 * 0.75 = 0.375
        assert config.fps == 0.375

    def test_very_low_risk_tier_multiplier(self, calculator):
        """Test VERY_LOW risk tier gets 0.5x FPS."""
        config = calculator.calculate_config(
            video_id="test_8",
            duration_seconds=300,
            risk_tier="VERY_LOW",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # VERY_LOW = 0.5x multiplier, 5min base = 0.5, so 0.5 * 0.5 = 0.25
        assert config.fps == 0.25

    def test_budget_pressure_adjustment(self, calculator):
        """Test FPS reduction when budget is low."""
        # Low budget scenario
        config_low = calculator.calculate_config(
            video_id="test_9",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=5.0,  # Only $5 left
            queue_size=100,
        )

        # Normal budget scenario
        config_normal = calculator.calculate_config(
            video_id="test_10",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # Low budget should have lower FPS
        assert config_low.fps <= config_normal.fps

    def test_offset_calculation_short_video(self, calculator):
        """Test offset calculation for short videos."""
        config = calculator.calculate_config(
            video_id="test_11",
            duration_seconds=30,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # Very short videos should have no offsets
        assert config.start_offset_seconds == 0
        assert config.end_offset_seconds == 30

    def test_offset_calculation_medium_video(self, calculator):
        """Test offset calculation for medium videos."""
        config = calculator.calculate_config(
            video_id="test_12",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # 5-10 min videos should skip 10s intro/outro
        assert config.start_offset_seconds == 10
        assert config.end_offset_seconds == 290
        assert config.effective_duration_seconds == 280

    def test_offset_calculation_long_video(self, calculator):
        """Test offset calculation for long videos."""
        config = calculator.calculate_config(
            video_id="test_13",
            duration_seconds=1800,  # 30 minutes
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # 30+ min videos should skip 30s intro, 60s outro
        assert config.start_offset_seconds == 30
        assert config.end_offset_seconds == 1740

    def test_cost_estimation_accuracy(self, calculator):
        """Test that cost estimation is reasonable."""
        config = calculator.calculate_config(
            video_id="test_14",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # 5 min video at 0.5 FPS should cost around $0.008
        assert 0.005 <= config.estimated_cost_usd <= 0.015
        assert config.estimated_input_tokens > 0
        assert config.estimated_output_tokens == 1000  # Fixed estimate

    def test_frames_analyzed_calculation(self, calculator):
        """Test that frames analyzed is calculated correctly."""
        config = calculator.calculate_config(
            video_id="test_15",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        # 5 min = 300s, offsets = 280s effective, 0.5 fps = 140 frames
        expected_frames = int(0.5 * 280)
        assert config.frames_analyzed == expected_frames

    def test_fps_clamping(self, calculator):
        """Test that FPS is clamped to 0.05-1.0 range."""
        # Test with extreme multipliers that could exceed bounds
        config_high = calculator.calculate_config(
            video_id="test_16",
            duration_seconds=60,  # Short video
            risk_tier="CRITICAL",  # 2x multiplier
            budget_remaining_usd=260.0,
            queue_size=1,
        )

        # Should not exceed 1.0 FPS
        assert config_high.fps <= 1.0

        config_low = calculator.calculate_config(
            video_id="test_17",
            duration_seconds=7200,  # 2 hours
            risk_tier="VERY_LOW",  # 0.5x multiplier
            budget_remaining_usd=10.0,  # Low budget
            queue_size=1000,
        )

        # Should not go below 0.05 FPS
        assert config_low.fps >= 0.05

    def test_media_resolution_always_low(self, calculator):
        """Test that media resolution is always set to low."""
        configs = [
            calculator.calculate_config(
                video_id=f"test_{i}",
                duration_seconds=d,
                risk_tier=tier,
                budget_remaining_usd=260.0,
                queue_size=100,
            )
            for i, (d, tier) in enumerate(
                [(60, "CRITICAL"), (300, "HIGH"), (1800, "LOW")]
            )
        ]

        for config in configs:
            assert config.media_resolution == "low"

    def test_estimate_videos_in_budget(self, calculator):
        """Test budget capacity estimation."""
        # With $260 budget and avg 5min videos
        videos = calculator.estimate_videos_in_budget(
            budget_usd=260.0, avg_duration_seconds=300
        )

        # Should be able to analyze many videos (20k-30k range)
        assert videos > 10000  # At least 10k videos
        assert videos < 50000  # But not unrealistic

    def test_zero_duration_video(self, calculator):
        """Test handling of zero duration (edge case)."""
        with pytest.raises(Exception):
            calculator.calculate_config(
                video_id="test_zero",
                duration_seconds=0,
                risk_tier="MEDIUM",
                budget_remaining_usd=260.0,
                queue_size=100,
            )

    def test_consistent_results(self, calculator):
        """Test that same inputs produce same outputs."""
        config1 = calculator.calculate_config(
            video_id="test_consistent",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        config2 = calculator.calculate_config(
            video_id="test_consistent",
            duration_seconds=300,
            risk_tier="MEDIUM",
            budget_remaining_usd=260.0,
            queue_size=100,
        )

        assert config1.fps == config2.fps
        assert config1.estimated_cost_usd == config2.estimated_cost_usd
        assert config1.frames_analyzed == config2.frames_analyzed
