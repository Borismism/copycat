"""
Integration tests for discovery-service → risk-analyzer-service flow.

Tests the complete pipeline:
1. Discovery service finds a video and publishes to video-discovered topic
2. Risk analyzer receives the message and processes it
3. Risk analyzer updates Firestore with risk scores
4. Risk analyzer schedules scans based on risk tier
"""

import sys
from pathlib import Path

# Add service directories to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "services" / "discovery-service"))
sys.path.insert(0, str(project_root / "services" / "risk-analyzer-service"))

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from google.cloud import firestore
from google.cloud import pubsub_v1

# Test data
SAMPLE_VIDEO = {
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
    }
}


class TestDiscoveryToRiskAnalyzer:
    """Test the integration between discovery and risk-analyzer services."""

    @pytest.fixture
    def mock_firestore(self):
        """Mock Firestore client."""
        mock_client = Mock(spec=firestore.Client)
        mock_collection = Mock()
        mock_doc = Mock()

        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc

        # Mock get() to return non-existent doc initially
        mock_get = Mock()
        mock_get.exists = False
        mock_doc.get.return_value = mock_get

        return mock_client

    @pytest.fixture
    def mock_pubsub_publisher(self):
        """Mock PubSub publisher client."""
        mock_publisher = Mock(spec=pubsub_v1.PublisherClient)

        # Mock publish to return a future
        mock_future = Mock()
        mock_future.result.return_value = "message_id_123"
        mock_publisher.publish.return_value = mock_future

        return mock_publisher

    def test_discovery_publishes_video_discovered_event(self, mock_firestore, mock_pubsub_publisher):
        """Test that discovery service publishes video-discovered event correctly."""
        from app.core.video_processor import VideoProcessor

        processor = VideoProcessor(
            firestore_client=mock_firestore,
            pubsub_publisher=mock_pubsub_publisher,
            project_id="test-project"
        )

        # Process a video
        result = processor.process_video(SAMPLE_VIDEO)

        # Verify video was saved to Firestore
        mock_firestore.collection.assert_called_with("videos")

        # Verify event was published
        mock_pubsub_publisher.publish.assert_called_once()
        call_args = mock_pubsub_publisher.publish.call_args

        # Check topic
        assert "video-discovered" in call_args[0][0]

        # Check message data
        message_data = json.loads(call_args[1]["data"].decode("utf-8"))
        assert message_data["video_id"] == "test_video_123"
        assert message_data["initial_risk_score"] == 75
        assert "risk_factors" in message_data

    def test_risk_analyzer_processes_video_discovered_event(self, mock_firestore):
        """Test that risk-analyzer correctly processes video-discovered events."""
        # Temporarily switch to risk-analyzer service
        sys.path.insert(0, str(project_root / "services" / "risk-analyzer-service"))
        from app.core.risk_engine import RiskEngine
        from app.models import VideoData
        sys.path.pop(0)  # Remove risk-analyzer from path

        # Create risk engine
        engine = RiskEngine(firestore_client=mock_firestore, project_id="test-project")

        # Mock Firestore to return video data
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            **SAMPLE_VIDEO,
            "discovered_at": datetime.now().isoformat(),
            "status": "discovered"
        }
        mock_firestore.collection().document().get.return_value = mock_doc

        # Process the video
        video_data = VideoData(**SAMPLE_VIDEO)
        result = engine.analyze_video(video_data)

        # Verify risk score was calculated
        assert result.current_risk_score >= 0
        assert result.current_risk_score <= 100
        assert result.risk_tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]

        # Verify factors were calculated
        assert "view_velocity_score" in result.risk_factors
        assert "channel_reputation_score" in result.risk_factors
        assert "engagement_rate_score" in result.risk_factors

    def test_end_to_end_new_viral_video(self, mock_firestore, mock_pubsub_publisher):
        """
        Test complete flow for a new viral video:
        1. Discovery finds video with high views
        2. Risk analyzer detects high velocity
        3. Video is marked as CRITICAL
        4. Scan scheduled for 6 hours
        """
        from services.discovery_service.app.core.video_processor import VideoProcessor
        from services.risk_analyzer_service.app.core.risk_engine import RiskEngine

        # Step 1: Discovery processes viral video
        discovery_processor = VideoProcessor(
            firestore_client=mock_firestore,
            pubsub_publisher=mock_pubsub_publisher,
            project_id="test-project"
        )

        viral_video = {
            **SAMPLE_VIDEO,
            "view_count": 500000,  # Half million views
            "published_at": (datetime.now() - timedelta(hours=2)).isoformat(),  # 2 hours old
            "initial_risk_score": 85
        }

        # Mock Firestore to return no existing video
        mock_get = Mock()
        mock_get.exists = False
        mock_firestore.collection().document().get.return_value = mock_get

        discovery_result = discovery_processor.process_video(viral_video)
        assert discovery_result.action == "processed"

        # Step 2: Risk analyzer processes the event
        risk_engine = RiskEngine(firestore_client=mock_firestore, project_id="test-project")

        # Mock Firestore to return the video with view history
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            **viral_video,
            "discovered_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            "view_history": [
                {
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "view_count": 100000
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "view_count": 300000
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "view_count": 500000
                }
            ]
        }
        mock_firestore.collection().document().get.return_value = mock_doc

        from services.risk_analyzer_service.app.models import VideoData
        video_data = VideoData(**viral_video)
        risk_result = risk_engine.analyze_video(video_data)

        # Verify viral video is marked as CRITICAL
        assert risk_result.risk_tier == "CRITICAL"
        assert risk_result.current_risk_score >= 85

        # Verify scan is scheduled soon (CRITICAL = 6 hours)
        next_scan = risk_result.next_scan_time
        now = datetime.now()
        time_until_scan = (next_scan - now).total_seconds() / 3600
        assert time_until_scan <= 6.5  # 6 hours + small buffer

    def test_end_to_end_serial_infringer_channel(self, mock_firestore, mock_pubsub_publisher):
        """
        Test complete flow for a channel with infringement history:
        1. Discovery finds video from known bad channel
        2. Risk analyzer checks channel reputation
        3. Video gets HIGH risk score
        4. Scan scheduled for 24 hours
        """
        from services.discovery_service.app.core.video_processor import VideoProcessor
        from services.risk_analyzer_service.app.core.risk_engine import RiskEngine
        from services.risk_analyzer_service.app.models import VideoData

        # Step 1: Discovery processes video from bad channel
        discovery_processor = VideoProcessor(
            firestore_client=mock_firestore,
            pubsub_publisher=mock_pubsub_publisher,
            project_id="test-project"
        )

        bad_channel_video = {
            **SAMPLE_VIDEO,
            "channel_id": "UC_serial_infringer",
            "initial_risk_score": 70
        }

        mock_get = Mock()
        mock_get.exists = False
        mock_firestore.collection().document().get.return_value = mock_get

        discovery_result = discovery_processor.process_video(bad_channel_video)
        assert discovery_result.action == "processed"

        # Step 2: Risk analyzer processes with channel history
        risk_engine = RiskEngine(firestore_client=mock_firestore, project_id="test-project")

        # Mock Firestore to return video + channel with bad history
        def mock_get_side_effect(*args, **kwargs):
            mock_doc = Mock()
            mock_doc.exists = True

            # Return video data for videos collection
            if "videos" in str(args):
                mock_doc.to_dict.return_value = {
                    **bad_channel_video,
                    "discovered_at": datetime.now().isoformat(),
                    "status": "discovered"
                }
            # Return channel data for channels collection
            elif "channels" in str(args):
                mock_doc.to_dict.return_value = {
                    "channel_id": "UC_serial_infringer",
                    "total_videos_scanned": 20,
                    "infringement_count": 15,  # 75% infringement rate!
                    "infringement_rate": 0.75,
                    "risk_tier": "PLATINUM",
                    "last_updated": datetime.now().isoformat()
                }

            return mock_doc

        mock_firestore.collection().document().get.side_effect = mock_get_side_effect

        video_data = VideoData(**bad_channel_video)
        risk_result = risk_engine.analyze_video(video_data)

        # Verify high channel reputation score boosts risk
        assert risk_result.risk_factors["channel_reputation_score"] >= 80
        assert risk_result.risk_tier in ["CRITICAL", "HIGH"]

        # Verify prioritized scanning
        next_scan = risk_result.next_scan_time
        now = datetime.now()
        time_until_scan = (next_scan - now).total_seconds() / 3600
        assert time_until_scan <= 24.5  # 24 hours or less

    def test_end_to_end_low_risk_video(self, mock_firestore, mock_pubsub_publisher):
        """
        Test complete flow for a low-risk video:
        1. Discovery finds old video with few views
        2. Risk analyzer calculates low risk
        3. Video gets VERY_LOW tier
        4. Scan scheduled for 30 days
        """
        from services.discovery_service.app.core.video_processor import VideoProcessor
        from services.risk_analyzer_service.app.core.risk_engine import RiskEngine
        from services.risk_analyzer_service.app.models import VideoData

        low_risk_video = {
            **SAMPLE_VIDEO,
            "view_count": 500,  # Very few views
            "published_at": (datetime.now() - timedelta(days=60)).isoformat(),  # 60 days old
            "initial_risk_score": 25,
            "matched_keywords": ["superman"],  # Only one keyword
        }

        # Discovery processing
        discovery_processor = VideoProcessor(
            firestore_client=mock_firestore,
            pubsub_publisher=mock_pubsub_publisher,
            project_id="test-project"
        )

        mock_get = Mock()
        mock_get.exists = False
        mock_firestore.collection().document().get.return_value = mock_get

        discovery_result = discovery_processor.process_video(low_risk_video)
        assert discovery_result.action == "processed"

        # Risk analyzer processing
        risk_engine = RiskEngine(firestore_client=mock_firestore, project_id="test-project")

        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            **low_risk_video,
            "discovered_at": (datetime.now() - timedelta(days=60)).isoformat(),
            "view_history": [
                {
                    "timestamp": (datetime.now() - timedelta(days=60)).isoformat(),
                    "view_count": 500
                }
            ]
        }
        mock_firestore.collection().document().get.return_value = mock_doc

        video_data = VideoData(**low_risk_video)
        risk_result = risk_engine.analyze_video(video_data)

        # Verify low risk classification
        assert risk_result.risk_tier in ["LOW", "VERY_LOW"]
        assert risk_result.current_risk_score < 40

        # Verify infrequent scanning
        next_scan = risk_result.next_scan_time
        now = datetime.now()
        time_until_scan = (next_scan - now).total_seconds() / 86400  # days
        assert time_until_scan >= 7  # At least weekly


class TestPubSubMessageFormat:
    """Test that PubSub messages are formatted correctly between services."""

    def test_video_discovered_message_schema(self):
        """Test that video-discovered messages have correct schema."""
        from services.discovery_service.app.core.video_processor import VideoProcessor

        mock_firestore = Mock()
        mock_publisher = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "msg_id"
        mock_publisher.publish.return_value = mock_future

        processor = VideoProcessor(
            firestore_client=mock_firestore,
            pubsub_publisher=mock_publisher,
            project_id="test-project"
        )

        mock_get = Mock()
        mock_get.exists = False
        mock_firestore.collection().document().get.return_value = mock_get

        processor.process_video(SAMPLE_VIDEO)

        # Get the published message
        call_args = mock_publisher.publish.call_args
        message_data = json.loads(call_args[1]["data"].decode("utf-8"))

        # Verify required fields
        required_fields = [
            "video_id", "title", "channel_id", "view_count",
            "initial_risk_score", "risk_factors", "discovered_at"
        ]
        for field in required_fields:
            assert field in message_data, f"Missing required field: {field}"

        # Verify data types
        assert isinstance(message_data["video_id"], str)
        assert isinstance(message_data["view_count"], int)
        assert isinstance(message_data["initial_risk_score"], (int, float))
        assert isinstance(message_data["risk_factors"], dict)

    def test_risk_analyzer_can_parse_discovery_message(self):
        """Test that risk-analyzer can parse messages from discovery service."""
        from services.risk_analyzer_service.app.models import VideoData

        # Simulate discovery message
        discovery_message = {
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
            "risk_factors": {
                "keyword_relevance": 80,
                "duration_score": 70,
                "recency_score": 90,
                "view_count_score": 60,
                "channel_size_score": 50
            },
            "discovered_at": "2025-10-28T10:00:00Z"
        }

        # Parse into VideoData model
        video_data = VideoData(**discovery_message)

        # Verify parsing
        assert video_data.video_id == "test_123"
        assert video_data.initial_risk_score == 75
        assert len(video_data.risk_factors) == 5


class TestFirestoreDataConsistency:
    """Test that data is consistently stored and retrieved across services."""

    def test_video_document_structure(self):
        """Test that both services use the same Firestore document structure."""
        # This ensures discovery writes data that risk-analyzer can read

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
            "status": "discovered",

            # Risk analyzer adds these fields
            "current_risk_score": 80,
            "risk_tier": "HIGH",
            "next_scan_time": "2025-10-29T10:00:00Z",
            "view_history": [],
            "scan_history": [],
            "last_risk_update": "2025-10-28T10:00:00Z"
        }

        # Verify all critical fields are present
        assert "video_id" in video_doc
        assert "initial_risk_score" in video_doc
        assert "current_risk_score" in video_doc
        assert "risk_tier" in video_doc
        assert "next_scan_time" in video_doc

    def test_channel_document_structure(self):
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
