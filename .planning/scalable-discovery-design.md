# Scalable Discovery Architecture Design

## Problem Statement

Current discovery service works well for 11 Justice League IPs (~60 keywords) but won't scale to 100+ IPs (~600+ keywords) because:

1. Sequential keyword processing → rotation time grows linearly
2. No priority-based allocation → all IPs treated equally
3. No "daily fresh" mode → miss trending content between rotations
4. Fixed quota allocation → inflexible

## Solution: Multi-Tier Intelligent Discovery

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DISCOVERY ORCHESTRATOR                    │
│                   (discovery_engine.py)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌─────────────┐
│ TIER 1   │    │ TIER 2   │    │ TIER 3      │
│ Fresh    │    │ Channel  │    │ Deep Keyword│
│ Content  │    │ Tracking │    │ Rotation    │
│ (20%)    │    │ (60%)    │    │ (20%)       │
└──────────┘    └──────────┘    └─────────────┘
    │               │                 │
    │               │                 │
    ▼               ▼                 ▼
Daily quota allocation based on priority
```

### Tier 1: Fresh Content Scanner (20% quota = 2,000 units)

**Goal:** Catch trending/viral content within 24 hours

**Strategy:**
- Scan HIGH priority IPs for content published in last 24h
- Uses efficient search with `publishedAfter` filter
- Runs on EVERY discovery cycle

**Cost Calculation:**
```python
HIGH_PRIORITY_IPS = 20 IPs (configurable)
KEYWORDS_PER_IP = 2 (top 2 most effective keywords)
SEARCHES = 20 × 2 = 40 searches
COST = 40 × 100 = 4,000 units (over budget!)

SOLUTION: Use rotation within HIGH priority
- Split HIGH IPs into 2 groups
- Group A: Days 1, 3, 5 (10 IPs → 20 searches → 2,000 units)
- Group B: Days 2, 4, 6 (10 IPs → 20 searches → 2,000 units)
```

**Coverage:**
- HIGH priority IPs: Scanned every 2 days for fresh content
- Ensures no viral content older than 48h is missed

### Tier 2: Channel Tracking (60% quota = 6,000 units)

**Goal:** Maximum discovery efficiency on known channels

**Strategy:**
- Scan channels with history of violations
- 3 units per channel = 2,000 channels/day
- Adaptive frequency based on infringement rate

**Cost Calculation:**
```python
QUOTA = 6,000 units
COST_PER_CHANNEL = 3 units (channel + playlist + details)
CHANNELS_PER_DAY = 6,000 / 3 = 2,000 channels

CHANNEL_TIERS:
- PLATINUM (>50% infringement): Scan daily
- GOLD (25-50% infringement): Scan every 3 days
- SILVER (10-25% infringement): Scan weekly
- BRONZE (<10% infringement): Scan monthly
```

**This already exists and works great!**

### Tier 3: Deep Keyword Rotation (20% quota = 2,000 units)

**Goal:** Discover NEW channels via comprehensive keyword scanning

**Strategy:**
- Priority-based rotation schedule
- Smart window-based scanning (already implemented)
- Adaptive based on keyword success rate

**Rotation Schedule:**
```python
# HIGH priority keywords (top performers)
ROTATION_FREQUENCY = 3 days
KEYWORDS = 30 keywords
SCANS_PER_DAY = 30 / 3 = 10 keywords/day
COST = 10 × 100 = 1,000 units ✅

# MEDIUM priority keywords
ROTATION_FREQUENCY = 14 days
KEYWORDS = 100 keywords
SCANS_PER_DAY = 100 / 14 = ~7 keywords/day
COST = 7 × 100 = 700 units ✅

# LOW priority keywords
ROTATION_FREQUENCY = 30 days
KEYWORDS = 200 keywords
SCANS_PER_DAY = 200 / 30 = ~7 keywords/day
COST = 7 × 100 = 700 units ✅

TOTAL TIER 3: ~24 keyword searches/day → 2,400 units
(Slightly over 20%, steal 400 units from Tier 2)
```

**Capacity at Scale:**
- HIGH: 30 keywords → covers 10 top IPs (3 keywords each)
- MEDIUM: 100 keywords → covers 25 IPs (4 keywords each)
- LOW: 200 keywords → covers 50 IPs (4 keywords each)
- **TOTAL: 85 IPs fully covered with 10k daily quota** 🎯

### Priority Assignment Logic

**Keyword Priority = IP Priority × Keyword Performance**

```python
class KeywordPriority(Enum):
    HIGH = "high"      # Scan every 3 days
    MEDIUM = "medium"  # Scan every 14 days
    LOW = "low"        # Scan every 30 days

def calculate_keyword_priority(ip: IPTarget, keyword: str) -> KeywordPriority:
    """
    Determine keyword priority based on IP priority and historical success.
    """
    # Base priority from IP
    base_priority = ip.priority

    # Get keyword performance
    stats = keyword_tracker.get_keyword_stats(keyword)
    success_rate = stats.videos_found / stats.total_scans if stats else 0

    # HIGH IP + high success rate = HIGH keyword
    if base_priority == IPPriority.HIGH and success_rate > 0.5:
        return KeywordPriority.HIGH

    # HIGH IP + low success rate = MEDIUM keyword
    if base_priority == IPPriority.HIGH:
        return KeywordPriority.MEDIUM

    # MEDIUM IP + high success rate = MEDIUM keyword
    if base_priority == IPPriority.MEDIUM and success_rate > 0.3:
        return KeywordPriority.MEDIUM

    # Everything else = LOW keyword
    return KeywordPriority.LOW
```

### Daily Discovery Flow

```python
async def discover(max_quota: int = 10_000) -> DiscoveryStats:
    """
    Intelligent multi-tier discovery.
    """
    # TIER 1: Fresh Content (20% quota)
    fresh_quota = int(max_quota * 0.20)
    fresh_stats = await scan_fresh_content(fresh_quota)

    # TIER 2: Channel Tracking (60% quota)
    channel_quota = int(max_quota * 0.60)
    channel_stats = await scan_channels(channel_quota)

    # TIER 3: Deep Keyword Rotation (20% quota)
    keyword_quota = int(max_quota * 0.20)
    keyword_stats = await scan_keywords_by_priority(keyword_quota)

    return aggregate_stats(fresh_stats, channel_stats, keyword_stats)
```

## Implementation Plan

### Phase 1: Schema Updates ✅
- [ ] Add `priority` field to IP targets YAML
- [ ] Update IPTarget model with priority default
- [ ] Add keyword priority tracking to Firestore

### Phase 2: Fresh Content Scanner 🆕
- [ ] Create `fresh_content_scanner.py`
- [ ] Implement HIGH IP rotation (Group A/B)
- [ ] Add 24h time window filtering

### Phase 3: Priority-Based Keyword Rotation 🆕
- [ ] Add priority calculation logic to KeywordTracker
- [ ] Implement rotation schedules by priority
- [ ] Track keyword success rates

### Phase 4: Discovery Orchestrator Update
- [ ] Implement 3-tier quota allocation
- [ ] Add priority-based discovery flow
- [ ] Update stats tracking

### Phase 5: Testing & Validation
- [ ] Test with 100 mock IPs
- [ ] Validate quota distribution
- [ ] Measure rotation times by priority

## Performance Projections

### Current System (11 IPs)
- Keywords: ~60
- Rotation: 2-3 days
- Coverage: Excellent ✅

### New System (100 IPs)
```
Tier 1 (Fresh - HIGH priority only):
- 20 HIGH priority IPs
- Coverage: Every 2 days
- Quota: 2,000 units/day

Tier 2 (Channels):
- ~2,000 channels scanned/day
- Adaptive frequency by infringement rate
- Quota: 6,000 units/day

Tier 3 (Deep keyword):
- HIGH: 30 keywords → 3-day rotation
- MEDIUM: 100 keywords → 14-day rotation
- LOW: 200 keywords → 30-day rotation
- Quota: 2,000 units/day

TOTAL CAPACITY:
- 85 IPs with current 10k quota
- 850 IPs with 100k quota (request increase)
```

### Scalability Limits

| Daily Quota | Max IPs | HIGH IPs | Rotation (HIGH) | Rotation (LOW) |
|-------------|---------|----------|-----------------|----------------|
| 10,000      | 85      | 20       | 2 days          | 30 days        |
| 50,000      | 425     | 100      | 2 days          | 30 days        |
| 100,000     | 850     | 200      | 2 days          | 30 days        |

## Adaptive Optimizations

### 1. Smart Keyword Pruning
```python
# Disable keywords with 0% success after 10 scans
if keyword.total_scans > 10 and keyword.success_rate == 0:
    keyword.enabled = False
```

### 2. Dynamic Tier Rebalancing
```python
# If Tier 2 has no channels to scan, give quota to Tier 3
if len(channels_to_scan) == 0:
    tier3_quota += tier2_quota
```

### 3. Trending API Integration
```python
# Use YouTube trending API (1 unit for 50 videos!)
# Filter for IP matches → publish to analysis pipeline
# Cost: 1 unit vs 100 units for keyword search
```

## Success Metrics

### KPIs to Track
1. **Rotation Time by Priority**
   - HIGH: <3 days ✅
   - MEDIUM: <14 days ✅
   - LOW: <30 days ✅

2. **Quota Utilization**
   - Tier 1: 20% ± 5%
   - Tier 2: 60% ± 10%
   - Tier 3: 20% ± 5%

3. **Discovery Efficiency**
   - Videos per quota unit: >0.5
   - Deduplication rate: >70%

4. **Freshness**
   - HIGH IPs: No viral content >48h old
   - MEDIUM IPs: Scanned within 2 weeks
   - LOW IPs: Scanned within 1 month

## Migration Strategy

### Week 1: Add Priorities
- Update YAML schema
- Assign priorities to existing 11 IPs
- Test with current system

### Week 2: Implement Fresh Scanner
- Deploy Tier 1 logic
- Monitor performance
- Validate 24h coverage

### Week 3: Priority Rotation
- Deploy Tier 3 rotation
- Test with 50 IPs
- Measure rotation times

### Week 4: Full Integration
- Deploy complete 3-tier system
- Scale to 100 IPs
- Request quota increase if needed
