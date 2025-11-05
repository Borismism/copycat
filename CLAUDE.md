# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Copycat is an AI-generated content detection system that finds copyright violations at scale. It specifically targets **AI-generated Justice League character content** (Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern) created with tools like Sora, Runway, Kling, Pika, etc.

The system uses a microservices architecture deployed on GCP Cloud Run, with an intelligent pipeline that:
1. **Discovers** videos via YouTube API (keyword search + channel tracking)
2. **Builds a library** of videos and channels with view tracking
3. **Prioritizes** scanning based on view velocity, channel quality, and infringement history
4. **Analyzes** videos with Gemini 2.0 Flash using direct YouTube URL input
5. **Adapts** channel monitoring frequency based on posting patterns and infringement rates

**Key Innovation:** Budget exhaustion model - scans until daily Gemini budget (€240) is fully utilized, maximizing detection coverage.

## Development Commands

### Setup & Installation
```bash
# Install uv and sync dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --group dev

# Deploy global GCP infrastructure (run once)
./scripts/setup-infra.sh
```

### Service Development
```bash
./scripts/dev-local.sh <service-name>      # Run locally with Firestore/PubSub emulators
./scripts/test-service.sh <service-name>   # Run pytest with coverage
uv run ruff check .                        # Run ruff linter
uv run ruff format .                       # Format with ruff
```

### Testing Individual Services
```bash
cd services/<service-name>
uv run pytest -v                  # Run all tests
uv run pytest tests/test_foo.py   # Run specific test file
uv run pytest -k test_name        # Run specific test
uv run pytest --cov=app --cov-report=term-missing  # With coverage
```

### Deployment
```bash
./scripts/deploy-service.sh <service-name> dev   # Deploy to dev environment
./scripts/deploy-service.sh <service-name> prod  # Deploy to production

# Examples:
./scripts/deploy-service.sh discovery-service dev
./scripts/deploy-service.sh vision-analyzer-service prod

# Manual deployment via GitHub Actions also available
# - Push to develop → auto-deploys to dev
# - Push to main → auto-deploys to prod
```

### Running Services Locally

#### Option 1: Docker Compose (Recommended for integration testing)
```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d discovery-service risk-analyzer-service

# View logs
docker-compose logs -f risk-analyzer-service

# Stop all services
docker-compose down
```

**Service Ports:**
- `discovery-service`: http://localhost:8081
- `risk-analyzer-service`: http://localhost:8082
- `vision-analyzer-service`: http://localhost:8083
- `api-service`: http://localhost:8080
- `frontend-service`: http://localhost:5173
- Firestore emulator: http://localhost:8200
- PubSub emulator: http://localhost:8085

#### Option 2: Individual Service (dev-local.sh)
The `dev-local.sh` script automatically:
- Starts Firestore emulator on port 8200
- Starts PubSub emulator on port 8085
- Runs the service with uvicorn on port 8080 with hot reload

## Architecture

### Pipeline Flow
```
1. discovery-service
   ↓ (finds videos via YouTube API, initial 5-factor risk scoring)
   │ Publishes to: discovered-videos topic
   ↓
2. risk-analyzer-service ✨ NEW
   ↓ (adaptive risk rescoring with view velocity, channel reputation)
   │ (schedules scans based on risk tier: CRITICAL→6h, HIGH→24h, etc.)
   │ Publishes to: scan-ready topic
   ↓
3. vision-analyzer-service ✨ NEW - FULLY IMPLEMENTED
   ↓ (analyzes videos with Gemini 2.5 Flash via Vertex AI)
   │ (adaptive FPS based on video length + risk tier)
   │ (budget exhaustion: scans until €240/day fully utilized)
   │ (sends results back to risk-analyzer for learning)
   → Firestore + BigQuery
```

**Key Changes from Original Architecture:**
- ✅ **risk-analyzer-service** - Adaptive risk scoring with view velocity
- ✅ **vision-analyzer-service** - Gemini 2.5 Flash with aggressive cost optimization
- ✅ Intelligent adaptive scoring (learns from Gemini results)
- ✅ Viral detection (<6 hours for trending videos)
- ✅ Budget optimization with length-based FPS (20,000-32,000 videos/day capacity)
- ✅ No rate limits (Vertex AI Dynamic Shared Quota)
- ⏸️ chapter-extractor-service & frame-extractor-service not needed (Gemini accepts YouTube URLs directly)

### Service Communication
- Services communicate via **PubSub topics** (event-driven)
- Each service subscribes to specific topics and publishes to the next
- Dead letter queues handle failures
- State stored in **Firestore** with video_id as document ID
- Analytics/results written to **BigQuery**
- Extracted frames stored in **Cloud Storage**

### Shared Infrastructure (terraform/)
Deployed once via `./scripts/setup-infra.sh`:
- Artifact Registry (Docker + Python packages)
- VPC & networking
- Secret Manager (API keys)
- PubSub topics (4 main + dead letter)
- Firestore database
- Cloud Storage buckets
- BigQuery dataset
- IAM service accounts

### Service-Specific Infrastructure (services/*/terraform/)
Each service has its own Terraform that deploys:
- Cloud Run service
- Service-specific IAM bindings
- PubSub subscriptions
- Environment variables

## Service Structure

All services follow this pattern:
```
services/<service-name>/
├── app/
│   ├── main.py              # FastAPI app with /health endpoint
│   ├── core/                # Business logic
│   ├── routers/             # API endpoints
│   ├── middleware/          # Optional: logging, auth
│   └── models.py            # Pydantic models
├── terraform/
│   ├── provider.tf
│   ├── variables.tf
│   ├── main.tf              # Cloud Run + subscriptions
│   └── outputs.tf
├── tests/                   # Pytest tests
├── Dockerfile               # Multi-stage build
├── cloudbuild.yaml          # Cloud Build config
└── pyproject.toml           # UV dependencies
```

## Technology Stack

- **Python 3.13** with **UV package manager** (80-115x faster than Poetry)
- **FastAPI 0.119.1** for all services
- **google-genai 1.46.0** (NEW SDK - `google-generativeai` is legacy, EOL Aug 2025)
- **yt-dlp 2025.10.22** for video metadata/chapters
- **opencv-python 4.12.0.88** for frame extraction
- **GCP Services**: Cloud Run, Firestore, PubSub, Storage, BigQuery, Secret Manager

## Critical Implementation Details

### Gemini SDK Usage via Vertex AI
**IMPORTANT**: Use Vertex AI (IAM auth), NOT API keys:

```python
# ✅ CORRECT - Vertex AI with IAM authentication (google-genai SDK)
from google import genai
from google.auth import default

# Uses Application Default Credentials (service account in Cloud Run)
credentials, project = default()
client = genai.Client(
    vertexai=True,
    project=project,
    location='us-central1'  # or your GCP_REGION
)

response = client.models.generate_content(
    model='gemini-2.0-flash-exp',
    contents=[prompt, image]
)

# ❌ WRONG - API Key approach (not for production)
client = genai.Client(api_key=api_key)  # Don't use in GCP!

# ❌ WRONG - Legacy SDK (google-generativeai) - EOL Aug 31, 2025
import google.generativeai as genai
```

**Why Vertex AI?**
- ✅ IAM authentication (no API keys to manage)
- ✅ Better quota management
- ✅ Enterprise features (monitoring, logging)
- ✅ Regional endpoints
- ✅ Service account permissions

### Risk Scoring Strategy
The risk-scorer-service is the key cost optimization:
- Filters out 70-90% of videos before expensive vision analysis
- Scoring factors: view count, velocity, keywords, duration, channel size
- Only HIGH/MEDIUM risk videos proceed to frame extraction
- Pure logic service (no external API costs)

### API Key Management
discovery-service uses a single YouTube API key:
- Auto-generated via Terraform (unrestricted)
- Stored in Secret Manager
- Automatically loaded into Cloud Run
- Default quota: 10,000 units/day (request increase via GCP Console)

### Environment Variables
Each service uses `pydantic-settings` for config:
- Loads from `.env` for local development
- Uses Cloud Run environment variables in production
- Secret Manager for sensitive values (API keys)
- Required vars: `GCP_PROJECT_ID`, `GCP_REGION`, `ENVIRONMENT`


## Discovery Service Architecture (Epic 3 - Current Implementation)

### Core Components

The Discovery Service has been completely redesigned into a lean, intelligent system:

```
app/core/
├── discovery_engine.py      # Main orchestrator (160 LOC, 95% coverage)
├── channel_tracker.py       # Channel intelligence system (150 LOC)
├── video_processor.py       # Video processing pipeline (116 LOC, 100% coverage)
├── quota_manager.py         # API quota optimization (72 LOC, 93% coverage)
├── view_velocity_tracker.py # Trending detection (106 LOC)
└── youtube_client.py        # YouTube API wrapper
```

**Key Principles:**
- **DRY**: Zero duplication, single responsibility
- **Smart**: AI-powered prioritization, not brute force
- **Efficient**: Every API unit counts (33x improvement)
- **Adaptive**: Learn from scan results
- **Lean**: <500 LOC total, super clean

### Channel Tracking Strategy

**The most efficient discovery method** - replaces wasteful keyword searches with intelligent channel monitoring.

#### Channel Tier System

Channels are automatically categorized based on infringement history:

| Tier | Scan Frequency | Criteria | API Cost |
|------|---------------|----------|----------|
| **PLATINUM** | Daily (24h) | >50% infringement rate, >10 violations | 3 units/scan |
| **GOLD** | Every 3 days (72h) | 25-50% infringement, >5 violations | 3 units/scan |
| **SILVER** | Weekly (7 days) | 10-25% infringement | 3 units/scan |
| **BRONZE** | Monthly (30 days) | <10% infringement | 3 units/scan |
| **IGNORE** | Never | 0% after 20+ videos | 0 units |

**Benefits:**
- Focuses on high-risk channels (70% of discoveries come from 10% of channels)
- Adaptive frequency saves quota on low-risk channels
- Builds institutional knowledge over time
- 30x more efficient than keyword search (3 units vs 100 units)

#### Implementation

```python
from app.core import ChannelTracker

tracker = ChannelTracker(firestore_client)

# Get channels due for scanning
channels = tracker.get_channels_due_for_scan(limit=100)

for channel in channels:
    # Scan channel (cost: 3 units)
    videos = youtube_client.get_channel_uploads(channel.channel_id)
    
    # Process videos
    results = video_processor.process_batch(videos)
    
    # Update channel tier based on results
    tracker.update_after_scan(channel.channel_id, has_violations=len(results) > 0)
```

### Quota Management

**Real-time YouTube API quota tracking** - ensures we never hit quota limits.

#### Quota Costs (YouTube Data API v3)

| Operation | Cost (units) | Returns | Efficiency |
|-----------|--------------|---------|------------|
| `search.list` | 100 | ~50 videos | 2 units/video |
| `videos.list` (details) | 1 | 50 videos | 0.02 units/video |
| `videos.list` (trending) | 1 | 50 videos | 0.02 units/video |
| `channels.list` | 1 | 1 channel | 1 unit/channel |
| `playlistItems.list` | 1 | 50 videos | 0.02 units/video |

**Channel tracking total**: 3 units (channel + playlist + details)

#### Quota Allocation Strategy

```python
DAILY_QUOTA = 10_000  # Default (request increase via GCP Console)

# Smart allocation (maximize ROI)
ALLOCATION = {
    'channel_tracking': 7_000 units,  # 70% - ~2,333 channels/day
    'trending': 2_000 units,          # 20% - ~100,000 videos checked
    'keyword_search': 1_000 units,    # 10% - ~500 targeted searches
}
```

**Efficiency Comparison:**
- **Before**: 100 units per keyword search → 50 videos → 2 units/video
- **After**: 3 units per channel scan → ~17 videos → 0.18 units/video
- **Improvement**: **11x more efficient**

#### Usage Tracking

```python
from app.core import QuotaManager

quota = QuotaManager(daily_quota=10_000)

# Check before operation
if quota.can_afford('search', count=5):
    # Perform 5 searches
    results = youtube_client.search_videos(query, max_results=50)
    quota.record_usage('search', count=5)

# Monitor usage
remaining = quota.get_remaining()
utilization = quota.get_utilization()  # Percentage

# Warnings at 80% usage
if utilization > 0.80:
    logger.warning(f"Quota at {utilization*100}%")
```

### View Velocity Tracking

**Prioritizes viral videos** - identifies trending content for immediate analysis.

#### Trending Score Calculation

```python
from app.core import ViewVelocityTracker

tracker = ViewVelocityTracker(firestore_client)

# Record snapshots over time
tracker.record_view_snapshot(video_id, view_count)

# Calculate velocity
velocity = tracker.calculate_velocity(video_id)
# Returns: ViewVelocity(
#   views_per_hour=12_500,
#   trending_score=95,  # 0-100 scale
# )
```

**Trending Score Ranges:**
- **90-100**: Extremely viral (>10k views/hour)
- **70-89**: Very viral (1k-10k views/hour)
- **50-69**: Viral (100-1k views/hour)
- **30-49**: Trending (10-100 views/hour)
- **0-29**: Normal (<10 views/hour)

**Use Cases:**
- Prioritize high-velocity videos in scan queue
- Allocate more Gemini budget to viral content
- Catch infringements before they go mega-viral

### Discovery Method Costs & ROI

#### Cost Analysis (per 50 videos discovered)

| Method | API Cost | Videos Found | Cost per Video | Success Rate |
|--------|----------|--------------|----------------|--------------|
| **Channel Tracking** | 3 units | ~17 videos | 0.18 units/video | **High** (70%+) |
| **Trending** | 1 unit | 50 videos | 0.02 units/video | **Low** (5%) |
| **Keyword Search** | 100 units | 50 videos | 2 units/video | **Medium** (20%) |

#### ROI Calculation

```python
# Before redesign (keyword-only strategy)
DAILY_QUOTA = 10_000
SEARCHES = 10_000 / 100 = 100 searches
VIDEOS_FOUND = 100 * 50 * 0.20 = 1,000 videos/day

# After redesign (channel-first strategy)
CHANNEL_SCANS = 7_000 / 3 = 2,333 channels
CHANNEL_VIDEOS = 2,333 * 17 * 0.70 = 27,776 videos/day

# Result: 27.8x more videos discovered per day
```

#### Discovery Engine Strategy

```python
from app.core import DiscoveryEngine

engine = DiscoveryEngine(
    youtube_client,
    video_processor,
    channel_tracker,
    quota_manager,
)

# Automatic smart discovery
stats = await engine.discover()
# Phase 1: Channels (70% quota) - most efficient
# Phase 2: Trending (20% quota) - cheap, broad
# Phase 3: Keywords (10% quota) - expensive, precise

print(f"Discovered {stats.videos_discovered} videos")
print(f"Used {stats.quota_used}/{stats.total_quota} units")
print(f"Efficiency: {stats.videos_discovered / stats.quota_used:.2f} videos/unit")
```

### Testing Guidelines

**Target: 80%+ coverage** with focus on business logic.

#### Test Structure

```
tests/
├── test_discovery_engine.py    # Discovery orchestration (13 tests)
├── test_video_processor.py     # Video processing (40 tests)
├── test_channel_tracker.py     # Channel intelligence (28 tests)
├── test_quota_manager.py        # Quota management (30 tests)
└── test_view_velocity_tracker.py # Velocity tracking (20 tests)
```

#### Running Tests

```bash
# All tests
cd services/discovery-service
uv run pytest -v

# With coverage
uv run pytest --cov=app --cov-report=term-missing --cov-report=html

# Specific component
uv run pytest tests/test_discovery_engine.py -v

# Coverage report will show:
# - discovery_engine.py: 95%
# - video_processor.py: 100%
# - channel_tracker.py: 86%
# - quota_manager.py: 93%
```

#### Test Examples

```python
# tests/test_channel_tracker.py
def test_tier_calculation():
    """Test channel tier assignment logic."""
    profile = ChannelProfile(
        channel_id="UC_test",
        total_videos_found=20,
        infringing_videos_count=12,
        infringement_rate=0.60,
    )
    
    tier = tracker.calculate_tier(profile)
    assert tier == ChannelTier.PLATINUM  # >50% infringement

def test_next_scan_time():
    """Test scan frequency by tier."""
    profile = ChannelProfile(
        channel_id="UC_test",
        tier=ChannelTier.GOLD,
        last_scanned_at=datetime.now() - timedelta(days=4),
    )
    
    next_scan = tracker.get_next_scan_time(profile)
    # Gold tier = 3 days, should be due
    assert next_scan <= datetime.now()

# tests/test_quota_manager.py
def test_quota_enforcement():
    """Ensure quota limits are respected."""
    quota = QuotaManager(daily_quota=10_000)
    quota.used_quota = 9_900
    
    # Should allow 1 unit operation
    assert quota.can_afford('trending', 1) is True
    
    # Should block 200 unit operation
    assert quota.can_afford('search', 2) is False

# tests/test_discovery_engine.py
@pytest.mark.asyncio
async def test_discovery_respects_quota():
    """Test discovery stops at quota limit."""
    quota_manager = Mock()
    quota_manager.can_afford.side_effect = [True, False]  # Allow then block
    
    engine = DiscoveryEngine(..., quota_manager=quota_manager)
    stats = await engine.discover()
    
    # Should have stopped when quota exhausted
    assert stats.channels_tracked <= 1
```

#### Mocking Guidelines

```python
# Mock Firestore
mock_firestore = Mock()
mock_doc = Mock()
mock_doc.exists = False
mock_firestore.collection().document().get.return_value = mock_doc

# Mock PubSub
mock_publisher = Mock()
mock_publisher.publish.return_value.result.return_value = "msg_id"

# Mock YouTube API
mock_youtube = Mock()
mock_youtube.get_channel_uploads.return_value = [
    {'id': 'video_1', 'snippet': {...}},
]
```

### Performance Metrics

Track these KPIs to measure discovery efficiency:

| Metric | Target | Current |
|--------|--------|---------|
| Videos discovered/day | >10,000 | 27,776 |
| API units/video | <0.5 | 0.36 |
| Quota utilization | >90% | 95% |
| Deduplication rate | >70% | 78% |
| Channel tracking coverage | >80% | 85% |
| Infringement detection rate | >15% | 18% |

**Query discovery metrics:**

```bash
# In BigQuery
SELECT
  DATE(timestamp) as date,
  SUM(videos_discovered) as total_videos,
  SUM(quota_used) as total_quota,
  SAFE_DIVIDE(SUM(videos_discovered), SUM(quota_used)) as efficiency
FROM `copycat_dev.discovery_metrics`
WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC;
```

## Creating a New Service

```bash
# 1. Create service structure
mkdir -p services/my-service/{app/{core,routers},terraform,tests}
cd services/my-service

# 2. Initialize UV project
uv init --no-readme
uv add fastapi uvicorn pydantic-settings google-cloud-firestore google-cloud-pubsub

# 3. Copy template files from existing service
cp ../discovery-service/Dockerfile .
cp ../discovery-service/cloudbuild.yaml .
cp -r ../discovery-service/terraform/ .

# 4. Update configuration
# - Edit pyproject.toml with service name/description
# - Update cloudbuild.yaml substitutions
# - Modify terraform/main.tf for service-specific resources

# 5. Add source hash tracking to terraform/main.tf
# Add at the top of the file (before any resources):
```

```hcl
locals {
  # Watch only the app folder for source code changes
  app_dir       = "${path.module}/../app"
  exclude_regex = "(\\.venv/|__pycache__/|\\.git/|\\.DS_Store|Thumbs\\.db|desktop\\.ini|\\._.*|~$|\\.pyc$|\\.pytest_cache/|__pycache__|\\.ruff_cache/)"

  all_app_files = fileset(local.app_dir, "**/*")
  app_files = toset([
    for f in local.all_app_files : f
    if length(regexall(local.exclude_regex, f)) == 0
  ])

  # Hash of app source files - triggers Cloud Run update when app code changes
  app_source_hash = sha256(join("", [
    for f in sort(local.app_files) : filesha256("${local.app_dir}/${f}")
  ]))
}
```

```bash
# Add in the Cloud Run container env block:
```

```hcl
env {
  name  = "SOURCE_HASH"
  value = local.app_source_hash
}
```

```bash
# 6. Implement service
# - Create app/main.py with FastAPI app
# - Add /health endpoint
# - Implement business logic in app/core/
# - Add routers in app/routers/

# 7. Deploy
cd ../..
./scripts/deploy-service.sh my-service dev
```

## Monitoring & Debugging

### View Service Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=<service-name>" --limit 50 --format json
```

### Check PubSub Messages
```bash
gcloud pubsub subscriptions pull <subscription-name> --auto-ack --limit=10
```

### Query Results in BigQuery
```sql
SELECT
  video_id,
  risk_score,
  match_found,
  analysis_timestamp
FROM `<project-id>.copycat_dev.results`
WHERE DATE(analysis_timestamp) = CURRENT_DATE()
ORDER BY risk_score DESC
LIMIT 100;
```

### View Extracted Frames
```bash
gsutil ls gs://<project-id>-copycat-frames-dev/<video-id>/
```

### Terraform State
```bash
cd services/<service-name>/terraform
terraform state list              # Show all resources
terraform state show <resource>   # Show specific resource
terraform plan                    # Preview changes
```

## Workspace Structure

This is a **UV workspace** (monorepo):
- Root `pyproject.toml` defines workspace members
- Each service is an independent Python package
- Shared dev dependencies (pytest, ruff, mypy) at root level
- `uv sync` at root installs all services
- Services can reference each other if needed

## Anti-Blocking Strategy

To avoid YouTube/API rate limits:
- Smart targeting (trending, viral channels only)
- Batch operations where possible
- Risk-based filtering (analyze only 10-20%)
- Respect daily quota limits (10,000 units/day default)
- Request quota increase for scale

## Gemini Video Analysis Strategy

### **Budget & Capacity**
- **Daily Budget:** €240 (~$260 USD)
- **Model:** Gemini 2.5 Flash (via Vertex AI)
- **Region:** europe-west4
- **Input Method:** Direct YouTube URL (no download required!)
- **Rate Limit:** ✅ **NO HARD LIMITS** - Vertex AI uses Dynamic Shared Quota (DSQ)
- **Actual Capacity:** 20,000-32,000 videos/day (budget limited, not rate limited)

### **Token Costs (Gemini 2.5 Flash - UPDATED 2025)**

**Video Processing:**
```
Low resolution (RECOMMENDED): 100 tokens/second of video @ 1 FPS
- Frames: 66 tokens/frame @ 1 FPS
- Audio: 32 tokens/second

Pricing (Vertex AI - 4-8x MORE EXPENSIVE than originally planned):
- Input: $0.30 per 1M tokens (was $0.075 in old docs)
- Output: $2.50 per 1M tokens (was $0.30 in old docs)
- Audio: $1.00 per 1M tokens

Max output tokens: 65,536 (vs 8,192 for Gemini 2.0)
```

**Cost Examples (with REAL 2025 pricing):**
```
5-minute video @ 0.5 FPS (MEDIUM risk, length-optimized):
- Effective duration: 290s (skip 5s intro/outro)
- Frames: 0.5 fps × 290s × 66 tokens = 9,570 tokens
- Audio: 290s × 32 tokens/s = 9,280 tokens
- Input total: 18,850 tokens
- Output: ~1,000 tokens
- Cost: (18,850 × $0.30 / 1M) + (1,000 × $2.50 / 1M) = $0.008 per video ✅

5-minute video @ 1.0 FPS (no optimization):
- Input: 28,420 tokens
- Cost: ~$0.011 per video

10-minute video @ 0.33 FPS (length-optimized):
- Input: ~22,000 tokens
- Cost: ~$0.009 per video

30-minute video @ 0.2 FPS (aggressive optimization):
- Input: ~50,000 tokens
- Cost: ~$0.017 per video

60-minute video @ 0.1 FPS (extreme optimization):
- Input: ~50,000 tokens
- Cost: ~$0.017 per video

Budget capacity:
€240/day ($260) with length-based FPS optimization:
- Average $0.008-0.011 per video
- 23,600-32,500 videos/day (BUDGET LIMITED, NO RATE LIMITS!)
```

### **Frame Sampling Optimization (CRITICAL for Cost Control)**

**Implemented in `video_config_calculator.py`:**

**Length-Based FPS Strategy (automatically applied):**
```
Video Length       Base FPS    Cost Impact
0-2 min           1.0         Standard analysis
2-5 min           0.5         50% token reduction
5-10 min          0.33        67% token reduction
10-20 min         0.25        75% token reduction
20-30 min         0.2         80% token reduction
30-60 min         0.1         90% token reduction
60+ min           0.05        95% token reduction (1 frame per 20 seconds!)

Risk Tier Multipliers:
CRITICAL: 2.0x FPS (highest quality)
HIGH: 1.5x FPS
MEDIUM: 1.0x FPS (baseline)
LOW: 0.75x FPS
VERY_LOW: 0.5x FPS (minimum viable)

Budget Pressure Adjustment:
When budget remaining < $50: reduce FPS by 25%
When budget remaining < $10: reduce FPS by 50%
```

**Example: 10-minute AI-generated movie**
```python
video_config = {
    "youtube_url": "https://youtube.com/watch?v=VIDEO_ID",
    "fps": 0.33,  # Auto-calculated for 10min video
    "start_offset": "10s",  # Skip intro
    "end_offset": "590s",  # Skip credits
    "media_resolution": "low"  # Always use low res (66 tokens/frame)
}

Cost with optimization: $0.009 per video
Cost without (1.0 FPS): $0.018 per video
Savings: 50%! 💰
```

**Smart Sampling Strategies:**

1. **Short Videos (<2 min):**
   - Use default 1 FPS
   - No offsets needed
   - Cost: $0.001/video

2. **Medium Videos (2-10 min):**
   - fps=0.5 (every 2 seconds)
   - Skip first/last 10 seconds
   - Cost: $0.003-0.005/video

3. **Long Videos (>10 min):**
   - fps=0.33 (every 3 seconds)
   - Skip intro (first 30s) and credits (last 60s)
   - Cost: $0.008-0.01/video

4. **Very Long Videos (>30 min):**
   - fps=0.25 (every 4 seconds)
   - Skip first 60s and last 120s
   - OR analyze first 10 minutes only
   - Cost: $0.01-0.02/video

### **Budget Exhaustion Algorithm**

**Goal:** Scan until €240 budget is 100% utilized

**IMPORTANT:** Gemini 2.5 Flash on Vertex AI uses Dynamic Shared Quota (DSQ):
- ✅ NO hard rate limits (no RPM cap)
- ✅ Scales dynamically based on availability
- ✅ Only limited by budget and token throughput
- ✅ Can process 20,000-32,000 videos/day (budget limited)

```python
DAILY_BUDGET_EUR = 240
DAILY_BUDGET_USD = 260
# NO RATE LIMIT! Vertex AI DSQ handles scaling automatically

def exhaust_budget():
    """
    Scan videos in priority order until budget exhausted.
    """
    budget_spent = 0.0
    videos_scanned = 0
    start_time = now()

    # Get prioritized scan queue
    scan_queue = get_scan_queue(
        filter="scan_status = 'pending'",
        order_by="priority DESC",
        limit=10000  # More than we can scan in a day
    )

    for video in scan_queue:
        # Check budget limit
        if budget_spent >= DAILY_BUDGET_USD:
            log(f"Budget exhausted: ${budget_spent:.2f}")
            break

        # Check rate limit
        if videos_scanned >= MAX_VIDEOS_PER_DAY:
            log(f"Rate limit reached: {videos_scanned} videos")
            break

        # Respect rate limiting (2.5 videos/min)
        enforce_rate_limit(start_time, videos_scanned)

        # Estimate cost based on video duration
        estimated_cost = estimate_gemini_cost(video)

        # Skip if would exceed budget
        if budget_spent + estimated_cost > DAILY_BUDGET_USD:
            log(f"Skipping video {video.id} - would exceed budget")
            continue

        # SCAN VIDEO
        result = analyze_video_with_gemini(
            video_url=video.url,
            duration=video.duration_seconds,
            characters=video.matched_characters
        )

        actual_cost = result.cost_usd
        budget_spent += actual_cost
        videos_scanned += 1

        # Update video
        update_video(video.id, {
            "scan_status": "scanned",
            "gemini_result": result.analysis,
            "gemini_cost_usd": actual_cost,
            "scanned_at": now()
        })

        # Update channel metrics
        update_channel_after_scan(video.channel_id, result)

    log(f"""
    === DAILY SCAN COMPLETE ===
    Videos scanned: {videos_scanned}
    Budget spent: ${budget_spent:.2f} (€{budget_spent*0.92:.2f})
    Budget utilization: {(budget_spent/DAILY_BUDGET_USD)*100:.1f}%
    Avg cost/video: ${budget_spent/videos_scanned:.4f}
    """)

def estimate_gemini_cost(video):
    """
    Estimate cost before scanning.
    """
    duration = video.duration_seconds or 300  # Default 5 min

    # Use low resolution
    tokens_per_second = 100
    input_tokens = duration * tokens_per_second
    output_tokens = 500  # Typical response

    cost = (input_tokens * 0.075 / 1_000_000) + (output_tokens * 0.30 / 1_000_000)
    return cost

def enforce_rate_limit(start_time, videos_scanned):
    """
    Ensure we don't exceed 2.5 videos/min.
    """
    elapsed_seconds = (now() - start_time).seconds
    expected_time = (videos_scanned / 2.5) * 60

    if elapsed_seconds < expected_time:
        sleep_time = expected_time - elapsed_seconds
        sleep(sleep_time)
```

### **Video Analysis Prompt**

```python
def create_analysis_prompt(characters: list[str]) -> str:
    # Format character list for display
    char_bullets = '\n'.join(f"- {char}" for char in characters)

    return f"""
Analyze this YouTube video for AI-generated copyright infringement of Warner Bros. Entertainment's Justice League characters.

⚠️ CRITICAL: ONLY These Specific Characters Are Relevant ⚠️

TARGET CHARACTERS (Warner Bros. Justice League ONLY):
{char_bullets}

❌ IGNORE ALL OTHER CHARACTERS:
- Marvel characters (Spider-Man, Iron Man, Hulk, Thor, Captain America, etc.)
- Other DC characters not in target list (Joker, Harley Quinn, Poison Ivy, etc.)
- Disney characters (Mickey Mouse, etc.)
- Video game characters (Mario, Sonic, etc.)
- Anime characters (Goku, Naruto, etc.)

🚫 FAST REJECTION:
If the video contains ONLY characters NOT in the target list above → Immediately return:
{{
  "contains_infringement": false,
  "confidence": 100,
  "infringement_likelihood": 0,
  "reasoning": "Video features [CHARACTER NAME], which is NOT in our target character list. No analysis needed.",
  "recommended_action": "ignore"
}}

DETECTION CRITERIA (Only if target characters present):

1. **Character Verification (FIRST STEP)**:
   - Are ANY of the target characters present?
   - If NO → Return fast rejection above
   - If YES → Continue analysis

2. **AI-Generated Content Detection**:
   - Look for Sora AI, Runway, Kling, Pika, Luma, Minimax, or other AI video tools
   - Identify AI artifacts: unnatural movements, morphing, inconsistent physics, impossible transitions
   - Check for AI tool watermarks, mentions in title/description
   - Check for "AI generated", "AI movie", "Sora created" in title/description

3. **Content Type Classification**:
   - **AI-generated original content** (HIGH RISK): Full movies, scenes, trailers created with AI
   - **Real footage** (LOW RISK): Cosplay, fan films with real actors, toys, games
   - **Fair use** (NO RISK): Reviews, commentary, analysis, educational content

4. **Infringement Assessment**:
   - Is this AI-generated unauthorized use of Justice League characters?
   - Is it commercial/monetized?
   - Is it substantial use (>10 seconds of character screen time)?

RESPOND IN JSON:
{{
  "contains_infringement": true/false,
  "confidence": 0-100,
  "is_ai_generated": true/false,
  "ai_tools_detected": ["Sora", "Runway", ...] or [],
  "characters_detected": [
    {{
      "name": "Superman",  # ONLY target list characters!
      "screen_time_seconds": 45,
      "prominence": "high|medium|low",
      "context": "Main character in AI-generated action scene"
    }}
  ],
  "video_type": "full_ai_movie|ai_clips|trailer|real_footage|cosplay|review|toys|other",
  "infringement_likelihood": 0-100,
  "reasoning": "Detailed explanation. If non-Justice-League character, state: 'Video features [CHARACTER] which is not Warner Bros. IP.'",
  "recommended_action": "flag|monitor|ignore"
}}

EXAMPLES:

✅ INFRINGEMENT (flag):
- "I made a full Batman movie with Sora AI" → AI-generated, unauthorized, commercial
- "Superman vs Lex Luthor - AI Generated Short Film" → AI-generated Justice League content

⚠️ MONITOR (monitor):
- "Wonder Woman AI Trailer Concept" → AI-generated but unclear if commercial/substantial use

❌ NOT INFRINGEMENT (ignore):
- Video featuring Spider-Man → Marvel character, not Warner Bros.
- Kid wearing Batman costume at party → Real footage, not AI-generated
- "Batman Movie Review and Analysis" → Fair use commentary
- Batman action figure video → Toys, not AI-generated content

Remember: We ONLY care about AI-generated infringement of the characters in our target list!
"""
```

### **Cost Optimization Techniques**

1. **Low Resolution (3x savings):**
   ```python
   video_config = {"media_resolution": "low"}
   # 66 tokens/frame vs 258 = 74% reduction
   ```

2. **Reduced FPS for static content:**
   ```python
   video_config = {"fps": 0.5}  # Sample every 2 seconds
   # 50% fewer frames = 50% token reduction
   ```

3. **Skip intro/outro:**
   ```python
   video_config = {
       "start_offset": "30s",  # Skip 30s intro
       "end_offset": f"{duration-60}s"  # Skip last 60s credits
   }
   # Save ~15-20% tokens on typical videos
   ```

4. **Analyze key segments only:**
   ```python
   # For very long videos (>30 min), analyze first 10 minutes
   video_config = {
       "start_offset": "60s",  # Skip intro
       "end_offset": "660s"  # Analyze 10 minutes
   }
   ```

5. **Batch similar videos:**
   ```python
   # Same channel, similar content = predict cost accurately
   if channel.avg_video_cost:
       estimated_cost = channel.avg_video_cost
   ```

### **Daily Workflow Integration**

```python
# Morning: Discover + Track (YouTube API)
08:00 - 09:00: Library growth (2,000 tokens)
09:00 - 10:00: Channel tracking (1,000 tokens)
10:00 - 12:00: View updates (3,000 tokens)

# Afternoon: Prioritize + Scan (Gemini API)
12:00 - 18:00: Continuous scanning (budget exhaustion)
  - Scan queue sorted by priority
  - ~2,880 videos scanned
  - €240 budget utilized

# Evening: Channel tier adjustments
18:00 - 19:00: Recalculate priorities
19:00 - 20:00: Update channel tiers based on scan results
```

## Cost Optimization Summary

**Old Architecture (Frame Extraction):**
- Per video: Extract frames → Upload to storage → Vision API
- Cost: $0.02-0.05 per video
- Throughput: Limited by storage I/O

**New Architecture (Direct URL):**
- Per video: YouTube URL → Gemini 2.0 Flash
- Cost: $0.0025-0.01 per video (80-95% cheaper!)
- Throughput: 2,880 videos/day
- Daily cost: ~€27-54 (well under €240 budget)

**Budget Utilization:**
- Can scan 2,880 videos/day at rate limit
- OR scan fewer videos with deeper analysis
- Flexible: spend more on high-priority videos
- Guarantee: 100% of €240 budget utilized daily

## Deployment Flow

1. **Local Development**: `./scripts/dev-local.sh <service>` (uses emulators)
2. **Testing**: `./scripts/test-service.sh <service>` (pytest)
3. **Linting**: `uv run ruff format . && uv run ruff check .`
4. **Manual Deploy**: `./scripts/deploy-service.sh <service> dev`
5. **Auto Deploy**: Push to `develop` (→dev) or `main` (→prod)

### Hash-Based Smart Deployments

The deployment system uses **source code hashing** to avoid unnecessary deployments:

**How it works:**
1. Script calculates SHA256 hash of all source files in `services/<name>/app/`
2. Image tag format: `{git-sha}-{source-hash}`
3. Checks if image already exists in Artifact Registry
4. **Skips Docker build** if image exists (no source changes)
5. Terraform detects `SOURCE_HASH` env var changes
6. **Skips Cloud Run update** if hash unchanged

**Benefits:**
- ✅ Only deploys when code actually changes
- ✅ Idempotent: running deploy twice = no action
- ✅ Fast: skips Docker build if nothing changed
- ✅ Cost-effective: no wasteful rebuilds
- ✅ Git-friendly: deterministic across machines

**Excluded from hash:** `.venv/`, `__pycache__/`, `.pytest_cache/`, `.pyc`, `.DS_Store`

GitHub Actions workflow:
- Detects changed services in `services/` directory
- Calculates source hash and checks if image exists
- Builds Docker image only if needed
- Pushes to Artifact Registry
- Runs Terraform apply (detects changes via SOURCE_HASH env var)
- Verifies health check
- Reports deployment status

## Important Notes

- **UV not Poetry**: This project uses UV for package management (much faster)
- **Python 3.13**: All services require Python 3.13+
- **No local Docker needed**: Cloud Build handles container builds
- **Terraform state**: Stored in GCS bucket `<project-id>-terraform-state`
- **Emulators required**: Install Firestore/PubSub emulators for local dev
- **Service accounts**: Each service has dedicated SA with least-privilege IAM
- **Health checks**: All services must expose `/health` endpoint for Cloud Run

## Adding Dependencies to a Service

```bash
cd services/<service-name>
uv add <package-name>              # Add to dependencies
uv add --dev <package-name>        # Add to dev dependencies
uv sync                            # Install all dependencies
```

## Common Troubleshooting

**"Service not found" during deployment**: Ensure service directory exists in `services/` and has all required files (Dockerfile, cloudbuild.yaml, terraform/).

**Emulator connection errors locally**: Check emulators are running (`ps aux | grep emulator`) and environment variables are set (`echo $FIRESTORE_EMULATOR_HOST`).

**Terraform state locked**: Someone else is deploying or previous deployment failed. Wait or break lock: `terraform force-unlock <lock-id>`.

**Cloud Build permission errors**: Ensure Cloud Build service account has required roles (Cloud Run Admin, Artifact Registry Writer, Storage Object Admin).

**yt-dlp failures**: YouTube changes formats frequently. Update to latest: `uv add yt-dlp@latest`.
