"""Process and store vision analysis results.

This module handles:
- Storing results in Firestore
- Exporting to BigQuery for analytics
- Publishing feedback to risk-analyzer
- Alerting on high-confidence infringements
"""

import json
import logging
from datetime import datetime, timezone

from google.cloud import firestore, bigquery, pubsub_v1

from ..config import settings
from ..models import VisionAnalysisResult, FeedbackMessage

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Process and distribute analysis results."""

    def __init__(
        self,
        firestore_client: firestore.Client,
        bigquery_client: bigquery.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
    ):
        """
        Initialize result processor.

        Args:
            firestore_client: Firestore client
            bigquery_client: BigQuery client
            pubsub_publisher: PubSub publisher client
        """
        self.firestore = firestore_client
        self.bigquery = bigquery_client
        self.publisher = pubsub_publisher

        self.videos_collection = settings.firestore_videos_collection
        self.feedback_topic = settings.pubsub_feedback_topic
        self.hourly_stats_collection = "hourly_stats"

        # Construct topic path
        self.feedback_topic_path = self.publisher.topic_path(
            settings.gcp_project_id, self.feedback_topic
        )

    def _increment_hourly_stat(self, stat_type: str, timestamp: datetime | None = None, increment: int = 1, cost_usd: float = 0.0, processing_time: float = 0.0):
        """
        Atomically increment (or decrement) hourly stats counter in Firestore.

        Args:
            stat_type: Type of stat to increment ("analyses", "infringements")
            timestamp: Timestamp to use (defaults to now)
            increment: Amount to increment (can be negative for decrement)
            cost_usd: Cost in USD to add to total_cost_usd
            processing_time: Processing time in seconds to add to total_processing_time
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)

            # Round to hour
            hour = timestamp.replace(minute=0, second=0, microsecond=0)
            hour_key = hour.strftime("%Y-%m-%d_%H")  # e.g., "2025-11-07_10"

            stats_ref = self.firestore.collection(self.hourly_stats_collection).document(hour_key)

            # Atomic increment (supports negative values for decrement)
            update_data = {
                "hour": hour,
                stat_type: firestore.Increment(increment),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

            # Add cost and processing time if provided
            if cost_usd > 0:
                update_data["total_cost_usd"] = firestore.Increment(cost_usd)
            if processing_time > 0:
                update_data["total_processing_time"] = firestore.Increment(processing_time)

            stats_ref.set(update_data, merge=True)

        except Exception as e:
            # Don't fail the main operation if stats update fails
            logger.warning(f"Failed to increment hourly stat {stat_type}: {e}")

        logger.info("Result processor initialized")

    async def _update_system_stats(self, has_infringement: bool):
        """
        Atomically increment global system stats counters.

        This provides O(1) lookups for dashboard metrics without expensive queries.

        Args:
            has_infringement: Whether this analysis found an infringement
        """
        try:
            stats_ref = self.firestore.collection("system_stats").document("global")

            # Atomic increments - always thread-safe and efficient
            update_data = {
                "total_analyzed": firestore.Increment(1),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

            if has_infringement:
                update_data["total_infringements"] = firestore.Increment(1)

            stats_ref.set(update_data, merge=True)

            logger.debug(f"Updated system stats: +1 analyzed, infringement={has_infringement}")

        except Exception as e:
            # Don't fail the main operation if stats update fails
            logger.warning(f"Failed to update system stats: {e}")

    async def process_result(self, result: VisionAnalysisResult, channel_id: str = None, view_count: int = 0):
        """
        Process analysis result through all channels.

        Args:
            result: Complete analysis result
            channel_id: Channel ID for feedback (optional, will fetch if not provided)
            view_count: View count for channel tracking (optional, will fetch if not provided)

        Raises:
            Exception: If processing fails
        """
        # Check if any IP has infringement
        has_infringement = any(ip.contains_infringement for ip in result.analysis.ip_results)
        max_likelihood = max((ip.infringement_likelihood for ip in result.analysis.ip_results), default=0)

        logger.info(
            f"Processing result for video {result.video_id}: "
            f"ips={len(result.analysis.ip_results)}, "
            f"infringement={has_infringement}, "
            f"action={result.analysis.overall_recommendation}"
        )

        try:
            # 1. Fetch video document FIRST to check previous state (before updating)
            doc_ref = self.firestore.collection("videos").document(result.video_id)
            video_doc = doc_ref.get()

            # Determine if this is a re-scan
            was_previously_analyzed = False
            previous_had_infringement = None

            if video_doc.exists:
                video_data = video_doc.to_dict()
                was_previously_analyzed = video_data.get("status") == "analyzed"

                # Get previous infringement status if it was analyzed before
                if was_previously_analyzed:
                    previous_analysis = video_data.get("analysis", {})
                    if isinstance(previous_analysis, dict):
                        previous_had_infringement = previous_analysis.get("contains_infringement", False)

                # Get channel_id and view_count if not provided
                if not channel_id:
                    channel_id = video_data.get("channel_id")
                    view_count = video_data.get("view_count", 0)

            # 2. Now update the document with new analysis
            doc_ref.update({
                "analysis": {
                    "analyzed_at": result.analyzed_at,
                    "gemini_model": result.gemini_model,
                    "contains_infringement": has_infringement,
                    "max_likelihood": max_likelihood,
                    "overall_recommendation": result.analysis.overall_recommendation,
                    "overall_notes": result.analysis.overall_notes,
                    "ip_results": [ip.dict() for ip in result.analysis.ip_results],
                    "cost_usd": result.metrics.cost_usd,
                },
                "status": "analyzed",
                "last_analyzed_at": result.analyzed_at,
            })

            logger.debug(f"Stored multi-IP result in Firestore: {result.video_id}")

            # 3. Publish feedback to risk-analyzer (always, even if no infringement)
            # Risk analyzer needs to know about all results to update channel reputation
            if channel_id:
                await self._publish_feedback(result, channel_id)
            else:
                logger.warning(f"No channel_id available for video {result.video_id}, skipping feedback")

            # 4. Update global system stats (O(1) atomic increment)
            await self._update_system_stats(has_infringement)

            # 5. Update hourly stats for Activity Timeline
            if was_previously_analyzed and previous_had_infringement is not None:
                # Re-scan: adjust counters if infringement status changed
                if previous_had_infringement and not has_infringement:
                    # Was infringement, now cleared - decrement infringements
                    self._increment_hourly_stat("infringements", timestamp=result.analyzed_at, increment=-1)
                    logger.debug(f"Hourly stats: video {result.video_id} reclassified from infringement to cleared")
                elif not previous_had_infringement and has_infringement:
                    # Was cleared, now infringement - increment infringements
                    self._increment_hourly_stat("infringements", timestamp=result.analyzed_at)
                    logger.debug(f"Hourly stats: video {result.video_id} reclassified from cleared to infringement")
                # else: same result, no change to hourly stats
            else:
                # First-time analysis: increment both analyses and infringements (if applicable)
                self._increment_hourly_stat("analyses", timestamp=result.analyzed_at)
                if has_infringement:
                    self._increment_hourly_stat("infringements", timestamp=result.analyzed_at)

            # 6. ALWAYS update channel stats (both clean and infringing videos)
            await self._update_channel_scan_stats(channel_id, has_infringement, view_count, result.video_id)

            # 7. Update infringement tracking if violation found
            if has_infringement:
                await self._update_channel_infringement_tracking(result, channel_id, view_count)

                # 8. Alert on high confidence infringements
                if max_likelihood >= 80:
                    await self._alert_high_confidence_infringement(result)

            # Note: BigQuery export removed - not needed for core feedback loop
            # Results are already stored in Firestore which is sufficient for analytics

            logger.info(f"Result processing complete for video {result.video_id}")

        except Exception as e:
            logger.error(f"Failed to process result for video {result.video_id}: {e}")
            raise

    async def _store_in_firestore(self, result: VisionAnalysisResult):
        """
        Store result in Firestore videos collection.

        Args:
            result: Analysis result
        """
        try:
            doc_ref = self.firestore.collection(self.videos_collection).document(
                result.video_id
            )

            # Update document with analysis results
            update_data = {
                "vision_analysis": {
                    "analyzed_at": result.analyzed_at,
                    "gemini_model": result.gemini_model,
                    "contains_infringement": result.analysis.contains_infringement,
                    "confidence_score": result.analysis.confidence_score,
                    "infringement_type": result.analysis.infringement_type,
                    "characters_detected": [
                        {
                            "name": char.name,
                            "screen_time_seconds": char.screen_time_seconds,
                            "prominence": char.prominence,
                        }
                        for char in result.analysis.characters_detected
                    ],
                    "recommended_action": result.analysis.recommended_action,
                    "cost_usd": result.metrics.cost_usd,
                    "processing_time_seconds": result.metrics.processing_time_seconds,
                    "full_analysis": result.analysis.dict(),
                },
                "status": "analyzed",  # Video has been analyzed
                "last_analyzed_at": result.analyzed_at,
            }

            doc_ref.update(update_data)

            # Increment hourly stats with cost and processing time
            self._increment_hourly_stat(
                "analyses",
                timestamp=result.analyzed_at,
                cost_usd=result.metrics.cost_usd,
                processing_time=result.metrics.processing_time_seconds
            )
            if result.analysis.contains_infringement:
                self._increment_hourly_stat("infringements", timestamp=result.analyzed_at)

            logger.debug(f"Stored result in Firestore: {result.video_id}")

        except Exception as e:
            logger.error(f"Failed to store in Firestore: {e}")
            raise

    async def _export_to_bigquery(self, result: VisionAnalysisResult):
        """
        Export result to BigQuery for analytics.

        Args:
            result: Analysis result
        """
        try:
            table_id = f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_results_table}"

            # Calculate overall metrics from IP results
            has_infringement = any(ip.contains_infringement for ip in result.analysis.ip_results)
            max_likelihood = max((ip.infringement_likelihood for ip in result.analysis.ip_results), default=0)

            # Collect all characters
            all_characters = []
            for ip in result.analysis.ip_results:
                for char in ip.characters_detected:
                    all_characters.append({
                        "name": char.name,
                        "screen_time_seconds": getattr(char, 'screen_time_seconds', 0),
                        "prominence": getattr(char, 'prominence', 'unknown'),
                    })

            # Collect AI tools
            all_ai_tools = []
            is_ai_generated = False
            for ip in result.analysis.ip_results:
                if ip.is_ai_generated:
                    is_ai_generated = True
                all_ai_tools.extend(ip.ai_tools_detected)
            all_ai_tools = list(set(all_ai_tools))  # Deduplicate

            # Prepare row data (multi-IP format)
            row = {
                "video_id": result.video_id,
                "analyzed_at": result.analyzed_at.isoformat(),
                "gemini_model": result.gemini_model,
                # Overall analysis fields
                "contains_infringement": has_infringement,
                "confidence_score": max_likelihood,
                "infringement_type": result.analysis.ip_results[0].content_type if result.analysis.ip_results else "none",
                "recommended_action": result.analysis.overall_recommendation,
                # AI detection
                "is_ai_generated": is_ai_generated,
                "ai_confidence": max_likelihood if is_ai_generated else 0,
                "ai_tools_detected": all_ai_tools,
                # Characters
                "characters_detected": json.dumps(all_characters),
                # Metrics
                "input_tokens": result.metrics.input_tokens,
                "output_tokens": result.metrics.output_tokens,
                "cost_usd": result.metrics.cost_usd,
                "processing_time_seconds": result.metrics.processing_time_seconds,
                "frames_analyzed": result.metrics.frames_analyzed,
                "fps_used": result.metrics.fps_used,
                # Config
                "config_used": json.dumps(result.config_used),
                # Full analysis JSON (multi-IP)
                "full_analysis_json": json.dumps(result.analysis.dict()),
            }

            # Insert row
            errors = self.bigquery.insert_rows_json(table_id, [row])

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                raise Exception(f"Failed to insert to BigQuery: {errors}")

            logger.debug(f"Exported result to BigQuery: {result.video_id}")

        except Exception as e:
            logger.error(f"Failed to export to BigQuery: {e}")
            # Don't raise - BigQuery is for analytics, not critical path
            # Log error but continue

    async def _publish_feedback(self, result: VisionAnalysisResult, channel_id: str):
        """
        Publish feedback to risk-analyzer for learning.

        Args:
            result: Analysis result
            channel_id: Channel ID for the video
        """
        try:
            # Extract character names from all IP results
            character_names = []
            for ip_result in result.analysis.ip_results:
                for char in ip_result.characters_detected:
                    if char.name not in character_names:
                        character_names.append(char.name)

            # Get overall infringement status and likelihood
            has_infringement = any(ip.contains_infringement for ip in result.analysis.ip_results)
            max_likelihood = max((ip.infringement_likelihood for ip in result.analysis.ip_results), default=0)

            # Build feedback message
            feedback = FeedbackMessage(
                video_id=result.video_id,
                channel_id=channel_id,
                contains_infringement=has_infringement,
                confidence_score=max_likelihood,  # Use infringement_likelihood as confidence
                infringement_type=result.analysis.ip_results[0].content_type if result.analysis.ip_results else "none",
                characters_found=character_names,
                analysis_cost_usd=result.metrics.cost_usd,
                analyzed_at=result.analyzed_at,
            )

            # Publish to PubSub
            message_data = feedback.json().encode("utf-8")
            future = self.publisher.publish(self.feedback_topic_path, message_data)
            message_id = future.result()

            logger.info(
                f"Published feedback for video {result.video_id} (channel {channel_id}): "
                f"message_id={message_id}, infringement={has_infringement}, "
                f"likelihood={max_likelihood}"
            )

        except Exception as e:
            logger.error(f"Failed to publish feedback: {e}")
            # Don't raise - feedback is important but not critical
            # Log error but continue

    async def _update_channel_scan_stats(self, channel_id: str, has_infringement: bool, view_count: int, video_id: str = None):
        """
        Update channel scan statistics (ALWAYS called, regardless of infringement).

        This increments videos_scanned counter which is used by the risk calculator
        to LOWER risk for channels with many clean scans.

        IMPORTANT: For re-scans, decrements old classification and increments new one.

        Args:
            channel_id: Channel ID
            has_infringement: Whether this video had an infringement
            view_count: Current view count of the video
            video_id: Video ID (used to check previous classification)
        """
        try:
            if not channel_id:
                logger.warning(f"No channel_id provided, cannot update channel stats")
                return

            # Check if this is a re-scan (video was already analyzed)
            was_previously_analyzed = False
            previous_had_infringement = None

            if video_id:
                video_ref = self.firestore.collection("videos").document(video_id)
                video_doc = video_ref.get()
                if video_doc.exists:
                    video_data = video_doc.to_dict()
                    if video_data.get("status") == "analyzed":
                        # Video was analyzed before
                        was_previously_analyzed = True
                        # Check what the previous result was
                        analysis = video_data.get("analysis", {})
                        if isinstance(analysis, dict):
                            previous_had_infringement = analysis.get("contains_infringement", False)

            # Update channel document
            channel_ref = self.firestore.collection("channels").document(channel_id)

            update_data = {
                "last_scanned_at": firestore.SERVER_TIMESTAMP,
            }

            if was_previously_analyzed and previous_had_infringement is not None:
                # Re-scan: decrement old classification, increment new one
                if previous_had_infringement and not has_infringement:
                    # Was infringement, now cleared
                    update_data["confirmed_infringements"] = firestore.Increment(-1)
                    update_data["videos_cleared"] = firestore.Increment(1)
                    logger.info(f"Video {video_id} reclassified: infringement → cleared")
                elif not previous_had_infringement and has_infringement:
                    # Was cleared, now infringement
                    update_data["videos_cleared"] = firestore.Increment(-1)
                    update_data["confirmed_infringements"] = firestore.Increment(1)
                    logger.info(f"Video {video_id} reclassified: cleared → infringement")
                else:
                    # Same classification - no change needed
                    logger.debug(f"Video {video_id} re-analyzed with same result: infringement={has_infringement}")
            else:
                # First-time scan: increment videos_scanned and classification
                update_data["videos_scanned"] = firestore.Increment(1)

                if has_infringement:
                    update_data["confirmed_infringements"] = firestore.Increment(1)
                else:
                    update_data["videos_cleared"] = firestore.Increment(1)

            channel_ref.update(update_data)

            logger.info(
                f"Updated channel {channel_id} scan stats: infringement={has_infringement}, "
                f"was_rescan={was_previously_analyzed}"
            )

        except Exception as e:
            logger.error(f"Failed to update channel scan stats: {e}")
            # Don't raise - stats tracking is important but not critical

    async def _update_channel_infringement_tracking(self, result: VisionAnalysisResult, channel_id: str, view_count: int):
        """
        Update channel metadata with infringement information.

        This enables the viral snowball discovery to find channels with confirmed infringements.

        Args:
            result: Analysis result with infringement
            channel_id: Channel ID
            view_count: Current view count of the video
        """
        try:
            if not channel_id:
                logger.warning(f"No channel_id provided, cannot update channel tracking")
                return

            # Update channel document
            channel_ref = self.firestore.collection("channels").document(channel_id)

            # Use Firestore transaction to safely update counters
            channel_ref.update({
                "has_infringements": True,
                "infringing_videos_count": firestore.Increment(1),
                "total_infringing_views": firestore.Increment(view_count),
                "last_infringement_date": firestore.SERVER_TIMESTAMP,
                "infringing_video_ids": firestore.ArrayUnion([result.video_id]),
            })

            logger.info(
                f"Updated channel {channel_id} infringement tracking: "
                f"+1 infringement, +{view_count:,} views"
            )

        except Exception as e:
            logger.error(f"Failed to update channel infringement tracking: {e}")
            # Don't raise - channel tracking is important but not critical
            # Log error but continue

    async def _alert_high_confidence_infringement(self, result: VisionAnalysisResult):
        """
        Alert on high-confidence infringement detection.

        Args:
            result: Analysis result
        """
        # Get max likelihood from IP results
        max_likelihood = max((ip.infringement_likelihood for ip in result.analysis.ip_results), default=0)

        # Get all detected characters
        all_characters = []
        for ip in result.analysis.ip_results:
            for char in ip.characters_detected:
                if char.name not in all_characters:
                    all_characters.append(char.name)

        logger.warning(
            f"🚨 HIGH CONFIDENCE INFRINGEMENT DETECTED 🚨\n"
            f"Video ID: {result.video_id}\n"
            f"Infringement Likelihood: {max_likelihood}%\n"
            f"IPs Affected: {len(result.analysis.ip_results)}\n"
            f"Overall Action: {result.analysis.overall_recommendation}\n"
            f"Characters: {all_characters}\n"
            f"Cost: ${result.metrics.cost_usd:.4f}"
        )

        # TODO: Send to alerting system (email, Slack, etc.)
        # For now, just log at WARNING level
