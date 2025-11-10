"""Tests for result_processor.py"""

import pytest
from unittest.mock import patch
from datetime import datetime, UTC
from app.core.result_processor import ResultProcessor
from app.models import (
    VisionAnalysisResult,
    GeminiAnalysisResult,
    AnalysisMetrics,
    AIGeneratedAnalysis,
    CopyrightAssessment,
    FairUseFactors,
    VideoCharacteristics,
)


class TestResultProcessor:
    """Test ResultProcessor class."""

    @pytest.fixture
    def processor(self, mock_firestore, mock_bigquery, mock_pubsub):
        """Create result processor instance."""
        return ResultProcessor(mock_firestore, mock_bigquery, mock_pubsub)

    @pytest.fixture
    def sample_result(self):
        """Create sample analysis result."""
        return VisionAnalysisResult(
            video_id="test_123",
            analyzed_at=datetime.now(UTC),
            gemini_model="gemini-2.5-flash",
            analysis=GeminiAnalysisResult(
                contains_infringement=True,
                confidence_score=85.0,
                infringement_type="ai_clips",
                ai_generated=AIGeneratedAnalysis(
                    is_ai=True,
                    confidence=90.0,
                    tools_detected=["Sora", "Runway"],
                    evidence="Watermark at 0:05",
                ),
                characters_detected=[],
                copyright_assessment=CopyrightAssessment(
                    infringement_likelihood=80.0,
                    reasoning="Test reasoning",
                    fair_use_applies=False,
                    fair_use_factors=FairUseFactors(
                        purpose="commercial",
                        nature="creative_work",
                        amount_used="substantial",
                        market_effect="high",
                    ),
                ),
                video_characteristics=VideoCharacteristics(
                    duration_category="medium",
                    content_type="clips",
                    monetization_detected=True,
                    professional_quality=True,
                ),
                recommended_action="monitor",
                legal_notes="Test notes",
            ),
            metrics=AnalysisMetrics(
                input_tokens=10000,
                output_tokens=500,
                total_tokens=10500,
                cost_usd=0.008,
                processing_time_seconds=5.2,
                frames_analyzed=150,
                fps_used=0.5,
            ),
            config_used={"fps": 0.5, "start_offset_seconds": 10},
        )

    @pytest.mark.asyncio
    async def test_process_result_success(
        self, processor, sample_result, mock_firestore, mock_bigquery, mock_pubsub
    ):
        """Test successful result processing."""
        await processor.process_result(sample_result)

        # Verify Firestore was called
        mock_firestore.collection().document().update.assert_called_once()

        # Verify BigQuery was called
        mock_bigquery.insert_rows_json.assert_called_once()

        # Verify PubSub was called
        mock_pubsub.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_in_firestore(
        self, processor, sample_result, mock_firestore
    ):
        """Test storing result in Firestore."""
        await processor._store_in_firestore(sample_result)

        # Verify document update was called
        update_call = mock_firestore.collection().document().update
        update_call.assert_called_once()

        # Check update data structure
        update_data = update_call.call_args[0][0]
        assert "vision_analysis" in update_data
        assert update_data["scan_status"] == "analyzed"
        assert "last_analyzed_at" in update_data

    @pytest.mark.asyncio
    async def test_export_to_bigquery(
        self, processor, sample_result, mock_bigquery
    ):
        """Test exporting result to BigQuery."""
        await processor._export_to_bigquery(sample_result)

        # Verify insert was called
        mock_bigquery.insert_rows_json.assert_called_once()

        # Check row data
        call_args = mock_bigquery.insert_rows_json.call_args
        table_id = call_args[0][0]
        rows = call_args[0][1]

        assert "vision_analysis_results" in table_id
        assert len(rows) == 1
        assert rows[0]["video_id"] == "test_123"
        assert rows[0]["contains_infringement"] is True

    @pytest.mark.asyncio
    async def test_publish_feedback(self, processor, sample_result, mock_pubsub):
        """Test publishing feedback to risk-analyzer."""
        await processor._publish_feedback(sample_result)

        # Verify publish was called
        mock_pubsub.publish.assert_called_once()

        # Check message data
        call_args = mock_pubsub.publish.call_args
        topic_path = call_args[0][0]
        message_data = call_args[0][1]

        assert "vision-feedback" in topic_path
        assert b"test_123" in message_data

    @pytest.mark.asyncio
    async def test_alert_high_confidence_infringement(
        self, processor, sample_result
    ):
        """Test alerting on high-confidence infringement."""
        sample_result.analysis.confidence_score = 95.0
        sample_result.analysis.contains_infringement = True

        # Should not raise exception
        await processor._alert_high_confidence_infringement(sample_result)

    @pytest.mark.asyncio
    async def test_process_result_calls_alert_for_high_confidence(
        self, processor, sample_result, mock_firestore, mock_bigquery, mock_pubsub
    ):
        """Test that high-confidence results trigger alerts."""
        sample_result.analysis.confidence_score = 95.0
        sample_result.analysis.contains_infringement = True

        with patch.object(
            processor, "_alert_high_confidence_infringement"
        ) as mock_alert:
            await processor.process_result(sample_result)
            mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_result_no_alert_for_low_confidence(
        self, processor, sample_result, mock_firestore, mock_bigquery, mock_pubsub
    ):
        """Test that low-confidence results don't trigger alerts."""
        sample_result.analysis.confidence_score = 50.0
        sample_result.analysis.contains_infringement = True

        with patch.object(
            processor, "_alert_high_confidence_infringement"
        ) as mock_alert:
            await processor.process_result(sample_result)
            mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_result_no_alert_when_no_infringement(
        self, processor, sample_result, mock_firestore, mock_bigquery, mock_pubsub
    ):
        """Test that non-infringement results don't trigger alerts."""
        sample_result.analysis.confidence_score = 95.0
        sample_result.analysis.contains_infringement = False

        with patch.object(
            processor, "_alert_high_confidence_infringement"
        ) as mock_alert:
            await processor.process_result(sample_result)
            mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_firestore_error_handling(
        self, processor, sample_result, mock_firestore
    ):
        """Test handling of Firestore errors."""
        mock_firestore.collection().document().update.side_effect = Exception(
            "Firestore error"
        )

        with pytest.raises(Exception):
            await processor._store_in_firestore(sample_result)

    @pytest.mark.asyncio
    async def test_bigquery_error_does_not_raise(
        self, processor, sample_result, mock_bigquery
    ):
        """Test that BigQuery errors don't break the flow."""
        mock_bigquery.insert_rows_json.side_effect = Exception("BigQuery error")

        # Should not raise (BigQuery is not critical path)
        await processor._export_to_bigquery(sample_result)

    @pytest.mark.asyncio
    async def test_pubsub_error_does_not_raise(
        self, processor, sample_result, mock_pubsub
    ):
        """Test that PubSub errors don't break the flow."""
        mock_pubsub.publish.side_effect = Exception("PubSub error")

        # Should not raise (feedback is not critical path)
        await processor._publish_feedback(sample_result)

    @pytest.mark.asyncio
    async def test_process_result_continues_on_non_critical_errors(
        self, processor, sample_result, mock_firestore, mock_bigquery, mock_pubsub
    ):
        """Test that processing continues even if non-critical steps fail."""
        # BigQuery fails but doesn't raise
        mock_bigquery.insert_rows_json.side_effect = Exception("BigQuery error")

        # PubSub fails but doesn't raise
        mock_pubsub.publish.side_effect = Exception("PubSub error")

        # Should still complete without raising
        await processor.process_result(sample_result)

        # Firestore should still be called
        mock_firestore.collection().document().update.assert_called_once()

    @pytest.mark.asyncio
    async def test_bigquery_row_structure(
        self, processor, sample_result, mock_bigquery
    ):
        """Test BigQuery row has all required fields."""
        await processor._export_to_bigquery(sample_result)

        rows = mock_bigquery.insert_rows_json.call_args[0][1]
        row = rows[0]

        # Check required fields
        assert "video_id" in row
        assert "analyzed_at" in row
        assert "gemini_model" in row
        assert "contains_infringement" in row
        assert "confidence_score" in row
        assert "input_tokens" in row
        assert "cost_usd" in row
        assert "full_analysis_json" in row

    @pytest.mark.asyncio
    async def test_initialization(
        self, mock_firestore, mock_bigquery, mock_pubsub
    ):
        """Test processor initialization."""
        processor = ResultProcessor(mock_firestore, mock_bigquery, mock_pubsub)

        assert processor.firestore == mock_firestore
        assert processor.bigquery == mock_bigquery
        assert processor.publisher == mock_pubsub
