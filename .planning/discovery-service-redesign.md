# Discovery Service Complete Redesign Plan
**Epic: Discovery Service Refactoring & Optimization**

---

## Executive Summary

The current discovery service has evolved organically and contains significant technical debt:
- Multiple discovery methods with overlapping logic
- Inefficient API quota usage patterns
- No channel-level intelligence or tracking
- Missing view velocity tracking
- No adaptive scanning frequency
- Redundant code in every discovery method
- Poor separation of concerns

**Goal:** Build a lean, intelligent, production-grade discovery service that maximizes detection per API unit spent.

---

## Current State Analysis (What's Wrong?)

### Code Smells Identified

1. **Massive Code Duplication** (400+ LOC in discovery.py)
   - Same metadata extraction logic repeated 6 times
   - Same Firestore save logic repeated 6 times
   - Same PubSub publish logic repeated 6 times
   - Same IP matching logic repeated 6 times

2. **No Channel Intelligence**
   - No channel tracking/profiling
   - No infringement history per channel
   - No adaptive scan frequency
   - Missing view velocity calculations

3. **Inefficient API Usage**
   - No quota tracking/management
   - No priority-based discovery
   - Multiple methods doing similar things
   - No batch optimization

4. **Poor Architecture**
   - God class (DiscoveryService does everything)
   - No separation of concerns
   - Hard to test individual components
   - Tight coupling between layers

5. **Missing Features from CLAUDE.md**
   - No budget exhaustion model
   - No channel tier system
   - No view velocity tracking
   - No adaptive monitoring frequency

---

## Target Architecture (The Vision)

### Core Principles
1. **DRY**: Single responsibility, zero duplication
2. **Smart**: AI-powered prioritization, not brute force
3. **Efficient**: Every API unit counts
4. **Adaptive**: Learn from scan results
5. **Lean**: <500 LOC total, super clean

### Component Breakdown

```
discovery-service/
├── app/
│   ├── core/
│   │   ├── discovery_engine.py      # Main orchestrator (100 LOC)
│   │   ├── youtube_client.py        # Existing, minimal changes
│   │   ├── channel_tracker.py       # NEW: Channel intelligence (150 LOC)
│   │   ├── video_processor.py       # NEW: Dedupe & processing (100 LOC)
│   │   ├── quota_manager.py         # NEW: API quota optimization (80 LOC)
│   │   └── ip_loader.py             # Existing, no changes
│   ├── models.py                    # Cleaned up models
│   └── routers/
│       └── discover.py              # Simplified endpoints (80 LOC)
```

---

## Epic Breakdown: Stories & Points

### **EPIC 1: Foundation Refactoring (21 points)**

---

#### **Story 1.1: Create VideoProcessor Class**
**Points:** 5
**Priority:** HIGH
**Why:** Eliminates 300+ lines of duplicate code across all discovery methods

**Acceptance Criteria:**
- [ ] Single class handles all video metadata extraction
- [ ] Single method for Firestore persistence
- [ ] Single method for PubSub publishing
- [ ] Single method for IP matching
- [ ] Deduplication logic centralized
- [ ] All methods return standardized VideoMetadata objects
- [ ] 100% test coverage for VideoProcessor

**Technical Details:**
```python
class VideoProcessor:
    """
    Handles ALL video processing operations.
    Zero duplication, single source of truth.
    """

    def __init__(self, firestore_client, pubsub_publisher, ip_manager):
        self.firestore = firestore_client
        self.publisher = pubsub_publisher
        self.ip_manager = ip_manager

    def extract_metadata(self, video_data: dict) -> VideoMetadata:
        """Extract metadata from YouTube API response."""
        # Single implementation, called by all discovery methods
        pass

    def is_duplicate(self, video_id: str, max_age_days: int = 7) -> bool:
        """Check if video already processed recently."""
        pass

    def match_ips(self, metadata: VideoMetadata) -> list[str]:
        """Match video content against configured IPs."""
        pass

    def save_and_publish(self, metadata: VideoMetadata) -> bool:
        """Atomic save to Firestore + publish to PubSub."""
        pass

    def process_batch(self, video_data_list: list[dict]) -> list[VideoMetadata]:
        """Process multiple videos efficiently."""
        # Handles extraction, dedup, IP matching, save, publish
        # Returns only successfully processed videos
        pass
```

**Benefits:**
- Reduces discovery.py from 685 LOC to ~200 LOC
- Single point for all video operations
- Easy to test and maintain
- Consistent error handling

---

#### **Story 1.2: Create QuotaManager Class**
**Points:** 3
**Priority:** MEDIUM
**Why:** Prevents quota exhaustion, optimizes API usage patterns

**Acceptance Criteria:**
- [ ] Tracks YouTube API quota usage in real-time
- [ ] Enforces daily quota limits (default: 10,000 units)
- [ ] Calculates cost before each API call
- [ ] Provides quota remaining/utilization metrics
- [ ] Logs warnings at 80% quota usage
- [ ] Prevents operations that would exceed quota

**Technical Details:**
```python
class QuotaManager:
    """
    YouTube API quota optimization.
    Ensures we never hit quota limits.
    """

    # YouTube API v3 costs
    COSTS = {
        'search': 100,           # search.list
        'video_details': 1,      # videos.list
        'trending': 1,           # videos.list (chart)
        'channel_details': 1,    # channels.list
        'playlist_items': 1,     # playlistItems.list
    }

    def __init__(self, daily_quota: int = 10_000):
        self.daily_quota = daily_quota
        self.used_quota = self._load_today_usage()

    def can_afford(self, operation: str, count: int = 1) -> bool:
        """Check if we can afford this operation."""
        pass

    def record_usage(self, operation: str, count: int = 1):
        """Record API usage."""
        # Update Firestore counter for today
        pass

    def get_remaining(self) -> int:
        """Get remaining quota for today."""
        pass

    def get_utilization(self) -> float:
        """Get quota utilization percentage."""
        pass

    def prioritize_operations(self, operations: list) -> list:
        """Sort operations by cost-efficiency (ROI per unit)."""
        # Trending (1 unit/50 videos) > Channel tracking (3 units/channel) > Search (100 units/50 videos)
        pass
```

**Benefits:**
- Never hit quota limits unexpectedly
- Optimize discovery strategy based on remaining quota
- Clear visibility into API usage
- Intelligent operation prioritization

---

#### **Story 1.3: Clean Up Discovery Models**
**Points:** 2
**Priority:** MEDIUM
**Why:** Remove unused models, add channel tracking models

**Acceptance Criteria:**
- [ ] Remove unused DiscoveryTarget enum values (gaming, viral, search_query)
- [ ] Add ChannelProfile model for channel tracking
- [ ] Add ChannelTier enum (PLATINUM, GOLD, SILVER, BRONZE, IGNORE)
- [ ] Add ViewVelocity model for trend tracking
- [ ] Update VideoMetadata with view_velocity field
- [ ] Add DiscoveryStats model for metrics

**New Models:**
```python
class ChannelTier(str, Enum):
    PLATINUM = "platinum"  # Daily scans (high infringement rate)
    GOLD = "gold"          # Every 3 days (consistent violations)
    SILVER = "silver"      # Weekly (occasional violations)
    BRONZE = "bronze"      # Monthly (rare violations)
    IGNORE = "ignore"      # Never scan (no violations)

class ChannelProfile(BaseModel):
    channel_id: str
    channel_title: str
    tier: ChannelTier
    subscriber_count: int
    total_videos_found: int
    infringing_videos_count: int
    infringement_rate: float  # percentage
    last_scanned_at: datetime
    next_scan_at: datetime
    avg_views_per_video: int
    posting_frequency_days: float
    discovered_at: datetime

class ViewVelocity(BaseModel):
    video_id: str
    current_views: int
    previous_views: int
    views_gained: int
    hours_elapsed: float
    views_per_hour: float
    trending_score: float  # 0-100
```

---

### **EPIC 2: Channel Intelligence System (34 points)**

---

#### **Story 2.1: Create ChannelTracker Class**
**Points:** 8
**Priority:** HIGH
**Why:** Core of the intelligent discovery system, replaces dumb keyword searches

**Acceptance Criteria:**
- [ ] Tracks all channels that posted IP content
- [ ] Calculates channel infringement rate
- [ ] Assigns channel tiers based on behavior
- [ ] Determines next scan time per channel
- [ ] Updates tier after each scan
- [ ] Stores channel profiles in Firestore
- [ ] Provides channel statistics and metrics

**Technical Details:**
```python
class ChannelTracker:
    """
    Intelligent channel profiling and tracking.
    Learns which channels violate IP frequently.
    """

    def __init__(self, firestore_client: firestore.Client):
        self.firestore = firestore_client
        self.channels_collection = "channels"

    def get_or_create_profile(self, channel_id: str, metadata: VideoMetadata) -> ChannelProfile:
        """Get existing profile or create new one."""
        pass

    def calculate_tier(self, profile: ChannelProfile) -> ChannelTier:
        """
        Calculate channel tier based on infringement history.

        Logic:
        - PLATINUM: >50% infringement rate, >10 violations
        - GOLD: 25-50% infringement rate, >5 violations
        - SILVER: 10-25% infringement rate
        - BRONZE: <10% infringement rate
        - IGNORE: 0% after 20+ videos scanned
        """
        pass

    def get_next_scan_time(self, profile: ChannelProfile) -> datetime:
        """
        Calculate when to scan this channel next.

        Frequency by tier:
        - PLATINUM: Every 24 hours
        - GOLD: Every 72 hours
        - SILVER: Every 7 days
        - BRONZE: Every 30 days
        - IGNORE: Never
        """
        pass

    def update_after_scan(self, channel_id: str, video_had_infringement: bool):
        """Update channel profile after scanning a video."""
        pass

    def get_channels_due_for_scan(self, limit: int = 100) -> list[ChannelProfile]:
        """Get channels that need scanning now."""
        # Query: next_scan_at <= now(), order by tier DESC
        pass

    def get_statistics(self) -> dict:
        """Get channel tracking statistics."""
        # Total channels, breakdown by tier, avg infringement rate, etc.
        pass
```

**Benefits:**
- Focuses discovery on high-risk channels
- Adaptive scan frequency saves quota
- Builds institutional knowledge
- Replaces spray-and-pray keyword searches

---

#### **Story 2.2: Implement View Velocity Tracking**
**Points:** 5
**Priority:** HIGH
**Why:** Prioritize viral videos (high view growth = high impact)

**Acceptance Criteria:**
- [ ] Store view counts over time in Firestore
- [ ] Calculate views per hour for recent videos
- [ ] Compute trending score (0-100)
- [ ] Update view counts periodically
- [ ] Prioritize high-velocity videos in scan queue
- [ ] Expose velocity metrics in API responses

**Technical Details:**
```python
class ViewVelocityTracker:
    """
    Tracks view count changes over time.
    Identifies viral videos for priority scanning.
    """

    def record_view_snapshot(self, video_id: str, view_count: int):
        """Store current view count with timestamp."""
        pass

    def calculate_velocity(self, video_id: str) -> ViewVelocity:
        """Calculate views/hour from historical snapshots."""
        pass

    def get_trending_score(self, velocity: ViewVelocity) -> float:
        """
        Score 0-100 based on view velocity.

        Logic:
        - >10k views/hour = 100
        - 1k-10k views/hour = 50-99
        - 100-1k views/hour = 10-49
        - <100 views/hour = 0-9
        """
        pass

    def update_all_velocities(self, video_ids: list[str]):
        """Batch update velocities for multiple videos."""
        pass
```

**Benefits:**
- Catch viral videos early
- Prioritize high-impact scans
- Optimize Gemini budget usage

---

#### **Story 2.3: Build Channel-First Discovery Strategy**
**Points:** 8
**Priority:** HIGH
**Why:** The most efficient discovery method (3 units per channel vs 100 per search)

**Acceptance Criteria:**
- [ ] Scan channels due for refresh (based on tier)
- [ ] Get recent uploads from each channel
- [ ] Process only new videos (dedup against Firestore)
- [ ] Update channel profile after scan
- [ ] Adjust tier based on results
- [ ] Schedule next scan time
- [ ] Log quota usage per channel

**Implementation:**
```python
async def discover_channel_based() -> list[VideoMetadata]:
    """
    MOST EFFICIENT discovery method.
    Cost: 3 units per channel vs 100 per search.
    """

    # Get channels due for scanning
    channels = channel_tracker.get_channels_due_for_scan(limit=50)

    discovered = []
    for channel in channels:
        # Cost: 3 units (channel + playlist + video details)
        videos = youtube_client.get_channel_uploads(channel.channel_id, max_results=20)

        # Process new videos only
        new_videos = [v for v in videos if not video_processor.is_duplicate(v['id'])]

        # Batch process
        results = video_processor.process_batch(new_videos)
        discovered.extend(results)

        # Update channel tier
        channel_tracker.update_after_scan(channel.channel_id, len(results) > 0)

    return discovered
```

**Benefits:**
- 30x more efficient than keyword search
- Builds on historical knowledge
- Adaptive frequency saves quota
- Targets known infringers

---

#### **Story 2.4: Implement Smart Quota Allocation**
**Points:** 5
**Priority:** MEDIUM
**Why:** Maximize discoveries per API unit spent

**Acceptance Criteria:**
- [ ] Allocate quota based on method efficiency
- [ ] 70% quota: Channel tracking (most efficient)
- [ ] 20% quota: Trending (cheap, broad coverage)
- [ ] 10% quota: Targeted keyword searches (expensive, high precision)
- [ ] Stop when daily quota reached
- [ ] Log allocation decisions

**Quota Allocation Strategy:**
```python
DAILY_QUOTA = 10_000

# Method costs (units per 50 videos discovered)
COST_TRENDING = 1 unit          # 50 videos = 1 unit
COST_CHANNEL = 3 units          # 1 channel ~17 videos = 3 units
COST_SEARCH = 100 units         # 50 videos = 100 units

# Allocation (maximize ROI)
ALLOCATION = {
    'channel_tracking': int(DAILY_QUOTA * 0.70),  # 7,000 units = ~2,333 channels
    'trending': int(DAILY_QUOTA * 0.20),          # 2,000 units = ~100,000 trending videos checked
    'keyword_search': int(DAILY_QUOTA * 0.10),    # 1,000 units = ~500 targeted searches
}
```

**Benefits:**
- Data-driven quota usage
- Maximizes discovery efficiency
- Prevents quota waste

---

#### **Story 2.5: Add Channel Analytics Dashboard Endpoint**
**Points:** 3
**Priority:** LOW
**Why:** Visibility into channel tracking performance

**Acceptance Criteria:**
- [ ] GET /analytics/channels endpoint
- [ ] Returns channel statistics by tier
- [ ] Shows infringement rates
- [ ] Lists top offending channels
- [ ] Displays quota usage by method
- [ ] Provides discovery funnel metrics

**Response Format:**
```json
{
  "total_channels": 1247,
  "by_tier": {
    "platinum": 12,
    "gold": 45,
    "silver": 234,
    "bronze": 789,
    "ignore": 167
  },
  "top_offenders": [
    {
      "channel_id": "UCxxxxx",
      "channel_title": "AI Movies Daily",
      "infringement_rate": 0.87,
      "total_videos": 156,
      "violations": 136
    }
  ],
  "quota_usage_today": {
    "total_used": 6234,
    "remaining": 3766,
    "by_method": {
      "channel_tracking": 4500,
      "trending": 1234,
      "keyword_search": 500
    }
  }
}
```

---

#### **Story 2.6: Implement Adaptive Keyword Search**
**Points:** 5
**Priority:** MEDIUM
**Why:** Make keyword search intelligent, not wasteful

**Acceptance Criteria:**
- [ ] Only search keywords that historically find violations
- [ ] Track success rate per keyword
- [ ] Disable low-performing keywords
- [ ] Use publishedAfter filter (last 48 hours only)
- [ ] Batch deduplication before getting details
- [ ] Stop searching if finding mostly duplicates

**Smart Keyword Logic:**
```python
class KeywordOptimizer:
    """
    Learns which keywords are effective.
    Stops wasting quota on bad keywords.
    """

    def track_keyword_performance(self, keyword: str, found: int, violations: int):
        """Track how many violations each keyword finds."""
        pass

    def get_effective_keywords(self, min_success_rate: float = 0.10) -> list[str]:
        """
        Return only keywords with >10% violation rate.

        Example:
        - "Superman AI generated" -> 45% violations -> KEEP
        - "Justice League trailer" -> 2% violations -> DISABLE
        """
        pass

    def should_search_keyword(self, keyword: str) -> bool:
        """Determine if keyword is worth searching."""
        pass
```

**Benefits:**
- Stops wasting quota on bad keywords
- Data-driven keyword selection
- Continuous optimization

---

### **EPIC 3: Core Discovery Engine Redesign (13 points)**

---

#### **Story 3.1: Create DiscoveryEngine Orchestrator**
**Points:** 8
**Priority:** HIGH
**Why:** Replaces the 685-line god class with clean, intelligent orchestration

**Acceptance Criteria:**
- [ ] Single entry point: discover()
- [ ] Executes discovery methods in priority order
- [ ] Respects quota limits
- [ ] Handles errors gracefully
- [ ] Returns consolidated metrics
- [ ] < 150 LOC total

**Implementation:**
```python
class DiscoveryEngine:
    """
    Lean, intelligent discovery orchestrator.
    Replaces the bloated DiscoveryService.
    """

    def __init__(
        self,
        youtube_client: YouTubeClient,
        video_processor: VideoProcessor,
        channel_tracker: ChannelTracker,
        quota_manager: QuotaManager,
    ):
        self.youtube = youtube_client
        self.processor = video_processor
        self.channels = channel_tracker
        self.quota = quota_manager

    async def discover(self, max_quota: int | None = None) -> DiscoveryResult:
        """
        Main discovery loop. Runs until quota exhausted.

        Strategy:
        1. Channel-based discovery (70% quota)
        2. Trending videos (20% quota)
        3. Targeted keywords (10% quota)
        """

        discovered = []
        quota_used = 0

        # Phase 1: Channel tracking (most efficient)
        if self.quota.can_afford('channel_details', 100):
            channels = self.channels.get_channels_due_for_scan(limit=100)
            for channel in channels:
                if not self.quota.can_afford('channel_details', 3):
                    break

                videos = self.youtube.get_channel_uploads(channel.channel_id)
                self.quota.record_usage('channel_details', 3)

                results = self.processor.process_batch(videos)
                discovered.extend(results)

        # Phase 2: Trending (cheap and broad)
        if self.quota.can_afford('trending', 1):
            trending = self.youtube.get_trending_videos(max_results=50)
            self.quota.record_usage('trending', 1)

            results = self.processor.process_batch(trending)
            discovered.extend(results)

        # Phase 3: Targeted keywords (expensive, use sparingly)
        if self.quota.can_afford('search', 10):
            keywords = self._get_priority_keywords()
            for keyword in keywords[:10]:  # Max 10 searches
                if not self.quota.can_afford('search', 1):
                    break

                results = self.youtube.search_videos(keyword, max_results=50)
                self.quota.record_usage('search', 1)

                video_data = self.processor.process_batch(results)
                discovered.extend(video_data)

        return DiscoveryResult(
            videos_discovered=len(discovered),
            quota_used=self.quota.used_quota,
            quota_remaining=self.quota.get_remaining(),
        )
```

**Benefits:**
- Clean, understandable flow
- Respects quota limits
- Prioritizes efficient methods
- Easy to test and modify

---

#### **Story 3.2: Simplify Discovery Router**
**Points:** 3
**Priority:** MEDIUM
**Why:** Current router has too many endpoints, needs consolidation

**Acceptance Criteria:**
- [ ] Single POST /discover endpoint (replaces 5 endpoints)
- [ ] GET /analytics/discovery for stats
- [ ] GET /channels for channel profiles
- [ ] Remove: discover_trending, discover_gaming, discover_viral, etc.
- [ ] Clean dependency injection
- [ ] OpenAPI docs updated

**New API Design:**
```python
@router.post("/discover")
async def discover(
    max_quota: int | None = None,
    engine: DiscoveryEngine = Depends(get_discovery_engine),
) -> DiscoveryResult:
    """
    Run intelligent discovery until quota exhausted.
    Automatically uses best strategy.
    """
    return await engine.discover(max_quota=max_quota)

@router.get("/analytics/discovery")
async def get_discovery_analytics() -> DiscoveryAnalytics:
    """Get discovery performance metrics."""
    pass

@router.get("/channels")
async def list_channels(
    tier: ChannelTier | None = None,
    limit: int = 50,
) -> list[ChannelProfile]:
    """List tracked channels with filters."""
    pass
```

**Benefits:**
- Simpler API surface
- One way to do things
- Self-documenting

---

#### **Story 3.3: Add Comprehensive Testing**
**Points:** 5
**Priority:** HIGH
**Why:** Current tests don't cover core logic, need 80%+ coverage

**Acceptance Criteria:**
- [ ] Unit tests for VideoProcessor (all methods)
- [ ] Unit tests for ChannelTracker (tier calculation, next scan)
- [ ] Unit tests for QuotaManager (quota enforcement)
- [ ] Integration tests for DiscoveryEngine
- [ ] Mock YouTube API responses
- [ ] Mock Firestore and PubSub
- [ ] Coverage >80%

**Test Structure:**
```python
# tests/test_video_processor.py
def test_extract_metadata():
    """Test video metadata extraction."""
    pass

def test_is_duplicate():
    """Test duplicate detection."""
    pass

def test_batch_processing():
    """Test batch video processing."""
    pass

# tests/test_channel_tracker.py
def test_tier_calculation():
    """Test channel tier assignment logic."""
    # Assert PLATINUM tier for 60% infringement rate
    # Assert GOLD tier for 35% infringement rate
    pass

def test_next_scan_time():
    """Test scan frequency by tier."""
    pass

# tests/test_discovery_engine.py
def test_quota_respected():
    """Ensure discovery stops at quota limit."""
    pass

def test_method_prioritization():
    """Ensure channel tracking runs first."""
    pass
```

---

### **EPIC 4: Cleanup & Documentation (8 points)**

---

#### **Story 4.1: Delete Dead Code**
**Points:** 2
**Priority:** HIGH
**Why:** Remove unused discovery methods

**Files to Modify:**
- [ ] Delete `discover_gaming()` - not used, gaming is just IP targets
- [ ] Delete `discover_viral()` - replaced by view velocity tracking
- [ ] Delete `discover_by_query()` - replaced by smart keyword search
- [ ] Delete `discover_smart()` - replaced by DiscoveryEngine
- [ ] Keep only: `discover_trending()`, `discover_by_keywords()`, `discover_channel()`

**After cleanup:**
- discovery.py: 685 LOC → 150 LOC
- router.py: 292 LOC → 80 LOC

---

#### **Story 4.2: Update CLAUDE.md**
**Points:** 2
**Priority:** MEDIUM
**Why:** Document new architecture

**Sections to Add:**
- [ ] Channel Tracking Strategy
- [ ] Quota Management
- [ ] View Velocity Tracking
- [ ] Discovery Method Costs & ROI
- [ ] Channel Tier System
- [ ] Testing Guidelines

---

#### **Story 4.3: Create Architecture Diagram**
**Points:** 1
**Priority:** LOW
**Why:** Visual documentation

**Diagram Contents:**
- Discovery flow (Channel → Trending → Keywords)
- Component interactions
- Firestore collections schema
- API endpoint map

---

#### **Story 4.4: Add Performance Monitoring**
**Points:** 3
**Priority:** MEDIUM
**Why:** Track discovery efficiency over time

**Metrics to Track:**
- [ ] Videos discovered per API unit spent
- [ ] Channel tier distribution over time
- [ ] Infringement rate by channel tier
- [ ] Quota usage by discovery method
- [ ] Deduplication effectiveness
- [ ] View velocity correlation with violations

**Implementation:**
- Store metrics in Firestore `discovery_metrics` collection
- Daily rollup job
- Expose via `/analytics/performance` endpoint

---

## Success Metrics

### Code Quality
- **LOC Reduction:** 977 LOC → <500 LOC (49% reduction)
- **Test Coverage:** 30% → 80%+
- **Cyclomatic Complexity:** Reduce from 15+ to <10 per function

### Efficiency Gains
- **API Units per Discovery:**
  - Before: 100 units (keyword search)
  - After: 3 units (channel tracking)
  - **33x improvement**

- **Discovery Yield:**
  - Before: ~50 videos/day with 5,000 units
  - After: ~2,000 videos/day with 5,000 units
  - **40x improvement**

### Intelligence
- **Adaptive Scanning:** Channels scanned based on infringement history (not random)
- **Viral Prioritization:** High-velocity videos scanned first
- **Quota Optimization:** 70% on efficient methods, 10% on expensive searches

---

## Implementation Order (Sprints)

### Sprint 1: Foundation (Stories 1.1, 1.2, 1.3) - 10 points
**Goal:** Build core components, eliminate duplication

**Deliverables:**
- VideoProcessor class (working)
- QuotaManager class (working)
- Updated models
- Unit tests for both

**Success:** Can process videos through VideoProcessor, quota tracked

---

### Sprint 2: Channel Intelligence (Stories 2.1, 2.2) - 13 points
**Goal:** Build channel tracking system

**Deliverables:**
- ChannelTracker class (working)
- ViewVelocityTracker class (working)
- Channel tier calculation logic
- Firestore schema for channels collection

**Success:** Channels profiled, tiers assigned, next scan calculated

---

### Sprint 3: Discovery Engine (Stories 2.3, 3.1, 3.2) - 21 points
**Goal:** Replace old discovery service

**Deliverables:**
- DiscoveryEngine orchestrator
- Channel-first discovery working
- Simplified router endpoints
- Integration with VideoProcessor + ChannelTracker

**Success:** Can run full discovery, respects quota, updates channels

---

### Sprint 4: Optimization (Stories 2.4, 2.6, 4.1) - 12 points
**Goal:** Smart quota allocation, keyword optimization

**Deliverables:**
- Quota allocation by method
- Keyword performance tracking
- Delete dead code
- Clean up unused endpoints

**Success:** Discovery allocates quota intelligently, stops bad keywords

---

### Sprint 5: Polish (Stories 2.5, 3.3, 4.2, 4.3, 4.4) - 14 points
**Goal:** Testing, analytics, documentation

**Deliverables:**
- 80% test coverage
- Analytics endpoints
- Updated CLAUDE.md
- Architecture diagram
- Performance monitoring

**Success:** Production-ready, documented, monitored

---

## Technical Debt Payoff

### Before Redesign
```python
# discovery.py - 685 LOC, massive duplication
class DiscoveryService:
    def discover_trending(self): # 50 LOC
        # Extract metadata inline (15 LOC)
        # Check duplicates inline (10 LOC)
        # Match IPs inline (8 LOC)
        # Save to Firestore inline (10 LOC)
        # Publish to PubSub inline (7 LOC)

    def discover_gaming(self): # 50 LOC
        # SAME code repeated

    def discover_viral(self): # 50 LOC
        # SAME code repeated

    # ... 6 methods, all duplicating same logic
```

### After Redesign
```python
# discovery_engine.py - 150 LOC, zero duplication
class DiscoveryEngine:
    def __init__(self, processor, tracker, quota):
        self.processor = processor  # Handles all video ops
        self.tracker = tracker      # Handles all channel ops
        self.quota = quota          # Handles quota management

    async def discover(self, max_quota=None):
        # Phase 1: Channels (efficient)
        channels = self.tracker.get_due_for_scan()
        for ch in channels:
            videos = self.youtube.get_uploads(ch.id)
            self.processor.process_batch(videos)  # Single call!

        # Phase 2: Trending (cheap)
        trending = self.youtube.get_trending()
        self.processor.process_batch(trending)  # Reuse!

        # Phase 3: Keywords (expensive)
        # ...
```

**Result:** Same functionality, 78% less code, infinitely more maintainable.

---

## Risk Mitigation

### Risk 1: Firestore Schema Changes
**Mitigation:** Create new collections (`channels_v2`), migrate gradually, run dual-write during transition

### Risk 2: Quota Tracking Accuracy
**Mitigation:** Conservative estimates, buffer (use 90% of quota), daily resets

### Risk 3: Channel Tier Miscalculation
**Mitigation:** Manual override capability, audit tier changes, A/B test tier logic

### Risk 4: Breaking Changes to Downstream Services
**Mitigation:** Keep VideoMetadata model compatible, version PubSub messages, staged rollout

---

## Definition of Done

### Code
- [ ] All stories implemented
- [ ] No duplicate logic
- [ ] 80%+ test coverage
- [ ] Ruff lint passes
- [ ] Type hints on all functions
- [ ] Error handling on all external calls

### Documentation
- [ ] CLAUDE.md updated
- [ ] API docs generated
- [ ] Architecture diagram created
- [ ] Inline code comments for complex logic

### Deployment
- [ ] All tests passing in CI
- [ ] Deployed to dev environment
- [ ] Smoke tests pass
- [ ] Metrics dashboard shows data
- [ ] Quota tracking working

### Performance
- [ ] Discovery completes in <5 min for 1000 videos
- [ ] API quota usage <10,000/day
- [ ] Zero duplicate videos saved
- [ ] Channel tiers updating correctly

---

## Conclusion

This redesign transforms the discovery service from a bloated, inefficient keyword-spam system into an intelligent, adaptive, channel-focused discovery engine.

**Key Innovations:**
1. **Channel Intelligence:** Learn from history, scan smart
2. **Quota Optimization:** 33x more efficient per API unit
3. **Zero Duplication:** Single responsibility, DRY code
4. **View Velocity:** Prioritize viral content
5. **Adaptive Frequency:** Scan high-risk channels more often

**Total Effort:** 70 story points (~7 sprints at 10 points/sprint = 7 weeks for 1 dev)

**ROI:**
- 40x more videos discovered per day
- 78% less code to maintain
- 33x more efficient API usage
- Intelligent, adaptive system vs dumb keyword spam

**This is how we build world-class software.** 🚀
