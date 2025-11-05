# Discovery Page

**Route**: `/discovery`
**File**: `services/frontend-service/app/web/src/pages/DiscoveryPage.tsx`

## Purpose

The Discovery Page provides **manual control over YouTube discovery runs**. It displays quota usage, allows triggering discovery, and shows real-time progress via Server-Sent Events (SSE).

## What It Shows

### 1. Key Metrics Cards
Shows 24-hour statistics:
- **Videos Discovered**: Total videos found
- **Channels Tracked**: Active channels monitored
- **Discovery Efficiency**: Videos per quota unit
- **Quota Utilization**: Percentage of daily quota used

### 2. Control Panel
**Trigger Discovery Runs**:
- **Max Quota Limit** input (100-10,000 units)
- **Trigger Discovery Run** button
- Shows warning if quota < 400 (too low for keyword searches)

### 3. Real-Time Progress
When discovery is running:
- Progress message (e.g., "Scanning channels...")
- Phase indicator (1-4 of 4)
- Animated spinner
- Color-coded status:
  - 🔵 Blue = In progress
  - ✅ Green = Complete
  - ❌ Red = Error

### 4. Last Discovery Run
Shows details of most recent run:
- Timestamp & duration
- Videos/channels/quota used
- **Tier breakdown**:
  - Channels tracked
  - Trending scans
  - Keyword searches
  - View updates

### 5. YouTube API Quota
Real-time quota tracker:
- Used / Total quota
- Progress bar (green/yellow/red based on usage)
- Remaining units
- Status level (Normal/High/Critical)

### 6. Discovery Results Panel
After successful run, shows BIG results panel:
- Videos discovered
- IP matches (character detections)
- Quota used
- Channels tracked
- Quick links to Videos and Channels pages

## Data Sources

| Endpoint | Data | When |
|----------|------|------|
| `/api/status/summary` | System summary stats | Every 30s |
| `/api/discovery/quota` | Quota status | On page load |
| `/api/discovery/trigger/stream` | Discovery progress | When triggered (SSE) |

**Location**: `services/frontend-service/app/web/src/api/discovery.ts`, `status.ts`

## How Discovery Works

### Discovery Process (4 Phases)

```
Phase 1: Channel Tracking (70% quota)
  ↓ Scan high-risk channels for new videos
Phase 2: Trending Scan (20% quota)
  ↓ Check YouTube trending/popular videos
Phase 3: Keyword Searches (10% quota)
  ↓ Search for AI-generated character content
Phase 4: View Updates
  ↓ Update view counts for existing videos
```

### Triggering a Discovery Run

1. User sets max quota (e.g., 1000 units)
2. Clicks "Trigger Discovery Run"
3. Frontend opens SSE connection to `/api/discovery/trigger/stream?max_quota=1000`
4. Backend streams progress messages in real-time
5. Frontend updates UI as messages arrive
6. Shows results panel when complete

### Server-Sent Events (SSE)

Discovery uses **SSE** for real-time progress updates:

```typescript
const eventSource = new EventSource('/api/discovery/trigger/stream?max_quota=1000')

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)

  // Update UI based on status
  if (data.status === 'tier1') {
    setProgress('Scanning channels...')
    setCurrentTier(1)
  } else if (data.status === 'complete') {
    setProgress('✅ Discovery Complete!')
    setLastRun(data)
  }
}
```

**Status messages**:
- `starting` - Discovery initiated
- `tier1` - Channel tracking phase
- `tier2` - Trending scan phase
- `tier3` - Keyword search phase
- `tier4` - View updates phase
- `complete` - Finished successfully
- `error` - Failed with error message

## Key Features

### Quota Safety
- Shows warning if quota < 400 units
- Blocks trigger button while running
- Displays critical/high/normal status based on usage

### Real-Time Feedback
- SSE connection for live progress
- Phase-by-phase updates
- Estimated time remaining (via backend)

### Error Handling
- Displays error messages prominently
- "Connection error" if backend unreachable
- Allows retry after error

### Results Display
- Large, colorful results panel on completion
- Quick navigation to Videos/Channels pages
- Can dismiss and view later in summary

## Where to Look

**Change quota limits**:
```typescript
// DiscoveryPage.tsx line 241-250
<input
  type="number"
  min={100}      // Change minimum
  max={10000}    // Change maximum
  step={100}     // Change increment
/>
```

**Modify SSE handling**:
```typescript
// DiscoveryPage.tsx line 42-147
// eventSource.onmessage handler
```

**Customize progress messages**:
```typescript
// DiscoveryPage.tsx line 62-114
// Update text based on data.status
```

**Change tier breakdown display**:
```typescript
// DiscoveryPage.tsx line 345-359
// Last run tier breakdown section
```

## Common Issues

**SSE connection fails**:
- Check api-service is running
- Verify `/api/discovery/trigger/stream` endpoint exists
- Check for CORS issues in browser console
- Ensure SSE response has correct headers (`Content-Type: text/event-stream`)

**Discovery runs but no progress**:
- Check backend is emitting SSE messages
- Verify eventSource.onmessage is firing (add console.log)
- Check SSE message format matches expected structure

**Results panel doesn't show**:
- Ensure `data.status === 'complete'` message arrives
- Check `setShowResults(true)` is called
- Verify `showResults && lastRun` condition (line 413)

**Quota not updating**:
- Check `/api/discovery/quota` endpoint works
- Verify loadQuota() is called after discovery completes (line 92)
- Check Firestore has quota tracking documents

## Related Files

- `services/frontend-service/app/web/src/api/discovery.ts` - Discovery API client
- `services/discovery-service/app/routers/discover.py` - Backend SSE endpoint
- `services/discovery-service/app/core/discovery_engine.py` - Discovery logic
