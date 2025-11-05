# STORY-003: Risk Analyzer Dashboard

**Epic:** Dashboard Improvements
**Type:** Feature Enhancement
**Priority:** HIGH
**Estimated Effort:** 4 days
**Status:** Not Started

---

## Overview

Create a specialized dashboard for the Risk Analyzer Service that provides real-time insights into video risk scoring, view velocity tracking, channel reputation analysis, scan scheduling optimization, and adaptive learning performance.

## User Story

**As a** risk analysis manager
**I want** comprehensive visibility into risk scoring, scan prioritization, and channel behavior patterns
**So that** I can optimize scan allocation, catch viral videos early, and maximize infringement detection ROI

---

## Current State Analysis

**Risk Analyzer Service Architecture:**
- **Continuous PubSub worker:** Processes discovered videos in real-time
- **6-factor risk scoring model:**
  1. View count magnitude (0-25 points)
  2. View velocity (0-25 points)
  3. Channel reputation (0-20 points)
  4. Video characteristics (0-15 points)
  5. Content signals (0-10 points)
  6. Recency (0-5 points)
- **Adaptive rescoring:** Learns from Gemini analysis results
- **Tiered scan scheduling:**
  - CRITICAL (80-100): Rescan every 6 hours
  - HIGH (60-79): Rescan every 24 hours
  - MEDIUM (40-59): Rescan every 3 days
  - LOW (20-39): Rescan every 7 days
  - VERY_LOW (0-19): Scan once only

**Available Data Sources:**
- Firestore `videos` collection: risk scores, tiers, view snapshots
- Firestore `channels` collection: reputation scores, infringement history
- Firestore `risk_metrics` collection: scoring performance, accuracy
- Risk analyzer publishes to `scan-ready` PubSub topic

**Existing Components:**
- RiskAnalyzer: 6-factor scoring engine
- RiskRescorer: Adaptive learning from Gemini results
- ViewVelocityTracker: Trending detection
- ChannelUpdater: Reputation management
- ScanScheduler: Priority queue management

---

## Design Requirements

### 1. Risk Analysis Overview (Hero Section)

**Purpose:** Real-time view of risk analysis performance

**Status Card:**
```
┌─────────────────────────────────────────────────────┐
│  Risk Analyzer Status: 🟢 PROCESSING                │
│  Queue depth: 2,360 videos pending analysis         │
│  Processing rate: 487 videos/hour                   │
│  Avg scoring time: 1.2s per video                   │
│                                                      │
│  Last 24h: 11,642 videos scored | 98.9% success    │
│  Adaptive learning: 147 rescore adjustments         │
│                                                      │
│  [View Queue] [Trigger Rescore] [View Logs]         │
└─────────────────────────────────────────────────────┘
```

**Key Metrics (4-column grid):**
- **Videos Analyzed (24h):** 11,642
  - New: 2,847 | Rescored: 8,795
  - Avg score: 54.2 (MEDIUM)
- **Scan Queue Depth:** 2,360 pending
  - Critical: 89 | High: 456 | Med: 1,234 | Low: 581
  - ETA to clear: 4.8 hours
- **Risk Accuracy:** 87.3%
  - True positives: 94.2%
  - False positives: 12.7%
  - Improving: ↑ 2.1%
- **View Velocity Detection:** 156 trending
  - Viral (>10k/h): 12
  - Growing (1k-10k/h): 45
  - Normal (<1k/h): 99

### 2. Risk Score Distribution

**Purpose:** Visualize risk tier breakdown and identify patterns

**Risk Tier Pyramid:**
```
Risk Tier Distribution (24,567 total videos)
┌─────────────────────────────────────────────┐
│          CRITICAL (80-100)                  │
│               234 (1%)                      │
│           ▲▲▲▲▲▲▲▲▲▲                       │
│                                             │
│        HIGH (60-79)                         │
│          1,456 (6%)                         │
│     ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲                    │
│                                             │
│      MEDIUM (40-59)                         │
│        9,234 (37%)                          │
│  ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲           │
│                                             │
│     LOW (20-39)                             │
│      8,567 (35%)                            │
│ ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲               │
│                                             │
│    VERY_LOW (0-19)                          │
│      5,076 (21%)                            │
│ ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲                     │
└─────────────────────────────────────────────┘
```

**Risk Score Histogram:**
```
Score Distribution (0-100 scale)
┌────────────────────────────────────┐
│ [Histogram Chart]                  │
│ Y-axis: Video count                │
│ X-axis: Risk score (0-100)         │
│                                     │
│ 3000│         ██                    │
│ 2500│         ██                    │
│ 2000│      ██ ██ ██                │
│ 1500│      ██ ██ ██                │
│ 1000│   ██ ██ ██ ██ ██             │
│  500│   ██ ██ ██ ██ ██ ██ ██      │
│    0└────────────────────────────  │
│      0  20  40  60  80  100        │
│     VL  L   M   H   C              │
└────────────────────────────────────┘

Peak: 50-55 (MEDIUM tier)
Mean: 54.2 | Median: 52 | Mode: 53
```

### 3. 6-Factor Scoring Breakdown

**Purpose:** Understand which factors drive risk scores

**Factor Contribution Analysis:**

| Factor | Weight | Avg Score | Impact | Trend | Top Drivers |
|--------|--------|-----------|--------|-------|-------------|
| 1. View Count | 0-25 | 14.2 | 26% | → | Videos >100k views |
| 2. View Velocity | 0-25 | 16.8 | 31% | ↑ | Viral detection working |
| 3. Channel Reputation | 0-20 | 11.3 | 21% | ↑ | Learning from results |
| 4. Video Characteristics | 0-15 | 8.9 | 16% | → | Duration, tags |
| 5. Content Signals | 0-10 | 2.1 | 4% | → | IP matches |
| 6. Recency | 0-5 | 1.0 | 2% | → | <24h bonus |

**Factor Distribution (Violin Plot):**
```
Score Distribution by Factor
┌────────────────────────────────────────────┐
│       [Violin Plots]                       │
│                                             │
│ View  ╱╲                                   │
│ Count ││  (most videos ~10-20 points)      │
│       ╲╱                                   │
│                                             │
│ View   ╱╲                                  │
│ Vel.  │││  (bimodal: normal vs viral)      │
│       ╲╱╲                                  │
│                                             │
│ Chan. ╱╲                                   │
│ Rep.  ││  (left-skewed: most clean)        │
│       ╲╱                                   │
└────────────────────────────────────────────┘
```

**Top Scoring Videos (High Risk):**

| Video ID | Title | Risk Score | Tier | View Count | Velocity | Channel | Actions |
|----------|-------|------------|------|------------|----------|---------|---------|
| abc123 | "Superman AI Movie..." | 94 | CRITICAL | 1.2M | 12k/h | AI Movies HD | [View] [Scan Now] |
| def456 | "Batman Sora Short..." | 89 | CRITICAL | 890k | 8k/h | Sora Daily | [View] [Queue] |
| ghi789 | "JL Runway Trailer" | 82 | CRITICAL | 567k | 5k/h | DC Fan AI | [View] [Monitor] |

### 4. View Velocity Tracking

**Purpose:** Detect viral/trending videos for immediate analysis

**Trending Videos Dashboard:**

**Velocity Categories:**
```
View Velocity Classification (Last 24h)
┌──────────────────────────────────────────┐
│ EXTREMELY VIRAL (>10k views/hour)       │
│   12 videos | Avg score: 92             │
│   [████░░░░░░] 1% of total              │
│   Status: 🔴 URGENT SCAN NEEDED         │
│                                          │
│ VERY VIRAL (1k-10k views/hour)          │
│   45 videos | Avg score: 78             │
│   [████████░░] 4% of total              │
│   Status: 🟡 HIGH PRIORITY              │
│                                          │
│ VIRAL (100-1k views/hour)               │
│   99 videos | Avg score: 64             │
│   [████████████░░░] 8% of total         │
│   Status: 🟢 SCHEDULED                  │
│                                          │
│ NORMAL (<100 views/hour)                │
│   1,089 videos | Avg score: 48          │
│   [████████████████████] 87% of total   │
│   Status: 🟢 REGULAR QUEUE              │
└──────────────────────────────────────────┘
```

**Velocity Timeline (Last 7 Days):**
```
Viral Video Detection (7-day trend)
┌─────────────────────────────────────────────┐
│ [Line Chart]                                │
│ Y-axis: Viral videos detected               │
│ X-axis: Day                                 │
│                                             │
│ 20│        ●                                │
│ 15│      ● │ ●                              │
│ 10│    ●   │   ● ●                          │
│  5│  ●     │       ● ●                      │
│  0└────────────────────────────             │
│   Mon Tue Wed Thu Fri Sat Sun              │
│                                             │
│ Spike on Thursday: 18 viral videos          │
│ Possible cause: Trending hashtag #SoraAI   │
└─────────────────────────────────────────────┘
```

**Fastest Growing Videos (Real-time):**

| Video | Current Views | 1h Ago | 6h Ago | Growth Rate | Risk Score | Status |
|-------|---------------|--------|--------|-------------|------------|--------|
| abc123 | 1.2M | 890k | 450k | 12k/h (🔥) | 94 | 🔴 Scanning |
| def456 | 890k | 720k | 380k | 8k/h (🔥) | 89 | 🟡 Queued |
| ghi789 | 567k | 489k | 290k | 5k/h (📈) | 82 | 🟢 Scheduled |

### 5. Channel Reputation Tracker

**Purpose:** Monitor channel risk scores and adaptive learning

**Channel Reputation Distribution:**
```
Channel Reputation Scores (1,234 channels)
┌─────────────────────────────────────────────┐
│ [Box Plot]                                  │
│                                             │
│ 100│                      ●                 │
│  80│               ┌───┐  ●                 │
│  60│               │   │                    │
│  40│          ┌────┤   ├────┐              │
│  20│     ●────┤    │   │    ├────●         │
│   0│          └────┴───┴────┘              │
│     MINIMAL  LOW  MED  HIGH  CRIT          │
│                                             │
│ Median: 42 (MEDIUM)                         │
│ Q1: 28 (LOW) | Q3: 68 (HIGH)               │
│ Outliers: 23 channels (CRITICAL)            │
└─────────────────────────────────────────────┘
```

**Top Risk Channels:**

| Channel | Rep Score | Tier | Videos Found | Confirmed Violations | Infringement Rate | Next Rescan |
|---------|-----------|------|--------------|----------------------|-------------------|-------------|
| AI Movies HD | 94 | CRITICAL | 89 | 67 | 75.3% | in 4h |
| Sora Daily | 87 | CRITICAL | 67 | 45 | 67.2% | in 5h |
| DC Fan AI | 82 | CRITICAL | 56 | 34 | 60.7% | in 3h |
| JL Content | 76 | HIGH | 45 | 23 | 51.1% | in 18h |
| Superhero Clips | 71 | HIGH | 38 | 19 | 50.0% | in 20h |

**Channel Tier Transitions (Last 7 Days):**
```
Channel Tier Changes (Adaptive Learning)
┌─────────────────────────────────────────────┐
│ [Sankey Diagram]                            │
│                                             │
│ CRITICAL ══════════════════> CRITICAL (20)  │
│    (23)  ══════════════════> HIGH (3)       │
│                                             │
│ HIGH ════════════════> HIGH (130)           │
│  (156) ═════════════> MEDIUM (20)           │
│        ═════════════> CRITICAL (6)          │
│                                             │
│ MEDIUM ══════════> MEDIUM (450)             │
│  (489)  ═══════> HIGH (30)                  │
│         ═══════> LOW (9)                    │
│                                             │
│ LOW ════════> LOW (540)                     │
│ (566) ══════> MEDIUM (26)                   │
└─────────────────────────────────────────────┘

Net upgrades: 62 channels ↑
Net downgrades: 32 channels ↓
Adaptive learning working! ✓
```

### 6. Adaptive Learning Performance

**Purpose:** Track how well the system learns from Gemini results

**Learning Metrics:**

**Rescore Accuracy Improvement:**
```
Risk Score Accuracy Over Time
┌─────────────────────────────────────────────┐
│ [Line Chart]                                │
│ Y-axis: Accuracy % (true positive rate)    │
│ X-axis: Days since launch                  │
│                                             │
│ 95%│                            ●───●       │
│ 90%│                      ●───●             │
│ 85%│                ●───●                   │
│ 80%│          ●───●                         │
│ 75%│    ●───●                               │
│ 70%│ ●                                      │
│   0└────────────────────────────────────── │
│     D1  D7  D14  D21  D28  D35  D42        │
│                                             │
│ Current: 87.3% (↑ 17.3% since launch)      │
│ Target: 90% by Day 60                      │
└─────────────────────────────────────────────┘
```

**Rescore Impact Analysis:**

| Metric | Before Rescore | After Rescore | Improvement |
|--------|----------------|---------------|-------------|
| True Positive Rate | 72.3% | 87.3% | ↑ 20.8% |
| False Positive Rate | 27.7% | 12.7% | ↓ 54.2% |
| Avg Score Accuracy | ±18 points | ±7 points | ↑ 61.1% |
| CRITICAL tier precision | 68% | 91% | ↑ 33.8% |

**Recent Rescores (Last 24h):**

| Video ID | Original Score | Gemini Result | New Score | Adjustment | Reason |
|----------|----------------|---------------|-----------|------------|---------|
| abc123 | 72 (HIGH) | Infringement (95%) | 88 (CRIT) | +16 | Channel rep ↑ |
| def456 | 58 (MED) | No violation (5%) | 42 (MED) | -16 | False positive |
| ghi789 | 81 (CRIT) | Infringement (88%) | 83 (CRIT) | +2 | Velocity ↑ |

### 7. Scan Scheduling Optimization

**Purpose:** Optimize scan queue and rescan frequency

**Scan Queue Breakdown:**
```
Scan Queue (2,360 videos pending)
┌─────────────────────────────────────────────┐
│ Priority Distribution:                      │
│                                             │
│ CRITICAL (rescan 6h)                        │
│   89 videos | Avg wait: 2.3h               │
│   [████████████████░░░] 4% of queue        │
│   Status: 🔴 12 overdue (>6h)              │
│                                             │
│ HIGH (rescan 24h)                           │
│   456 videos | Avg wait: 8.7h              │
│   [████████████████████] 19% of queue      │
│   Status: 🟡 23 approaching deadline       │
│                                             │
│ MEDIUM (rescan 3d)                          │
│   1,234 videos | Avg wait: 1.2d            │
│   [████████████████████████] 52% of queue  │
│   Status: 🟢 On track                      │
│                                             │
│ LOW (rescan 7d)                             │
│   581 videos | Avg wait: 2.8d              │
│   [████████████░░░] 25% of queue           │
│   Status: 🟢 On track                      │
└─────────────────────────────────────────────┘
```

**Rescan Schedule Adherence:**
```
On-Time Rescan Performance (Last 7 Days)
┌─────────────────────────────────────────────┐
│ Tier      │ On-time │ Late │ Rate │ Target │
│───────────┼─────────┼──────┼──────┼────────│
│ CRITICAL  │   234   │  12  │ 95%  │  >95%  │
│ HIGH      │   456   │  34  │ 93%  │  >90%  │
│ MEDIUM    │ 1,234   │  56  │ 96%  │  >85%  │
│ LOW       │   581   │  23  │ 96%  │  >80%  │
│───────────┴─────────┴──────┴──────┴────────│
│ Overall: 95.2% on-time (↑ 8% vs last week) │
└─────────────────────────────────────────────┘
```

**Optimization Recommendations:**
```
💡 SCHEDULING OPTIMIZATIONS:

1. CRITICAL tier has 12 overdue rescans (>6h wait)
   → Increase vision-analyzer budget allocation by 15%
   → Expected impact: Clear backlog in 2 hours

2. 23 HIGH tier videos approaching 24h deadline
   → Reduce MEDIUM/LOW scan rate by 10%
   → Reallocate to HIGH priority queue

3. Avg MEDIUM wait time (1.2d) is under target (3d)
   → Can reduce frequency to 4 days
   → Save 25% of scan budget, reallocate to CRITICAL

4. Viral detection working well (95% caught <6h)
   → View velocity tracking is effective ✓
   → No changes needed
```

### 8. Risk Model Performance Dashboard

**Purpose:** Monitor risk model health and calibration

**Calibration Chart:**
```
Risk Score Calibration (Predicted vs Actual)
┌─────────────────────────────────────────────┐
│ [Scatter Plot]                              │
│ Y-axis: Actual infringement rate (Gemini)  │
│ X-axis: Predicted risk score (0-100)       │
│                                             │
│100%│                              ●●●       │
│ 80%│                        ●●●●●           │
│ 60%│                  ●●●●●                 │
│ 40%│            ●●●●●                       │
│ 20%│      ●●●●●                             │
│  0%│●●●●●                                   │
│    └────────────────────────────────────── │
│     0   20   40   60   80  100             │
│    VL   L    M    H    C                   │
│                                             │
│ Correlation: 0.92 (excellent) ✓            │
│ Ideal: perfect diagonal line               │
└─────────────────────────────────────────────┘
```

**Precision-Recall by Tier:**

| Tier | Precision | Recall | F1 Score | Sample Size |
|------|-----------|--------|----------|-------------|
| CRITICAL | 91% | 89% | 0.90 | 234 |
| HIGH | 84% | 86% | 0.85 | 1,456 |
| MEDIUM | 67% | 72% | 0.69 | 9,234 |
| LOW | 45% | 51% | 0.48 | 8,567 |
| VERY_LOW | 12% | 18% | 0.14 | 5,076 |

**Overall:** F1 = 0.73 (good), Target: 0.80 by month 3

---

## Technical Implementation

### Phase 1: Backend Enhancements

**New API Endpoints:**

1. **GET /api/risk/stats**
   - Aggregated risk analysis metrics
   - Queue depth, processing rate, accuracy

2. **GET /api/risk/distribution**
   - Risk tier distribution
   - Score histogram, factor breakdown

3. **GET /api/risk/factor-analysis**
   - 6-factor scoring contribution
   - Factor distributions, correlations

4. **GET /api/risk/velocity-tracking**
   - Viral video detection metrics
   - Velocity categories, trending videos

5. **GET /api/risk/channel-reputation**
   - Channel risk scores and tiers
   - Tier transitions, top channels

6. **GET /api/risk/adaptive-learning**
   - Rescore performance metrics
   - Accuracy improvements, recent rescores

7. **GET /api/risk/scan-queue**
   - Scan queue status by tier
   - Overdue scans, schedule adherence

8. **GET /api/risk/model-performance**
   - Calibration data, precision-recall
   - Model health metrics

**Database Queries:**
- Aggregate `risk_metrics` by factor
- Join `videos` with `vision_analysis` for accuracy
- Calculate velocity from view snapshots

### Phase 2: Frontend Components

**New Components:**

1. **RiskOverview.tsx**
   - Status card, key metrics
   - Processing stats

2. **RiskDistributionCharts.tsx**
   - Pyramid chart, histogram
   - Interactive filtering

3. **FactorAnalysis.tsx**
   - Factor contribution table
   - Violin plots, correlation matrix

4. **VelocityTracker.tsx**
   - Velocity categories
   - Timeline chart, fastest growing

5. **ChannelReputationDashboard.tsx**
   - Reputation distribution
   - Top channels table, tier transitions

6. **AdaptiveLearningMetrics.tsx**
   - Accuracy improvement chart
   - Rescore impact table, recent changes

7. **ScanScheduler.tsx**
   - Queue breakdown by tier
   - Schedule adherence, recommendations

8. **ModelPerformance.tsx**
   - Calibration scatter plot
   - Precision-recall table

**Libraries:**
- `recharts` - Charts
- `d3` - Sankey diagrams
- `react-table` - Tables
- `swr` - Data fetching

---

## Success Metrics

**Risk Accuracy:**
- Increase true positive rate from 87% to 90%
- Reduce false positive rate from 13% to 8%
- Improve F1 score from 0.73 to 0.80

**Scan Efficiency:**
- Maintain 95%+ on-time rescan rate
- Clear CRITICAL backlog to <5 videos
- Catch 98% of viral videos within 6 hours

**Adaptive Learning:**
- Rescore accuracy improvement: +3% per week
- Channel tier accuracy: 85%+
- Model calibration correlation: >0.90

---

## Acceptance Criteria

- [ ] Dashboard loads with all metrics
- [ ] Risk distribution charts update in real-time
- [ ] Velocity tracking shows trending videos
- [ ] Channel reputation table is sortable
- [ ] Adaptive learning charts show improvements
- [ ] Scan queue displays overdue scans
- [ ] Model performance metrics are accurate
- [ ] All charts render in <500ms
- [ ] Responsive design for tablet/desktop

---

## Future Enhancements

- **Explainable AI:** Show why a video got a specific score
- **What-if Analysis:** Predict score changes with different factors
- **Auto-tuning:** ML-based factor weight optimization
- **Anomaly Detection:** Flag unusual scoring patterns
- **Competitive Benchmarking:** Compare to industry standards
