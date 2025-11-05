# Vision Analyzer Page

**Route**: `/vision`
**File**: `services/frontend-service/app/web/src/pages/VisionAnalyzerPage.tsx`

## Purpose

The Vision Analyzer Page provides **control and monitoring for Gemini 2.5 Flash video analysis**. It displays budget utilization, allows batch scanning, shows adaptive FPS optimization, and provides an editable Gemini configuration interface.

## What It Shows

### 1. Key Metrics Cards
- **Videos Analyzed**: Total scanned with Gemini
- **Infringements Detected**: Confirmed violations + detection rate
- **Daily Budget**: Budget spent (€) out of total (€240)
- **Avg Cost/Video**: Average cost per video analysis (length-optimized)

### 2. Batch Scan Controls (Header)
Manual batch scanning:
- **Batch Size** input (1-100 videos)
- **Scan Batch** button
- Scans highest-priority videos immediately

### 3. Budget Utilization
Real-time budget tracking:
- Progress bar (€ used / €240 daily budget)
- Color-coded: Green (Normal), Orange (High), Red (Critical)
- **3 Cards**:
  - Remaining budget (€)
  - Estimated capacity (~2,880 videos/day)
  - Budget status (Normal/High/Critical)
- **Data freshness**: Shows cache age and source project

### 4. Adaptive FPS Strategy
Length-based frame sampling optimization:

| Video Length | FPS | Cost | Savings |
|--------------|-----|------|---------|
| 0-2 min | 1.0 | $0.001 | 0% (baseline) |
| 2-5 min | 0.5 | $0.004 | 50% |
| 5-10 min | 0.33 | $0.009 | 67% |
| 10-20 min | 0.25 | $0.012 | 75% |
| 20-30 min | 0.2 | $0.017 | 80% |
| 30-60 min | 0.1 | $0.017 | 90% |

**Smart Optimization**: FPS automatically adjusted based on video length to maximize coverage within budget.

### 5. Gemini Model Configuration (EDITABLE!)
Shows/edits Gemini 2.5 Flash settings:

**View Mode**:
- Model version (gemini-2.5-flash / gemini-2.5-pro)
- Region (europe-west4)
- Input method (Direct YouTube URL)
- Resolution (Low = 66 tokens/frame)
- Rate limit type (Dynamic Shared Quota)
- Max output tokens (65,536)
- Input cost ($0.30 / 1M tokens)
- Output cost ($2.50 / 1M tokens)

**Edit Mode** (click ✏️ Edit button):
- Change model version (auto-updates pricing!)
- Change region
- Adjust max output tokens
- Adjust tokens per frame
- **Save to Firestore** - persists across restarts!

### 6. Analysis Performance
Real-time performance metrics:
- **Success Rate**: % of successful analyses (98.9%)
- **Avg Processing Time**: Time per video (1.2s)
- **Queue Depth**: Videos pending analysis
- **Processing Rate**: Videos per hour (487)

### 7. Character Detection Stats
Justice League character breakdown:
- Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern
- Shows count and percentage of total infringements

## Data Sources

| Endpoint | Data | Refresh Rate |
|----------|------|--------------|
| `/api/status/summary` | System summary stats | 30s |
| `/api/vision/budget` | Budget tracking (real Firestore data!) | 30s |
| `/api/vision/config` | Gemini configuration | 5 min |
| `/api/vision/batch-scan` | Start batch scan | On demand |

**Location**: `services/frontend-service/app/web/src/api/vision.ts`, `status.ts`

## Key Features

### Real Budget Data
- Fetches **actual budget usage** from Firestore
- Shows cost breakdown by video
- Tracks daily budget exhaustion
- 5-minute cache on backend for performance

### Editable Configuration
**How to edit**:
1. Click "✏️ Edit" button
2. Change model version (auto-sets pricing!)
3. Modify region, tokens, etc.
4. Click "💾 Save"
5. Configuration **persists in Firestore**
6. Takes effect immediately for new scans

**Supported Models**:
- `gemini-2.5-flash` - Fast & cheap ($0.30 input, $2.50 output)
- `gemini-2.5-pro` - Powerful & accurate ($1.25 input, $10.00 output)

### Batch Scanning
Manually trigger scans for high-priority videos:
1. Enter batch size (1-100)
2. Click "▶ Scan Batch"
3. Backend queues videos sorted by scan_priority
4. Shows confirmation with videos queued
5. Dashboard refreshes to show progress

### Adaptive FPS Visualization
Shows how cost savings work:
- Short videos (0-2 min): 1 FPS = standard analysis
- Long videos (30-60 min): 0.1 FPS = 90% token reduction
- Maximizes budget coverage while maintaining accuracy

## How Vision Analysis Works

### Gemini 2.5 Flash Process

1. **Video Selection**:
   - Get highest priority videos from Firestore
   - Filter: `status == "discovered"` AND `scan_priority > threshold`

2. **Adaptive FPS Calculation**:
   ```python
   if duration < 120:  # 2 min
       fps = 1.0
   elif duration < 300:  # 5 min
       fps = 0.5
   elif duration < 600:  # 10 min
       fps = 0.33
   # ... etc
   ```

3. **Gemini API Call**:
   ```python
   result = client.models.generate_content(
       model='gemini-2.5-flash',
       contents=[prompt, video_url],
       config={
           'fps': calculated_fps,
           'media_resolution': 'low'
       }
   )
   ```

4. **Result Processing**:
   - Parse JSON response
   - Extract infringement status, characters, confidence
   - Calculate actual cost (input tokens × $0.30 + output tokens × $2.50)
   - Update video document in Firestore
   - Update budget tracking

5. **Budget Tracking**:
   - Daily budget: €240 (~$260)
   - Tracks cumulative spend
   - Stops scanning when budget exhausted

### Budget Exhaustion Model

The vision-analyzer scans **until budget is 100% utilized**:
- Not limited by rate (Vertex AI Dynamic Shared Quota)
- Only limited by budget
- Capacity: 20,000-32,000 videos/day depending on video lengths

## Where to Look

**Change batch scan size limits**:
```typescript
// VisionAnalyzerPage.tsx line 92-100
<input
  type="number"
  min="1"      // Change minimum
  max="100"    // Change maximum
/>
```

**Modify FPS strategy table**:
```typescript
// VisionAnalyzerPage.tsx line 240-247
// Update length ranges, FPS values, costs
```

**Add new Gemini models**:
```typescript
// VisionAnalyzerPage.tsx line 312-315
<option value="gemini-2.5-flash">gemini-2.5-flash</option>
<option value="gemini-3.0-flash">gemini-3.0-flash (New!)</option>
```

**Change budget warning thresholds**:
```typescript
// VisionAnalyzerPage.tsx line 193-197
(budgetUsed / dailyBudget) > 0.9 ? 'bg-red-600'   // 90%+ = critical
  : (budgetUsed / dailyBudget) > 0.7 ? 'bg-orange-600'  // 70%+ = high
  : 'bg-blue-600'  // <70% = normal
```

**Customize configuration editor**:
```typescript
// VisionAnalyzerPage.tsx line 270-427
// Edit mode UI with input fields
```

## Common Issues

**Budget data not loading**:
- Check `/api/vision/budget` endpoint works
- Verify vision-analyzer is writing budget docs to Firestore
- Check Firestore collection: `budget_tracking_dev`
- Ensure proper date formatting (YYYY-MM-DD)

**Configuration saves but doesn't persist**:
- Check Firestore write permissions
- Verify configuration document ID: `gemini_config`
- Check for Firestore errors in backend logs
- Refresh page to see if config was actually saved

**Batch scan fails**:
- Check vision-analyzer-service is running
- Verify videos with `status="discovered"` exist
- Check PubSub subscription is processing messages
- Look for errors in vision-analyzer logs

**Wrong costs displayed**:
- Ensure Gemini pricing in config matches Vertex AI 2025 pricing
- gemini-2.5-flash: $0.30 input, $2.50 output (NOT $0.075 / $0.30 from 2024!)
- Update config via Edit mode if outdated

## Related Files

- `services/frontend-service/app/web/src/api/vision.ts` - Vision API client
- `services/vision-analyzer-service/app/worker.py` - Gemini scanning logic
- `services/vision-analyzer-service/app/core/video_config_calculator.py` - Adaptive FPS
- `services/vision-analyzer-service/app/core/budget_tracker.py` - Budget tracking
- `services/api-service/app/routers/vision_budget.py` - Budget API endpoint
