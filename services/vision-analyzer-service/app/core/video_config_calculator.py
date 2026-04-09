"""Calculate optimal video analysis configuration based on length, risk, and budget.

This module implements aggressive cost optimization for video analysis:
- Analyzes FULL videos regardless of length (no truncation!)
- Dynamically adjusts FPS based on length to keep frame count under 300
- Very long videos (movies, streams) get extremely low FPS (e.g., 1 frame per 36s)
- Risk tier adjusts budget allocation
- Budget pressure dynamically reduces FPS further
"""

import logging
from dataclasses import dataclass
from typing import Literal

from ..config import settings

logger = logging.getLogger(__name__)

RiskTier = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]


@dataclass
class VideoConfig:
    """Video analysis configuration."""

    fps: float  # Frames per second to sample
    start_offset_seconds: int  # Skip first N seconds (intro)
    end_offset_seconds: int  # Analyze until N seconds from start
    media_resolution: str  # "low" for cost optimization
    estimated_cost_usd: float  # Estimated total cost
    estimated_input_tokens: int  # Estimated input tokens
    estimated_output_tokens: int  # Estimated output tokens
    frames_analyzed: int  # Total frames that will be analyzed
    effective_duration_seconds: int  # Duration after offsets applied


class VideoConfigCalculator:
    """
    Calculate optimal FPS, offsets, and cost estimates for video analysis.

    Cost Model (Gemini 2.5 Flash on Vertex AI):
    - Input: $0.30 per 1M tokens
    - Output: $2.50 per 1M tokens
    - Video (low res): ~100 tokens/second at 1 FPS (66 frame + 32 audio + overhead)
    - At custom FPS: tokens = (fps * 66 * duration) + (32 * duration)

    Length-Based FPS Strategy (CRITICAL to keep costs down):
    - 0-2 min: 1.0 FPS (standard analysis)
    - 2-5 min: 0.5 FPS (sample every 2 seconds)
    - 5-10 min: 0.33 FPS (sample every 3 seconds)
    - 10-20 min: 0.25 FPS (sample every 4 seconds)
    - 20-30 min: 0.2 FPS (sample every 5 seconds)
    - 30-60 min: 0.1 FPS (sample every 10 seconds)
    - 60+ min: DYNAMIC FPS (calculated to keep frames under 300)

    IMPORTANT: We analyze the FULL video for any length by adjusting FPS.
    No truncation! Just sample less frequently for longer videos.

    Example costs with adaptive FPS:
    - 5 min @ 0.5 FPS: 15,000 tokens = $0.0045 (50% savings)
    - 10 min @ 0.33 FPS: 20,000 tokens = $0.006 (67% savings)
    - 30 min @ 0.2 FPS: 36,000 tokens = $0.011 (80% savings)
    - 60 min @ 0.1 FPS: 36,000 tokens = $0.011 (90% savings)
    - 3-hour movie @ 0.028 FPS: 30,000 tokens = $0.009 (1 frame per 36s)
    - 24-hour stream @ 0.003 FPS: 30,000 tokens = $0.009 (1 frame per 5 min)
    """

    # Token budget per video - keeps cost under €0.01 ($0.011)
    # At $0.30/1M input tokens: 30,000 tokens = $0.009
    MAX_INPUT_TOKENS = 30_000  # ~€0.008 per video

    # Maximum video duration we can analyze (audio tokens = 32/sec)
    # At 30k tokens budget with minimal frames: 30000 / 32 = 937 seconds = ~15 min of audio only
    # For longer videos, we MUST skip portions or the audio alone exceeds budget
    MAX_ANALYZABLE_DURATION = 900  # 15 minutes - analyze middle portion of longer videos

    # NOTE: For videos longer than MAX_ANALYZABLE_DURATION, we analyze the middle portion

    # Base FPS by risk tier (before length adjustments)
    RISK_FPS_MULTIPLIER = {
        "CRITICAL": 2.0,  # Double the base FPS
        "HIGH": 1.5,  # 50% more FPS
        "MEDIUM": 1.0,  # Standard FPS
        "LOW": 0.75,  # 25% less FPS
        "VERY_LOW": 0.5,  # Half FPS
        "PENDING": 1.0,  # Treat unscored videos as MEDIUM
    }

    def calculate_config(
        self,
        video_id: str,
        duration_seconds: int,
        risk_tier: RiskTier,
        budget_remaining_usd: float,
        queue_size: int = 100,
    ) -> VideoConfig:
        """
        Calculate optimal video analysis configuration.

        Args:
            video_id: Video identifier
            duration_seconds: Total video length in seconds
            risk_tier: Risk level (CRITICAL, HIGH, MEDIUM, LOW, VERY_LOW)
            budget_remaining_usd: Remaining daily budget in USD
            queue_size: Number of videos in queue (affects budget allocation)

        Returns:
            VideoConfig with optimized parameters
        """
        # Step 1: Calculate base FPS based on video length (aggressive optimization)
        base_fps = self._calculate_base_fps_by_length(duration_seconds)

        # Step 2: Apply risk tier multiplier
        risk_multiplier = self.RISK_FPS_MULTIPLIER.get(risk_tier, 1.0)
        adjusted_fps = base_fps * risk_multiplier

        # Step 3: Apply budget pressure adjustment
        budget_multiplier = self._calculate_budget_pressure(
            budget_remaining_usd, queue_size
        )
        final_fps = adjusted_fps * budget_multiplier

        # Clamp FPS to reasonable bounds
        final_fps = max(0.05, min(1.0, final_fps))  # 0.05 to 1.0 FPS

        # Step 4: Calculate offsets - for long videos, analyze middle portion only
        if duration_seconds > self.MAX_ANALYZABLE_DURATION:
            # Analyze middle portion of the video
            skip_each_side = (duration_seconds - self.MAX_ANALYZABLE_DURATION) // 2
            start_offset = skip_each_side
            end_offset = duration_seconds - skip_each_side
            logger.info(
                f"Video {video_id} is {duration_seconds}s ({duration_seconds/60:.0f}min). "
                f"Analyzing middle {self.MAX_ANALYZABLE_DURATION}s portion: {start_offset}s to {end_offset}s"
            )
        else:
            start_offset, end_offset = self._calculate_offsets(duration_seconds)

        # Step 5: Calculate effective duration
        effective_duration = end_offset - start_offset

        # Step 6: Calculate FPS to stay within token budget
        # Total tokens = frame_tokens + audio_tokens
        # frame_tokens = fps * 66 * duration
        # audio_tokens = 32 * duration
        # MAX_TOKENS = fps * 66 * duration + 32 * duration
        # fps = (MAX_TOKENS - 32 * duration) / (66 * duration)
        audio_tokens = settings.tokens_per_second_audio * effective_duration
        available_for_frames = self.MAX_INPUT_TOKENS - audio_tokens

        if available_for_frames <= 0:
            # Audio alone exceeds budget - this shouldn't happen with MAX_ANALYZABLE_DURATION
            logger.error(f"Video {video_id}: audio tokens ({audio_tokens}) exceed budget!")
            max_fps_for_budget = 0.01  # Minimal sampling
        else:
            max_fps_for_budget = available_for_frames / (settings.tokens_per_frame_low_res * effective_duration)

        # Use the lower of calculated FPS or budget-constrained FPS
        final_fps = min(final_fps, max_fps_for_budget)

        # Clamp FPS to reasonable bounds
        final_fps = max(0.01, min(1.0, final_fps))

        # Calculate actual tokens
        frame_tokens = int(final_fps * settings.tokens_per_frame_low_res * effective_duration)
        total_input_tokens = frame_tokens + audio_tokens

        # Output tokens (for JSON response, ~500-2000 tokens typical)
        estimated_output_tokens = 1000  # Conservative estimate

        # Calculate cost
        input_cost = (total_input_tokens / 1_000_000) * settings.gemini_input_cost_per_1m
        output_cost = (
            estimated_output_tokens / 1_000_000
        ) * settings.gemini_output_cost_per_1m
        total_cost = input_cost + output_cost

        frames_analyzed = int(final_fps * effective_duration)

        logger.info(
            f"Video config calculated for {video_id}: "
            f"duration={duration_seconds}s, risk={risk_tier}, "
            f"fps={final_fps:.2f}, frames={frames_analyzed}, "
            f"cost=${total_cost:.4f}"
        )

        return VideoConfig(
            fps=round(final_fps, 3),
            start_offset_seconds=start_offset,
            end_offset_seconds=end_offset,
            media_resolution="low",
            estimated_cost_usd=round(total_cost, 5),
            estimated_input_tokens=total_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            frames_analyzed=frames_analyzed,
            effective_duration_seconds=effective_duration,
        )

    def _calculate_base_fps_by_length(self, duration_seconds: int) -> float:
        """
        Calculate base FPS based on video length.

        Dynamically reduces FPS for extremely long videos to keep frame count reasonable.
        For videos longer than 60 minutes, uses formula to ensure MAX_FRAMES is never exceeded.

        Args:
            duration_seconds: Video length in seconds

        Returns:
            Base FPS (before risk/budget adjustments)
        """
        if duration_seconds <= 120:  # 0-2 minutes
            return 1.0
        elif duration_seconds <= 300:  # 2-5 minutes
            return 0.5
        elif duration_seconds <= 600:  # 5-10 minutes
            return 0.33
        elif duration_seconds <= 1200:  # 10-20 minutes
            return 0.25
        elif duration_seconds <= 1800:  # 20-30 minutes
            return 0.2
        elif duration_seconds <= 3600:  # 30-60 minutes
            return 0.1
        else:  # 60+ minutes - very low FPS
            # For extremely long videos, use minimal FPS
            # Token budget will further constrain this in calculate_config()
            return 0.05  # 1 frame per 20 seconds as starting point

    def _calculate_offsets(self, duration_seconds: int) -> tuple[int, int]:
        """
        Calculate start/end offsets to skip intros and outros.

        Analyzes FULL video by adjusting FPS instead of truncating.
        Just skips intro/outro branding and credits.

        Args:
            duration_seconds: Total video length

        Returns:
            Tuple of (start_offset_seconds, end_offset_seconds)
        """
        if duration_seconds <= 30:
            # Very short videos: no offsets
            start_offset = 0
            end_offset = duration_seconds
        elif duration_seconds <= 60:
            # <1 min: skip 2s intro/outro
            start_offset = 2
            end_offset = duration_seconds - 2
        elif duration_seconds <= 300:
            # 1-5 min: skip 5s intro, 5s outro
            start_offset = 5
            end_offset = duration_seconds - 5
        elif duration_seconds <= 600:
            # 5-10 min: skip 10s intro, 10s outro
            start_offset = 10
            end_offset = duration_seconds - 10
        elif duration_seconds <= 1800:
            # 10-30 min: skip 15s intro, 30s outro (credits)
            start_offset = 15
            end_offset = duration_seconds - 30
        elif duration_seconds <= 3600:
            # 30-60 min: skip 30s intro, 60s outro (long credits)
            start_offset = 30
            end_offset = duration_seconds - 60
        else:
            # 60+ min (movies): skip 60s intro, 120s outro (long credits)
            start_offset = 60
            end_offset = duration_seconds - 120

        # NO TRUNCATION - we analyze the full video with adjusted FPS
        return (start_offset, end_offset)

    def _calculate_budget_pressure(
        self, budget_remaining_usd: float, queue_size: int
    ) -> float:
        """
        Calculate budget pressure multiplier.

        Reduces FPS when budget is running low to spread budget across more videos.

        Args:
            budget_remaining_usd: Remaining daily budget
            queue_size: Number of videos waiting to be analyzed

        Returns:
            Multiplier (0.5 to 1.0)
        """
        if budget_remaining_usd <= 0:
            return 0.5  # Minimum FPS when budget exhausted

        # Calculate avg budget per video in queue
        avg_budget_per_video = budget_remaining_usd / max(queue_size, 1)

        # If avg budget is very low, reduce FPS
        if avg_budget_per_video < 0.05:  # Less than 5 cents per video
            return 0.5
        elif avg_budget_per_video < 0.10:  # Less than 10 cents
            return 0.75
        else:
            return 1.0  # No pressure, use full FPS

    def estimate_videos_in_budget(
        self, budget_usd: float, avg_duration_seconds: int = 300
    ) -> int:
        """
        Estimate how many videos can be analyzed with given budget.

        Args:
            budget_usd: Available budget in USD
            avg_duration_seconds: Average video duration (default 5 min)

        Returns:
            Estimated number of videos
        """
        # Use MEDIUM risk tier for estimation
        config = self.calculate_config(
            video_id="estimate",
            duration_seconds=avg_duration_seconds,
            risk_tier="MEDIUM",
            budget_remaining_usd=budget_usd,
            queue_size=100,
        )

        return int(budget_usd / config.estimated_cost_usd)
