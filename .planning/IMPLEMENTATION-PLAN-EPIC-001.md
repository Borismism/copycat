# Epic 001 Implementation Plan: Two-Service Discovery & Risk Analysis Architecture

**Status**: Ready for Implementation
**Repository**: https://github.com/Borismism/copycat
**Last Updated**: 2025-10-29
**Estimated Effort**: 2-3 days (16-24 hours)

---

## 🎯 Executive Summary

### Current State ✅
- **Discovery service**: Fully functional with 167 passing tests
- **Test coverage**: 49% overall, 52-100% on core modules
- **Architecture**: Monolithic discovery service handling all operations
- **Schema**: Enhanced with risk scoring fields (`initial_risk`, `current_risk`, `risk_tier`)
- **Code quality**: All tests passing, optimized pytest configuration (17s runtime)

### Target State 🎯
- **Two specialized services**: Discovery (find) + Risk Analyzer (prioritize)
- **Clear separation**: Discovery finds new content, Risk Analyzer manages priorities
- **Budget optimization**: €240/day Gemini capacity fully utilized
- **Hit rate improvement**: 0% → 15%+ discovery, 30%+ Gemini accuracy
- **Adaptive scanning**: CRITICAL (6h) to VERY_LOW (monthly) based on risk

---

## 📊 Implementation Phases

### Phase 1: Discovery Service Refactor (4-6 hours)
**Epic 2: Stories 2.1-2.4**

#### Story 2.1: Remove Rescanning Logic ⚠️ CRITICAL
**Status**: Pending
**Effort**: 1 hour
**Priority**: P0

**Tasks**:
1. ✅ Identify all rescanning logic in discovery-service
   - `app/core/video_rescanner.py` (64 LOC, 30% coverage) - **DELETE**
   - Remove imports and usages from `discovery_engine.py`
   - Remove any references in routers

2. ✅ Update tests
   - Delete `tests/test_video_rescanner.py` if exists
   - Update `test_discovery_engine.py` to not expect rescanning

3. ✅ Verify deletion
   - Run full test suite (should still pass 167 tests)
   - Check no broken imports

**Acceptance Criteria**:
- [ ] `video_rescanner.py` deleted
- [ ] All 167 tests still passing
- [ ] No rescanning logic remains in discovery-service
- [ ] Discovery service only discovers new videos

**Impact**: Removes 64 LOC, clarifies service responsibility

---

#### Story 2.2: Add Initial Risk Scoring Algorithm
**Status**: Pending
**Effort**: 2 hours
**Priority**: P0

**Current State**:
- `VideoMetadata` has `initial_risk` field (0-100) ✅
- `video_processor.py` has 100% test coverage ✅
- No actual risk calculation yet

**Tasks**:
1. ✅ Implement `calculate_initial_risk()` in `video_processor.py`
   ```python
   def calculate_initial_risk(self, metadata: VideoMetadata, channel_risk: int) -> int:
       """
       Calculate initial risk score (0-100) for newly discovered video.

       Factors:
       - Channel risk score (0-50 points)
       - View count (0-15 points)
       - Keywords matched (0-20 points)
       - Duration (0-10 points)
       - Age (0-5 points)
       """
       risk = 0

       # Channel reputation (50% weight)
       risk += min(channel_risk // 2, 50)

       # View count indicates popularity
       if metadata.view_count > 1_000_000:
           risk += 15
       elif metadata.view_count > 100_000:
           risk += 10
       elif metadata.view_count > 10_000:
           risk += 5

       # More IP matches = higher risk
       risk += min(len(metadata.matched_ips) * 5, 20)

       # Longer videos = more content to review
       if metadata.duration_seconds > 600:  # >10 min
           risk += 10
       elif metadata.duration_seconds > 300:  # >5 min
           risk += 5

       # Recent videos get priority
       age_days = (datetime.now(timezone.utc) - metadata.published_at).days
       if age_days <= 7:
           risk += 5
       elif age_days <= 30:
           risk += 3

       return min(risk, 100)
   ```

2. ✅ Update `save_and_publish()` to call `calculate_initial_risk()`
   - Get channel risk from `channel_tracker`
   - Set `metadata.initial_risk` and `metadata.current_risk` (initially same)
   - Set `metadata.risk_tier` based on score

3. ✅ Add tests in `test_video_processor.py`
   - Test risk calculation with various inputs
   - Test edge cases (new channel, viral video, etc.)
   - Maintain 100% coverage

4. ✅ Update PubSub publishing
   - Include `initial_risk` in published message
   - Publish to `video-discovered` topic

**Acceptance Criteria**:
- [ ] `calculate_initial_risk()` implemented with 5-factor algorithm
- [ ] All new videos get `initial_risk` (0-100)
- [ ] `risk_tier` set correctly (CRITICAL/HIGH/MEDIUM/LOW/VERY_LOW)
- [ ] Tests maintain 100% coverage on `video_processor.py`
- [ ] PubSub messages include risk data

**Testing**:
```python
def test_calculate_initial_risk_high_channel():
    """Test high risk for video from known infringer."""
    metadata = VideoMetadata(
        video_id="test",
        title="Superman AI video",
        channel_id="UC_infringer",
        channel_title="AI Movies",
        published_at=datetime.now(timezone.utc),
        view_count=500_000,
        duration_seconds=600,
        matched_ips=["Superman", "Batman"]
    )

    channel_risk = 90  # Known infringer
    risk = processor.calculate_initial_risk(metadata, channel_risk)

    # Should be HIGH or CRITICAL
    assert risk >= 60
    assert risk <= 100
```

---

#### Story 2.3: Keyword Performance Tracking
**Status**: Check if already implemented
**Effort**: 2 hours (if needed)
**Priority**: P1

**Check First**:
- Does `keyword_tracker.py` already exist? **YES** (147 LOC, 12% coverage)
- Does it track keyword performance? **CHECK IMPLEMENTATION**

**Tasks** (if needed):
1. Review `app/core/keyword_tracker.py`
2. Implement if missing:
   - Track keywords that find videos (success rate)
   - Track keywords that find infringements (quality rate)
   - Adaptive priority based on performance
3. Add tests to achieve 80%+ coverage

**Acceptance Criteria**:
- [ ] Keywords tracked with success metrics
- [ ] Poor performers deprioritized
- [ ] Good performers prioritized
- [ ] 80%+ test coverage on `keyword_tracker.py`

---

#### Story 2.4: Trending/Viral Discovery Method
**Status**: Check if already implemented
**Effort**: 1 hour (if needed)
**Priority**: P1

**Check First**:
- Does discovery engine have trending method? **CHECK**
- Does `fresh_content_scanner.py` handle trending? **YES** (85 LOC, 16% coverage)

**Tasks** (if needed):
1. Review existing implementation
2. Add tests to improve coverage to 80%+
3. Verify integration with discovery engine

**Acceptance Criteria**:
- [ ] Trending videos discovered from YouTube trending feed
- [ ] View velocity tracked for viral detection
- [ ] Tests achieve 80%+ coverage

---

### Phase 2: Risk Analyzer Service Creation (8-12 hours)
**Epic 3: Stories 3.1-3.8**

#### Story 3.1: Create Risk Analyzer Service Infrastructure
**Status**: Ready to implement
**Effort**: 2 hours
**Priority**: P0

**Current State**:
- `services/risk-scorer-service/` exists but empty
- Needs complete service scaffolding

**Tasks**:
1. ✅ Rename service directory
   ```bash
   mv services/risk-scorer-service services/risk-analyzer-service
   ```

2. ✅ Copy service template from discovery-service
   ```
   services/risk-analyzer-service/
   ├── app/
   │   ├── __init__.py
   │   ├── main.py              # FastAPI app
   │   ├── config.py            # Settings
   │   ├── models.py            # Pydantic models
   │   ├── core/
   │   │   ├── __init__.py
   │   │   ├── risk_rescorer.py         # NEW
   │   │   ├── view_velocity_tracker.py  # COPY from discovery
   │   │   ├── channel_updater.py       # NEW
   │   │   └── scan_scheduler.py        # NEW
   │   ├── routers/
   │   │   ├── __init__.py
   │   │   └── health.py
   │   └── middleware/
   │       ├── __init__.py
   │       └── logging.py
   ├── tests/
   │   ├── __init__.py
   │   └── test_health.py
   ├── terraform/
   │   ├── provider.tf
   │   ├── variables.tf
   │   ├── main.tf              # Cloud Run + PubSub subscriptions
   │   └── outputs.tf
   ├── Dockerfile
   ├── cloudbuild.yaml
   ├── pyproject.toml
   └── README.md
   ```

3. ✅ Configure dependencies in `pyproject.toml`
   ```toml
   [project]
   name = "risk-analyzer-service"
   version = "0.1.0"
   description = "Continuous risk analysis and prioritization service"
   requires-python = ">=3.13"
   dependencies = [
       "fastapi>=0.119.1",
       "uvicorn[standard]>=0.32.0",
       "pydantic-settings>=2.10.0",
       "google-cloud-firestore>=2.21.0",
       "google-cloud-pubsub>=2.31.1",
       "python-json-logger>=3.2.0",
   ]
   ```

4. ✅ Create Terraform infrastructure
   - Cloud Run service
   - PubSub subscription to `video-discovered` topic
   - IAM permissions for Firestore/PubSub
   - Environment variables

5. ✅ Add health check endpoint
   ```python
   @router.get("/health")
   async def health_check():
       return {"status": "healthy", "service": "risk-analyzer"}
   ```

**Acceptance Criteria**:
- [ ] Service directory renamed to `risk-analyzer-service`
- [ ] Basic FastAPI app structure in place
- [ ] Health endpoint works locally
- [ ] Terraform ready for deployment
- [ ] Dependencies installed

**Testing**:
```bash
cd services/risk-analyzer-service
uv sync
./scripts/dev-local.sh risk-analyzer-service
curl http://localhost:8080/health
```

---

#### Story 3.2: Implement View Velocity Tracking
**Status**: Ready to implement
**Effort**: 2 hours
**Priority**: P0

**Current State**:
- `view_velocity_tracker.py` exists in discovery-service (106 LOC, 78% coverage)
- Needs to be **copied/shared** with risk-analyzer-service

**Decision Options**:
1. **Duplicate file** in risk-analyzer-service (simpler, independent services)
2. **Create shared library** (more elegant, but adds complexity)

**Recommendation**: **Option 1** - Duplicate for now

**Tasks**:
1. ✅ Copy `view_velocity_tracker.py` to risk-analyzer-service
   ```bash
   cp services/discovery-service/app/core/view_velocity_tracker.py \
      services/risk-analyzer-service/app/core/
   ```

2. ✅ Copy tests
   ```bash
   cp services/discovery-service/tests/test_view_velocity_tracker.py \
      services/risk-analyzer-service/tests/
   ```

3. ✅ Update imports if needed

4. ✅ Run tests to verify 78% coverage maintained

**Acceptance Criteria**:
- [ ] View velocity tracking works in risk-analyzer-service
- [ ] Tests passing with 78%+ coverage
- [ ] Can detect viral videos (>1000 views/hour)

---

#### Story 3.3: Build Adaptive Risk Rescoring Algorithm
**Status**: Ready to implement
**Effort**: 3 hours
**Priority**: P0

**This is the CORE of the Risk Analyzer Service**

**Tasks**:
1. ✅ Create `risk_rescorer.py`
   ```python
   class RiskRescorer:
       """
       Adaptive risk rescoring algorithm.

       Factors (5 total):
       1. View velocity (+0 to +30 points) - Viral detection
       2. Channel reputation (+0 to +20 points) - Serial infringers
       3. Engagement rate (+0 to +10 points) - Likes, comments
       4. Age decay (-15 to 0 points) - Old videos lose priority
       5. Prior analysis results (-10 to +20 points) - Learn from Gemini
       """

       def __init__(
           self,
           firestore_client,
           velocity_tracker: ViewVelocityTracker,
           channel_tracker: ChannelTracker
       ):
           self.firestore = firestore_client
           self.velocity = velocity_tracker
           self.channels = channel_tracker

       async def recalculate_risk(self, video_id: str) -> int:
           """Recalculate current risk for a video."""
           # Fetch video from Firestore
           video = await self.get_video(video_id)

           # Start with initial risk
           risk = video.initial_risk

           # Factor 1: View velocity (viral detection)
           velocity = await self.velocity.calculate_velocity(video_id)
           if velocity.views_per_hour > 10_000:  # Extremely viral
               risk += 30
           elif velocity.views_per_hour > 1_000:  # Very viral
               risk += 20
           elif velocity.views_per_hour > 100:  # Viral
               risk += 10

           # Factor 2: Channel reputation
           channel = await self.channels.get_or_create_profile(
               video.channel_id,
               video.channel_title
           )
           if channel.infringement_rate > 0.5:  # 50%+ infringer
               risk += 20
           elif channel.infringement_rate > 0.25:  # 25%+ infringer
               risk += 10

           # Factor 3: Engagement rate
           if video.view_count > 0:
               engagement = (video.like_count + video.comment_count) / video.view_count
               if engagement > 0.05:  # 5%+ engagement
                   risk += 10
               elif engagement > 0.02:  # 2%+ engagement
                   risk += 5

           # Factor 4: Age decay
           age_days = (datetime.now(timezone.utc) - video.published_at).days
           if age_days > 180:  # >6 months old
               risk -= 15
           elif age_days > 90:  # >3 months old
               risk -= 10
           elif age_days > 30:  # >1 month old
               risk -= 5

           # Factor 5: Prior analysis results
           if video.gemini_result:
               if video.gemini_result.contains_infringement:
                   risk += 20  # Confirmed infringement
               else:
                   risk -= 10  # Confirmed clean

           return max(0, min(risk, 100))
   ```

2. ✅ Add risk tier calculation
   ```python
   def calculate_tier(self, risk: int) -> str:
       """Calculate risk tier from score."""
       if risk >= 90:
           return "CRITICAL"
       elif risk >= 70:
           return "HIGH"
       elif risk >= 40:
           return "MEDIUM"
       elif risk >= 20:
           return "LOW"
       else:
           return "VERY_LOW"
   ```

3. ✅ Write comprehensive tests
   - Test each factor independently
   - Test factor combinations
   - Test edge cases (new video, old video, viral, etc.)
   - Target 90%+ coverage

**Acceptance Criteria**:
- [ ] 5-factor risk algorithm implemented
- [ ] Risk properly adjusted based on velocity, channel, engagement, age, results
- [ ] Risk tier calculated correctly
- [ ] 90%+ test coverage
- [ ] Handles edge cases (missing data, new channels, etc.)

---

#### Story 3.4: Implement Risk-Based Rescanning Scheduler
**Status**: Ready to implement
**Effort**: 2 hours
**Priority**: P0

**Tasks**:
1. ✅ Create `scan_scheduler.py`
   ```python
   class ScanScheduler:
       """
       Risk-based rescanning scheduler.

       Tiers:
       - CRITICAL (90-100): Every 6 hours
       - HIGH (70-89): Daily
       - MEDIUM (40-69): Every 3 days
       - LOW (20-39): Weekly
       - VERY_LOW (0-19): Monthly
       """

       SCAN_INTERVALS = {
           "CRITICAL": timedelta(hours=6),
           "HIGH": timedelta(hours=24),
           "MEDIUM": timedelta(days=3),
           "LOW": timedelta(days=7),
           "VERY_LOW": timedelta(days=30),
       }

       def __init__(self, firestore_client):
           self.firestore = firestore_client

       async def get_videos_due_for_scan(self, limit: int = 100) -> list[VideoMetadata]:
           """Get videos due for rescanning, prioritized by risk."""
           now = datetime.now(timezone.utc)

           # Query Firestore for videos where next_scan_at <= now
           query = (
               self.firestore.collection("videos")
               .where("next_scan_at", "<=", now)
               .order_by("next_scan_at")
               .limit(limit * 2)
           )

           videos = []
           async for doc in query.stream():
               video = VideoMetadata(**doc.to_dict())
               videos.append(video)

           # Sort by current_risk (highest first)
           videos.sort(key=lambda v: v.current_risk, reverse=True)

           return videos[:limit]

       def calculate_next_scan_time(self, risk_tier: str) -> datetime:
           """Calculate next scan time based on tier."""
           interval = self.SCAN_INTERVALS.get(risk_tier, timedelta(days=30))
           return datetime.now(timezone.utc) + interval
   ```

2. ✅ Add continuous scanning endpoint
   ```python
   @router.post("/scan/run")
   async def run_scan_cycle():
       """Run one scan cycle - process videos due for rescanning."""
       videos = await scheduler.get_videos_due_for_scan(limit=100)

       for video in videos:
           # Recalculate risk
           new_risk = await rescorer.recalculate_risk(video.video_id)

           # Update Firestore
           await update_video_risk(video.video_id, new_risk)

           # If HIGH risk, publish to vision-analyzer
           if new_risk >= 70:
               await publish_high_risk_video(video)

       return {"videos_processed": len(videos)}
   ```

3. ✅ Add Cloud Scheduler job in Terraform
   ```hcl
   resource "google_cloud_scheduler_job" "risk_analyzer_scan" {
     name     = "risk-analyzer-scan-cycle"
     schedule = "*/15 * * * *"  # Every 15 minutes

     http_target {
       uri = "${google_cloud_run_service.risk_analyzer.status[0].url}/scan/run"
     }
   }
   ```

4. ✅ Write tests
   - Test video selection (only due videos)
   - Test priority ordering (high risk first)
   - Test next_scan_at calculation

**Acceptance Criteria**:
- [ ] Videos rescanned based on tier schedule
- [ ] High-risk videos scanned more frequently
- [ ] Low-risk videos scanned less frequently
- [ ] Cloud Scheduler triggers every 15 minutes
- [ ] Tests cover scheduling logic

---

#### Story 3.5: Add Channel Risk Updates
**Status**: Ready to implement
**Effort**: 1 hour
**Priority**: P1

**Tasks**:
1. ✅ Create `channel_updater.py`
   ```python
   class ChannelUpdater:
       """Update channel risk based on video scan results."""

       def __init__(self, channel_tracker: ChannelTracker):
           self.channels = channel_tracker

       async def update_channel_after_scan(
           self,
           channel_id: str,
           video_id: str,
           scan_result: dict
       ):
           """Update channel metrics after video analysis."""
           if scan_result.get("contains_infringement"):
               # Increment infringement count
               await self.channels.mark_video_as_infringement(
                   channel_id,
                   infringement_date=datetime.now(timezone.utc)
               )
           else:
               # Increment cleared count
               await self.channels.mark_video_as_cleared(channel_id)
   ```

2. ✅ Integrate with risk rescorer

3. ✅ Add tests

**Acceptance Criteria**:
- [ ] Channel reputation updates after video scans
- [ ] Infringement rate calculated correctly
- [ ] Tests verify channel updates

---

#### Story 3.6: Integrate PubSub
**Status**: Ready to implement
**Effort**: 1 hour
**Priority**: P0

**Tasks**:
1. ✅ Subscribe to `video-discovered` topic
   - Process new videos
   - Calculate initial risk
   - Schedule first rescan

2. ✅ Publish to `video-high-risk` topic
   - When `current_risk >= 70`
   - Vision analyzer subscribes to this

3. ✅ Add PubSub handler
   ```python
   @router.post("/pubsub/video-discovered")
   async def handle_video_discovered(request: Request):
       """Handle video-discovered PubSub messages."""
       message = await request.json()
       video_data = base64.b64decode(message["message"]["data"])
       video = json.loads(video_data)

       # Calculate risk and schedule
       await process_new_video(video)

       return {"status": "processed"}
   ```

4. ✅ Add tests

**Acceptance Criteria**:
- [ ] Subscribes to `video-discovered` successfully
- [ ] Publishes high-risk videos to `video-high-risk`
- [ ] PubSub messages processed correctly
- [ ] Tests verify PubSub integration

---

#### Stories 3.7-3.8: Performance & Monitoring
**Status**: Ready to implement
**Effort**: 2 hours
**Priority**: P2

**Tasks**:
1. ✅ Add performance metrics
   - Videos processed per minute
   - Risk calculation latency
   - PubSub message latency

2. ✅ Add monitoring dashboards
   - Cloud Monitoring metrics
   - Alerting for failures

3. ✅ Performance optimization
   - Batch Firestore operations
   - Cache channel data
   - Optimize queries

**Acceptance Criteria**:
- [ ] Can handle 100+ videos/min
- [ ] Monitoring dashboards configured
- [ ] Alerts set up for failures

---

### Phase 3: Integration & Testing (3-4 hours)
**Epic 4: Stories 4.1-4.4**

#### Story 4.1: End-to-End Integration Testing
**Status**: Ready after Phase 2
**Effort**: 2 hours
**Priority**: P0

**Tasks**:
1. ✅ Create integration test suite
   ```python
   async def test_full_discovery_to_risk_flow():
       """Test video flow from discovery to risk analysis."""
       # 1. Discovery service finds video
       video = await discovery.discover_videos(query="Superman AI")
       assert video.initial_risk > 0

       # 2. PubSub message published
       message = await pubsub.pull("video-discovered")
       assert message.video_id == video.video_id

       # 3. Risk analyzer processes video
       await risk_analyzer.process_video(video)

       # 4. Risk updated in Firestore
       updated = await firestore.get_video(video.video_id)
       assert updated.current_risk >= 0

       # 5. If high risk, published to vision-analyzer
       if updated.current_risk >= 70:
           message = await pubsub.pull("video-high-risk")
           assert message.video_id == video.video_id
   ```

2. ✅ Test with emulators locally
   - Firestore emulator
   - PubSub emulator

3. ✅ Test in dev environment

**Acceptance Criteria**:
- [ ] Full flow tested end-to-end
- [ ] Discovery → Risk Analyzer → Vision Analyzer works
- [ ] PubSub messages flow correctly
- [ ] Firestore updates propagate

---

#### Story 4.2: Success Metrics Dashboard
**Status**: Ready after Phase 2
**Effort**: 1 hour
**Priority**: P1

**Tasks**:
1. ✅ Create BigQuery views for metrics
   ```sql
   CREATE VIEW discovery_metrics AS
   SELECT
     DATE(timestamp) as date,
     COUNT(*) as videos_discovered,
     AVG(initial_risk) as avg_initial_risk,
     SUM(CASE WHEN initial_risk >= 70 THEN 1 ELSE 0 END) as high_risk_count
   FROM videos
   GROUP BY date;
   ```

2. ✅ Add metrics endpoints to API service

3. ✅ Create dashboard UI

**Acceptance Criteria**:
- [ ] Key metrics visible in dashboard
- [ ] Historical trends shown (30 days)
- [ ] Can track success metrics from Epic goals

---

#### Story 4.3: Production Deployment
**Status**: Ready after testing
**Effort**: 1 hour
**Priority**: P0

**Tasks**:
1. ✅ Deploy risk-analyzer-service to dev
   ```bash
   ./scripts/deploy-service.sh risk-analyzer-service dev
   ```

2. ✅ Verify health checks

3. ✅ Monitor for 24 hours

4. ✅ Deploy to production
   ```bash
   ./scripts/deploy-service.sh risk-analyzer-service prod
   ```

**Acceptance Criteria**:
- [ ] Both services deployed to prod
- [ ] Health checks passing
- [ ] No errors in logs (24h monitoring)
- [ ] Metrics showing expected behavior

---

## 📋 Checklist: Before Starting Implementation

### Prerequisites
- [x] All 167 tests passing
- [x] Code pushed to GitHub
- [x] Epic document reviewed
- [ ] GCP project set up
- [ ] Firestore emulator installed
- [ ] PubSub emulator installed

### Development Environment
```bash
# Install emulators
gcloud components install cloud-firestore-emulator
gcloud components install pubsub-emulator

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync --group dev
```

---

## 🎯 Success Criteria (Epic Complete)

### Technical Criteria
- [ ] Both services deployed to production and stable
- [ ] All unit tests pass (>80% coverage per service)
- [ ] Integration tests pass
- [ ] No critical bugs or performance issues
- [ ] Documentation complete

### Business Criteria
- [ ] Discovery hit rate >15% (videos found / quota spent)
- [ ] Channel database >80% relevant (DC-related channels)
- [ ] Viral detection latency <6 hours
- [ ] Gemini utilization >€150/day (62% of €240 budget)
- [ ] System processes >1,000 videos/day

### Operational Criteria
- [ ] Monitoring and alerts configured
- [ ] Runbooks created for common issues
- [ ] 7 days of stable production operation
- [ ] Rollback plan tested

---

## ⏱️ Time Estimates

| Phase | Stories | Estimated Time | Priority |
|-------|---------|----------------|----------|
| **Phase 1: Discovery Refactor** | 2.1-2.4 | 4-6 hours | P0 |
| **Phase 2: Risk Analyzer** | 3.1-3.8 | 8-12 hours | P0 |
| **Phase 3: Integration** | 4.1-4.4 | 3-4 hours | P0 |
| **Total** | | **16-24 hours** | |

**Recommended Schedule**:
- **Day 1 (8h)**: Phase 1 complete, Story 3.1-3.3 started
- **Day 2 (8h)**: Story 3.3-3.8 complete
- **Day 3 (4h)**: Phase 3 integration and deployment

---

## 🔄 Development Workflow

### For Each Story

1. **Create feature branch**
   ```bash
   git checkout -b feature/story-2.1-remove-rescanning
   ```

2. **Implement with TDD**
   - Write test first
   - Implement feature
   - Run tests: `uv run pytest`
   - Check coverage: `uv run pytest --cov`

3. **Code quality**
   ```bash
   uv run ruff format .
   uv run ruff check .
   ```

4. **Commit with message**
   ```bash
   git commit -m "feat(discovery): remove rescanning logic

   - Delete video_rescanner.py
   - Remove imports from discovery_engine
   - All 167 tests still passing

   Epic 001, Story 2.1"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/story-2.1-remove-rescanning
   ```

---

## 📚 References

- **Epic Document**: `.planning/EPIC-001-two-service-discovery-architecture.md`
- **Architecture**: `.planning/ARCHITECTURE.md`
- **Implementation Standards**: `.planning/IMPLEMENTATION-STANDARDS.md`
- **Quick Checklist**: `.planning/QUICK-CHECKLIST.md`
- **Repository**: https://github.com/Borismism/copycat

---

## 🚀 Next Steps

1. **Review this plan** - Ensure all stakeholders agree
2. **Set up GCP project** - Terraform infrastructure
3. **Start Phase 1** - Story 2.1 (remove rescanning)
4. **Daily standups** - Track progress
5. **Deploy to dev** - After each phase
6. **Production deployment** - After Epic 4.3

---

**Ready to start implementation?** 🎯

The codebase is clean, tests are passing, and this plan provides a clear roadmap to complete the Epic 001 two-service architecture redesign.
