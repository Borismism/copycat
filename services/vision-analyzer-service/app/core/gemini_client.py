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

        # Initialize client with Vertex AI
        self.client = self._init_client()

        logger.info(
            f"Gemini client initialized: model={self.model_name}, "
            f"location={self.location}, project={self.project_id}"
        )

    def _init_client(self) -> genai.Client:
        """
        Initialize Gemini client with Vertex AI authentication.

        Uses Application Default Credentials (service account in Cloud Run).
        """
        try:
            _credentials, project = default()
            logger.info(f"Using GCP project: {project}")

            client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )

            return client

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise

    async def analyze_video(
        self,
        youtube_url: str,
        prompt: str,
        fps: float,
        start_offset_seconds: int,
        end_offset_seconds: int,
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
                prompt, youtube_url, fps, start_offset_seconds, end_offset_seconds
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
        max_retries: int = 5,
    ) -> Any:
        """
        Call Gemini API with exponential backoff retry for rate limits.

        Args:
            prompt: Analysis prompt
            youtube_url: YouTube video URL
            fps: Frames per second
            start_offset: Start offset in seconds
            end_offset: End offset in seconds
            max_retries: Maximum retry attempts (default: 5)

        Returns:
            Gemini API response

        Raises:
            Exception: If all retries fail
        """
        # Exponential backoff delays: 1s, 8s, 16s, 32s, 64s
        backoff_delays = [1, 8, 16, 32, 64]

        for attempt in range(max_retries):
            try:
                # Use Part.from_uri for YouTube video (official SDK pattern)
                from google.genai.types import Part

                # Build request with simplified content structure
                # IMPORTANT: Run blocking Gemini API call in thread to avoid blocking event loop
                # This ensures health checks can still respond during long video analysis
                #
                # Use asyncio.wait_for with asyncio.to_thread for proper async timeout handling
                # The worker pool in main.py ensures proper parallelism
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.client.models.generate_content,
                            model=self.model_name,
                            contents=[
                                Part.from_uri(
                                    file_uri=youtube_url,
                                    mime_type="video/mp4",  # YouTube videos are mp4
                                ),
                                prompt,  # Text prompt as string
                            ],
                            config={
                                "temperature": settings.gemini_temperature,
                                "max_output_tokens": settings.gemini_max_output_tokens,
                                "response_mime_type": "application/json",  # Force JSON output
                            },
                        ),
                        timeout=900  # 15 minutes
                    )
                except asyncio.TimeoutError:
                    # Gemini API call timed out after 15 minutes
                    logger.error(
                        f"Gemini API call timed out after 900 seconds for {youtube_url}. "
                        "Video may be too long, inaccessible, or Gemini backend is having issues."
                    )
                    raise TimeoutError(
                        "Gemini API call timed out after 15 minutes - video may be inaccessible or too complex"
                    )

                # Validate response has valid JSON before returning
                try:
                    response_text = response.text
                    response_data = json.loads(response_text)

                    # Check for None values in critical boolean fields
                    has_invalid_data = False
                    if "ip_results" in response_data:
                        for ip_result in response_data["ip_results"]:
                            if ip_result.get("fair_use_applies") is None or ip_result.get("is_ai_generated") is None:
                                has_invalid_data = True
                                break

                    if has_invalid_data and attempt < max_retries - 1:
                        logger.warning(
                            f"Gemini returned invalid data (None for boolean fields), "
                            f"retrying (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(2)  # Short delay before retry
                        continue

                    # Also try to validate with Pydantic to catch schema issues early
                    try:
                        # Fix None values before validation
                        if "ip_results" in response_data:
                            for ip_result in response_data["ip_results"]:
                                if ip_result.get("fair_use_applies") is None:
                                    ip_result["fair_use_applies"] = False
                                if ip_result.get("is_ai_generated") is None:
                                    ip_result["is_ai_generated"] = False

                        # Try to create the model - if this fails, retry
                        from app.models import GeminiAnalysisResult
                        GeminiAnalysisResult(**response_data)

                    except Exception as validation_error:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Gemini response failed validation: {validation_error}, "
                                f"retrying (attempt {attempt + 1}/{max_retries})"
                            )
                            logger.debug(f"Invalid response data: {json.dumps(response_data, indent=2)}")
                            await asyncio.sleep(2)  # Short delay before retry
                            continue
                        else:
                            # Last attempt - let it fail in _parse_response with full error details
                            pass

                except (json.JSONDecodeError, KeyError):
                    # If we can't validate, let the _parse_response handle it
                    pass

                return response

            except google_exceptions.ResourceExhausted:
                # Rate limit hit
                if attempt < max_retries - 1:
                    wait_time = backoff_delays[attempt]
                    logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {max_retries} retries")
                    raise

            except google_exceptions.PermissionDenied as e:
                # Video is not accessible (private, restricted, or requires ownership)
                logger.warning(f"Video not accessible (PERMISSION_DENIED): {youtube_url} - {e}")
                # Raise a specific exception that the caller can catch and skip
                raise ValueError(f"PERMISSION_DENIED: Video not accessible - {e}") from e

            except Exception as e:
                # Check if error message contains PERMISSION_DENIED (in case it's wrapped)
                error_str = str(e)
                if "PERMISSION_DENIED" in error_str or "not owned by the user" in error_str:
                    logger.warning(f"Video not accessible (permission error): {youtube_url} - {e}")
                    raise ValueError(f"PERMISSION_DENIED: Video not accessible - {e}") from e

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
            logger.debug(f"Response text: {response_text}")
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
