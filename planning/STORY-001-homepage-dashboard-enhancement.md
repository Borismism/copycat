# STORY-001: Homepage Dashboard Enhancement

**Epic:** Dashboard Improvements
**Type:** Feature Enhancement
**Priority:** HIGH
**Estimated Effort:** 5 days
**Status:** Not Started

---

## Overview

Redesign the homepage dashboard to provide a comprehensive, real-time view of the entire Copycat system with actionable insights, beautiful visualizations, and proactive alerting.

## User Story

**As a** content protection manager
**I want** a comprehensive dashboard showing system health, activity metrics, and actionable insights
**So that** I can quickly understand system performance, identify issues, and make data-driven decisions about resource allocation

## Current State Analysis

**Existing Dashboard (services/frontend-service/app/web/src/pages/Dashboard.tsx):**
- ✅ Service health status (5 services)
- ✅ 24-hour summary (videos discovered, channels tracked, quota usage)
- ✅ Last discovery run statistics
- ✅ Quick action buttons
- ❌ No real-time updates
- ❌ No trend visualization
- ❌ No alerting for critical issues
- ❌ No cost/budget tracking
- ❌ No infringement detection metrics (vision analyzer)
- ❌ No performance metrics (throughput, efficiency)

**Available Data Sources:**
- API endpoint: `GET /api/status` (SystemStatus model)
- API endpoint: `GET /api/status/summary` (SystemSummary model)
- API endpoint: `GET /api/status/services` (ServiceHealth[] model)
- Firestore: `discovery_metrics` collection (historical)
- Firestore: `gemini_budget` collection (cost tracking)
- Firestore: `videos` collection (analysis results)
- Firestore: `channels` collection (channel profiles)

---

## Design Requirements

### 1. Hero Section: System Health at a Glance

**Purpose:** Immediate visual indicator of system status

**Components:**
- Large status badge (🟢 All Systems Operational / 🟡 Degraded / 🔴 Issues Detected)
- Service status grid (5 services with health indicators)
- Auto-refresh every 30 seconds
- Click to view detailed service logs

**Visual Design:**
```
┌─────────────────────────────────────────────────────┐
│  🟢 ALL SYSTEMS OPERATIONAL                         │
│  Last updated: 2 seconds ago                        │
│                                                      │
│  Services (5):                                       │
│  [🟢 discovery] [🟢 risk] [🟢 vision] [🟢 api] [🟢 ui] │
└─────────────────────────────────────────────────────┘
```

### 2. Key Metrics Grid (Real-time)

**Purpose:** Show current 24-hour activity at a glance

**Metrics (4x2 grid):**

**Row 1: Discovery & Channel Tracking**
- **Videos Discovered (24h):** 2,847
  - Trend: ↑ 12% vs yesterday
  - Sparkline chart (last 7 days)
- **Channels Tracked:** 1,234 total
  - Critical: 23 | High: 156 | Medium: 489 | Low: 566
  - Pie chart breakdown
- **YouTube Quota Usage:** 8,456 / 10,000 (84.6%)
  - Progress bar with color coding (green → yellow → red)
  - ETA to limit: ~3.2 hours
- **Discovery Efficiency:** 2.84 videos/unit
  - Trend: ↑ 5% vs yesterday
  - Target: >2.5 (show green if met)

**Row 2: Vision Analysis & Budget**
- **Videos Analyzed (24h):** 487
  - Processing: 12 | Failed: 3
  - Queue depth: 2,360 pending
- **Infringements Detected:** 89 (18.3% rate)
  - Critical: 12 | High confidence: 34 | Medium: 43
  - Alert if rate > 20%
- **Gemini Budget Usage:** $187.40 / $240.00 (78.1%)
  - Avg cost/video: $0.38
  - Progress bar with projected daily total
- **Analysis Throughput:** 20.3 videos/hour
  - Trend: → flat vs yesterday
  - ETA to clear queue: ~4.8 days

**Visual Design:**
```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Videos Discovered│ Channels Tracked │  Quota Usage     │   Efficiency     │
│     2,847        │    1,234 total   │  8,456 / 10,000  │  2.84 vid/unit   │
│   ↑ 12% ▲        │  [Pie Chart]     │ [████████░░] 85% │    ↑ 5% ✓       │
│  [Sparkline]     │ 23C|156H|489M    │  ~3.2h remaining │  Target: >2.5    │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
│ Videos Analyzed  │   Infringements  │  Gemini Budget   │   Throughput     │
│      487         │   89 (18.3%)     │ $187.40 / $240   │  20.3 vids/hr    │
│  12 proc | 3 fail│  12C|34H|43M    │ [████████░░] 78% │    → flat        │
│  Queue: 2,360    │  Alert: <20%✓    │  Avg: $0.38/vid  │  ETA: ~4.8 days  │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### 3. Activity Timeline (Last 24 Hours)

**Purpose:** Visualize system activity over time

**Components:**
- Dual-axis chart:
  - Primary Y-axis: Video discoveries (bar chart, blue)
  - Secondary Y-axis: Infringement detections (line chart, red)
- X-axis: Time (hourly buckets)
- Hover tooltip: detailed metrics
- Highlight anomalies (spikes, drops)

**Visual Design:**
```
Activity Timeline (Last 24 Hours)
┌─────────────────────────────────────────────────────┐
│ Videos Discovered (bars) | Infringements (line)    │
│                                                      │
│ 400│    ██                    ██                    │
│ 300│    ██  ██          ██    ██    ██              │
│ 200│    ██  ██    ██    ██    ██    ██    ██       │
│ 100│    ██  ██    ██    ██    ██    ██    ██  ██   │
│   0└────────────────────────────────────────────────│
│     12a  3a  6a  9a  12p  3p  6p  9p  12a          │
└─────────────────────────────────────────────────────┘
```

### 4. Alert Center

**Purpose:** Proactive issue detection and notification

**Alert Types:**
- 🔴 **CRITICAL:** Service down, budget exceeded, quota exhausted
- 🟡 **WARNING:** Budget > 90%, quota > 85%, error rate > 5%
- 🔵 **INFO:** Discovery complete, milestone reached

**Example Alerts:**
```
⚠️ WARNING: YouTube quota at 92% (9,200/10,000)
   Action: Reduce discovery frequency or request quota increase
   [Acknowledge] [View Details]

⚠️ WARNING: Gemini budget at 95% ($228/$240)
   Action: Analysis will pause at limit
   [Acknowledge] [Increase Budget]

✓ INFO: Discovery run completed - 487 new videos found
   Efficiency: 3.2 videos/unit (↑15%)
   [View Details]
```

### 5. Recent Activity Feed

**Purpose:** Show latest system events in chronological order

**Event Types:**
- Discovery runs (completed, started)
- Video analysis (completed, failed)
- Channel tier changes
- Infringement detections (high confidence)
- Service restarts/deployments

**Visual Design:**
```
Recent Activity
┌─────────────────────────────────────────────────────┐
│ 🔍 Discovery run completed                          │
│    2 minutes ago • 487 videos • 102 quota           │
│    [View Details]                                    │
├─────────────────────────────────────────────────────┤
│ ⚠️  Infringement detected: Superman AI movie        │
│    5 minutes ago • 95% confidence • video_abc123    │
│    [View Analysis] [View Video]                     │
├─────────────────────────────────────────────────────┤
│ 📊 Channel upgraded to HIGH risk                    │
│    12 minutes ago • "AI Movies Daily" (3 violations)│
│    [View Channel]                                    │
└─────────────────────────────────────────────────────┘
```

### 6. Quick Stats Cards

**Purpose:** Show key performance indicators

**Cards (3 columns):**

**Discovery Performance:**
- Total videos in library: 24,567
- New channels discovered (24h): 89
- Deduplication rate: 78%
- Top IP detected: Superman (34%)

**Risk Analysis:**
- Avg time to first scan: 2.3 hours
- Viral detection rate: 95% (<6h)
- Channel tier accuracy: 82%
- Rescan efficiency: 3.1x improvement

**Vision Analysis:**
- Total infringements found: 1,234
- False positive rate: 3.2%
- Avg confidence score: 87%
- Processing time: 8.2s/video

### 7. System Performance Gauges

**Purpose:** Show system efficiency metrics

**Gauges (4):**
- Discovery efficiency: 2.84 / 3.0 target (95%)
- Analysis throughput: 487 / 600 target (81%)
- Budget utilization: $187 / $240 (78%)
- Queue health: 2,360 pending (good if <5,000)

**Visual Design:**
```
System Performance
┌──────────┬──────────┬──────────┬──────────┐
│Discovery │Throughput│  Budget  │  Queue   │
│  95%     │   81%    │   78%    │  Good    │
│ [Gauge]  │ [Gauge]  │ [Gauge]  │ [Gauge]  │
│  🟢      │   🟡     │   🟢     │   🟢     │
└──────────┴──────────┴──────────┴──────────┘
```

---

## Technical Implementation

### Phase 1: API Enhancements (Backend)

**New Endpoints:**

1. **GET /api/analytics/hourly-stats**
   - Returns hourly buckets for last 24h (discoveries, analyses, infringements)
   - Used for timeline chart

2. **GET /api/analytics/system-health**
   - Returns aggregated health metrics
   - Includes alerts, warnings, recent events

3. **GET /api/analytics/performance-metrics**
   - Returns efficiency, throughput, budget stats
   - Used for gauges and KPI cards

4. **GET /api/analytics/recent-events?limit=20**
   - Returns recent activity feed
   - Filterable by event type

**Database Queries:**
- Add indexes on `discovered_at`, `analyzed_at`, `status` in videos collection
- Create aggregated views for hourly stats
- Cache frequently accessed metrics (Redis optional)

### Phase 2: Frontend Components (React + TypeScript)

**New Components:**

1. **SystemHealthBanner.tsx**
   - Overall health status
   - Service grid

2. **MetricsGrid.tsx**
   - 4x2 key metrics grid
   - Sparklines, trend indicators
   - Auto-refresh every 30s

3. **ActivityTimeline.tsx**
   - Chart.js or Recharts dual-axis chart
   - Hourly data visualization

4. **AlertCenter.tsx**
   - Alert cards with actions
   - WebSocket updates (optional)

5. **RecentActivityFeed.tsx**
   - Event list with filtering
   - Auto-refresh

6. **PerformanceGauges.tsx**
   - Gauge chart library (react-gauge-chart)
   - Color-coded thresholds

7. **QuickStatsCards.tsx**
   - KPI cards with icons
   - Expandable details

**Libraries:**
- `recharts` - Charts and visualizations
- `react-gauge-chart` - Gauge components
- `date-fns` - Date formatting
- `swr` or `react-query` - Data fetching with auto-refresh

### Phase 3: Real-time Updates

**Options:**
1. **Polling (Simple):** Refresh data every 30-60 seconds
2. **Server-Sent Events (Better):** Stream updates from backend
3. **WebSocket (Advanced):** Bi-directional real-time updates

**Recommended:** Start with polling, add SSE for alerts

---

## Success Metrics

**Usability:**
- Time to identify system issues: <10 seconds (from dashboard load)
- Alert response time: <2 minutes (for critical issues)
- User satisfaction: 8/10 or higher (team survey)

**Performance:**
- Dashboard load time: <2 seconds
- Auto-refresh impact: <100ms additional load
- Chart rendering: <500ms

**Business Value:**
- Faster issue detection: 80% reduction in MTTR
- Improved resource allocation: 30% better quota utilization
- Proactive alerting: Catch issues before user reports

---

## Acceptance Criteria

- [ ] Dashboard loads in <2 seconds with all data
- [ ] Service health auto-refreshes every 30 seconds
- [ ] All 8 key metrics display with correct data
- [ ] Activity timeline shows last 24 hours of data
- [ ] Alert center displays critical/warning/info alerts
- [ ] Recent activity feed shows last 20 events
- [ ] Performance gauges update in real-time
- [ ] Quick stats cards show accurate KPIs
- [ ] Responsive design works on tablet/desktop
- [ ] Error states handled gracefully
- [ ] Loading states prevent layout shift

---

## Future Enhancements (Post-MVP)

- **Custom date ranges:** View metrics for last 7/30 days
- **Downloadable reports:** Export dashboard as PDF
- **Comparison mode:** Compare today vs yesterday/last week
- **Predictive alerts:** ML-based anomaly detection
- **Mobile app:** Native iOS/Android dashboard
- **Team collaboration:** Comments, annotations on events
- **Webhook notifications:** Slack/Discord integration
- **Custom dashboards:** User-configurable layouts

---

## Dependencies

- STORY-002: Discovery Service Dashboard (for detailed discovery metrics)
- STORY-003: Risk Analyzer Dashboard (for risk scoring insights)
- STORY-004: Vision Analyzer Dashboard (for Gemini analysis details)

---

## Design Mockup Reference

See Figma: `Copycat Dashboard v2.0` (to be created)

**Color Palette:**
- Success: #10B981 (green)
- Warning: #F59E0B (amber)
- Critical: #EF4444 (red)
- Info: #3B82F6 (blue)
- Neutral: #6B7280 (gray)

**Typography:**
- Headers: Inter Bold 24px/32px
- Metrics: Inter SemiBold 36px/48px
- Body: Inter Regular 14px/20px
- Labels: Inter Medium 12px/16px
