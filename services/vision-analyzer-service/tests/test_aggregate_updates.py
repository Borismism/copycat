"""
Comprehensive tests for aggregate field updates in result_processor.py

Tests all scenarios for "subtract old, add new" logic across:
- Channel stats (videos_scanned, confirmed_infringements, videos_cleared)
- Channel infringement tracking (infringing_videos_count, total_infringing_views)
- Global system stats (total_analyzed, total_infringements)
- Hourly stats (analyses, infringements)
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, call
from datetime import datetime, UTC
from google.cloud import firestore

from app.core.result_processor import ResultProcessor
from app.models import (
    VisionAnalysisResult,
    GeminiAnalysisResult,
    AnalysisMetrics,
    IPAnalysisResult,
    IPCharacterDetection,
)


@pytest.fixture
def mock_firestore():
    """Create mock Firestore client with proper increment tracking."""
    mock_client = Mock()

    # Track all increment operations for assertions
    mock_client.increment_calls = []

    # Mock collection/document chain
    mock_collection = Mock()
    mock_doc_ref = Mock()

    # Track update calls
    mock_doc_ref.update_calls = []
    mock_doc_ref.set_calls = []

    def track_update(update_data):
        """Track update calls for assertions."""
        mock_doc_ref.update_calls.append(update_data)
        # Extract increment operations
        for key, value in update_data.items():
            if isinstance(value, firestore.Increment):
                mock_client.increment_calls.append((key, value._value))

    def track_set(data, merge=False):
        """Track set calls for assertions."""
        mock_doc_ref.set_calls.append((data, merge))
        # Extract increment operations from set
        for key, value in data.items():
            if isinstance(value, firestore.Increment):
                mock_client.increment_calls.append((key, value._value))

    mock_doc_ref.update = Mock(side_effect=track_update)
    mock_doc_ref.set = Mock(side_effect=track_set)

    # Mock get() for fetching previous state
    mock_doc_ref.get = Mock()

    mock_collection.document = Mock(return_value=mock_doc_ref)
    mock_client.collection = Mock(return_value=mock_collection)

    return mock_client


@pytest.fixture
def mock_bigquery():
    """Create mock BigQuery client."""
    mock = Mock()
    mock.insert_rows_json = Mock(return_value=[])  # No errors
    return mock


@pytest.fixture
def mock_pubsub():
    """Create mock PubSub client."""
    mock = Mock()
    mock.topic_path = Mock(return_value="projects/test/topics/test")

    # Mock publish to return a future
    future = Mock()
    future.result = Mock(return_value="test_message_id")
    mock.publish = Mock(return_value=future)

    return mock


@pytest.fixture
def processor(mock_firestore, mock_bigquery, mock_pubsub):
    """Create ResultProcessor instance."""
    return ResultProcessor(mock_firestore, mock_bigquery, mock_pubsub)


def create_result(video_id: str, recommendation: str, has_infringement: bool) -> VisionAnalysisResult:
    """
    Create a VisionAnalysisResult for testing.

    Args:
        video_id: Video ID
        recommendation: Overall recommendation (immediate_takedown, monitor, etc.)
        has_infringement: Whether any IP has infringement
    """
    return VisionAnalysisResult(
        video_id=video_id,
        analyzed_at=datetime.now(UTC),
        gemini_model="gemini-2.0-flash-exp",
        analysis=GeminiAnalysisResult(
            overall_recommendation=recommendation,
            overall_notes="Test notes",
            ip_results=[
                IPAnalysisResult(
                    ip_id="superman",
                    ip_name="Superman",
                    contains_infringement=has_infringement,
                    infringement_likelihood=85 if has_infringement else 10,
                    content_type="character_depiction",
                    is_ai_generated=True,
                    ai_tools_detected=["Sora"],
                    characters_detected=[
                        IPCharacterDetection(
                            name="Superman",
                            screen_time_seconds=120.0,
                            prominence="primary",
                            timestamps=["0:00", "1:00"],
                            description="Flying scene"
                        )
                    ],
                    recommended_action=recommendation,
                    reasoning="Test reasoning",
                )
            ],
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
        config_used={"fps": 0.5},
    )


def mock_video_document(exists: bool, previous_analysis: dict | None = None):
    """Create a mock video document snapshot."""
    mock_doc = Mock()
    mock_doc.exists = exists

    if exists and previous_analysis:
        mock_doc.to_dict = Mock(return_value={
            "channel_id": "test_channel",
            "view_count": 1000,
            "analysis": previous_analysis,
        })
    elif exists:
        mock_doc.to_dict = Mock(return_value={
            "channel_id": "test_channel",
            "view_count": 1000,
        })

    return mock_doc


class TestAggregateUpdates:
    """Test all aggregate field update scenarios."""

    # ===========================================
    # SCENARIO 1: First-time scan → Infringement
    # ===========================================

    @pytest.mark.asyncio
    async def test_first_scan_actionable_infringement(self, processor, mock_firestore):
        """
        Test first-time scan with actionable infringement (immediate_takedown).

        Expected deltas:
        - videos_scanned: +1
        - confirmed_infringements: +1
        - videos_cleared: 0
        - infringing_videos_count: +1
        - total_infringing_views: +1000
        - total_analyzed: +1
        - total_infringements: +1
        - analyses: +1
        - infringements: +1
        """
        result = create_result("video1", "immediate_takedown", True)

        # Mock: video doesn't exist yet (first scan)
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True, previous_analysis=None
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        # Collect all increment operations
        increments = mock_firestore.increment_calls

        # Check channel stats
        assert ("videos_scanned", 1) in increments
        assert ("confirmed_infringements", 1) in increments
        assert ("videos_cleared", 1) not in increments  # Should NOT increment cleared

        # Check infringement tracking
        assert ("infringing_videos_count", 1) in increments
        assert ("total_infringing_views", 1000) in increments

        # Check system stats
        assert ("total_analyzed", 1) in increments
        assert ("total_infringements", 1) in increments

        # Check hourly stats
        assert ("analyses", 1) in increments
        assert ("infringements", 1) in increments

    # ===========================================
    # SCENARIO 2: First-time scan → Cleared/Tolerated
    # ===========================================

    @pytest.mark.asyncio
    async def test_first_scan_cleared(self, processor, mock_firestore):
        """
        Test first-time scan with cleared result (monitor/tolerate_with_limits).

        Expected deltas:
        - videos_scanned: +1
        - confirmed_infringements: 0
        - videos_cleared: +1
        - infringing_videos_count: 0
        - total_infringing_views: 0
        - total_analyzed: +1
        - total_infringements: 0
        - analyses: +1
        - infringements: 0
        """
        result = create_result("video2", "monitor", True)  # Has infringement but not actionable

        # Mock: video doesn't exist yet (first scan)
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True, previous_analysis=None
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check channel stats
        assert ("videos_scanned", 1) in increments
        assert ("videos_cleared", 1) in increments
        assert ("confirmed_infringements", 1) not in increments

        # Check infringement tracking - should NOT increment
        assert ("infringing_videos_count", 1) not in increments
        assert ("total_infringing_views", 1000) not in increments

        # Check system stats - has_infringement=True but not actionable
        assert ("total_analyzed", 1) in increments
        assert ("total_infringements", 1) in increments  # Still counts as infringement

        # Check hourly stats
        assert ("analyses", 1) in increments
        assert ("infringements", 1) in increments

    # ===========================================
    # SCENARIO 3: Re-scan with no change (infringement → infringement)
    # ===========================================

    @pytest.mark.asyncio
    async def test_rescan_no_change_infringement(self, processor, mock_firestore):
        """
        Test re-scan where result stays the same (infringement → infringement).

        Expected deltas: ALL ZERO (no changes)
        """
        result = create_result("video3", "immediate_takedown", True)

        # Mock: video exists with previous actionable infringement
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check NO increments for channel stats
        assert ("videos_scanned", 1) not in increments  # Already counted
        assert ("confirmed_infringements", 1) not in increments  # No change
        assert ("videos_cleared", 1) not in increments

        # Check NO increments for infringement tracking
        assert ("infringing_videos_count", 1) not in increments
        assert ("total_infringing_views", 1000) not in increments

        # Check NO increments for system stats
        assert ("total_analyzed", 1) not in increments  # Re-scan
        assert ("total_infringements", 1) not in increments  # No change

        # Check NO increments for hourly stats
        assert ("analyses", 1) not in increments  # Re-scan
        assert ("infringements", 1) not in increments  # No change

    # ===========================================
    # SCENARIO 4: Re-scan with no change (cleared → cleared)
    # ===========================================

    @pytest.mark.asyncio
    async def test_rescan_no_change_cleared(self, processor, mock_firestore):
        """
        Test re-scan where result stays the same (cleared → cleared).

        Expected deltas: ALL ZERO (no changes)
        """
        result = create_result("video4", "monitor", True)

        # Mock: video exists with previous non-actionable result
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "monitor",
            }
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check NO changes
        assert ("videos_scanned", 1) not in increments
        assert ("confirmed_infringements", 1) not in increments
        assert ("videos_cleared", 1) not in increments
        assert ("infringing_videos_count", 1) not in increments
        assert ("total_analyzed", 1) not in increments
        assert ("total_infringements", 1) not in increments
        assert ("analyses", 1) not in increments
        assert ("infringements", 1) not in increments

    # ===========================================
    # SCENARIO 5: Re-scan changed (infringement → cleared) ⭐ CRITICAL
    # ===========================================

    @pytest.mark.asyncio
    async def test_rescan_infringement_to_cleared(self, processor, mock_firestore):
        """
        Test re-scan where video changes from actionable infringement to cleared (tolerated).

        THIS IS THE CRITICAL BUG FIX TEST!

        Expected deltas:
        - videos_scanned: 0 (no change)
        - confirmed_infringements: -1 (decrement) ⭐ ACTIONABLE STATUS CHANGED
        - videos_cleared: +1 (increment)
        - infringing_videos_count: -1 (decrement) ⭐ CRITICAL FIX
        - total_infringing_views: -1000 (decrement) ⭐ CRITICAL FIX
        - total_analyzed: 0 (no change)
        - total_infringements: 0 (no change - STILL has infringement, just not actionable)
        - analyses: 0 (no change)
        - infringements: 0 (no change - STILL has infringement)
        """
        result = create_result("video5", "monitor", True)

        # Mock: video exists with previous actionable infringement
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check channel stats: subtract old, add new
        assert ("videos_scanned", 1) not in increments  # No change
        assert ("confirmed_infringements", -1) in increments  # ⭐ Decrement (actionable → tolerated)
        assert ("videos_cleared", 1) in increments  # Increment

        # Check infringement tracking: ⭐ CRITICAL - must decrement
        assert ("infringing_videos_count", -1) in increments
        assert ("total_infringing_views", -1000) in increments

        # Check system stats
        assert ("total_analyzed", 1) not in increments  # No change
        # NOTE: total_infringements doesn't change - still has infringement, just tolerated now
        assert ("total_infringements", -1) not in increments
        assert ("total_infringements", 1) not in increments

        # Check hourly stats
        assert ("analyses", 1) not in increments  # No change
        # NOTE: infringements doesn't change - still has infringement
        assert ("infringements", -1) not in increments
        assert ("infringements", 1) not in increments

    # ===========================================
    # SCENARIO 6: Re-scan changed (cleared → infringement)
    # ===========================================

    @pytest.mark.asyncio
    async def test_rescan_cleared_to_infringement(self, processor, mock_firestore):
        """
        Test re-scan where video changes from cleared (tolerated) to actionable infringement.

        Expected deltas:
        - videos_scanned: 0 (no change)
        - confirmed_infringements: +1 (increment) ⭐ ACTIONABLE STATUS CHANGED
        - videos_cleared: -1 (decrement)
        - infringing_videos_count: +1 (increment)
        - total_infringing_views: +1000 (increment)
        - total_analyzed: 0 (no change)
        - total_infringements: 0 (no change - STILL has infringement, just more serious now)
        - analyses: 0 (no change)
        - infringements: 0 (no change - STILL has infringement)
        """
        result = create_result("video6", "immediate_takedown", True)

        # Mock: video exists with previous non-actionable result
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "monitor",
            }
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check channel stats: subtract old, add new
        assert ("videos_scanned", 1) not in increments  # No change
        assert ("confirmed_infringements", 1) in increments  # Increment (tolerated → actionable)
        assert ("videos_cleared", -1) in increments  # Decrement

        # Check infringement tracking
        assert ("infringing_videos_count", 1) in increments
        assert ("total_infringing_views", 1000) in increments

        # Check system stats
        assert ("total_analyzed", 1) not in increments  # No change
        # NOTE: total_infringements doesn't change - still has infringement, just actionable now
        assert ("total_infringements", 1) not in increments
        assert ("total_infringements", -1) not in increments

        # Check hourly stats
        assert ("analyses", 1) not in increments  # No change
        # NOTE: infringements doesn't change - still has infringement
        assert ("infringements", 1) not in increments
        assert ("infringements", -1) not in increments

    # ===========================================
    # SCENARIO 7: Re-scan changed (no infringement → infringement)
    # ===========================================

    @pytest.mark.asyncio
    async def test_rescan_safe_to_infringement(self, processor, mock_firestore):
        """
        Test re-scan where video changes from safe (no infringement) to infringement.

        Expected deltas:
        - videos_scanned: 0
        - confirmed_infringements: +1
        - videos_cleared: -1
        - total_analyzed: 0
        - total_infringements: +1
        - infringements (hourly): +1
        """
        result = create_result("video7", "immediate_takedown", True)

        # Mock: video exists with previous safe result
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": False,
                "overall_recommendation": "ignore",
            }
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check changes
        assert ("confirmed_infringements", 1) in increments
        assert ("videos_cleared", -1) in increments
        assert ("total_infringements", 1) in increments
        assert ("infringements", 1) in increments

    # ===========================================
    # SCENARIO 8: Re-scan changed (infringement → no infringement)
    # ===========================================

    @pytest.mark.asyncio
    async def test_rescan_infringement_to_safe(self, processor, mock_firestore):
        """
        Test re-scan where video changes from infringement to safe (no infringement).

        Expected deltas:
        - videos_scanned: 0
        - confirmed_infringements: -1
        - videos_cleared: +1
        - total_analyzed: 0
        - total_infringements: -1
        - infringements (hourly): -1
        """
        result = create_result("video8", "ignore", False)

        # Mock: video exists with previous actionable infringement
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )

        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        increments = mock_firestore.increment_calls

        # Check changes
        assert ("confirmed_infringements", -1) in increments
        assert ("videos_cleared", 1) in increments
        assert ("infringing_videos_count", -1) in increments
        assert ("total_infringing_views", -1000) in increments
        assert ("total_infringements", -1) in increments
        assert ("infringements", -1) in increments

    # ===========================================
    # INVARIANTS TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_invariant_videos_scanned_equals_sum(self, processor, mock_firestore):
        """
        Test invariant: videos_scanned = confirmed_infringements + videos_cleared

        This should hold true for any sequence of scans.
        """
        # Simulate sequence: 3 first scans (2 infringement, 1 cleared)
        results = [
            (create_result("v1", "immediate_takedown", True), None),
            (create_result("v2", "immediate_takedown", True), None),
            (create_result("v3", "monitor", True), None),
        ]

        scanned_delta = 0
        confirmed_delta = 0
        cleared_delta = 0

        for result, prev_analysis in results:
            mock_firestore.increment_calls = []
            mock_firestore.collection().document().get.return_value = mock_video_document(
                exists=True, previous_analysis=prev_analysis
            )

            await processor.process_result(result, channel_id="test_channel", view_count=1000)

            increments = mock_firestore.increment_calls

            # Accumulate deltas
            for key, value in increments:
                if key == "videos_scanned":
                    scanned_delta += value
                elif key == "confirmed_infringements":
                    confirmed_delta += value
                elif key == "videos_cleared":
                    cleared_delta += value

        # Check invariant
        assert scanned_delta == confirmed_delta + cleared_delta
        assert scanned_delta == 3  # 3 first scans
        assert confirmed_delta == 2  # 2 actionable
        assert cleared_delta == 1  # 1 cleared

    @pytest.mark.asyncio
    async def test_invariant_no_double_counting_on_rescan(self, processor, mock_firestore):
        """
        Test that re-scanning a video never increments total_analyzed or videos_scanned.
        """
        result = create_result("video9", "immediate_takedown", True)

        # First scan
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True, previous_analysis=None
        )
        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        first_increments = mock_firestore.increment_calls
        assert ("videos_scanned", 1) in first_increments
        assert ("total_analyzed", 1) in first_increments

        # Re-scan (same result)
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )
        await processor.process_result(result, channel_id="test_channel", view_count=1000)

        rescan_increments = mock_firestore.increment_calls

        # ⭐ CRITICAL: These should NOT be incremented on re-scan
        assert ("videos_scanned", 1) not in rescan_increments
        assert ("total_analyzed", 1) not in rescan_increments

    # ===========================================
    # EDGE CASES
    # ===========================================

    @pytest.mark.asyncio
    async def test_multiple_rescans_same_video(self, processor, mock_firestore):
        """
        Test multiple re-scans of the same video with changing results.

        Sequence:
        1. First scan: actionable infringement
        2. Re-scan: cleared
        3. Re-scan: actionable again
        4. Re-scan: cleared again

        Net result should be: cleared (videos_cleared = +1, confirmed = 0)
        """
        video_id = "video_multi"

        # Scan 1: First scan → actionable infringement
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True, previous_analysis=None
        )
        result1 = create_result(video_id, "immediate_takedown", True)
        await processor.process_result(result1, channel_id="test_channel", view_count=1000)

        increments1 = mock_firestore.increment_calls
        assert ("videos_scanned", 1) in increments1
        assert ("confirmed_infringements", 1) in increments1

        # Scan 2: Re-scan → cleared
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )
        result2 = create_result(video_id, "monitor", True)
        await processor.process_result(result2, channel_id="test_channel", view_count=1000)

        increments2 = mock_firestore.increment_calls
        assert ("confirmed_infringements", -1) in increments2
        assert ("videos_cleared", 1) in increments2

        # Scan 3: Re-scan → actionable again
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "monitor",
            }
        )
        result3 = create_result(video_id, "immediate_takedown", True)
        await processor.process_result(result3, channel_id="test_channel", view_count=1000)

        increments3 = mock_firestore.increment_calls
        assert ("confirmed_infringements", 1) in increments3
        assert ("videos_cleared", -1) in increments3

        # Scan 4: Re-scan → cleared again
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )
        result4 = create_result(video_id, "monitor", True)
        await processor.process_result(result4, channel_id="test_channel", view_count=1000)

        increments4 = mock_firestore.increment_calls
        assert ("confirmed_infringements", -1) in increments4
        assert ("videos_cleared", 1) in increments4

        # Net result calculation
        # videos_scanned: +1 (scan 1 only)
        # confirmed: +1 (scan 1) -1 (scan 2) +1 (scan 3) -1 (scan 4) = 0
        # cleared: +1 (scan 2) -1 (scan 3) +1 (scan 4) = +1
        # Total: scanned=1, confirmed=0, cleared=1 ✅

    @pytest.mark.asyncio
    async def test_view_count_changes_on_rescan(self, processor, mock_firestore):
        """
        Test that view count changes are NOT reflected in total_infringing_views on re-scan.

        The view count at time of classification is what matters, not updates.
        """
        video_id = "video_views"

        # First scan: 1000 views, actionable infringement
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True, previous_analysis=None
        )
        result1 = create_result(video_id, "immediate_takedown", True)
        await processor.process_result(result1, channel_id="test_channel", view_count=1000)

        increments1 = mock_firestore.increment_calls
        assert ("total_infringing_views", 1000) in increments1

        # Re-scan: 5000 views (video went viral), same result
        mock_firestore.increment_calls = []
        mock_firestore.collection().document().get.return_value = mock_video_document(
            exists=True,
            previous_analysis={
                "contains_infringement": True,
                "overall_recommendation": "immediate_takedown",
            }
        )
        result2 = create_result(video_id, "immediate_takedown", True)
        await processor.process_result(result2, channel_id="test_channel", view_count=5000)

        increments2 = mock_firestore.increment_calls

        # Should NOT update view count (same classification)
        assert ("total_infringing_views", 5000) not in increments2
        assert ("total_infringing_views", 4000) not in increments2  # Delta
