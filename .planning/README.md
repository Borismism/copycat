# Discovery Service Redesign - Planning Documents

This directory contains internal planning documents for the Copycat discovery service redesign.

## Documents

### 📋 `discovery-service-redesign.md` (6,900 lines)
Complete epic/story breakdown for refactoring the discovery service from a bloated 685-line god class into a lean, intelligent, production-grade system.

### 📖 `IMPLEMENTATION-STANDARDS.md` (1,800 lines)
**MUST READ before starting ANY story.**

Defines what "fantastic code" means and our zero-tolerance policy for code slop. Includes:
- Definition of Done (9-step checklist)
- Story implementation workflow
- Code quality standards
- Testing requirements
- Deployment verification
- Common pitfalls to avoid
- Complete example implementation

### ✅ `QUICK-CHECKLIST.md` (Quick Reference)
**Print this and keep it visible while coding.**

Daily reference for:
- Story completion checklist (6 sections)
- Common failure fixes
- Daily workflow
- Quality mantras
- Zero tolerance rules

### 🎯 `STORY-FLOW.md` (Visual Guide)
**Step-by-step walkthrough of implementing a story.**

Complete example of Story 1.1 (VideoProcessor):
- Detailed 11-step workflow
- Code examples at each step
- Time estimates per step
- Testing approach
- Deployment verification
- Success indicators
- Momentum tips

**Key Goals:**
- Reduce code from 977 LOC → <500 LOC (49% reduction)
- Eliminate massive code duplication (6 methods repeating same 50 lines)
- Build channel intelligence system (tier-based adaptive scanning)
- Implement quota optimization (33x more efficient per API unit)
- Add view velocity tracking (prioritize viral videos)
- Achieve 80%+ test coverage

**Total Effort:** 70 story points across 5 sprints

## Why This Matters

The current discovery service is a classic example of technical debt:
- **Copy-paste programming:** Same video processing logic repeated 6 times
- **Inefficient:** Wastes 97% of API quota on duplicate keyword searches
- **Dumb:** No learning, no adaptation, no intelligence
- **Unmaintainable:** 685-line god class, impossible to test

The redesign follows these principles:
1. **DRY** - Single responsibility, zero duplication
2. **Smart** - Learn from history, adapt behavior
3. **Efficient** - Every API unit counts
4. **Lean** - Super clean code, <500 LOC total

## Quick Stats

### Before
```
discovery.py: 685 LOC
router.py: 292 LOC
Total: 977 LOC
Duplication: Massive (6 methods × 50 LOC each)
Test Coverage: ~30%
Efficiency: 100 API units per 50 videos (keyword search)
Intelligence: Zero
```

### After
```
Core files: ~500 LOC total
  - discovery_engine.py: 150 LOC
  - video_processor.py: 100 LOC
  - channel_tracker.py: 150 LOC
  - quota_manager.py: 80 LOC
  - router.py: 80 LOC
Duplication: Zero
Test Coverage: 80%+
Efficiency: 3 API units per channel (33x improvement)
Intelligence: Channel tiers, view velocity, adaptive frequency
```

## Implementation Phases

1. **Sprint 1: Foundation** (10 pts) - VideoProcessor, QuotaManager
2. **Sprint 2: Intelligence** (13 pts) - ChannelTracker, ViewVelocity
3. **Sprint 3: Engine** (21 pts) - DiscoveryEngine, new endpoints
4. **Sprint 4: Optimization** (12 pts) - Quota allocation, keyword learning
5. **Sprint 5: Polish** (14 pts) - Testing, analytics, docs

## Success Criteria

- [ ] 49% code reduction achieved
- [ ] Zero duplicate logic remains
- [ ] 80%+ test coverage
- [ ] 33x improvement in API efficiency
- [ ] Channel-based discovery operational
- [ ] View velocity tracking working
- [ ] Adaptive scan frequency implemented
- [ ] All dead code deleted
- [ ] CLAUDE.md updated
- [ ] Production deployment successful

---

**Status:** Planning complete, ready for implementation
**Owner:** Development team
**Last Updated:** 2025-10-28
