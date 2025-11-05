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

        # Construct topic path
        self.feedback_topic_path = self.publisher.topic_path(
            settings.gcp_project_id, self.feedback_topic
        )

        logger.info("Result processor initialized")

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
            # 1. Store basic analysis in Firestore
            doc_ref = self.firestore.collection("videos").document(result.video_id)
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

            # 2. Publish feedback to risk-analyzer (always, even if no infringement)
            # Risk analyzer needs to know about all results to update channel reputation
            if not channel_id:
                # Fetch channel_id from Firestore if not provided
                video_doc = doc_ref.get()
                if video_doc.exists:
                    video_data = video_doc.to_dict()
                    channel_id = video_data.get("channel_id")
                    view_count = video_data.get("view_count", 0)

            if channel_id:
                await self._publish_feedback(result, channel_id)
            else:
                logger.warning(f"No channel_id available for video {result.video_id}, skipping feedback")

            # 3. Update channel tracking if infringement found
            if has_infringement:
                await self._update_channel_infringement_tracking(result, channel_id, view_count)

                # 4. Alert on high confidence infringements
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
