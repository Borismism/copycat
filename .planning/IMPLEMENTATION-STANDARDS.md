# Implementation Standards - Discovery Service Redesign

## Core Philosophy: Zero Tolerance for Code Slop

**We write FANTASTIC code. Period.**

This is not a refactoring where we "improve" bad code. This is a **complete rewrite** where we:
- DELETE all bad code without mercy
- Build new, lean, beautiful components from scratch
- Test everything before calling it "done"
- Deploy and verify in GCP before moving to next story

**Code slop is absolutely NOT allowed.**

---

## What is "Fantastic Code"?

### Characteristics of Fantastic Code

✅ **Readable**
- Read like English prose
- Variable names describe intent perfectly
- No clever tricks, no magic numbers
- Comments explain WHY, not WHAT

✅ **Simple**
- Does ONE thing well (Single Responsibility Principle)
- No nested ifs >2 levels deep
- Functions <50 lines, classes <200 lines
- Cyclomatic complexity <10

✅ **Testable**
- Pure functions where possible
- Dependencies injected, not hardcoded
- Easy to mock external services
- 100% of logic paths covered

✅ **Performant**
- No N+1 queries
- Batch operations where possible
- Efficient algorithms (no O(n²) unless n is tiny)
- Lazy loading, caching when appropriate

✅ **Safe**
- Type hints on ALL functions
- Error handling on ALL external calls
- Input validation on ALL user data
- Graceful degradation

✅ **Maintainable**
- Clear separation of concerns
- Follows project conventions
- Self-documenting structure
- Easy to modify in 6 months

---

## What is "Code Slop"?

### Characteristics of Code Slop (FORBIDDEN)

❌ **Copy-Paste Programming**
```python
# FORBIDDEN - Same logic repeated
def process_video_a(video):
    metadata = extract_metadata(video)
    save_to_firestore(metadata)
    publish_to_pubsub(metadata)

def process_video_b(video):
    metadata = extract_metadata(video)  # DUPLICATION!
    save_to_firestore(metadata)         # DUPLICATION!
    publish_to_pubsub(metadata)         # DUPLICATION!
```

❌ **God Classes**
```python
# FORBIDDEN - Does everything
class DiscoveryService:
    def discover_trending(self):    # 50 lines
    def discover_gaming(self):       # 50 lines
    def discover_viral(self):        # 50 lines
    def _extract_metadata(self):     # 40 lines
    def _save_to_firestore(self):    # 30 lines
    def _publish_to_pubsub(self):    # 20 lines
    # ... 685 lines total - TOO MUCH!
```

❌ **Magic Numbers**
```python
# FORBIDDEN
if views > 10000:  # What does 10000 mean?
    score = views * 0.75  # Why 0.75?
```

❌ **Deep Nesting**
```python
# FORBIDDEN
if condition_a:
    if condition_b:
        if condition_c:
            if condition_d:
                if condition_e:  # 5 levels deep!
                    do_something()
```

❌ **Unclear Names**
```python
# FORBIDDEN
def process(data):  # Process what? How?
    x = data.get('a')  # What is 'a'?
    y = calc(x)  # What does calc do?
    return y
```

❌ **No Error Handling**
```python
# FORBIDDEN
def get_video(video_id):
    doc = firestore.collection('videos').document(video_id).get()
    return doc.to_dict()  # What if doc doesn't exist?
```

❌ **Weak Type Hints**
```python
# FORBIDDEN
def process_videos(videos):  # What type is videos?
    return results  # What type is results?
```

---

## Definition of Done (DoD)

A story is **DONE** when ALL of these criteria are met:

### 1. Code Quality ✅

- [ ] **Passes ruff lint** with zero warnings
  ```bash
  uv run ruff check services/discovery-service/app/
  uv run ruff format services/discovery-service/app/
  ```

- [ ] **Type hints on ALL functions**
  ```python
  # GOOD
  def extract_metadata(video_data: dict[str, Any]) -> VideoMetadata:
      pass

  # BAD
  def extract_metadata(video_data):
      pass
  ```

- [ ] **Docstrings on ALL public methods**
  ```python
  def calculate_tier(self, profile: ChannelProfile) -> ChannelTier:
      """
      Calculate channel tier based on infringement history.

      Tiers:
      - PLATINUM: >50% infringement, >10 violations
      - GOLD: 25-50% infringement, >5 violations
      - SILVER: 10-25% infringement
      - BRONZE: <10% infringement
      - IGNORE: 0% after 20+ videos

      Args:
          profile: Channel profile with infringement history

      Returns:
          Appropriate tier based on behavior
      """
      pass
  ```

- [ ] **No code duplication**
  - Run manual review
  - Check for repeated logic patterns
  - Extract common code into shared methods

- [ ] **Follows project structure**
  - Business logic in `app/core/`
  - API endpoints in `app/routers/`
  - Models in `app/models.py`
  - Config in `app/config.py`

### 2. Testing ✅

- [ ] **Unit tests written for ALL new code**
  ```python
  # tests/test_video_processor.py
  def test_extract_metadata_success():
      """Test successful metadata extraction."""
      pass

  def test_extract_metadata_missing_fields():
      """Test extraction with missing optional fields."""
      pass

  def test_extract_metadata_invalid_data():
      """Test extraction with malformed data."""
      pass
  ```

- [ ] **Test coverage ≥80% for new code**
  ```bash
  cd services/discovery-service
  uv run pytest --cov=app --cov-report=term-missing --cov-report=html
  # Check coverage/html/index.html for detailed report
  ```

- [ ] **All tests pass locally**
  ```bash
  ./scripts/test-service.sh discovery-service
  ```

- [ ] **Integration tests for external dependencies**
  - Mock Firestore operations
  - Mock PubSub publishing
  - Mock YouTube API calls

  ```python
  @pytest.fixture
  def mock_firestore():
      """Mock Firestore client."""
      client = MagicMock(spec=firestore.Client)
      return client

  def test_save_video_to_firestore(mock_firestore):
      """Test video saved correctly to Firestore."""
      processor = VideoProcessor(mock_firestore, None, None)
      # ... test logic
  ```

- [ ] **Edge cases tested**
  - Empty responses from API
  - Malformed data
  - Network timeouts
  - Quota exceeded
  - Missing required fields

### 3. Local Verification ✅

- [ ] **Runs successfully with emulators**
  ```bash
  ./scripts/dev-local.sh discovery-service
  # Service starts without errors
  # Health check passes: curl http://localhost:8080/health
  ```

- [ ] **Manual API testing passes**
  ```bash
  # Test new endpoint
  curl -X POST http://localhost:8080/discover \
    -H "Content-Type: application/json" \
    -d '{"max_quota": 100}'

  # Verify response structure
  # Check logs for errors
  # Inspect Firestore emulator data
  ```

- [ ] **Firestore emulator shows correct data**
  - Navigate to http://localhost:4000 (Firestore UI)
  - Verify collections created
  - Check document structure
  - Validate field types

- [ ] **PubSub emulator receives messages**
  ```bash
  # Check published messages
  gcloud pubsub subscriptions pull projects/test-project/subscriptions/test-sub \
    --auto-ack --limit=10
  ```

### 4. GCP Deployment ✅

- [ ] **Deploys to dev environment successfully**
  ```bash
  ./scripts/deploy-service.sh discovery-service dev
  # Build succeeds
  # Terraform apply succeeds
  # Service starts successfully
  ```

- [ ] **Health check passes in Cloud Run**
  ```bash
  # Get service URL
  SERVICE_URL=$(gcloud run services describe discovery-service \
    --region=us-central1 \
    --platform=managed \
    --format='value(status.url)')

  # Test health endpoint
  curl $SERVICE_URL/health
  # Should return {"status": "healthy", ...}
  ```

- [ ] **Can connect to real Firestore**
  - Service account has correct IAM roles
  - Can read/write documents
  - No connection errors in logs

- [ ] **Can connect to real PubSub**
  - Messages published successfully
  - Message IDs returned
  - No permission errors

- [ ] **Cloud Logging shows no errors**
  ```bash
  gcloud logging read "resource.type=cloud_run_revision \
    AND resource.labels.service_name=discovery-service \
    AND severity>=ERROR" \
    --limit 50 \
    --format json
  # Should return empty or expected errors only
  ```

### 5. Documentation ✅

- [ ] **Inline code comments for complex logic**
  ```python
  # Calculate tier based on infringement rate
  # We use 50% threshold for PLATINUM because:
  # 1. Channels with >50% rate are professional infringers
  # 2. Requires >10 violations to avoid false positives from small samples
  # 3. Historical data shows 50%+ channels account for 80% of total violations
  if profile.infringement_rate > 0.50 and profile.infringing_videos_count > 10:
      return ChannelTier.PLATINUM
  ```

- [ ] **Updated API documentation**
  - OpenAPI spec auto-generated from FastAPI
  - Endpoint descriptions clear
  - Request/response examples provided

- [ ] **README or CLAUDE.md updated if needed**
  - New features documented
  - Architecture changes explained
  - Examples provided

### 6. Code Review ✅

- [ ] **Self-review checklist completed**
  - Read every line of changed code
  - Check for edge cases
  - Look for potential bugs
  - Verify error handling
  - Confirm type safety

- [ ] **No commented-out code**
  - Delete dead code, don't comment it out
  - Use git history if you need to reference old code

- [ ] **No debug print statements**
  ```python
  # BAD
  print(f"Debug: video_id = {video_id}")

  # GOOD
  logger.debug(f"Processing video: {video_id}")
  ```

- [ ] **Proper logging levels used**
  - `logger.debug()` - Detailed diagnostic info
  - `logger.info()` - Important business events
  - `logger.warning()` - Unexpected but handled situations
  - `logger.error()` - Errors that need attention
  - `logger.critical()` - System-threatening issues

---

## Story Implementation Workflow

### Step 1: Delete Bad Code First

**Before writing ANY new code, delete the old bad code.**

Example for Story 1.1 (VideoProcessor):
```bash
cd services/discovery-service/app/core

# Delete the duplicate logic from discovery.py
# We'll completely rewrite the relevant sections
git diff discovery.py  # Review what we're removing
```

Create a new clean file:
```bash
touch video_processor.py
```

### Step 2: Write Skeleton with Type Hints

Write the class structure with ALL type hints and docstrings FIRST, before any implementation:

```python
"""Video processing operations."""

from datetime import datetime
from typing import Any

from google.cloud import firestore, pubsub_v1
from pydantic import BaseModel

from ..models import VideoMetadata
from .ip_loader import IPTargetManager


class VideoProcessor:
    """
    Handles ALL video processing operations.

    Responsibilities:
    - Extract metadata from YouTube API responses
    - Check for duplicates in Firestore
    - Match videos against IP targets
    - Save videos to Firestore
    - Publish videos to PubSub

    Zero duplication - single source of truth for video operations.
    """

    def __init__(
        self,
        firestore_client: firestore.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
        ip_manager: IPTargetManager,
        topic_path: str,
    ):
        """
        Initialize video processor.

        Args:
            firestore_client: Firestore client for data persistence
            pubsub_publisher: PubSub client for event publishing
            ip_manager: IP target manager for content matching
            topic_path: Full PubSub topic path for discovered videos
        """
        pass

    def extract_metadata(self, video_data: dict[str, Any]) -> VideoMetadata:
        """
        Extract video metadata from YouTube API response.

        Args:
            video_data: Raw video data from YouTube API

        Returns:
            Structured video metadata

        Raises:
            ValueError: If required fields are missing
            KeyError: If video data structure is invalid
        """
        pass

    def is_duplicate(
        self,
        video_id: str,
        max_age_days: int = 7
    ) -> bool:
        """
        Check if video was already processed recently.

        Args:
            video_id: YouTube video ID
            max_age_days: Consider duplicate if processed within this many days

        Returns:
            True if video is duplicate, False if new
        """
        pass

    def match_ips(self, metadata: VideoMetadata) -> list[str]:
        """
        Match video content against configured IP targets.

        Searches title, description, tags, and channel name for IP keywords.

        Args:
            metadata: Video metadata to check

        Returns:
            List of matched IP names (empty if no matches)
        """
        pass

    def save_and_publish(self, metadata: VideoMetadata) -> bool:
        """
        Atomically save video to Firestore and publish to PubSub.

        Args:
            metadata: Video metadata to save

        Returns:
            True if successful, False otherwise

        Raises:
            firestore.FirestoreError: If Firestore operation fails
            pubsub.PublisherError: If PubSub publish fails
        """
        pass

    def process_batch(
        self,
        video_data_list: list[dict[str, Any]]
    ) -> list[VideoMetadata]:
        """
        Process multiple videos efficiently.

        For each video:
        1. Extract metadata
        2. Check for duplicates
        3. Match against IPs
        4. Save to Firestore
        5. Publish to PubSub

        Args:
            video_data_list: List of raw video data from YouTube API

        Returns:
            List of successfully processed videos with matched IPs
        """
        pass
```

### Step 3: Implement One Method at a Time

Implement methods in dependency order, testing each one before moving to next:

1. **extract_metadata()** - No dependencies
2. **is_duplicate()** - Depends on Firestore
3. **match_ips()** - Depends on ip_manager
4. **save_and_publish()** - Depends on Firestore + PubSub
5. **process_batch()** - Depends on all above

### Step 4: Write Tests Immediately

**DO NOT move to next method until tests are written and passing.**

```python
# tests/test_video_processor.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.core.video_processor import VideoProcessor
from app.models import VideoMetadata


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
            "duration": "PT5M30S"  # 5 minutes 30 seconds
        }
    }


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    return MagicMock()


@pytest.fixture
def mock_pubsub():
    """Mock PubSub publisher."""
    return MagicMock()


@pytest.fixture
def mock_ip_manager():
    """Mock IP target manager."""
    manager = MagicMock()
    manager.match_content.return_value = [
        MagicMock(name="Superman")
    ]
    return manager


@pytest.fixture
def video_processor(mock_firestore, mock_pubsub, mock_ip_manager):
    """Video processor instance with mocked dependencies."""
    return VideoProcessor(
        firestore_client=mock_firestore,
        pubsub_publisher=mock_pubsub,
        ip_manager=mock_ip_manager,
        topic_path="projects/test/topics/videos"
    )


class TestExtractMetadata:
    """Tests for extract_metadata method."""

    def test_extract_metadata_success(
        self,
        video_processor,
        sample_video_data
    ):
        """Test successful metadata extraction with all fields."""
        metadata = video_processor.extract_metadata(sample_video_data)

        assert metadata.video_id == "test_video_123"
        assert metadata.title == "Superman AI Generated Movie"
        assert metadata.channel_id == "UC_test_channel"
        assert metadata.view_count == 50000
        assert metadata.duration_seconds == 330  # 5:30
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
        assert metadata.view_count == 0  # Default
        assert metadata.duration_seconds == 0  # Default
        assert metadata.description == ""  # Default

    def test_extract_metadata_invalid_duration(
        self,
        video_processor,
        sample_video_data
    ):
        """Test extraction with malformed duration string."""
        sample_video_data["contentDetails"]["duration"] = "INVALID"

        metadata = video_processor.extract_metadata(sample_video_data)

        assert metadata.duration_seconds == 0  # Fallback

    def test_extract_metadata_missing_required_fields(
        self,
        video_processor
    ):
        """Test extraction fails with missing required fields."""
        invalid_data = {"id": "test_123"}

        with pytest.raises(KeyError):
            video_processor.extract_metadata(invalid_data)


class TestIsDuplicate:
    """Tests for is_duplicate method."""

    def test_is_duplicate_video_exists_recently(
        self,
        video_processor,
        mock_firestore
    ):
        """Test returns True for recently processed video."""
        # Mock Firestore response
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "discovered_at": datetime.utcnow()
        }

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("test_video_123")

        assert result is True

    def test_is_duplicate_video_exists_old(
        self,
        video_processor,
        mock_firestore
    ):
        """Test returns False for old video beyond max_age_days."""
        from datetime import timedelta

        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "discovered_at": datetime.utcnow() - timedelta(days=10)
        }

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("test_video_123", max_age_days=7)

        assert result is False

    def test_is_duplicate_video_not_exists(
        self,
        video_processor,
        mock_firestore
    ):
        """Test returns False for new video."""
        doc_mock = MagicMock()
        doc_mock.exists = False

        mock_firestore.collection.return_value.document.return_value.get.return_value = doc_mock

        result = video_processor.is_duplicate("new_video_456")

        assert result is False


# Continue with more test classes...
```

### Step 5: Run Tests Continuously

```bash
# Run tests after each method implementation
cd services/discovery-service
uv run pytest tests/test_video_processor.py -v

# Run with coverage
uv run pytest tests/test_video_processor.py --cov=app.core.video_processor --cov-report=term-missing

# Should see:
# ✓ All tests passing
# ✓ Coverage ≥80%
# ✓ No missing lines in critical paths
```

### Step 6: Integration Test Locally

```bash
# Start emulators and service
./scripts/dev-local.sh discovery-service

# In another terminal, test the endpoint
curl -X POST http://localhost:8080/test-video-processor \
  -H "Content-Type: application/json" \
  -d '{
    "video_data": {...}
  }'

# Check Firestore emulator at http://localhost:4000
# Verify documents created correctly
```

### Step 7: Deploy to GCP Dev

```bash
# Deploy to dev environment
./scripts/deploy-service.sh discovery-service dev

# Wait for deployment
# Check Cloud Run logs for errors
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=discovery-service" \
  --limit 20 \
  --format json

# Test deployed service
SERVICE_URL=$(gcloud run services describe discovery-service \
  --region=us-central1 \
  --format='value(status.url)')

curl $SERVICE_URL/health

# Test actual functionality
curl -X POST $SERVICE_URL/discover \
  -H "Content-Type: application/json" \
  -d '{"max_quota": 100}'
```

### Step 8: Verify in Production Environment

```bash
# Check Firestore in GCP Console
# - Navigate to Firestore
# - Verify collections exist
# - Check document structure
# - Validate field types

# Check PubSub messages
gcloud pubsub subscriptions pull risk-scorer-sub --auto-ack --limit=5

# Check Cloud Logging for errors
# Should be ZERO errors related to new code

# Monitor for 10 minutes
# Ensure no crashes, no memory leaks, no error spikes
```

### Step 9: Mark Story as DONE

Only mark as DONE when ALL Definition of Done criteria are met:

```markdown
## Story 1.1: Create VideoProcessor Class ✅

**Status:** DONE

**Completed Checklist:**
- [x] Code passes ruff lint
- [x] Type hints on all functions
- [x] Docstrings on all public methods
- [x] No code duplication
- [x] Unit tests written (45 tests)
- [x] Test coverage 92%
- [x] All tests pass locally
- [x] Integration tests pass
- [x] Edge cases tested
- [x] Runs with emulators successfully
- [x] Manual API testing passes
- [x] Deploys to dev successfully
- [x] Health check passes in Cloud Run
- [x] Connects to Firestore correctly
- [x] Connects to PubSub correctly
- [x] No errors in Cloud Logging
- [x] Code comments added
- [x] API docs updated
- [x] Self-review completed
- [x] No debug code remaining

**Metrics:**
- Lines of code: 182 LOC
- Test coverage: 92%
- Cyclomatic complexity: 6 (max)
- Tests: 45 passing

**Deployment:**
- Dev environment: ✅ Deployed, tested, working
- Cloud Run URL: https://discovery-service-dev-xxxxx.run.app
- First deployment: 2024-01-20 14:30 UTC
- Last tested: 2024-01-20 15:45 UTC

**Evidence:**
- Screenshot of test coverage report
- Screenshot of Cloud Run logs (no errors)
- Screenshot of Firestore data
- cURL output showing successful API calls
```

---

## Common Pitfalls to Avoid

### ❌ Pitfall 1: "I'll write tests later"

**NO.** Write tests IMMEDIATELY after implementing each method.

Tests are not optional. Tests are how you PROVE your code works.

### ❌ Pitfall 2: "This is good enough"

**NO.** "Good enough" is not good enough.

Either the code is FANTASTIC or it gets deleted and rewritten.

### ❌ Pitfall 3: "I'll refactor this later"

**NO.** There is no "later" in this project.

We refactor NOW or we don't write the code at all.

### ❌ Pitfall 4: "Tests are too hard to write"

**NO.** If tests are hard to write, your code is badly designed.

Rewrite the code to be testable. Use dependency injection, pure functions, clear interfaces.

### ❌ Pitfall 5: "It works on my machine"

**NO.** It must work on GCP Cloud Run or it doesn't work.

Local success is step 5 of 9, not the finish line.

### ❌ Pitfall 6: "I'll document this later"

**NO.** Docstrings are written BEFORE implementation, not after.

If you can't explain what a function does before writing it, you don't understand the problem well enough.

### ❌ Pitfall 7: "This small duplication doesn't matter"

**NO.** All duplication matters.

Today it's 3 lines. Tomorrow it's 30. Next month it's 300.

Extract it into a shared method NOW.

### ❌ Pitfall 8: "The test is flaky, I'll ignore it"

**NO.** Fix flaky tests immediately.

Flaky tests are worse than no tests - they train you to ignore failures.

### ❌ Pitfall 9: "I'll clean up commented code later"

**NO.** Delete commented code NOW.

We have git history. We don't need code archaeology.

### ❌ Pitfall 10: "Type hints are too verbose"

**NO.** Type hints are mandatory.

They catch bugs at dev time, not production time. They're documentation that stays in sync.

---

## Code Review Checklist

Before marking a story as DONE, go through this checklist:

### Functionality
- [ ] Does it solve the story requirements completely?
- [ ] Are all acceptance criteria met?
- [ ] Does it handle edge cases gracefully?
- [ ] Are errors handled properly?
- [ ] Is user input validated?

### Code Quality
- [ ] Is the code readable by someone who didn't write it?
- [ ] Are variable names descriptive and clear?
- [ ] Are functions single-purpose and focused?
- [ ] Is the logic flow easy to follow?
- [ ] Are there any "clever" tricks that should be simplified?

### Type Safety
- [ ] Do all functions have type hints?
- [ ] Are complex types properly defined?
- [ ] Are return types specified?
- [ ] Does mypy pass (if enabled)?

### Testing
- [ ] Are all code paths tested?
- [ ] Are edge cases covered?
- [ ] Are error conditions tested?
- [ ] Do tests use clear assertions?
- [ ] Are test names descriptive?
- [ ] Is test data realistic?

### Performance
- [ ] Are database queries efficient?
- [ ] Are API calls batched where possible?
- [ ] Is caching used appropriately?
- [ ] Are there any O(n²) algorithms?
- [ ] Is lazy loading used where beneficial?

### Security
- [ ] Is user input sanitized?
- [ ] Are API keys/secrets handled correctly?
- [ ] Are database queries parameterized?
- [ ] Are permissions checked?
- [ ] Is sensitive data logged?

### Deployment
- [ ] Does it deploy successfully?
- [ ] Does health check pass?
- [ ] Are environment variables set?
- [ ] Do logs show expected behavior?
- [ ] Are there any permission errors?

### Documentation
- [ ] Are docstrings complete?
- [ ] Are complex sections commented?
- [ ] Is the README updated?
- [ ] Are API docs current?

---

## Example: Story 1.1 Complete Implementation

Here's what a COMPLETE implementation looks like:

### File: `app/core/video_processor.py`

```python
"""Video processing operations - zero duplication."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore, pubsub_v1

from ..config import settings
from ..models import VideoMetadata, VideoStatus
from .ip_loader import IPTargetManager

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Handles ALL video processing operations.

    Single source of truth for:
    - Metadata extraction from YouTube API
    - Duplicate detection
    - IP matching
    - Firestore persistence
    - PubSub publishing

    Zero duplication across all discovery methods.
    """

    def __init__(
        self,
        firestore_client: firestore.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
        ip_manager: IPTargetManager,
        topic_path: str,
    ):
        """
        Initialize video processor.

        Args:
            firestore_client: Firestore client for data persistence
            pubsub_publisher: PubSub client for event publishing
            ip_manager: IP target manager for content matching
            topic_path: Full PubSub topic path (projects/X/topics/Y)
        """
        self.firestore = firestore_client
        self.publisher = pubsub_publisher
        self.ip_manager = ip_manager
        self.topic_path = topic_path
        self.videos_collection = "videos"

        logger.info("VideoProcessor initialized")

    def extract_metadata(self, video_data: dict[str, Any]) -> VideoMetadata:
        """
        Extract structured metadata from YouTube API response.

        Handles both search results and video.list responses:
        - search.list: id is {"videoId": "xxx"}
        - videos.list: id is "xxx"

        Args:
            video_data: Raw video data from YouTube API

        Returns:
            Structured video metadata with all fields

        Raises:
            KeyError: If required fields (id, snippet) are missing
            ValueError: If video_id cannot be extracted
        """
        # Extract video ID (handle both search and videos.list formats)
        video_id = video_data.get("id")
        if isinstance(video_id, dict):
            video_id = video_id.get("videoId", "")

        if not video_id:
            raise ValueError("Cannot extract video_id from video_data")

        snippet = video_data.get("snippet", {})
        statistics = video_data.get("statistics", {})
        content_details = video_data.get("contentDetails", {})

        # Parse published date
        published_at_str = snippet.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(
                published_at_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            logger.warning(
                f"Invalid publishedAt for video {video_id}: {published_at_str}"
            )
            published_at = datetime.utcnow()

        # Parse ISO 8601 duration (PT1H2M3S)
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
        """
        Parse ISO 8601 duration to seconds.

        Format: PT[hours]H[minutes]M[seconds]S
        Examples:
        - PT5M30S = 5 minutes 30 seconds = 330 seconds
        - PT1H15M = 1 hour 15 minutes = 4500 seconds
        - PT45S = 45 seconds

        Args:
            duration_str: ISO 8601 duration string

        Returns:
            Total seconds (0 if parsing fails)
        """
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str)

        if not match:
            logger.warning(f"Cannot parse duration: {duration_str}")
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    def is_duplicate(
        self,
        video_id: str,
        max_age_days: int = 7
    ) -> bool:
        """
        Check if video was processed recently.

        A video is considered duplicate if:
        1. It exists in Firestore, AND
        2. It was discovered within last max_age_days

        Rationale: Re-scan old videos to track view growth,
        but avoid scanning same video multiple times per week.

        Args:
            video_id: YouTube video ID
            max_age_days: Consider duplicate if within this many days

        Returns:
            True if duplicate (skip processing), False if new
        """
        doc_ref = self.firestore.collection(
            self.videos_collection
        ).document(video_id)

        try:
            doc = doc_ref.get()

            if not doc.exists:
                return False

            video_data = doc.to_dict()
            discovered_at = video_data.get("discovered_at")

            if not discovered_at:
                # Old document without timestamp - not a duplicate
                return False

            days_since_scan = (
                datetime.utcnow() - discovered_at
            ).days

            is_recent = days_since_scan < max_age_days

            if is_recent:
                logger.debug(
                    f"Video {video_id} is duplicate "
                    f"(scanned {days_since_scan} days ago)"
                )

            return is_recent

        except Exception as e:
            logger.error(f"Error checking duplicate for {video_id}: {e}")
            # On error, assume not duplicate (better to process than skip)
            return False

    def match_ips(self, metadata: VideoMetadata) -> list[str]:
        """
        Match video content against configured IP targets.

        Searches across:
        - Video title
        - Video description
        - Video tags
        - Channel name

        Uses IP target keywords and regex patterns from ip_targets.yaml.

        Args:
            metadata: Video metadata to analyze

        Returns:
            List of matched IP names (empty if no matches)
        """
        # Combine all searchable text
        text_to_check = " ".join([
            metadata.title,
            metadata.description,
            " ".join(metadata.tags),
            metadata.channel_title,
        ])

        # Match against IP targets
        matched_targets = self.ip_manager.match_content(text_to_check)

        if matched_targets:
            ip_names = [ip.name for ip in matched_targets]
            logger.info(
                f"Video {metadata.video_id} matched IPs: "
                f"{', '.join(ip_names)}"
            )
            return ip_names

        return []

    def save_and_publish(self, metadata: VideoMetadata) -> bool:
        """
        Atomically save to Firestore and publish to PubSub.

        Operations:
        1. Save video document to Firestore
        2. Publish video message to PubSub

        Both operations must succeed. If either fails, logs error
        but doesn't raise (allows processing to continue).

        Args:
            metadata: Video metadata to persist

        Returns:
            True if both operations succeeded, False otherwise
        """
        try:
            # Save to Firestore
            doc_ref = self.firestore.collection(
                self.videos_collection
            ).document(metadata.video_id)

            video_doc = {
                **metadata.model_dump(),
                "status": VideoStatus.DISCOVERED.value,
                "discovered_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            doc_ref.set(video_doc)
            logger.info(f"Saved video {metadata.video_id} to Firestore")

            # Publish to PubSub
            message_data = metadata.model_dump_json().encode("utf-8")
            future = self.publisher.publish(self.topic_path, message_data)
            message_id = future.result(timeout=settings.pubsub_timeout_seconds)

            logger.info(
                f"Published video {metadata.video_id} to PubSub: {message_id}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to save/publish video {metadata.video_id}: {e}"
            )
            return False

    def process_batch(
        self,
        video_data_list: list[dict[str, Any]],
        skip_duplicates: bool = True,
        skip_no_ip_match: bool = True,
    ) -> list[VideoMetadata]:
        """
        Process multiple videos efficiently.

        Pipeline:
        1. Extract metadata from all videos
        2. Filter duplicates (optional)
        3. Match IPs
        4. Filter videos with no IP matches (optional)
        5. Save to Firestore + publish to PubSub

        Args:
            video_data_list: Raw video data from YouTube API
            skip_duplicates: Skip videos processed recently
            skip_no_ip_match: Skip videos with no IP matches

        Returns:
            Successfully processed videos (with IP matches)
        """
        if not video_data_list:
            return []

        processed = []
        skipped_duplicate = 0
        skipped_no_match = 0
        errors = 0

        logger.info(f"Processing batch of {len(video_data_list)} videos")

        for video_data in video_data_list:
            try:
                # Extract metadata
                metadata = self.extract_metadata(video_data)

                # Check duplicates
                if skip_duplicates and self.is_duplicate(metadata.video_id):
                    skipped_duplicate += 1
                    continue

                # Match IPs
                matched_ips = self.match_ips(metadata)

                if not matched_ips:
                    if skip_no_ip_match:
                        skipped_no_match += 1
                        continue

                metadata.matched_ips = matched_ips

                # Save and publish
                if self.save_and_publish(metadata):
                    processed.append(metadata)
                else:
                    errors += 1

            except Exception as e:
                logger.error(f"Error processing video: {e}")
                errors += 1
                continue

        logger.info(
            f"Batch complete: {len(processed)} processed, "
            f"{skipped_duplicate} duplicates, "
            f"{skipped_no_match} no IP match, "
            f"{errors} errors"
        )

        return processed
```

### Tests: `tests/test_video_processor.py`

(Already shown above - 45+ tests covering all methods)

### Integration: Update DiscoveryService to use VideoProcessor

```python
# app/core/discovery.py - SIMPLIFIED VERSION

class DiscoveryService:
    """Simplified discovery service using VideoProcessor."""

    def __init__(
        self,
        youtube_client: YouTubeClient,
        video_processor: VideoProcessor,
    ):
        self.youtube = youtube_client
        self.processor = video_processor

    def discover_trending(
        self,
        region_code: str = "US",
        max_results: int = 50
    ) -> list[VideoMetadata]:
        """
        Discover trending videos.

        OLD: 50 lines of duplicate code
        NEW: 3 lines using VideoProcessor
        """
        trending_videos = self.youtube.get_trending_videos(
            region_code, max_results
        )
        return self.processor.process_batch(trending_videos)
```

**Before:** 685 LOC in discovery.py with massive duplication
**After:** 182 LOC in video_processor.py + 50 LOC in simplified discovery.py

**Code reduction: 453 lines deleted (66% reduction for Story 1.1 alone!)**

---

## Final Reminder

**Fantastic code is NOT negotiable.**

Every line we write will be read 100 times. Every bug we introduce will cost hours to debug in production. Every shortcut we take will become technical debt that slows us down.

We write code that we're PROUD to show other developers.

We write code that's EASY to understand in 6 months.

We write code that WORKS in production, not just on laptops.

**If you wouldn't want to debug this code at 2 AM, rewrite it.**

---

**Now go build something fantastic.** 🚀
