"""Tests for VideoProcessor class."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.core.video_processor import VideoProcessor
from app.models import VideoMetadata, VideoStatus


@pytest.fixture
def sample_video_data():
    """Sample YouTube API video data (videos.list format)."""
    return {
        "id": "test_video_123",
        "snippet": {
            "title": "Superman AI Generated Movie",
            "channelId": "UC_test_channel",
            "channelTitle": "AI Movies",
            "publishedAt": "2024-01-15T10:30:00Z",
            "description": "AI-generated Superman content made with Sora",
            "tags": ["Superman", "AI", "Sora"],
            "categoryId": "20",
            "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/test/hq.jpg"}},
        },
        "statistics": {
            "viewCount": "50000",
            "likeCount": "1000",
            "commentCount": "250",
        },
        "contentDetails": {"duration": "PT5M30S"},
    }


@pytest.fixture
def sample_search_result():
    """Sample YouTube API search result (search.list format)."""
    return {
        "id": {"videoId": "search_video_456"},
        "snippet": {
            "title": "Batman AI Animation",
            "channelId": "UC_search_channel",
            "channelTitle": "AI Content Creator",
            "publishedAt": "2024-01-20T14:00:00Z",
            "description": "AI-generated Batman animation",
            "tags": ["Batman", "AI"],
            "categoryId": "1",
            "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/search/mq.jpg"}},
        },
        "statistics": {"viewCount": "10000"},
        "contentDetails": {"duration": "PT2M15S"},
    }


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    return MagicMock()


@pytest.fixture
def mock_pubsub():
    """Mock PubSub publisher."""
    publisher = MagicMock()
    future = MagicMock()
    future.result.return_value = "mock_message_id_12345"
    publisher.publish.return_value = future
    return publisher


@pytest.fixture
def mock_ip_manager():
    """Mock IP target manager."""
    manager = MagicMock()
    # By default, return Superman match
    superman_target = MagicMock()
    superman_target.name = "Superman"
    manager.match_content.return_value = [superman_target]
    return manager


@pytest.fixture
def video_processor(mock_firestore, mock_pubsub, mock_ip_manager):
    """Video processor instance with mocked dependencies."""
    return VideoProcessor(
        firestore_client=mock_firestore,
        pubsub_publisher=mock_pubsub,
        ip_manager=mock_ip_manager,
        topic_path="projects/test-project/topics/test-topic",
    )


class TestVideoProcessorInit:
    """Tests for VideoProcessor initialization."""

    def test_initialization_success(self, mock_firestore, mock_pubsub, mock_ip_manager):
        """Test VideoProcessor initializes correctly with all dependencies."""
        processor = VideoProcessor(
            firestore_client=mock_firestore,
            pubsub_publisher=mock_pubsub,
            ip_manager=mock_ip_manager,
            topic_path="projects/test/topics/videos",
        )

        assert processor.firestore == mock_firestore
        assert processor.publisher == mock_pubsub
        assert processor.ip_manager == mock_ip_manager
        assert processor.topic_path == "projects/test/topics/videos"
        assert processor.videos_collection == "videos"


class TestExtractMetadata:
    """Tests for extract_metadata method."""

    def test_extract_metadata_success(self, video_processor, sample_video_data):
        """Test successful metadata extraction with all fields."""
        metadata = video_processor.extract_metadata(sample_video_data)

        assert metadata.video_id == "test_video_123"
        assert metadata.title == "Superman AI Generated Movie"
        assert metadata.channel_id == "UC_test_channel"
        assert metadata.channel_title == "AI Movies"
        assert metadata.description == "AI-generated Superman content made with Sora"
        assert metadata.view_count == 50000
        assert metadata.like_count == 1000
        assert metadata.comment_count == 250
        assert metadata.duration_seconds == 330  # 5 min 30 sec
        assert "Superman" in metadata.tags
        assert "AI" in metadata.tags
        assert metadata.category_id == "20"
        assert "hq.jpg" in metadata.thumbnail_url

    def test_extract_metadata_search_format(
        self, video_processor, sample_search_result
    ):
        """Test extraction from search.list format (id is dict)."""
        metadata = video_processor.extract_metadata(sample_search_result)

        assert metadata.video_id == "search_video_456"
        assert metadata.title == "Batman AI Animation"
        assert metadata.channel_id == "UC_search_channel"

    def test_extract_metadata_missing_optional_fields(self, video_processor):
        """Test extraction with missing optional fields."""
        minimal_data = {
            "id": "test_123",
            "snippet": {
                "title": "Test Video",
                "channelId": "UC_test",
                "channelTitle": "Test Channel",
                "publishedAt": "2024-01-15T10:30:00Z",
            },
            "statistics": {},
            "contentDetails": {},
        }

        metadata = video_processor.extract_metadata(minimal_data)

        assert metadata.video_id == "test_123"
        assert metadata.title == "Test Video"
        assert metadata.view_count == 0  # Default
        assert metadata.like_count == 0  # Default
        assert metadata.duration_seconds == 0  # Default
        assert metadata.description == ""  # Default
        assert metadata.tags == []  # Default

    def test_extract_metadata_invalid_duration(
        self, video_processor, sample_video_data
    ):
        """Test extraction with malformed duration string."""
        sample_video_data["contentDetails"]["duration"] = "INVALID"

        metadata = video_processor.extract_metadata(sample_video_data)

        assert metadata.duration_seconds == 0  # Fallback

    def test_extract_metadata_invalid_published_date(
        self, video_processor, sample_video_data
    ):
        """Test extraction with malformed published date."""
        sample_video_data["snippet"]["publishedAt"] = "INVALID_DATE"

        metadata = video_processor.extract_metadata(sample_video_data)

        # Should fallback to current time
        assert isinstance(metadata.published_at, datetime)
        assert (datetime.now(timezone.utc) - metadata.published_at).seconds < 5

    def test_extract_metadata_missing_video_id(self, video_processor):
        """Test extraction fails without video ID."""
        invalid_data = {"snippet": {"title": "No ID"}}

        with pytest.raises(ValueError, match="Cannot extract video_id"):
            video_processor.extract_metadata(invalid_data)

    def test_extract_metadata_empty_video_id_dict(self, video_processor):
        """Test extraction fails with empty video ID dict."""
        invalid_data = {"id": {"videoId": ""}, "snippet": {"title": "Empty ID"}}

        with pytest.raises(ValueError, match="Cannot extract video_id"):
            video_processor.extract_metadata(invalid_data)

    def test_extract_metadata_missing_snippet(self, video_processor):
        """Test extraction handles missing snippet gracefully."""
        invalid_data = {"id": "test_123"}

        # Should not raise, will use empty dicts for missing fields
        metadata = video_processor.extract_metadata(invalid_data)

        assert metadata.video_id == "test_123"
        assert metadata.title == ""
        assert metadata.channel_id == ""

    def test_extract_metadata_thumbnail_priority(self, video_processor):
        """Test thumbnail selection prioritizes high quality."""
        data_with_all_thumbnails = {
            "id": "test_thumb",
            "snippet": {
                "title": "Test",
                "channelId": "UC_test",
                "channelTitle": "Test",
                "publishedAt": "2024-01-15T10:30:00Z",
                "thumbnails": {
                    "default": {"url": "http://example.com/default.jpg"},
                    "medium": {"url": "http://example.com/medium.jpg"},
                    "high": {"url": "http://example.com/high.jpg"},
                },
            },
            "statistics": {},
            "contentDetails": {},
        }

        metadata = video_processor.extract_metadata(data_with_all_thumbnails)
        assert metadata.thumbnail_url == "http://example.com/high.jpg"

    def test_extract_metadata_thumbnail_fallback(self, video_processor):
        """Test thumbnail fallback to medium then default."""
        data_no_high = {
            "id": "test_thumb",
            "snippet": {
                "title": "Test",
                "channelId": "UC_test",
                "channelTitle": "Test",
                "publishedAt": "2024-01-15T10:30:00Z",
                "thumbnails": {
                    "default": {"url": "http://example.com/default.jpg"},
                    "medium": {"url": "http://example.com/medium.jpg"},
                },
            },
            "statistics": {},
            "contentDetails": {},
        }

        metadata = video_processor.extract_metadata(data_no_high)
        assert metadata.thumbnail_url == "http://example.com/medium.jpg"


class TestParseDuration:
    """Tests for _parse_duration helper method."""

    def test_parse_duration_full(self, video_processor):
        """Test parsing duration with hours, minutes, seconds."""
        assert video_processor._parse_duration("PT1H30M45S") == 5445

    def test_parse_duration_minutes_seconds(self, video_processor):
        """Test parsing duration with minutes and seconds."""
        assert video_processor._parse_duration("PT5M30S") == 330

    def test_parse_duration_seconds_only(self, video_processor):
        """Test parsing duration with seconds only."""
        assert video_processor._parse_duration("PT45S") == 45

    def test_parse_duration_hours_only(self, video_processor):
        """Test parsing duration with hours only."""
        assert video_processor._parse_duration("PT2H") == 7200

    def test_parse_duration_minutes_only(self, video_processor):
        """Test parsing duration with minutes only."""
        assert video_processor._parse_duration("PT15M") == 900

    def test_parse_duration_zero(self, video_processor):
        """Test parsing zero duration."""
        assert video_processor._parse_duration("PT0S") == 0

    def test_parse_duration_invalid(self, video_processor):
        """Test parsing invalid duration returns 0."""
        assert video_processor._parse_duration("INVALID") == 0
        assert video_processor._parse_duration("") == 0
        assert video_processor._parse_duration("PT") == 0


class TestIsDuplicate:
    """Tests for is_duplicate method."""

    def test_is_duplicate_video_not_exists(self, video_processor, mock_firestore):
        """Test returns False for new video."""
        doc_mock = MagicMock()
        doc_mock.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("new_video_456")

        assert result is False

    def test_is_duplicate_video_exists_recently(self, video_processor, mock_firestore):
        """Test returns True for recently processed video."""
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {"discovered_at": datetime.now(timezone.utc)}

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("test_video_123")

        assert result is True

    def test_is_duplicate_video_exists_old(self, video_processor, mock_firestore):
        """Test returns False for old video beyond max_age_days."""
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "discovered_at": datetime.now(timezone.utc) - timedelta(days=10)
        }

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("test_video_123", max_age_days=7)

        assert result is False

    def test_is_duplicate_video_exists_no_timestamp(
        self, video_processor, mock_firestore
    ):
        """Test returns False for old video without timestamp."""
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {}  # No discovered_at field

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("old_video_789")

        assert result is False

    def test_is_duplicate_custom_max_age(self, video_processor, mock_firestore):
        """Test custom max_age_days parameter."""
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "discovered_at": datetime.now(timezone.utc) - timedelta(days=5)
        }

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        # 5 days old, max_age=3 -> duplicate
        assert video_processor.is_duplicate("video_1", max_age_days=3) is False
        # 5 days old, max_age=7 -> duplicate
        assert video_processor.is_duplicate("video_1", max_age_days=7) is True

    def test_is_duplicate_error_handling(self, video_processor, mock_firestore):
        """Test error handling returns False (fail open)."""
        mock_firestore.collection.return_value.document.return_value.get.side_effect = (
            Exception("Firestore error")
        )

        result = video_processor.is_duplicate("error_video")

        # Should return False (better to process than skip on error)
        assert result is False


class TestMatchIPs:
    """Tests for match_ips method."""

    def test_match_ips_title_match(self, video_processor, mock_ip_manager):
        """Test IP matching in video title."""
        metadata = VideoMetadata(
            video_id="test_1",
            title="Superman AI Generated Movie",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
        )

        result = video_processor.match_ips(metadata)

        assert result == ["Superman"]
        mock_ip_manager.match_content.assert_called_once()

    def test_match_ips_description_match(self, video_processor, mock_ip_manager):
        """Test IP matching in video description."""
        metadata = VideoMetadata(
            video_id="test_2",
            title="AI Movie",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
            description="This is a Batman movie made with AI",
        )

        batman_target = MagicMock()
        batman_target.name = "Batman"
        mock_ip_manager.match_content.return_value = [batman_target]

        result = video_processor.match_ips(metadata)

        assert result == ["Batman"]

    def test_match_ips_tags_match(self, video_processor, mock_ip_manager):
        """Test IP matching in video tags."""
        metadata = VideoMetadata(
            video_id="test_3",
            title="AI Animation",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
            tags=["Wonder Woman", "AI", "DC"],
        )

        wonder_woman_target = MagicMock()
        wonder_woman_target.name = "Wonder Woman"
        mock_ip_manager.match_content.return_value = [wonder_woman_target]

        result = video_processor.match_ips(metadata)

        assert result == ["Wonder Woman"]

    def test_match_ips_channel_match(self, video_processor, mock_ip_manager):
        """Test IP matching in channel name."""
        metadata = VideoMetadata(
            video_id="test_4",
            title="Latest Upload",
            channel_id="UC_test",
            channel_title="Flash AI Movies",
            published_at=datetime.now(timezone.utc),
        )

        flash_target = MagicMock()
        flash_target.name = "Flash"
        mock_ip_manager.match_content.return_value = [flash_target]

        result = video_processor.match_ips(metadata)

        assert result == ["Flash"]

    def test_match_ips_multiple_matches(self, video_processor, mock_ip_manager):
        """Test multiple IP matches."""
        metadata = VideoMetadata(
            video_id="test_5",
            title="Superman vs Batman AI Movie",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
        )

        superman_target = MagicMock()
        superman_target.name = "Superman"
        batman_target = MagicMock()
        batman_target.name = "Batman"
        mock_ip_manager.match_content.return_value = [superman_target, batman_target]

        result = video_processor.match_ips(metadata)

        assert len(result) == 2
        assert "Superman" in result
        assert "Batman" in result

    def test_match_ips_no_match(self, video_processor, mock_ip_manager):
        """Test no IP matches."""
        metadata = VideoMetadata(
            video_id="test_6",
            title="Random Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
        )

        mock_ip_manager.match_content.return_value = []

        result = video_processor.match_ips(metadata)

        assert result == []


class TestSaveAndPublish:
    """Tests for save_and_publish method."""

    def test_save_and_publish_success(
        self, video_processor, mock_firestore, mock_pubsub
    ):
        """Test successful save and publish."""
        metadata = VideoMetadata(
            video_id="test_save_1",
            title="Test Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
            matched_ips=["Superman"],
        )

        result = video_processor.save_and_publish(metadata)

        assert result is True
        mock_firestore.collection.assert_called_with("videos")
        mock_pubsub.publish.assert_called_once()

    def test_save_and_publish_includes_status(
        self, video_processor, mock_firestore, mock_pubsub
    ):
        """Test that saved document includes status and timestamps."""
        metadata = VideoMetadata(
            video_id="test_save_2",
            title="Test Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
        )

        video_processor.save_and_publish(metadata)

        # Get the call args
        doc_ref_mock = mock_firestore.collection.return_value.document.return_value
        call_args = doc_ref_mock.set.call_args[0][0]

        assert call_args["status"] == VideoStatus.DISCOVERED.value
        assert "discovered_at" in call_args
        assert "updated_at" in call_args
        assert isinstance(call_args["discovered_at"], datetime)

    def test_save_and_publish_firestore_error(
        self, video_processor, mock_firestore, mock_pubsub
    ):
        """Test handling Firestore error."""
        metadata = VideoMetadata(
            video_id="test_error",
            title="Test Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
        )

        mock_firestore.collection.return_value.document.return_value.set.side_effect = (
            Exception("Firestore error")
        )

        result = video_processor.save_and_publish(metadata)

        assert result is False

    def test_save_and_publish_pubsub_error(
        self, video_processor, mock_firestore, mock_pubsub
    ):
        """Test handling PubSub error."""
        metadata = VideoMetadata(
            video_id="test_pubsub_error",
            title="Test Video",
            channel_id="UC_test",
            channel_title="Test Channel",
            published_at=datetime.now(timezone.utc),
        )

        mock_pubsub.publish.side_effect = Exception("PubSub error")

        result = video_processor.save_and_publish(metadata)

        assert result is False


class TestProcessBatch:
    """Tests for process_batch method."""

    def test_process_batch_success(self, video_processor, sample_video_data):
        """Test successful batch processing."""
        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list)

        assert len(result) == 1
        assert result[0].video_id == "test_video_123"
        assert "Superman" in result[0].matched_ips

    def test_process_batch_empty_list(self, video_processor):
        """Test processing empty video list."""
        result = video_processor.process_batch([])

        assert result == []

    def test_process_batch_skip_duplicates(
        self, video_processor, sample_video_data, mock_firestore
    ):
        """Test batch skips duplicate videos."""
        # Make video appear as duplicate
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {"discovered_at": datetime.now(timezone.utc)}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list, skip_duplicates=True)

        assert len(result) == 0  # Should be skipped

    def test_process_batch_no_skip_duplicates(
        self, video_processor, sample_video_data, mock_firestore
    ):
        """Test batch processes duplicates when skip_duplicates=False."""
        # Make video appear as duplicate
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {"discovered_at": datetime.now(timezone.utc)}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list, skip_duplicates=False)

        assert len(result) == 1  # Should NOT be skipped

    def test_process_batch_skip_no_ip_match(
        self, video_processor, sample_video_data, mock_ip_manager
    ):
        """Test batch skips videos with no IP matches."""
        mock_ip_manager.match_content.return_value = []  # No matches

        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list, skip_no_ip_match=True)

        assert len(result) == 0  # Should be skipped

    def test_process_batch_no_skip_no_ip_match(
        self, video_processor, sample_video_data, mock_ip_manager
    ):
        """Test batch processes videos with no IP match when skip_no_ip_match=False."""
        mock_ip_manager.match_content.return_value = []  # No matches

        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list, skip_no_ip_match=False)

        # Should process but with empty matched_ips
        assert len(result) == 1
        assert result[0].matched_ips == []

    def test_process_batch_multiple_videos(
        self, video_processor, sample_video_data, sample_search_result
    ):
        """Test processing multiple videos."""
        video_list = [sample_video_data, sample_search_result]

        result = video_processor.process_batch(video_list)

        assert len(result) == 2
        assert result[0].video_id == "test_video_123"
        assert result[1].video_id == "search_video_456"

    def test_process_batch_error_handling(self, video_processor):
        """Test batch continues processing after individual video error."""
        valid_video = {
            "id": "valid_123",
            "snippet": {
                "title": "Valid Superman Video",
                "channelId": "UC_valid",
                "channelTitle": "Valid Channel",
                "publishedAt": "2024-01-15T10:30:00Z",
            },
            "statistics": {},
            "contentDetails": {},
        }
        invalid_video = {}  # Completely invalid - no id at all

        video_list = [invalid_video, valid_video]

        result = video_processor.process_batch(video_list)

        # Should process valid video despite error on invalid
        assert len(result) == 1
        assert result[0].video_id == "valid_123"

    def test_process_batch_save_publish_failure(
        self, video_processor, sample_video_data, mock_pubsub
    ):
        """Test batch handles save/publish failures."""
        # Make publish fail
        mock_pubsub.publish.side_effect = Exception("PubSub error")

        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list)

        # Should return empty list (video failed to save/publish)
        assert len(result) == 0


class TestCalculateInitialRisk:
    """Test initial risk score calculation."""

    def test_calculate_initial_risk_new_channel_low_views(self, video_processor):
        """Test risk for new channel with low views."""
        from datetime import datetime, timezone

        from app.models import VideoMetadata

        metadata = VideoMetadata(
            video_id="test_123",
            title="Superman Video",
            channel_id="UC_new",
            channel_title="New Channel",
            published_at=datetime.now(timezone.utc),
            view_count=100,
            duration_seconds=180,  # 3 min
            matched_ips=["Justice League"],
        )

        risk = video_processor.calculate_initial_risk(metadata, channel_risk=0)

        # channel=0, views=0, ips=5, duration=0, age=5
        # Total = 10
        assert risk == 10

    def test_calculate_initial_risk_high_channel_viral_video(self, video_processor):
        """Test risk for high-risk channel with viral video."""
        from datetime import datetime, timedelta, timezone

        from app.models import VideoMetadata

        metadata = VideoMetadata(
            video_id="test_456",
            title="Batman AI Generated Movie",
            channel_id="UC_high_risk",
            channel_title="AI Movie Channel",
            published_at=datetime.now(timezone.utc) - timedelta(days=3),
            view_count=2_000_000,
            duration_seconds=900,  # 15 min
            matched_ips=["Justice League", "Batman", "Superman"],
        )

        risk = video_processor.calculate_initial_risk(metadata, channel_risk=80)

        # channel=40, views=15, ips=15, duration=10, age=5
        # Total = 85
        assert risk == 85

    def test_calculate_initial_risk_medium_scenario(self, video_processor):
        """Test risk for medium scenario."""
        from datetime import datetime, timedelta, timezone

        from app.models import VideoMetadata

        metadata = VideoMetadata(
            video_id="test_789",
            title="Wonder Woman Fan Video",
            channel_id="UC_medium",
            channel_title="Fan Channel",
            published_at=datetime.now(timezone.utc) - timedelta(days=15),
            view_count=50_000,
            duration_seconds=400,  # 6.5 min
            matched_ips=["Justice League", "Wonder Woman"],
        )

        risk = video_processor.calculate_initial_risk(metadata, channel_risk=40)

        # channel=20, views=5 (50k is >10k but <100k), ips=10, duration=5, age=3
        # Total = 43
        assert risk == 43

    def test_calculate_initial_risk_caps_at_100(self, video_processor):
        """Test risk score caps at 100."""
        from datetime import datetime, timezone

        from app.models import VideoMetadata

        metadata = VideoMetadata(
            video_id="test_999",
            title="Full AI Generated Justice League Movie",
            channel_id="UC_max_risk",
            channel_title="AI Studio",
            published_at=datetime.now(timezone.utc),
            view_count=10_000_000,
            duration_seconds=3600,  # 1 hour
            matched_ips=["Justice League", "Batman", "Superman", "Wonder Woman"],
        )

        risk = video_processor.calculate_initial_risk(metadata, channel_risk=100)

        # channel=50, views=15, ips=20, duration=10, age=5
        # Total = 100 (capped)
        assert risk == 100

    def test_calculate_initial_risk_no_ips(self, video_processor):
        """Test risk with no IP matches (should be lowest)."""
        from datetime import datetime, timedelta, timezone

        from app.models import VideoMetadata

        metadata = VideoMetadata(
            video_id="test_000",
            title="Generic Video",
            channel_id="UC_clean",
            channel_title="Clean Channel",
            published_at=datetime.now(timezone.utc) - timedelta(days=60),
            view_count=500,
            duration_seconds=120,  # 2 min
            matched_ips=[],
        )

        risk = video_processor.calculate_initial_risk(metadata, channel_risk=0)

        # channel=0, views=0, ips=0, duration=0, age=0
        # Total = 0
        assert risk == 0


class TestCalculateRiskTier:
    """Test risk tier calculation."""

    def test_risk_tier_critical(self, video_processor):
        """Test CRITICAL tier (80-100)."""
        assert video_processor.calculate_risk_tier(100) == "CRITICAL"
        assert video_processor.calculate_risk_tier(85) == "CRITICAL"
        assert video_processor.calculate_risk_tier(80) == "CRITICAL"

    def test_risk_tier_high(self, video_processor):
        """Test HIGH tier (60-79)."""
        assert video_processor.calculate_risk_tier(79) == "HIGH"
        assert video_processor.calculate_risk_tier(65) == "HIGH"
        assert video_processor.calculate_risk_tier(60) == "HIGH"

    def test_risk_tier_medium(self, video_processor):
        """Test MEDIUM tier (40-59)."""
        assert video_processor.calculate_risk_tier(59) == "MEDIUM"
        assert video_processor.calculate_risk_tier(50) == "MEDIUM"
        assert video_processor.calculate_risk_tier(40) == "MEDIUM"

    def test_risk_tier_low(self, video_processor):
        """Test LOW tier (20-39)."""
        assert video_processor.calculate_risk_tier(39) == "LOW"
        assert video_processor.calculate_risk_tier(25) == "LOW"
        assert video_processor.calculate_risk_tier(20) == "LOW"

    def test_risk_tier_very_low(self, video_processor):
        """Test VERY_LOW tier (0-19)."""
        assert video_processor.calculate_risk_tier(19) == "VERY_LOW"
        assert video_processor.calculate_risk_tier(10) == "VERY_LOW"
        assert video_processor.calculate_risk_tier(0) == "VERY_LOW"


class TestRiskScoringIntegration:
    """Test risk scoring in process_batch."""

    def test_process_batch_sets_risk_scores(self, video_processor, sample_video_data):
        """Test that process_batch sets risk scores on videos."""
        video_list = [sample_video_data]

        result = video_processor.process_batch(video_list)

        assert len(result) == 1
        video = result[0]

        # Verify risk fields are set
        assert video.initial_risk >= 0
        assert video.initial_risk <= 100
        assert video.current_risk == video.initial_risk
        assert video.risk_tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]

    def test_process_batch_high_risk_video(self, video_processor):
        """Test processing a high-risk video."""
        from datetime import datetime, timezone

        high_risk_video = {
            "id": "high_risk_123",
            "snippet": {
                "title": "FULL AI Generated Superman Batman Movie - Sora AI",
                "channelId": "UC_ai_studio",
                "channelTitle": "AI Movie Studio",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "description": "AI generated Justice League movie",
                "tags": ["superman", "batman", "ai", "sora"],
            },
            "statistics": {"viewCount": "500000", "likeCount": "10000"},
            "contentDetails": {"duration": "PT15M30S"},  # 15.5 min
        }

        result = video_processor.process_batch([high_risk_video])

        assert len(result) == 1
        video = result[0]

        # channel=0, views=10 (500k>100k), ips=5 (1 match), duration=10 (>10min), age=5 (recent)
        # Total = 30 = LOW tier
        assert video.initial_risk == 30
        assert video.risk_tier == "LOW"

        # But this would be upgraded by risk-analyzer-service based on view velocity
