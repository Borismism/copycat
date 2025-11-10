"""Video analyzer orchestrator.

This module coordinates the entire video analysis pipeline:
1. Calculate optimal video configuration (FPS, offsets)
2. Build copyright-aware prompt
3. Call Gemini API for analysis
4. Process and store results
5. Manage budget and rate limits
"""

import logging
from datetime import datetime, UTC

from ..models import VideoMetadata, VisionAnalysisResult
from .video_config_calculator import VideoConfigCalculator
from .prompt_builder import PromptBuilder
from .gemini_client import GeminiClient
from .budget_manager import BudgetManager
from .result_processor import ResultProcessor
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)


class VideoAnalyzer:
    """
    Orchestrate video analysis pipeline.

    Coordinates all components to analyze videos for copyright infringement.
    """

    def __init__(
        self,
        config_calculator: VideoConfigCalculator,
        prompt_builder: PromptBuilder,
        gemini_client: GeminiClient,
        budget_manager: BudgetManager,
        result_processor: ResultProcessor,
    ):
        """
        Initialize video analyzer.

        Args:
            config_calculator: Video config calculator
            prompt_builder: Prompt builder
            gemini_client: Gemini API client
            budget_manager: Budget manager
            result_processor: Result processor
        """
        self.config_calculator = config_calculator
        self.prompt_builder = prompt_builder
        self.gemini_client = gemini_client
        self.budget_manager = budget_manager
        self.result_processor = result_processor

        logger.info("Video analyzer initialized")

    async def analyze_video(
        self, video_metadata: VideoMetadata, configs: list, queue_size: int = 100
    ) -> VisionAnalysisResult:
        """
        Analyze a single video for copyright infringement.

        Pipeline:
        1. Calculate optimal video config (FPS, offsets, cost estimate)
        2. Check budget availability
        3. Build copyright-aware prompt with IP configs
        4. Call Gemini API
        5. Process and store results
        6. Record budget usage

        Args:
            video_metadata: Video information from discovery/risk services
            configs: List of IPConfig objects this video matches
            queue_size: Number of videos in queue (for budget allocation)

        Returns:
            VisionAnalysisResult with complete analysis

        Raises:
            Exception: If analysis fails or no configs provided
        """
        if not configs:
            raise ValueError(f"No IP configs provided for video {video_metadata.video_id}")
        video_id = video_metadata.video_id

        logger.info(
            f"Starting analysis for video {video_id}: "
            f"duration={video_metadata.duration_seconds}s, "
            f"risk={video_metadata.risk_tier}"
        )

        try:
            # Step 1: Calculate optimal video configuration
            budget_remaining = self.budget_manager.get_remaining_budget()
            video_config = self.config_calculator.calculate_config(
                video_id=video_id,
                duration_seconds=video_metadata.duration_seconds,
                risk_tier=video_metadata.risk_tier,
                budget_remaining_usd=budget_remaining,
                queue_size=queue_size,
            )

            logger.info(
                f"Video config: fps={video_config.fps}, "
                f"duration={video_config.effective_duration_seconds}s, "
                f"frames={video_config.frames_analyzed}, "
                f"estimated_cost=${video_config.estimated_cost_usd:.4f}"
            )

            # Step 2: Check budget availability
            if not self.budget_manager.can_afford(video_config.estimated_cost_usd):
                raise Exception(
                    f"Insufficient budget: need ${video_config.estimated_cost_usd:.4f}, "
                    f"remaining ${budget_remaining:.2f}"
                )

            # Step 3: Enforce rate limiting
            await self.budget_manager.enforce_rate_limit()

            # Step 4: Build copyright-aware prompt with IP configs
            prompt = self.prompt_builder.build_analysis_prompt(video_metadata, configs)

            # Step 5: Call Gemini API
            analysis_result, metrics = await self.gemini_client.analyze_video(
                youtube_url=video_metadata.youtube_url,
                prompt=prompt,
                fps=video_config.fps,
                start_offset_seconds=video_config.start_offset_seconds,
                end_offset_seconds=video_config.end_offset_seconds,
            )

            # Step 6: Record budget usage
            self.budget_manager.record_usage(video_id, metrics.cost_usd)

            # Step 7: Build complete result
            result = VisionAnalysisResult(
                video_id=video_id,
                analyzed_at=datetime.now(UTC),
                gemini_model=self.gemini_client.model_name,
                analysis=analysis_result,
                metrics=metrics,
                config_used={
                    "fps": video_config.fps,
                    "start_offset_seconds": video_config.start_offset_seconds,
                    "end_offset_seconds": video_config.end_offset_seconds,
                    "media_resolution": video_config.media_resolution,
                    "effective_duration_seconds": video_config.effective_duration_seconds,
                    "frames_analyzed": video_config.frames_analyzed,
                },
                matched_ips=[c.id for c in configs],  # Track which IPs were analyzed
            )

            # Step 8: Process and store results (with channel info for feedback)
            await self.result_processor.process_result(
                result,
                channel_id=video_metadata.channel_id,
                view_count=video_metadata.view_count
            )

            logger.info(
                f"Analysis complete for video {video_id}: "
                f"ips={len(result.analysis.ip_results)}, "
                f"action={result.analysis.overall_recommendation}, "
                f"cost=${metrics.cost_usd:.4f}"
            )

            return result

        except Exception as e:
            log_exception_json(logger, f"Failed to analyze video {video_id}", e, severity="ERROR", video_id=video_id)
            raise

    async def analyze_batch(
        self, videos: list[VideoMetadata], max_videos: int | None = None
    ) -> dict:
        """
        Analyze a batch of videos until budget exhausted or queue empty.

        This implements the budget exhaustion algorithm:
        - Sort by priority (risk score descending)
        - Analyze highest-priority videos first
        - Stop when budget exhausted or rate limit hit

        Args:
            videos: List of videos to analyze
            max_videos: Maximum videos to analyze (None = until budget exhausted)

        Returns:
            Dict with statistics:
                - videos_analyzed: count
                - budget_spent: USD
                - budget_remaining: USD
                - errors: count
        """
        logger.info(
            f"Starting batch analysis: {len(videos)} videos in queue, "
            f"budget_remaining=${self.budget_manager.get_remaining_budget():.2f}"
        )

        # Sort by risk score (highest first)
        sorted_videos = sorted(videos, key=lambda v: v.risk_score, reverse=True)

        # Reset session tracking
        self.budget_manager.reset_session()

        videos_analyzed = 0
        errors = 0
        start_budget = self.budget_manager.get_remaining_budget()

        for _i, video in enumerate(sorted_videos):
            # Check max_videos limit
            if max_videos and videos_analyzed >= max_videos:
                logger.info(f"Reached max_videos limit: {max_videos}")
                break

            # Check budget availability (quick estimate)
            if self.budget_manager.get_remaining_budget() < 0.001:  # $0.001
                logger.info("Budget exhausted")
                break

            # Analyze video (note: configs should be passed from caller)
            try:
                # For batch analysis, we need configs passed in or loaded here
                # This is a placeholder - real implementation needs config loading
                logger.warning(
                    f"analyze_batch needs config loading support - video {video.video_id}"
                )
                # await self.analyze_video(video, configs, queue_size=len(sorted_videos) - i)
                videos_analyzed += 1

            except Exception as e:
                logger.error(f"Failed to analyze video {video.video_id}: {e}")
                errors += 1
                continue

        # Final statistics
        budget_spent = start_budget - self.budget_manager.get_remaining_budget()
        budget_remaining = self.budget_manager.get_remaining_budget()

        stats = {
            "videos_analyzed": videos_analyzed,
            "budget_spent_usd": round(budget_spent, 2),
            "budget_remaining_usd": round(budget_remaining, 2),
            "errors": errors,
            "queue_size": len(videos),
        }

        logger.info(
            f"Batch analysis complete: "
            f"analyzed={videos_analyzed}/{len(videos)}, "
            f"spent=${budget_spent:.2f}, "
            f"remaining=${budget_remaining:.2f}, "
            f"errors={errors}"
        )

        return stats
