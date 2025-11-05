# Risk Analyzer Page

**Route**: `/risk`
**File**: `services/frontend-service/app/web/src/pages/RiskAnalyzerPage.tsx`

## Purpose

The Risk Analyzer Page provides a **dashboard for the adaptive risk scoring system**. It displays risk tier distribution, 6-factor model breakdown, view velocity tracking, and adaptive learning performance metrics.

## What It Shows

### 1. Key Metrics Cards
- **Videos Analyzed**: Total videos in system
- **Average Risk Score**: Mean risk score (0-100)
- **Infringements Found**: Confirmed violations
- **Videos Analyzed**: Scanned by Gemini

### 2. Risk Tier Distribution
Interactive breakdown of risk tiers:

| Tier | Score Range | Count | Percentage |
|------|-------------|-------|------------|
| CRITICAL | 80-100 | Count | % |
| HIGH | 60-79 | Count | % |
| MEDIUM | 40-59 | Count | % |
| LOW | 20-39 | Count | % |
| VERY_LOW | 0-19 | Count | % |

**Visualization**:
- Color-coded progress bars (red → orange → yellow → blue → gray)
- Total videos, mean score, high risk percentage

### 3. 6-Factor Scoring Model
Breakdown of risk scoring components:

| Factor | Weight | Current Score | Impact % | Trend |
|--------|--------|---------------|----------|-------|
| **View Count** | 0-25 | 14.2 | 26% | → |
| **View Velocity** | 0-25 | 16.8 | 31% | ↑ |
| **Channel Reputation** | 0-20 | 11.3 | 21% | ↑ |
| **Video Characteristics** | 0-15 | 8.9 | 16% | → |
| **Content Signals** | 0-10 | 2.1 | 4% | → |
| **Recency** | 0-5 | 1.0 | 2% | → |

**Top Driver Indicator**:
Shows which factor has the highest impact (e.g., "View Velocity (31% impact)")

### 4. View Velocity Tracking
Real-time tracking of trending videos:

| Category | Threshold | Count | Avg Score | Status |
|----------|-----------|-------|-----------|--------|
| **Extremely Viral** | >10k views/hour | 12 | 92 | 🔴 URGENT |
| **Very Viral** | 1k-10k/h | 45 | 78 | 🟡 HIGH |
| **Viral** | 100-1k/h | 99 | 64 | 🟢 SCHEDULED |
| **Normal** | <100/h | 1089 | 48 | 🟢 REGULAR |

**Metrics**:
- Total tracking: 1,245 videos
- Viral detection rate: 95% caught <6h

### 5. Adaptive Learning Performance
Machine learning model metrics:

| Metric | Value | Trend |
|--------|-------|-------|
| **True Positive Rate** | 87.3% | ↑ 2.1% |
| **False Positive Rate** | 12.7% | ↓ 1.8% |
| **Rescore Adjustments** | 147 | Last 24h |
| **Model Accuracy** | ±7 pts | ↑ 61% improvement |

Shows model is learning from Gemini results and improving over time.

## Data Sources

| Endpoint | Data | Refresh Rate |
|----------|------|--------------|
| `/api/status/summary` | System summary stats | 30s |

**Note**: Currently uses **mock data** for most visualizations. Risk scoring data will come from:
- `/api/risk/tiers` (future)
- `/api/risk/factors` (future)
- `/api/risk/velocity` (future)
- `/api/risk/learning` (future)

**Location**: `services/frontend-service/app/web/src/api/status.ts`

## How Risk Scoring Works

### 6-Factor Adaptive Model

The risk-analyzer-service scores videos using 6 factors:

1. **View Count (0-25 pts)**: Absolute view count
2. **View Velocity (0-25 pts)**: Views per hour (trending detection)
3. **Channel Reputation (0-20 pts)**: Channel's infringement history
4. **Video Characteristics (0-15 pts)**: Duration, upload date, title/description keywords
5. **Content Signals (0-10 pts)**: AI tool mentions, character keywords
6. **Recency (0-5 pts)**: Time since upload (newer = higher priority)

**Total**: 0-100 score → Determines scan priority

### Risk Tiers

Videos are assigned tiers based on total score:
- **CRITICAL** (80-100): Scan within 6 hours
- **HIGH** (60-79): Scan within 24 hours
- **MEDIUM** (40-59): Scan within 7 days
- **LOW** (20-39): Scan within 30 days
- **VERY_LOW** (0-19): Low priority

### Adaptive Learning

After Gemini analyzes a video:
1. Risk-analyzer receives result (infringement: yes/no)
2. Compares predicted risk to actual result
3. Adjusts channel reputation score
4. Recalculates risk for all videos from that channel
5. Improves accuracy over time

## Key Features

### Visual Risk Distribution
Color-coded progress bars make it easy to see risk distribution at a glance.

### Factor Impact Analysis
Shows which scoring factors are most influential (e.g., view velocity has 31% impact).

### Trending Detection
Identifies viral videos quickly (<6 hours) for immediate scanning.

### Performance Tracking
Monitors model accuracy and shows improvement trends.

### Quick Navigation
- "View High Risk Videos" → VideoListPage filtered by high priority
- "View Channel Reputation" → ChannelListPage sorted by risk

## Where to Look

**Add real API data**:
```typescript
// RiskAnalyzerPage.tsx line 6-10
// Replace useSWR with actual API endpoints
const { data: riskTiers } = useSWR('risk-tiers', () => riskAPI.getTiers())
```

**Customize risk tiers**:
```typescript
// RiskAnalyzerPage.tsx line 19-26
const riskTiers = [
  { tier: 'CRITICAL', range: '80-100', ... },
  // Modify ranges, colors, etc.
]
```

**Change factor weights**:
```typescript
// RiskAnalyzerPage.tsx line 158-165
// Update weight ranges (e.g., change View Count from 0-25 to 0-30)
```

**Modify velocity thresholds**:
```typescript
// RiskAnalyzerPage.tsx line 199-204
// Change thresholds (e.g., Extremely Viral from >10k/h to >5k/h)
```

## Common Issues

**"Mock data" displayed**:
- This page currently uses calculated/mock data
- Backend risk-analyzer endpoints need to be exposed via api-service
- Implement API endpoints for tiers, factors, velocity, learning metrics

**Percentages don't add up to 100%**:
- Risk tier distribution uses floor() for counts
- Rounding errors may cause slight discrepancies
- Consider using Math.round() or adjusting last tier

**Real-time data not updating**:
- Check if risk-analyzer is writing metrics to Firestore
- Verify analytics aggregation is running
- Add API endpoints to expose risk-analyzer data

## Future Enhancements

### Real API Integration
Replace mock data with actual risk-analyzer metrics:
- Risk tier distribution from Firestore
- Factor breakdown from recent scorings
- Velocity tracking from view snapshots
- Learning metrics from model evaluations

### Interactive Filtering
- Click on risk tier to filter VideoListPage
- Click on factor to see videos most influenced by it
- Click on velocity category to see trending videos

### Historical Trends
- Show risk distribution over time (line chart)
- Compare factor weights week-over-week
- Track model accuracy improvements

## Related Files

- `services/risk-analyzer-service/app/core/risk_analyzer.py` - Risk scoring logic
- `services/risk-analyzer-service/app/core/channel_risk_calculator.py` - Channel reputation
- `services/risk-analyzer-service/app/core/video_risk_calculator.py` - Video scoring
- `services/risk-analyzer-service/app/core/scan_priority_calculator.py` - Priority calculation
