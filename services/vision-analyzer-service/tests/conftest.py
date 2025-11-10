"""Pytest configuration and fixtures."""

import os
import pytest
from datetime import datetime, UTC
from unittest.mock import Mock

# Set up environment variables for testing
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_REGION", "us-central1")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("FIRESTORE_DATABASE_ID", "(default)")
os.environ.setdefault("PUBSUB_SCAN_READY_SUBSCRIPTION", "test-scan-ready-sub")
os.environ.setdefault("PUBSUB_FEEDBACK_TOPIC", "test-feedback-topic")


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    mock_client = Mock()
    mock_doc = Mock()
    mock_doc.exists = False
    mock_client.collection().document().get.return_value = mock_doc
    return mock_client


@pytest.fixture
def mock_bigquery():
    """Mock BigQuery client."""
    mock_client = Mock()
    mock_client.insert_rows_json.return_value = []
    return mock_client


@pytest.fixture
def mock_pubsub():
    """Mock PubSub publisher."""
    mock_publisher = Mock()
    mock_future = Mock()
    mock_future.result.return_value = "msg_123"
    mock_publisher.publish.return_value = mock_future
    mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
    return mock_publisher


@pytest.fixture
def sample_video_metadata():
    """Sample video metadata for testing."""
    from app.models import VideoMetadata

    return VideoMetadata(
        video_id="test_video_123",
        youtube_url="https://youtube.com/watch?v=test_video_123",
        title="Test AI Superman Video",
        duration_seconds=300,  # 5 minutes
        view_count=10000,
        channel_id="UC_test_channel",
        channel_title="Test Channel",
        risk_score=75.0,
        risk_tier="HIGH",
        matched_characters=["Superman", "Batman"],
        discovered_at=datetime.now(UTC),
        last_risk_update=datetime.now(UTC),
    )
