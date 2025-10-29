# Story Implementation Flow - Visual Guide

**How to implement a story from start to finish.**

---

## 🎯 The Flow

```
START
  ↓
1. DELETE BAD CODE
  ↓
2. WRITE SKELETON (types + docstrings)
  ↓
3. IMPLEMENT METHOD 1
  ↓
4. TEST METHOD 1
  ↓
  ✓ PASS? → METHOD 2
  ✗ FAIL? → FIX METHOD 1
  ↓
5. REPEAT FOR ALL METHODS
  ↓
6. INTEGRATION TEST (local)
  ↓
7. DEPLOY TO GCP DEV
  ↓
8. VERIFY IN PRODUCTION
  ↓
9. MARK AS DONE
  ↓
END
```

---

## 📝 Example: Story 1.1 (VideoProcessor)

### Step 1: Delete Bad Code (5 min)

```bash
cd services/discovery-service/app/core

# Review what we're deleting
git diff discovery.py

# We're going to extract ALL duplicate video processing logic
# from discover_trending(), discover_gaming(), discover_viral(), etc.
# into a new VideoProcessor class
```

**Lines to delete from discovery.py:**
- Line 70-110: `_extract_video_metadata()` method
- Line 112-137: `_check_ip_matches()` method
- Line 139-156: `_is_video_already_scanned()` method
- Line 158-176: `_save_video_to_firestore()` method
- Line 178-188: `_publish_to_pubsub()` method

**Result:** ~180 lines deleted (will be rewritten better in VideoProcessor)

### Step 2: Write Skeleton (15 min)

```bash
# Create new file
touch app/core/video_processor.py
```

**Write complete skeleton with ALL type hints and docstrings:**

```python
"""Video processing operations."""

from datetime import datetime
from typing import Any

from google.cloud import firestore, pubsub_v1

from ..models import VideoMetadata
from .ip_loader import IPTargetManager


class VideoProcessor:
    """Handles ALL video processing operations."""

    def __init__(
        self,
        firestore_client: firestore.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
        ip_manager: IPTargetManager,
        topic_path: str,
    ):
        """Initialize video processor."""
        pass

    def extract_metadata(self, video_data: dict[str, Any]) -> VideoMetadata:
        """Extract metadata from YouTube API response."""
        pass

    def is_duplicate(self, video_id: str, max_age_days: int = 7) -> bool:
        """Check if video was already processed recently."""
        pass

    def match_ips(self, metadata: VideoMetadata) -> list[str]:
        """Match video content against configured IP targets."""
        pass

    def save_and_publish(self, metadata: VideoMetadata) -> bool:
        """Atomically save to Firestore and publish to PubSub."""
        pass

    def process_batch(
        self,
        video_data_list: list[dict[str, Any]]
    ) -> list[VideoMetadata]:
        """Process multiple videos efficiently."""
        pass
```

**Checkpoint:**
- [ ] All methods declared
- [ ] All type hints present
- [ ] All docstrings written
- [ ] No implementation yet (just `pass`)

### Step 3: Implement `__init__` (5 min)

```python
def __init__(
    self,
    firestore_client: firestore.Client,
    pubsub_publisher: pubsub_v1.PublisherClient,
    ip_manager: IPTargetManager,
    topic_path: str,
):
    """Initialize video processor."""
    self.firestore = firestore_client
    self.publisher = pubsub_publisher
    self.ip_manager = ip_manager
    self.topic_path = topic_path
    self.videos_collection = "videos"

    logger.info("VideoProcessor initialized")
```

### Step 4: Test `__init__` (5 min)

```bash
# Create test file
touch tests/test_video_processor.py
```

```python
import pytest
from unittest.mock import MagicMock

from app.core.video_processor import VideoProcessor


@pytest.fixture
def mock_firestore():
    return MagicMock()


@pytest.fixture
def mock_pubsub():
    return MagicMock()


@pytest.fixture
def mock_ip_manager():
    return MagicMock()


def test_video_processor_initialization(
    mock_firestore,
    mock_pubsub,
    mock_ip_manager
):
    """Test VideoProcessor initializes correctly."""
    processor = VideoProcessor(
        firestore_client=mock_firestore,
        pubsub_publisher=mock_pubsub,
        ip_manager=mock_ip_manager,
        topic_path="projects/test/topics/videos"
    )

    assert processor.firestore == mock_firestore
    assert processor.publisher == mock_pubsub
    assert processor.ip_manager == mock_ip_manager
    assert processor.topic_path == "projects/test/topics/videos"
    assert processor.videos_collection == "videos"
```

**Run test:**
```bash
cd services/discovery-service
uv run pytest tests/test_video_processor.py::test_video_processor_initialization -v
```

**Expected:** ✅ PASS

### Step 5: Implement `extract_metadata` (30 min)

**Copy existing logic from discovery.py, but IMPROVE it:**

```python
def extract_metadata(self, video_data: dict[str, Any]) -> VideoMetadata:
    """
    Extract structured metadata from YouTube API response.

    Handles both search results and video.list responses:
    - search.list: id is {"videoId": "xxx"}
    - videos.list: id is "xxx"

    Args:
        video_data: Raw video data from YouTube API

    Returns:
        Structured video metadata

    Raises:
        KeyError: If required fields missing
        ValueError: If video_id cannot be extracted
    """
    # Extract video ID (handle both formats)
    video_id = video_data.get("id")
    if isinstance(video_id, dict):
        video_id = video_id.get("videoId", "")

    if not video_id:
        raise ValueError("Cannot extract video_id")

    snippet = video_data.get("snippet", {})
    statistics = video_data.get("statistics", {})
    content_details = video_data.get("contentDetails", {})

    # Parse published date with error handling
    published_at_str = snippet.get("publishedAt", "")
    try:
        published_at = datetime.fromisoformat(
            published_at_str.replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        logger.warning(f"Invalid publishedAt: {published_at_str}")
        published_at = datetime.utcnow()

    # Parse duration
    duration_str = content_details.get("duration", "PT0S")
    duration_seconds = self._parse_duration(duration_str)

    # Extract thumbnail (prefer high quality)
    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = (
        thumbnails.get("high", {}).get("url", "")
        or thumbnails.get("medium", {}).get("url", "")
        or thumbnails.get("default", {}).get("url", "")
    )

    return VideoMetadata(
        video_id=video_id,
        title=snippet.get("title", ""),
        channel_id=snippet.get("channelId", ""),
        channel_title=snippet.get("channelTitle", ""),
        published_at=published_at,
        description=snippet.get("description", ""),
        view_count=int(statistics.get("viewCount", 0)),
        like_count=int(statistics.get("likeCount", 0)),
        comment_count=int(statistics.get("commentCount", 0)),
        duration_seconds=duration_seconds,
        tags=snippet.get("tags", []),
        category_id=snippet.get("categoryId", ""),
        thumbnail_url=thumbnail_url,
    )


def _parse_duration(self, duration_str: str) -> int:
    """Parse ISO 8601 duration to seconds."""
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration_str)

    if not match:
        logger.warning(f"Cannot parse duration: {duration_str}")
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds
```

### Step 6: Test `extract_metadata` (45 min)

**Write comprehensive tests:**

```python
@pytest.fixture
def sample_video_data():
    """Sample YouTube API video data."""
    return {
        "id": "test_video_123",
        "snippet": {
            "title": "Superman AI Generated Movie",
            "channelId": "UC_test_channel",
            "channelTitle": "AI Movies",
            "publishedAt": "2024-01-15T10:30:00Z",
            "description": "AI-generated Superman content",
            "tags": ["Superman", "AI", "Sora"],
            "categoryId": "20",
            "thumbnails": {
                "high": {"url": "https://i.ytimg.com/vi/test/hq.jpg"}
            }
        },
        "statistics": {
            "viewCount": "50000",
            "likeCount": "1000",
            "commentCount": "250"
        },
        "contentDetails": {
            "duration": "PT5M30S"
        }
    }


class TestExtractMetadata:
    """Tests for extract_metadata method."""

    def test_extract_metadata_success(
        self,
        video_processor,
        sample_video_data
    ):
        """Test successful extraction with all fields."""
        metadata = video_processor.extract_metadata(sample_video_data)

        assert metadata.video_id == "test_video_123"
        assert metadata.title == "Superman AI Generated Movie"
        assert metadata.channel_id == "UC_test_channel"
        assert metadata.view_count == 50000
        assert metadata.duration_seconds == 330
        assert "Superman" in metadata.tags

    def test_extract_metadata_missing_optional_fields(
        self,
        video_processor
    ):
        """Test extraction with missing optional fields."""
        minimal_data = {
            "id": "test_123",
            "snippet": {
                "title": "Test Video",
                "channelId": "UC_test",
                "channelTitle": "Test Channel",
                "publishedAt": "2024-01-15T10:30:00Z"
            },
            "statistics": {},
            "contentDetails": {}
        }

        metadata = video_processor.extract_metadata(minimal_data)

        assert metadata.video_id == "test_123"
        assert metadata.view_count == 0
        assert metadata.duration_seconds == 0
        assert metadata.description == ""

    def test_extract_metadata_search_format(
        self,
        video_processor
    ):
        """Test extraction from search.list format (id is dict)."""
        search_data = {
            "id": {"videoId": "search_video_456"},
            "snippet": {
                "title": "Search Result",
                "channelId": "UC_search",
                "channelTitle": "Search Channel",
                "publishedAt": "2024-01-15T10:30:00Z"
            }
        }

        metadata = video_processor.extract_metadata(search_data)

        assert metadata.video_id == "search_video_456"

    def test_extract_metadata_invalid_duration(
        self,
        video_processor,
        sample_video_data
    ):
        """Test extraction with malformed duration."""
        sample_video_data["contentDetails"]["duration"] = "INVALID"

        metadata = video_processor.extract_metadata(sample_video_data)

        assert metadata.duration_seconds == 0

    def test_extract_metadata_missing_video_id(
        self,
        video_processor
    ):
        """Test extraction fails without video ID."""
        invalid_data = {"snippet": {"title": "No ID"}}

        with pytest.raises(ValueError, match="Cannot extract video_id"):
            video_processor.extract_metadata(invalid_data)

    def test_extract_metadata_missing_required_fields(
        self,
        video_processor
    ):
        """Test extraction fails with missing snippet."""
        invalid_data = {"id": "test_123"}

        with pytest.raises(KeyError):
            video_processor.extract_metadata(invalid_data)


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

    def test_parse_duration_invalid(self, video_processor):
        """Test parsing invalid duration returns 0."""
        assert video_processor._parse_duration("INVALID") == 0
        assert video_processor._parse_duration("") == 0
```

**Run tests:**
```bash
uv run pytest tests/test_video_processor.py::TestExtractMetadata -v
uv run pytest tests/test_video_processor.py::TestParseDuration -v
```

**Expected:** ✅ ALL PASS

**Check coverage:**
```bash
uv run pytest tests/test_video_processor.py \
  --cov=app.core.video_processor \
  --cov-report=term-missing
```

**Expected:** `extract_metadata` and `_parse_duration` at 100% coverage

### Step 7: Repeat for Remaining Methods

**Implement in this order:**
1. ✅ `__init__` (done)
2. ✅ `extract_metadata` (done)
3. ⏭️ `is_duplicate` (next)
4. ⏭️ `match_ips`
5. ⏭️ `save_and_publish`
6. ⏭️ `process_batch`

**For each method:**
- Implement (30-45 min)
- Write tests (45-60 min)
- Run tests until 100% pass
- Check coverage ≥80%
- Move to next method

**Total time for Story 1.1:** ~6 hours

### Step 8: Integration Test Locally (30 min)

**Create test endpoint in router:**

```python
# app/routers/discover.py

@router.post("/test-processor")
async def test_processor(
    video_processor: VideoProcessor = Depends(get_video_processor)
):
    """Test VideoProcessor with real YouTube data."""
    # Hardcode a known video ID
    youtube = YouTubeClient(api_key=settings.youtube_api_key)
    video_data = youtube.get_video_details(["dQw4w9WgXcQ"])[0]

    # Process it
    metadata = video_processor.extract_metadata(video_data)

    # Check duplicates
    is_dup = video_processor.is_duplicate(metadata.video_id)

    # Match IPs
    matched_ips = video_processor.match_ips(metadata)

    return {
        "video_id": metadata.video_id,
        "title": metadata.title,
        "is_duplicate": is_dup,
        "matched_ips": matched_ips
    }
```

**Test with emulators:**
```bash
# Terminal 1: Start service
./scripts/dev-local.sh discovery-service

# Terminal 2: Test endpoint
curl -X POST http://localhost:8080/test-processor

# Expected: JSON response with video data
```

**Verify in Firestore emulator:**
- Open http://localhost:4000
- Check `videos` collection
- Verify document structure

### Step 9: Deploy to GCP Dev (15 min)

```bash
# Deploy
./scripts/deploy-service.sh discovery-service dev

# Wait for deployment...

# Get service URL
SERVICE_URL=$(gcloud run services describe discovery-service \
  --region=us-central1 \
  --format='value(status.url)')

# Test health
curl $SERVICE_URL/health

# Test processor
curl -X POST $SERVICE_URL/test-processor
```

**Expected:**
- ✅ Deployment succeeds
- ✅ Health check returns 200
- ✅ Test endpoint works
- ✅ No errors in Cloud Logging

### Step 10: Verify in Production (10 min)

```bash
# Check Cloud Logging
gcloud logging read \
  "resource.type=cloud_run_revision \
   AND resource.labels.service_name=discovery-service \
   AND severity>=ERROR" \
  --limit 50 \
  --format json

# Expected: Empty or no new errors

# Check Firestore
# - Open GCP Console → Firestore
# - Check videos collection
# - Verify documents created

# Check PubSub
gcloud pubsub topics list
gcloud pubsub subscriptions pull risk-scorer-sub --limit=5

# Monitor for 10 minutes
# Watch logs, check for crashes, memory issues, etc.
```

### Step 11: Mark Story as DONE ✅

**Update epic document:**

```markdown
## Story 1.1: Create VideoProcessor Class ✅

**Status:** DONE
**Completed:** 2024-01-20

**Checklist:**
- [x] Code passes ruff lint
- [x] Type hints on all functions
- [x] Docstrings complete
- [x] No duplication
- [x] 45 tests written
- [x] 92% coverage
- [x] All tests pass
- [x] Integration tests pass
- [x] Runs with emulators
- [x] Deploys to dev
- [x] Health check passes
- [x] No errors in logs
- [x] Documentation updated

**Metrics:**
- LOC: 182
- Tests: 45 passing
- Coverage: 92%
- Complexity: 6 (max)

**Deployment:**
- Dev: ✅ https://discovery-service-dev-xxx.run.app
- Tested: 2024-01-20 15:45 UTC
```

**Commit and push:**
```bash
git add .
git commit -m "feat(discovery): implement VideoProcessor for zero-duplication video operations

- Eliminates 300+ lines of duplicate code
- Single source of truth for video processing
- 92% test coverage (45 tests)
- All edge cases handled
- Deployed and verified in GCP

Closes #1 (Story 1.1)
"
git push origin main
```

---

## ⏱️ Time Estimates by Story Size

### Small Story (2-3 points)
- Implementation: 2-3 hours
- Testing: 1-2 hours
- Deployment: 0.5 hours
- **Total: 3.5-5.5 hours**

### Medium Story (5-8 points)
- Implementation: 4-6 hours
- Testing: 3-4 hours
- Deployment: 0.5 hours
- **Total: 7.5-10.5 hours**

### Large Story (10-13 points)
- Implementation: 8-10 hours
- Testing: 5-6 hours
- Deployment: 1 hour
- **Total: 14-17 hours**

**Rule of thumb:** 1 story point = ~1.5 hours

---

## 🎯 Daily Goals

### Junior Developer
- 3-5 story points per day
- 1 small story OR partial medium story
- Focus on quality over speed

### Mid-Level Developer
- 5-8 story points per day
- 1 medium story OR 2 small stories
- Balance speed and quality

### Senior Developer
- 8-13 story points per day
- 1 large story OR 2 medium stories
- Fast iteration, high quality

---

## 📊 Sprint Planning

### Sprint 1 (10 points)
- Story 1.1: 5 points (2-3 days)
- Story 1.2: 3 points (1-2 days)
- Story 1.3: 2 points (1 day)
- **Duration: 5 days**

### Sprint 2 (13 points)
- Story 2.1: 8 points (3-4 days)
- Story 2.2: 5 points (2-3 days)
- **Duration: 6 days**

### Sprint 3 (21 points)
- Story 2.3: 8 points (3-4 days)
- Story 3.1: 8 points (3-4 days)
- Story 3.2: 3 points (1-2 days)
- **Duration: 8 days**

**Total for all 5 sprints:** ~40 working days (8 weeks)

---

## ✅ Success Indicators

**Story is going well if:**
- Tests are easy to write
- Coverage increases steadily
- No major blockers
- Code reads clearly
- Deployment is smooth

**Story needs help if:**
- Can't figure out how to test
- Coverage stuck below 70%
- Multiple deployment failures
- Code is confusing to read
- Taking 2x estimated time

**Action:** Review IMPLEMENTATION-STANDARDS.md, ask for help, or redesign approach

---

## 🚀 Momentum Tips

1. **Start with easiest method** - Build confidence
2. **Test immediately** - Don't accumulate untested code
3. **Commit often** - Every method that passes tests
4. **Deploy early** - Don't wait until "done"
5. **Celebrate wins** - Each passing test is progress

**Consistent daily progress beats heroic all-nighters.**

---

**Now you know the flow. Go implement Story 1.1!** 🚀
