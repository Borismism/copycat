"""Gemini 2.5 Flash client for video analysis via Vertex AI.

This module provides a client for interacting with Google's Gemini 2.5 Flash model
through Vertex AI, supporting direct YouTube URL analysis.
"""

import asyncio
import json
import logging
import time
from typing import Any

from google import genai
from google.auth import default
from google.api_core import exceptions as google_exceptions

from ..config import settings
from ..models import GeminiAnalysisResult, AnalysisMetrics
from app.utils.logging_utils import log_exception_json

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Gemini 2.5 Flash via Vertex AI.

    Features:
    - Vertex AI authentication (IAM, no API keys)
    - Direct YouTube URL input
    - Structured JSON output
    - Cost tracking
    - Rate limit handling
    """

    def __init__(self):
        """Initialize Gemini client with Vertex AI authentication."""
        # Use VERTEX_AI_PROJECT_ID for production, fallback to GCP_PROJECT_ID
        import os
        self.project_id = os.getenv("VERTEX_AI_PROJECT_ID", settings.gcp_project_id)
        self.location = settings.gemini_location
        self.model_name = settings.gemini_model

        # Initialize async client with Vertex AI
        self.client = self._init_client()

        logger.info(
            f"Gemini async client initialized: model={self.model_name}, "
            f"location={self.location}, project={self.project_id}"
        )

    def _init_client(self):
        """
        Initialize Gemini async client with Vertex AI authentication.

        Uses Application Default Credentials (service account in Cloud Run).
        Returns async client via .aio property.
        """
        try:
            _credentials, project = default()
            logger.info(f"Using GCP project: {project}")

            # Create async client using .aio property
            client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            ).aio

            return client

        except Exception as e:
            logger.error(f"Failed to initialize Gemini async client: {e}")
            raise

    async def analyze_video(
        self,
        youtube_url: str,
        prompt: str,
        fps: float,
        start_offset_seconds: int,
        end_offset_seconds: int,
        video_id: str = None,
        firestore_client = None,
    ) -> tuple[GeminiAnalysisResult, AnalysisMetrics]:
        """
        Analyze a YouTube video for copyright infringement.

        Args:
            youtube_url: Full YouTube URL (e.g., https://youtube.com/watch?v=VIDEO_ID)
            prompt: Analysis prompt with legal context
            fps: Frames per second to sample
            start_offset_seconds: Skip first N seconds
            end_offset_seconds: Analyze until N seconds from start

        Returns:
            Tuple of (GeminiAnalysisResult, AnalysisMetrics)

        Raises:
            Exception: If analysis fails after retries
        """
        start_time = time.time()

        try:
            logger.info(
                f"Analyzing video: url={youtube_url}, "
                f"fps={fps}, offsets={start_offset_seconds}-{end_offset_seconds}s"
            )

            # Call Gemini 2.5 Flash
            response = await self._call_gemini_with_retry(
                prompt, youtube_url, fps, start_offset_seconds, end_offset_seconds,
                video_id, firestore_client
            )

            # Parse JSON response
            analysis_result = self._parse_response(response)

            # Calculate metrics
            processing_time = time.time() - start_time
            metrics = self._calculate_metrics(
                response, processing_time, fps, end_offset_seconds - start_offset_seconds
            )

            logger.info(
                f"Analysis complete: "
                f"ips_analyzed={len(analysis_result.ip_results)}, "
                f"recommendation={analysis_result.overall_recommendation}, "
                f"cost=${metrics.cost_usd:.4f}, "
                f"time={metrics.processing_time_seconds:.1f}s"
            )

            return analysis_result, metrics

        except Exception as e:
            log_exception_json(logger, "Video analysis failed", e, severity="ERROR")
            raise

    async def _call_gemini_with_retry(
        self,
        prompt: str,
        youtube_url: str,
        fps: float,
        start_offset: int,
        end_offset: int,
        video_id: str = None,
        firestore_client = None,
        max_retries: int = 8,
    ) -> Any:
        """
        Call Gemini API - no retry logic, let PubSub handle retries.

        Args:
            prompt: Analysis prompt
            youtube_url: YouTube video URL
            fps: Frames per second
            start_offset: Start offset in seconds
            end_offset: End offset in seconds

        Returns:
            Gemini API response

        Raises:
            Exception: On any API error
        """
        try:
            # Use Part.from_uri for YouTube video (official SDK pattern)
            from google.genai.types import Part, VideoMetadata, MediaResolution

            # Build video part with FPS and offset settings
            # CRITICAL: Without video_metadata, Gemini uses 1 FPS at default resolution
            # which causes ~1M tokens per video instead of ~30K tokens
            video_part = Part.from_uri(
                file_uri=youtube_url,
                mime_type="video/mp4",
            )
            video_part.video_metadata = VideoMetadata(
                fps=fps,
                start_offset=f"{start_offset}s",
                end_offset=f"{end_offset}s",
            )

            logger.info(
                f"Video part configured: fps={fps}, "
                f"start={start_offset}s, end={end_offset}s, resolution=LOW"
            )

            # Build request with simplified content structure
            # Using native async client for non-blocking API calls
            try:
                response = await asyncio.wait_for(
                    self.client.models.generate_content(
                        model=self.model_name,
                        contents=[
                            video_part,
                            prompt,  # Text prompt as string
                        ],
                        config={
                            "temperature": settings.gemini_temperature,
                            "max_output_tokens": settings.gemini_max_output_tokens,
                            "response_mime_type": "application/json",  # Force JSON output
                            "media_resolution": MediaResolution.MEDIA_RESOLUTION_LOW,  # 66 tokens/frame vs 258
                        },
                    ),
                    timeout=3000  # 50 minutes (CloudRun timeout is 1 hour)
                )
            except asyncio.TimeoutError:
                # Gemini API call timed out after 50 minutes
                logger.error(
                    f"Gemini API call timed out after 3000 seconds for {youtube_url}. "
                    "Video may be too long, inaccessible, or Gemini backend is having issues."
                )
                raise TimeoutError(
                    "Gemini API call timed out after 50 minutes - video may be inaccessible or too complex"
                )

            # Fix None values in response before returning
            try:
                response_text = response.text
                response_data = json.loads(response_text)

                # Fix None values in critical boolean fields
                if "ip_results" in response_data:
                    for ip_result in response_data["ip_results"]:
                        if ip_result.get("fair_use_applies") is None:
                            ip_result["fair_use_applies"] = False
                        if ip_result.get("is_ai_generated") is None:
                            ip_result["is_ai_generated"] = False

            except (json.JSONDecodeError, KeyError):
                # If we can't fix, let the _parse_response handle it
                pass

            return response

        except google_exceptions.PermissionDenied as e:
            # Video is not accessible (private, restricted, or requires ownership)
            logger.warning(f"Video not accessible (PERMISSION_DENIED): {youtube_url} - {e}")
            # Raise a specific exception that the caller can catch and skip
            raise ValueError(f"PERMISSION_DENIED: Video not accessible - {e}") from e

        except google_exceptions.ResourceExhausted as e:
            # Rate limit hit - just raise it, let PubSub retry
            logger.warning(f"⚠️  Rate limit hit (429 RESOURCE_EXHAUSTED): {e}")
            raise

        except Exception as e:
            # Check if error message contains specific errors
            error_str = str(e)
            if "PERMISSION_DENIED" in error_str or "not owned by the user" in error_str:
                logger.warning(f"Video not accessible (permission error): {youtube_url} - {e}")
                raise ValueError(f"PERMISSION_DENIED: Video not accessible - {e}") from e

            # Just raise any other exception - let the handler decide what to do
            logger.error(f"Gemini API call failed: {e}")
            raise

    def _parse_response(self, response: Any) -> GeminiAnalysisResult:
        """
        Parse Gemini response into structured model.

        Args:
            response: Raw Gemini API response

        Returns:
            GeminiAnalysisResult with validated data

        Raises:
            ValueError: If response is invalid or unparseable
        """
        try:
            # Extract text from response
            response_text = response.text

            # Parse JSON
            response_data = json.loads(response_text)

            # Fix None values that should be booleans (Gemini sometimes returns null)
            if "ip_results" in response_data:
                for ip_result in response_data["ip_results"]:
                    # Fix fair_use_applies: None -> False
                    if ip_result.get("fair_use_applies") is None:
                        logger.warning(
                            f"Gemini returned None for fair_use_applies in IP {ip_result.get('ip_id')}, "
                            "defaulting to False"
                        )
                        ip_result["fair_use_applies"] = False

                    # Fix is_ai_generated: None -> False
                    if ip_result.get("is_ai_generated") is None:
                        ip_result["is_ai_generated"] = False

            # Validate with Pydantic model
            analysis_result = GeminiAnalysisResult(**response_data)

            return analysis_result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text (first 500 chars): {response_text[:500] if response_text else 'None'}")
            logger.error(f"Response text (last 500 chars): {response_text[-500:] if response_text and len(response_text) > 500 else ''}")
            # NOTE: Gemini API occasionally returns truncated/malformed JSON with unterminated strings
            # This is a known Gemini API bug, not our fault. Mark as permanent failure.
            raise ValueError(f"Invalid JSON response from Gemini: {e}")

        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            logger.error(f"Response data that failed validation: {json.dumps(response_data, indent=2)}")
            raise

    def _calculate_metrics(
        self, response: Any, processing_time: float, fps: float, duration: int
    ) -> AnalysisMetrics:
        """
        Calculate cost and performance metrics.

        Args:
            response: Gemini API response
            processing_time: Time taken in seconds
            fps: FPS used for analysis
            duration: Effective video duration analyzed

        Returns:
            AnalysisMetrics with cost and performance data
        """
        # Extract token counts from response
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count
        output_tokens = usage.candidates_token_count
        total_tokens = input_tokens + output_tokens

        # Calculate cost (Gemini 2.5 Flash pricing)
        input_cost = (input_tokens / 1_000_000) * settings.gemini_input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * settings.gemini_output_cost_per_1m
        total_cost = input_cost + output_cost

        # Calculate frames analyzed
        frames_analyzed = int(fps * duration)

        logger.debug(
            f"Metrics: input_tokens={input_tokens}, "
            f"output_tokens={output_tokens}, "
            f"cost=${total_cost:.4f}"
        )

        return AnalysisMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=round(total_cost, 6),
            processing_time_seconds=round(processing_time, 2),
            frames_analyzed=frames_analyzed,
            fps_used=fps,
        )
