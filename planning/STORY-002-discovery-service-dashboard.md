# STORY-002: Discovery Service Dashboard

**Epic:** Dashboard Improvements
**Type:** Feature Enhancement
**Priority:** HIGH
**Estimated Effort:** 4 days
**Status:** Not Started

---

## Overview

Create a dedicated dashboard for the Discovery Service that provides deep insights into YouTube API usage, channel tracking efficiency, IP target coverage, keyword performance, and discovery optimization opportunities.

## User Story

**As a** discovery operations manager
**I want** detailed visibility into discovery service performance, quota allocation, and channel tracking
**So that** I can optimize YouTube API usage, prioritize high-value targets, and maximize discovery efficiency

---

## Current State Analysis

**Existing Discovery Page (services/frontend-service/app/web/src/pages/DiscoveryPage.tsx):**
- Minimal implementation (likely basic)
- No tier-by-tier breakdown
- No keyword performance tracking
- No channel discovery insights
- No quota optimization recommendations

**Available Data:**
- Discovery engine implements 4-tier strategy:
  - Tier 1 (25%): Fresh content scanner (HIGH priority IPs, last 24h)
  - Tier 2 (10%): Deep channel scan (find ALL videos in history)
  - Tier 3 (15%): Channel monitoring (regular tracking)
  - Tier 4 (50%): Priority-based keyword rotation
- ChannelTracker: channel profiles, tiers, scan frequency
- QuotaManager: daily quota tracking, usage by operation type
- KeywordTracker: keyword-to-IP mapping, scan results
- IPTargetManager: 100+ IP targets with priorities
- FreshContentScanner: 24-hour lookback for trending content

**Discovery Metrics Available (Firestore):**
```python
{
  "timestamp": datetime,
  "videos_discovered": int,
  "quota_used": int,
  "channels_tracked": int,
  "duration_seconds": float,
  "tier_breakdown": {
    "tier1": {...},  # fresh content
    "tier2": {...},  # deep scan
    "tier3": {...},  # monitoring
    "tier4": {...},  # keywords
  }
}
```

---

## Design Requirements

### 1. Discovery Overview (Hero Section)

**Purpose:** High-level discovery performance at a glance

**Components:**

**Current Status Card:**
```
┌─────────────────────────────────────────────────────┐
│  Discovery Service Status: 🟢 ACTIVE                │
│  Last run: 2 minutes ago                            │
│  Next run: in 58 minutes (hourly schedule)          │
│                                                      │
│  Current Efficiency: 2.84 videos/quota unit         │
│  Target: >2.5 ✓  |  Best: 3.2 (Jan 28)             │
│                                                      │
│  [Trigger Manual Discovery] [View Logs]             │
└─────────────────────────────────────────────────────┘
```

**Key Metrics (4-column grid):**
- **Videos Discovered (24h):** 2,847
  - Unique channels: 234
  - Avg per run: 142
- **Quota Efficiency:** 2.84 vid/unit
  - 7-day avg: 2.67
  - Trend: ↑ 6.4%
- **Discovery Rate:** 3.2 runs/hour
  - Total today: 76 runs
  - Success rate: 98.7%
- **Deduplication:** 78.4%
  - Saved quota: 10,234 units
  - Total checked: 13,045 videos

### 2. 4-Tier Strategy Performance

**Purpose:** Visualize efficiency of each discovery tier

**Tier Breakdown Table:**

| Tier | Strategy | Quota Used | Videos Found | Efficiency | Channels | Status |
|------|----------|------------|--------------|------------|----------|--------|
| Tier 1 | Fresh Content (24h) | 2,500 (25%) | 876 | 0.35 vid/unit | 89 new | 🟢 |
| Tier 2 | Deep Channel Scan | 1,000 (10%) | 456 | 0.46 vid/unit | 67 scanned | 🟢 |
| Tier 3 | Channel Monitoring | 1,500 (15%) | 732 | 0.49 vid/unit | 245 tracked | 🟢 |
| Tier 4 | Keyword Rotation | 5,000 (50%) | 783 | 0.16 vid/unit | 156 new | 🟡 |
| **Total** | **4-Tier Strategy** | **10,000** | **2,847** | **0.28 vid/unit** | **557 total** | **🟢** |

**Visual Design:**
```
4-Tier Discovery Strategy Performance
┌────────────────────────────────────────────────────┐
│ Tier 1: Fresh Content                              │
│ ████████████░░░░░░░░░░░░░ 25% quota (2,500 units) │
│ 876 videos | 0.35 vid/unit | 89 new channels       │
│ Status: 🟢 Excellent  [View Details]               │
├────────────────────────────────────────────────────┤
│ Tier 2: Deep Channel Scan                          │
│ █████░░░░░░░░░░░░░░░░░░░ 10% quota (1,000 units)  │
│ 456 videos | 0.46 vid/unit | 67 channels scanned   │
│ Status: 🟢 Good  [View Deep Scan Queue]            │
├────────────────────────────────────────────────────┤
│ Tier 3: Channel Monitoring                         │
│ ███████░░░░░░░░░░░░░░░░░ 15% quota (1,500 units)  │
│ 732 videos | 0.49 vid/unit | 245 channels tracked  │
│ Status: 🟢 Excellent  [View Channel List]          │
├────────────────────────────────────────────────────┤
│ Tier 4: Keyword Rotation                           │
│ ████████████████████████ 50% quota (5,000 units)  │
│ 783 videos | 0.16 vid/unit | 156 new channels      │
│ Status: 🟡 Below target (0.2)  [Optimize Keywords] │
└────────────────────────────────────────────────────┘
```

### 3. Quota Usage Tracking

**Purpose:** Monitor YouTube API quota consumption and optimize allocation

**Quota Allocation Donut Chart:**
```
Daily Quota: 10,000 units
┌─────────────────────────────────────┐
│         Used: 8,456 (84.6%)         │
│      Remaining: 1,544 (15.4%)       │
│                                      │
│       [Donut Chart]                  │
│   Tier 1: 25% | Tier 2: 10%        │
│   Tier 3: 15% | Tier 4: 50%        │
│                                      │
│  ETA to limit: 3.2 hours            │
│  Reset: 11:47 PM UTC                │
└─────────────────────────────────────┘
```

**Quota Usage by Operation Type:**

| Operation | Cost/Call | Calls Today | Total Used | % of Quota |
|-----------|-----------|-------------|------------|------------|
| Keyword Search | 100 | 50 | 5,000 | 50% |
| Channel Details | 3 | 500 | 1,500 | 15% |
| Video Details | 1 | 1,000 | 1,000 | 10% |
| Playlist Items | 1 | 956 | 956 | 9.6% |
| Trending | 1 | 1,000 | 1,000 | 10% |

**Quota Optimization Recommendations:**
```
💡 OPTIMIZATION SUGGESTIONS:
1. Tier 4 (Keywords) is 50% of quota but only 27% of discoveries
   → Reduce to 40%, reallocate 10% to Tier 3 (channels)
   Projected impact: +15% efficiency

2. Deep scan queue has 89 channels waiting
   → Increase Tier 2 from 10% to 15%
   Projected impact: Clear queue in 3 days

3. Fresh content scanner found 89 NEW channels in 24h
   → These need deep scanning (Tier 2 priority)
   Action: [Auto-queue for Deep Scan]
```

### 4. Channel Discovery & Tracking

**Purpose:** Monitor channel discovery and tracking effectiveness

**Channel Discovery Funnel:**
```
Channel Discovery Funnel (Last 24h)
┌─────────────────────────────────────────────┐
│ New Channels Discovered: 89                 │
│   ├─ From Fresh Content: 67 (75%)          │
│   ├─ From Keywords: 22 (25%)               │
│   └─ From Manual Add: 0                    │
│                                             │
│ Deep Scan Queue: 89 (100% need scanning)   │
│   ├─ Pending: 67                           │
│   └─ In Progress: 22                       │
│                                             │
│ Channels Promoted to Monitoring: 34         │
│   ├─ Found violations: 12 (35%)            │
│   └─ No violations: 22 (65%)               │
│                                             │
│ Total Channels Tracked: 1,234               │
│   ├─ Critical: 23 (2%)                     │
│   ├─ High: 156 (13%)                       │
│   ├─ Medium: 489 (40%)                     │
│   ├─ Low: 566 (45%)                        │
│   └─ Ignored: 0                            │
└─────────────────────────────────────────────┘
```

**Channel Tier Distribution Chart:**
```
Channel Risk Tiers (1,234 total)
┌─────────────────────────────────────┐
│ [Horizontal Stacked Bar Chart]      │
│ Critical ██ 23                       │
│ High █████████ 156                   │
│ Medium ████████████████████ 489      │
│ Low ██████████████████████ 566       │
└─────────────────────────────────────┘
```

**Top Performing Channels (by video count):**

| Channel | Risk Tier | Videos Found | Last Upload | Next Scan | Actions |
|---------|-----------|--------------|-------------|-----------|---------|
| AI Movies Daily | CRITICAL | 89 | 2h ago | in 4h | [View] [Deep Scan] |
| Sora Shorts | HIGH | 67 | 5h ago | in 19h | [View] [Monitor] |
| JL Fan Content | MEDIUM | 45 | 1d ago | in 2d | [View] [Upgrade Tier] |

### 5. IP Target Coverage

**Purpose:** Track which Justice League IPs are being discovered

**IP Discovery Heatmap (Last 7 Days):**

| IP Name | Priority | Videos Found | Coverage | Channels | Trend |
|---------|----------|--------------|----------|----------|-------|
| Superman | HIGH | 876 (31%) | 🟢 Excellent | 234 | ↑ 12% |
| Batman | HIGH | 734 (26%) | 🟢 Good | 189 | ↑ 8% |
| Wonder Woman | MEDIUM | 456 (16%) | 🟡 Fair | 123 | → flat |
| Flash | MEDIUM | 345 (12%) | 🟡 Fair | 98 | ↓ 3% |
| Aquaman | LOW | 234 (8%) | 🔴 Poor | 67 | ↓ 5% |
| Cyborg | LOW | 123 (4%) | 🔴 Poor | 45 | → flat |
| Green Lantern | LOW | 79 (3%) | 🔴 Poor | 23 | ↓ 2% |

**Visual Design:**
```
IP Coverage Matrix (Last 7 Days)
┌────────────────────────────────────────┐
│           [Heat Map Grid]              │
│   Mon  Tue  Wed  Thu  Fri  Sat  Sun   │
│ S  🟢  🟢  🟢  🟢  🟢  🟢  🟢       │
│ B  🟢  🟢  🟢  🟢  🟡  🟢  🟢       │
│ WW 🟡  🟡  🟡  🟢  🟡  🟡  🟡       │
│ F  🟡  🟡  🟡  🟡  🟡  🟡  🔴       │
│ A  🔴  🔴  🟡  🔴  🔴  🔴  🔴       │
│ C  🔴  🔴  🔴  🔴  🔴  🔴  🔴       │
│ GL 🔴  🔴  🔴  🔴  🔴  🔴  🔴       │
└────────────────────────────────────────┘

🟢 >100 videos  🟡 50-100  🔴 <50
```

**IP Optimization Suggestions:**
```
⚠️ ATTENTION NEEDED:
1. Aquaman, Cyborg, Green Lantern are underperforming
   → Only 14% of total discoveries (target: 25%)
   Action: Boost keyword priority, add trending search terms

2. Superman over-indexed at 31% (target: 25%)
   → Consider reducing Tier 4 keyword frequency
   → Reallocate quota to under-performing IPs

3. Flash trending DOWN 3% this week
   → Check if trending keywords changed
   → Review channel tier assignments
```

### 6. Keyword Performance Tracker

**Purpose:** Optimize keyword searches for discovery

**Top Performing Keywords (Last 7 Days):**

| Keyword | IP | Scans | Videos Found | Efficiency | Last Scan | Status |
|---------|----|----|--------------|------------|-----------|--------|
| "sora superman ai" | Superman | 28 | 89 | 3.18 vid/scan | 2h ago | 🟢 |
| "batman runway ai" | Batman | 24 | 67 | 2.79 vid/scan | 3h ago | 🟢 |
| "ai justice league" | Multiple | 32 | 45 | 1.41 vid/scan | 1h ago | 🟡 |
| "wonder woman kling" | WW | 18 | 23 | 1.28 vid/scan | 5h ago | 🟡 |
| "flash ai video" | Flash | 16 | 8 | 0.50 vid/scan | 8h ago | 🔴 |

**Keyword Efficiency Distribution:**
```
Keyword Efficiency (videos/scan)
┌────────────────────────────────────┐
│ [Scatter Plot]                     │
│ Y-axis: Efficiency (0-5)           │
│ X-axis: Keyword (sorted by scans)  │
│                                     │
│ 5.0 │    ●                          │
│ 4.0 │                               │
│ 3.0 │  ● ●                          │
│ 2.0 │      ● ●                      │
│ 1.0 │          ● ● ●                │
│ 0.0 │              ● ● ●            │
└────────────────────────────────────┘
```

**Keyword Optimization Actions:**
```
RECOMMENDED ACTIONS:
1. Pause low-performers: "flash ai video" (0.50 vid/scan)
   → Try alternatives: "flash sora movie", "ai speedster"

2. Increase frequency: "sora superman ai" (3.18 vid/scan)
   → Currently scanned 1x/day, try 2x/day

3. New keyword suggestions:
   - "justice league runway" (trending on Twitter)
   - "dc heroes kling ai" (Reddit mention spike)
   - "ai superhero movie" (broad coverage)
```

### 7. Discovery Timeline (Hourly)

**Purpose:** Visualize discovery activity over time

**Components:**
- Dual-axis chart:
  - Primary: Videos discovered (bar chart)
  - Secondary: Quota used (line chart)
- X-axis: Time (hourly buckets, last 24h)
- Annotations for discovery runs

**Visual Design:**
```
Discovery Timeline (Last 24 Hours)
┌─────────────────────────────────────────────────────┐
│ Videos Discovered (bars) | Quota Used (line)        │
│                                                      │
│ 200│    ██              ██                   ██     │
│ 150│    ██      ██      ██      ██          ██     │
│ 100│    ██      ██      ██      ██      ██  ██     │
│  50│    ██  ██  ██  ██  ██  ██  ██  ██  ██  ██     │
│   0└────────────────────────────────────────────────│
│     12a  2a  4a  6a  8a 10a 12p  2p  4p  6p  8p 10p│
│                                                      │
│  Total: 2,847 videos | 8,456 quota (84.6%)          │
└─────────────────────────────────────────────────────┘
```

### 8. Deep Scan Queue Management

**Purpose:** Track deep scan backlog and prioritize channels

**Deep Scan Queue (Tier 2):**

| Channel | Discovered | Videos Count | Risk Score | Wait Time | Priority | Actions |
|---------|------------|--------------|------------|-----------|----------|---------|
| AI Movies HD | 2h ago | ~150 | 85 | 2h | HIGH | [Scan Now] |
| Sora Creations | 3h ago | ~89 | 72 | 3h | MEDIUM | [Queue] |
| JL Fan Channel | 5h ago | ~67 | 68 | 5h | MEDIUM | [Queue] |
| ... | ... | ... | ... | ... | ... | ... |

**Queue Stats:**
```
Deep Scan Queue Status
┌────────────────────────────────────────┐
│ Total in queue: 67 channels            │
│ Avg wait time: 4.2 hours               │
│ ETA to clear: 18 hours (at 10% quota)  │
│                                         │
│ Priority breakdown:                     │
│   HIGH: 12 (needs <6h scan)           │
│   MEDIUM: 34 (needs <24h scan)        │
│   LOW: 21 (needs <7d scan)            │
│                                         │
│ [Increase Tier 2 Quota] [Pause Tier 4] │
└────────────────────────────────────────┘
```

---

## Technical Implementation

### Phase 1: Backend Enhancements

**New API Endpoints:**

1. **GET /api/discovery/stats**
   - Returns aggregated discovery metrics
   - Tier breakdown, efficiency, quota usage

2. **GET /api/discovery/tier-performance**
   - Returns performance metrics for each tier
   - Videos found, efficiency, channels tracked

3. **GET /api/discovery/quota-usage**
   - Returns quota breakdown by operation type
   - Daily usage, projections, recommendations

4. **GET /api/discovery/channel-funnel**
   - Returns channel discovery funnel metrics
   - New channels, deep scan queue, tier distribution

5. **GET /api/discovery/ip-coverage**
   - Returns IP target discovery metrics
   - Videos by IP, trend data, coverage scores

6. **GET /api/discovery/keyword-performance?days=7**
   - Returns keyword efficiency metrics
   - Scans, videos found, efficiency scores

7. **GET /api/discovery/deep-scan-queue**
   - Returns channels waiting for deep scan
   - Priority, wait time, estimated size

8. **POST /api/discovery/trigger?max_quota=1000**
   - Trigger manual discovery run
   - Returns run ID for tracking

**Database Queries:**
- Add indexes: `discovered_at`, `channel_id`, `matched_ips`
- Aggregate `discovery_metrics` by tier
- Join with `channels` for risk tiers

### Phase 2: Frontend Components

**New Components:**

1. **DiscoveryOverview.tsx**
   - Status card, key metrics grid
   - Trigger discovery button

2. **TierPerformanceTable.tsx**
   - 4-tier breakdown table
   - Expandable details per tier

3. **QuotaUsageChart.tsx**
   - Donut chart for allocation
   - Table for operation breakdown
   - Optimization suggestions

4. **ChannelFunnel.tsx**
   - Funnel visualization
   - Tier distribution chart
   - Top performing channels table

5. **IPCoverageHeatmap.tsx**
   - Heatmap grid for 7-day coverage
   - IP performance table
   - Optimization suggestions

6. **KeywordPerformanceTable.tsx**
   - Sortable keyword table
   - Efficiency scatter plot
   - Action buttons (pause, boost)

7. **DiscoveryTimeline.tsx**
   - Dual-axis chart (videos + quota)
   - Hourly buckets, last 24h

8. **DeepScanQueueTable.tsx**
   - Paginated queue table
   - Priority sorting
   - Manual trigger buttons

**Libraries:**
- `recharts` - Charts and heatmaps
- `react-table` - Sortable tables
- `date-fns` - Date formatting
- `swr` - Data fetching

---

## Success Metrics

**Discovery Efficiency:**
- Increase overall efficiency from 2.5 to 3.0 vid/unit (20% improvement)
- Reduce Tier 4 (keyword) quota from 50% to 40% while maintaining output
- Clear deep scan queue to <20 channels within 7 days

**Quota Optimization:**
- Reduce wasted quota by 15% (better targeting)
- Increase quota utilization to 95%+ daily
- Reduce quota exhaustion incidents by 80%

**Channel Coverage:**
- Discover 100+ new channels per day
- Maintain 85%+ of channels in HIGH/MEDIUM tiers
- Reduce deep scan wait time from 4.2h to <2h

---

## Acceptance Criteria

- [ ] Dashboard loads with all tier breakdowns
- [ ] Quota usage updates in real-time
- [ ] Channel funnel shows accurate counts
- [ ] IP coverage heatmap displays 7-day data
- [ ] Keyword performance table is sortable
- [ ] Deep scan queue is paginated and actionable
- [ ] Manual discovery trigger works
- [ ] Optimization suggestions are contextual
- [ ] All charts render in <500ms
- [ ] Responsive design for tablet/desktop

---

## Future Enhancements

- **A/B Testing:** Test keyword variations automatically
- **ML Predictions:** Predict which keywords will perform best
- **Auto-Optimization:** Auto-adjust tier quotas based on performance
- **Keyword Suggestions:** AI-generated keyword recommendations
- **Channel Clustering:** Group similar channels for efficient scanning
- **Geo-Targeting:** Discover by region/language
- **Competitive Analysis:** Track competitor channel discoveries

---

## Dependencies

- STORY-001: Homepage Dashboard (for overall system context)
- Backend: Discovery service metrics collection
- Database: Proper indexing on discovery_metrics collection
