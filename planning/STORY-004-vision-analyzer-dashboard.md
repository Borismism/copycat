# STORY-004: Vision Analyzer Dashboard

**Epic:** Dashboard Improvements
**Type:** Feature Enhancement
**Priority:** HIGH
**Estimated Effort:** 5 days
**Status:** Not Started

---

## Overview

Create a comprehensive dashboard for the Vision Analyzer Service (Gemini 2.5 Flash) that provides real-time insights into AI-powered copyright infringement detection, budget management, analysis throughput, character detection accuracy, and cost optimization opportunities.

## User Story

**As a** vision analysis manager
**I want** detailed visibility into Gemini API usage, detection accuracy, budget consumption, and analysis performance
**So that** I can optimize daily budget allocation, maximize video throughput, improve detection precision, and demonstrate ROI to stakeholders

---

## Current State Analysis

**Vision Analyzer Service Architecture:**
- **Gemini 2.5 Flash** via Vertex AI (no rate limits, Dynamic Shared Quota)
- **Budget exhaustion algorithm:** Scans until €240/day ($260) fully utilized
- **Adaptive FPS optimization:**
  - Length-based: 0.05-1.0 FPS based on video duration
  - Risk-based: 0.5x-2.0x multiplier based on risk tier
  - Budget pressure: Reduce FPS when budget <$50
- **Daily capacity:** 20,000-32,000 videos (budget limited, not rate limited)
- **Average cost:** $0.008-0.011 per video (with optimization)

**Available Data Sources:**
- Firestore `gemini_budget` collection: daily spend tracking
- Firestore `videos` collection: `vision_analysis` field with results
- Firestore `vision_metrics` collection: analysis performance
- Video analyzer metrics: cost, tokens, processing time, FPS used

**Analysis Results Structure:**
```python
{
  "video_id": str,
  "analyzed_at": datetime,
  "gemini_model": "gemini-2.5-flash",
  "analysis": {
    "contains_infringement": bool,
    "confidence_score": int,  # 0-100
    "is_ai_generated": bool,
    "ai_tools_detected": list[str],
    "characters_detected": [
      {
        "name": str,
        "screen_time_seconds": float,
        "prominence": "high|medium|low",
        "context": str
      }
    ],
    "video_type": str,
    "reasoning": str,
    "recommended_action": "flag|monitor|ignore"
  },
  "metrics": {
    "cost_usd": float,
    "input_tokens": int,
    "output_tokens": int,
    "processing_time_seconds": float
  },
  "config_used": {
    "fps": float,
    "start_offset_seconds": int,
    "end_offset_seconds": int,
    "effective_duration_seconds": int,
    "frames_analyzed": int
  }
}
```

---

## Design Requirements

### 1. Vision Analysis Overview (Hero Section)

**Purpose:** Real-time view of Gemini analysis performance and budget

**Status Card:**
```
┌─────────────────────────────────────────────────────┐
│  Vision Analyzer Status: 🟢 SCANNING                │
│  Queue: 2,360 pending | Processing: 12 videos       │
│  Throughput: 20.3 videos/hour (24h avg)            │
│  Avg analysis time: 8.2s per video                  │
│                                                      │
│  Daily Budget: $187.40 / $240.00 (78.1%)           │
│  Avg cost/video: $0.38 | Videos scanned: 487       │
│  ETA to budget exhaustion: 3.4 hours                │
│  ETA to clear queue: 116 hours (4.8 days)          │
│                                                      │
│  [View Queue] [Pause Scanning] [Increase Budget]    │
└─────────────────────────────────────────────────────┘
```

**Key Metrics (4-column grid):**
- **Videos Analyzed (24h):** 487
  - Infringements: 89 (18.3%)
  - No violations: 398 (81.7%)
  - Failed: 3 (0.6%)
- **Detection Rate:** 18.3%
  - Critical: 12 (13.5%)
  - High confidence: 34 (38.2%)
  - Medium: 43 (48.3%)
- **Budget Utilization:** 78.1%
  - Spent: $187.40
  - Remaining: $52.60
  - Projected daily: $229.20
- **Analysis Accuracy:** 96.8%
  - True positives: 94.2%
  - False positives: 3.2%
  - User confirmations: 487

### 2. Budget Management Dashboard

**Purpose:** Track daily Gemini budget consumption and optimize spending

**Daily Budget Tracker:**
```
Daily Budget Tracking ($240 limit)
┌─────────────────────────────────────────────────────┐
│ [Area Chart - Hourly Spend]                        │
│ Y-axis: Cumulative spend ($USD)                    │
│ X-axis: Hour of day (0-24)                         │
│                                                      │
│$240│                                    ┌─────────  │
│$200│                              ┌─────┘           │
│$160│                        ┌─────┘                 │
│$120│                  ┌─────┘                       │
│ $80│            ┌─────┘                             │
│ $40│      ┌─────┘                                   │
│  $0└─────┘                                          │
│     0  2  4  6  8 10 12 14 16 18 20 22 24          │
│                                                      │
│ Current: $187.40 (78.1% at 6:00 PM)                │
│ Projected: $229.20 (95.5% utilization) ✓           │
│ Target: >90% daily utilization                      │
└─────────────────────────────────────────────────────┘
```

**Budget Breakdown Table:**

| Metric | Today | Yesterday | 7-day Avg | Trend |
|--------|-------|-----------|-----------|-------|
| Total Spend | $187.40 | $231.20 | $218.50 | ↓ 19% |
| Videos Analyzed | 487 | 602 | 556 | ↓ 19% |
| Avg Cost/Video | $0.385 | $0.384 | $0.393 | → flat |
| Budget Utilization | 78.1% | 96.3% | 91.0% | ↓ 19% |
| Projected Daily | $229.20 | $231.20 | $228.30 | → |

**Cost Optimization Savings:**

| Optimization | Videos Affected | Savings/Video | Total Saved | Status |
|--------------|-----------------|---------------|-------------|--------|
| Length-based FPS | 487 (100%) | $0.004 | $1.95/day | ✅ Active |
| Skip intro/outro | 487 (100%) | $0.002 | $0.97/day | ✅ Active |
| Risk-tier FPS | 89 (18%) | $0.003 | $0.27/day | ✅ Active |
| Budget pressure | 0 (0%) | $0.001 | $0.00/day | ⏸️ Not triggered |
| **Total** | - | - | **$3.19/day** | **↑ 1.6%** |

**Budget Pressure Indicator:**
```
Budget Remaining vs Queue Depth
┌─────────────────────────────────────────────────────┐
│ Remaining: $52.60 | Queue: 2,360 videos            │
│                                                      │
│ [Gauge Chart]                                        │
│                                                      │
│   Budget Health: 🟢 HEALTHY                         │
│   Can afford: ~137 more videos at current rate      │
│   Pressure mode: OFF (remaining >$50)               │
│                                                      │
│ Recommendations:                                     │
│ ✓ No action needed - on track for 95% utilization  │
│ ✓ Queue will require 4.8 days to clear             │
│ ⚠️ Consider increasing daily budget to $300         │
│    → Would clear queue in 3.6 days (25% faster)    │
└─────────────────────────────────────────────────────┘
```

### 3. Detection Performance Analytics

**Purpose:** Track infringement detection accuracy and patterns

**Detection Summary:**
```
Infringement Detection (Last 24h)
┌─────────────────────────────────────────────────────┐
│ Total Analyzed: 487 videos                          │
│                                                      │
│ INFRINGEMENT DETECTED: 89 (18.3%)                   │
│   ├─ Critical (95-100% conf): 12 (13.5%)           │
│   ├─ High (80-94% conf): 34 (38.2%)                │
│   └─ Medium (60-79% conf): 43 (48.3%)              │
│                                                      │
│ NO VIOLATION: 398 (81.7%)                           │
│   ├─ Clear (0-20% conf): 367 (92.2%)               │
│   └─ Borderline (21-59% conf): 31 (7.8%)           │
│                                                      │
│ FAILED ANALYSIS: 3 (0.6%)                           │
│   └─ Errors: API timeout (2), Invalid video (1)    │
│                                                      │
│ Confidence Distribution:                             │
│ [Histogram: most at 0-10% or 90-100%] ✓            │
└─────────────────────────────────────────────────────┘
```

**Confidence Score Distribution:**
```
Confidence Score Histogram (0-100%)
┌─────────────────────────────────────────────┐
│ [Histogram Chart]                           │
│ Y-axis: Video count                         │
│ X-axis: Confidence score                    │
│                                             │
│ 200│ ██                              ██     │
│ 150│ ██                              ██     │
│ 100│ ██                              ██     │
│  50│ ██  ░░  ░░  ░░  ░░  ░░  ░░  ░░ ██     │
│   0└───────────────────────────────────── │
│     0  10  20  30  40  50  60  70  80  90  │
│    Clear         Borderline      Infring.  │
│                                             │
│ Bimodal distribution ✓ (clear separation)  │
│ Mean infringement conf: 84.2%               │
│ Mean clear conf: 3.7%                       │
└─────────────────────────────────────────────┘
```

**Detection Accuracy Metrics:**

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| True Positive Rate (Recall) | 94.2% | >90% | ✅ |
| False Positive Rate | 3.2% | <5% | ✅ |
| Precision | 96.8% | >95% | ✅ |
| F1 Score | 0.95 | >0.90 | ✅ |
| Avg Confidence (infringements) | 84.2% | >80% | ✅ |
| Confidence Range | 0.0-99.8% | Wide | ✅ |

### 4. Character Detection Analysis

**Purpose:** Track which Justice League characters are being detected

**Character Detection Summary:**
```
Justice League Character Detection (Last 7 Days)
┌─────────────────────────────────────────────────────┐
│ [Horizontal Bar Chart]                              │
│                                                      │
│ Superman      ████████████████████ 234 (26%)        │
│ Batman        ███████████████ 189 (21%)             │
│ Wonder Woman  ███████████ 145 (16%)                 │
│ Flash         ████████ 98 (11%)                     │
│ Aquaman       ██████ 67 (8%)                        │
│ Multiple      ████████ 89 (10%)                     │
│ Cyborg        ███ 45 (5%)                           │
│ Green Lantern ██ 23 (3%)                            │
│                                                      │
│ Total characters detected: 890 across 487 videos    │
│ Avg characters/video: 1.83                          │
│ Single character: 345 (71%) | Multiple: 142 (29%)   │
└─────────────────────────────────────────────────────┘
```

**Character Screen Time Analysis:**

| Character | Videos | Avg Screen Time | Prominence High | Prominence Med | Prominence Low |
|-----------|--------|-----------------|-----------------|----------------|----------------|
| Superman | 234 | 127s | 89 (38%) | 123 (53%) | 22 (9%) |
| Batman | 189 | 98s | 67 (35%) | 98 (52%) | 24 (13%) |
| Wonder Woman | 145 | 76s | 45 (31%) | 78 (54%) | 22 (15%) |
| Flash | 98 | 54s | 23 (23%) | 56 (57%) | 19 (19%) |
| Aquaman | 67 | 43s | 12 (18%) | 34 (51%) | 21 (31%) |

**Top Character Combinations:**

| Combination | Count | Avg Infringement | Avg Confidence |
|-------------|-------|------------------|----------------|
| Superman solo | 192 | 87.5% | 86.2% |
| Batman solo | 147 | 82.3% | 83.4% |
| Justice League (3+) | 89 | 95.5% | 91.8% |
| Superman + Batman | 56 | 92.9% | 89.1% |
| Wonder Woman solo | 112 | 78.6% | 81.2% |

### 5. AI Tool Detection

**Purpose:** Identify which AI video generation tools are being used

**AI Tool Detection Frequency:**
```
AI Video Generation Tools Detected
┌─────────────────────────────────────────────────────┐
│ [Treemap Chart]                                     │
│                                                      │
│ ┌────────────────┬────────────┬─────────────┐      │
│ │   Sora AI      │  Runway    │   Kling     │      │
│ │   234 (48%)    │ 123 (25%)  │  89 (18%)   │      │
│ ├────────────────┴────────────┴─────────────┤      │
│ │ Pika Labs    │ Luma Dream  │ Other/Multi  │      │
│ │  34 (7%)     │  12 (2%)    │   8 (2%)     │      │
│ └──────────────┴─────────────┴──────────────┘      │
│                                                      │
│ Total videos with AI tool detection: 487 (100%)    │
│ Multiple tools detected: 34 (7%)                    │
└─────────────────────────────────────────────────────┘
```

**AI Tool + Character Combinations:**

| AI Tool | Superman | Batman | Wonder Woman | Flash | Other | Total |
|---------|----------|--------|--------------|-------|-------|-------|
| Sora AI | 98 | 76 | 45 | 23 | 12 | 234 |
| Runway | 56 | 34 | 23 | 12 | 8 | 123 |
| Kling | 45 | 28 | 12 | 8 | 6 | 89 |
| Pika | 23 | 12 | 6 | 4 | 3 | 34 |
| Luma | 8 | 4 | 2 | 1 | 1 | 12 |

**Trending Tools (7-day growth):**
```
AI Tool Trend Analysis
┌─────────────────────────────────────────────────────┐
│ Tool      │ 7 Days Ago │ Today │ Growth │ Trend    │
│───────────┼────────────┼───────┼────────┼──────────│
│ Sora AI   │    189     │  234  │ +23.8% │ 🔥🔥🔥  │
│ Runway    │    112     │  123  │ +9.8%  │ 📈📈    │
│ Kling     │     78     │   89  │ +14.1% │ 📈📈    │
│ Pika      │     38     │   34  │ -10.5% │ 📉      │
│ Luma      │     14     │   12  │ -14.3% │ 📉      │
└─────────────────────────────────────────────────────┘

Insight: Sora AI is dominant and growing fastest
Action: Optimize keywords for Sora content discovery
```

### 6. Video Type Classification

**Purpose:** Categorize infringement types

**Video Type Breakdown:**
```
Video Type Classification (89 infringements)
┌─────────────────────────────────────────────────────┐
│ [Donut Chart]                                       │
│                                                      │
│ Full AI Movie: 34 (38%)                             │
│   Avg duration: 8.4 min | Avg conf: 92.1%          │
│                                                      │
│ AI Clips: 28 (31%)                                  │
│   Avg duration: 2.1 min | Avg conf: 86.3%          │
│                                                      │
│ Trailer: 18 (20%)                                   │
│   Avg duration: 1.2 min | Avg conf: 81.7%          │
│                                                      │
│ Review/Commentary: 9 (10%)                          │
│   Avg duration: 5.6 min | Avg conf: 72.4%          │
│   Note: Fair use consideration needed               │
│                                                      │
│ Other: 0 (0%)                                       │
└─────────────────────────────────────────────────────┘
```

**Recommended Actions Distribution:**

| Action | Count | % | Avg Confidence | Next Steps |
|--------|-------|---|----------------|------------|
| Flag (immediate takedown) | 34 | 38% | 94.2% | Legal review |
| Monitor (watch for growth) | 43 | 48% | 78.3% | Rescan in 3d |
| Ignore (fair use/low risk) | 12 | 14% | 61.8% | Archive |

### 7. Analysis Performance Metrics

**Purpose:** Track Gemini API performance and optimize throughput

**Processing Time Analysis:**
```
Video Analysis Processing Time
┌─────────────────────────────────────────────────────┐
│ [Box Plot by Video Length]                         │
│                                                      │
│ <2 min    │───●───│                                 │
│           0s  5s  10s  (avg: 4.2s)                 │
│                                                      │
│ 2-5 min   │──────●──────│                           │
│           0s     8s     16s  (avg: 7.8s)           │
│                                                      │
│ 5-10 min  │─────────●─────────│                     │
│           0s        12s       24s  (avg: 11.3s)    │
│                                                      │
│ 10+ min   │───────────●───────────│                 │
│           0s           18s          36s (avg: 17.2s)│
│                                                      │
│ Overall avg: 8.2s per video                         │
│ Target: <10s (✓ met)                                │
└─────────────────────────────────────────────────────┘
```

**Token Usage Efficiency:**

| Video Length | Avg Input Tokens | Avg Output Tokens | Total Tokens | Cost |
|--------------|------------------|-------------------|--------------|------|
| <2 min | 12,400 | 890 | 13,290 | $0.006 |
| 2-5 min | 18,850 | 1,120 | 19,970 | $0.009 |
| 5-10 min | 22,100 | 1,340 | 23,440 | $0.011 |
| 10-20 min | 28,700 | 1,560 | 30,260 | $0.014 |
| 20+ min | 35,200 | 1,780 | 36,980 | $0.017 |

**Throughput Timeline:**
```
Hourly Analysis Throughput (Last 24h)
┌─────────────────────────────────────────────────────┐
│ [Area Chart]                                        │
│ Y-axis: Videos analyzed per hour                   │
│ X-axis: Hour of day                                │
│                                                      │
│ 40│    ██                    ██                     │
│ 30│    ██  ██          ██    ██    ██              │
│ 20│    ██  ██    ██    ██    ██    ██    ██       │
│ 10│    ██  ██    ██    ██    ██    ██    ██  ██   │
│  0└────────────────────────────────────────────────│
│    12a  3a  6a  9a  12p  3p  6p  9p  12a          │
│                                                      │
│ Peak: 38 videos/hour (2:00 PM)                     │
│ Average: 20.3 videos/hour                           │
│ Lowest: 8 videos/hour (4:00 AM - low queue)        │
└─────────────────────────────────────────────────────┘
```

**FPS Optimization Impact:**

| FPS Strategy | Videos | Avg FPS | Avg Cost | Total Saved | Status |
|--------------|--------|---------|----------|-------------|--------|
| Standard (no optimization) | 0 | 1.0 | $0.011 | $0.00 | ❌ |
| Length-based (auto) | 487 | 0.52 | $0.009 | $0.97 | ✅ |
| Risk-tier adjusted | 89 | 0.78 | $0.010 | $0.09 | ✅ |
| Budget pressure | 0 | 0.39 | $0.007 | $0.00 | ⏸️ |
| **Current strategy** | **487** | **0.54** | **$0.009** | **$1.06/day** | **✅** |

### 8. Error Analysis & Troubleshooting

**Purpose:** Track and resolve analysis failures

**Error Breakdown:**
```
Analysis Errors (Last 24h)
┌─────────────────────────────────────────────────────┐
│ Total: 3 errors (0.6% failure rate) ✓ Target: <1%  │
│                                                      │
│ [Pie Chart]                                          │
│                                                      │
│ API Timeout: 2 (67%)                                │
│   Avg video length: 45 min (very long)             │
│   Action: Added 60s timeout, retry logic            │
│                                                      │
│ Invalid Video: 1 (33%)                              │
│   Reason: Private video, URL no longer valid        │
│   Action: Pre-validate URLs before analysis         │
│                                                      │
│ Other: 0 (0%)                                       │
└─────────────────────────────────────────────────────┘
```

**Recent Errors (Last 10):**

| Time | Video ID | Error Type | Duration | Cost | Retry | Status |
|------|----------|------------|----------|------|-------|--------|
| 2h ago | abc123 | API Timeout | 45 min | $0.00 | ✓ | ✅ Resolved |
| 3h ago | def456 | Invalid Video | N/A | $0.00 | ✗ | 🔴 Failed |
| 5h ago | ghi789 | API Timeout | 52 min | $0.00 | ✓ | ✅ Resolved |

**Error Rate Trend:**
```
Error Rate Over Time (7 days)
┌─────────────────────────────────────────────────────┐
│ [Line Chart]                                        │
│ Y-axis: Error rate %                                │
│ X-axis: Day                                         │
│                                                      │
│ 2.0%│ ●                                              │
│ 1.5%│   ●                                            │
│ 1.0%│     ● ●                                        │
│ 0.5%│         ● ● ●                                  │
│ 0.0%└────────────────────────────────               │
│      D1  D2  D3  D4  D5  D6  D7                    │
│                                                      │
│ Improving: ↓ 1.4% reduction over 7 days ✓          │
│ Root cause: Added URL validation, increased timeout │
└─────────────────────────────────────────────────────┘
```

---

## Technical Implementation

### Phase 1: Backend Enhancements

**New API Endpoints:**

1. **GET /api/vision/stats**
   - Overview metrics: queue, throughput, budget, accuracy

2. **GET /api/vision/budget**
   - Budget tracking: daily spend, projections, optimization

3. **GET /api/vision/detection**
   - Detection metrics: infringements, confidence, accuracy

4. **GET /api/vision/characters**
   - Character detection: frequency, screen time, combinations

5. **GET /api/vision/ai-tools**
   - AI tool detection: frequency, trends, combinations

6. **GET /api/vision/video-types**
   - Video classification: types, actions, durations

7. **GET /api/vision/performance**
   - Processing time, token usage, throughput, FPS optimization

8. **GET /api/vision/errors**
   - Error analysis: types, frequency, trends

9. **POST /api/vision/budget/update**
   - Update daily budget limit (admin only)

**Database Queries:**
- Aggregate `vision_analysis` results by confidence
- Join with `videos` for character extraction
- Calculate budget from `gemini_budget` collection
- Track errors from `vision_metrics`

### Phase 2: Frontend Components

**New Components:**

1. **VisionOverview.tsx**
   - Status card, key metrics
   - Budget gauge, queue depth

2. **BudgetTracker.tsx**
   - Daily spend chart
   - Breakdown table, optimization savings
   - Budget pressure indicator

3. **DetectionAnalytics.tsx**
   - Detection summary
   - Confidence histogram
   - Accuracy metrics table

4. **CharacterDetection.tsx**
   - Character frequency chart
   - Screen time analysis
   - Top combinations table

5. **AIToolDetection.tsx**
   - Tool frequency treemap
   - Tool + character matrix
   - Trend analysis

6. **VideoTypeClassification.tsx**
   - Type breakdown donut
   - Recommended actions table

7. **PerformanceMetrics.tsx**
   - Processing time box plots
   - Token efficiency table
   - Throughput timeline

8. **ErrorAnalysis.tsx**
   - Error breakdown pie
   - Recent errors table
   - Error rate trend line

**Libraries:**
- `recharts` - Charts
- `react-gauge-chart` - Gauges
- `react-table` - Tables
- `date-fns` - Dates
- `swr` - Data fetching

---

## Success Metrics

**Budget Optimization:**
- Maintain 90-95% daily budget utilization
- Keep avg cost per video <$0.40
- Save >$3/day through optimizations

**Detection Accuracy:**
- True positive rate: >94%
- False positive rate: <5%
- F1 score: >0.95

**Throughput:**
- Average: >20 videos/hour
- Peak: >35 videos/hour
- Queue clear time: <5 days

**Reliability:**
- Error rate: <1%
- Avg processing time: <10s
- API timeout rate: <0.5%

---

## Acceptance Criteria

- [ ] Dashboard loads with all metrics
- [ ] Budget tracker updates in real-time
- [ ] Detection charts show accurate data
- [ ] Character detection displays properly
- [ ] AI tool trends are visible
- [ ] Performance metrics render quickly
- [ ] Error analysis shows failures
- [ ] All charts render in <500ms
- [ ] Admin can adjust budget
- [ ] Responsive design works

---

## Future Enhancements

- **Multi-language Support:** Detect non-English content
- **Sentiment Analysis:** Understand video tone/context
- **Scene Detection:** Identify specific infringement scenes
- **Explainable Results:** Show which frames triggered detection
- **A/B Testing:** Test different prompts for accuracy
- **Cost Prediction:** Forecast daily spend based on queue
- **Auto-scaling:** Dynamically adjust budget based on queue
- **Integration:** Export results to DMCA takedown tools
