# Video List Page

**Route**: `/videos`
**File**: `services/frontend-service/app/web/src/pages/VideoListPage.tsx`

## Purpose

The Video List Page is the **main video browser** where users can view, filter, sort, and scan videos. It provides a grid view of discovered videos with thumbnails, metadata, risk scores, and action buttons.

## What It Shows

### 1. Page Header
- Title: "Video Library"
- Total count: "{X} videos discovered"
- **Sort dropdown**: 7 sorting options

### 2. Filters Panel
Collapsible filter section:
- **Channel Filter**: Dropdown of all channels (loads up to 500)
- **Status Filter**: discovered / processing / analyzed / failed
- **Clear all** button (shows count of active filters)

### 3. Video Grid
4-column responsive grid (desktop) / stacks on mobile:

**Each Video Card Shows**:
- **Thumbnail**: Clickable → YouTube video page
  - Play button overlay on hover
- **Title**: Clickable, truncated to 2 lines
- **Channel name**: Clickable → Channel YouTube page
- **View count**: Formatted with commas
- **Duration**: MM:SS format
- **IP Matches**: Character tags (e.g., "Batman", "Superman")
  - Shows first 2, "+X more" if >2
- **Scan Priority**: 0-100 score with color-coded badge
  - Tier label (CRITICAL/HIGH/MEDIUM/LOW/VERY_LOW)
  - Channel risk + Video risk breakdown
- **Infringement Summary** (analyzed videos only):
  - 🟢 NO INFRINGEMENT or ⚠️ INFRINGEMENT DETECTED
  - Confidence score (%)
  - Characters detected list
- **Action Buttons**:
  - "Scan Now" (discovered videos)
  - "Retry Scan" (failed videos)
  - "View Progress" (processing videos)
  - "View Analysis Details" (analyzed videos)
  - "Watch on YouTube" (all videos)

### 4. Pagination
- Previous / Next buttons
- "Page X of Y" display
- 20 videos per page

### 5. Active Scans Overlay
Bottom-right corner widget:
- Shows count of videos currently being scanned
- Click to view progress
- Auto-updates when scans complete

### 6. Modals
- **ScanProgressModal**: Real-time scan progress via SSE
- **AnalysisDetailModal**: Full Gemini analysis results

## Data Sources

| Endpoint | Data | When |
|----------|------|------|
| `/api/videos/list` | Paginated video list | On load, filter, sort, page change |
| `/api/channels/list` | All channels (for dropdown) | On page load |
| `/api/videos/{id}/scan` | Trigger single video scan | On "Scan Now" click |
| `/api/videos/{id}/scan/status` | Scan progress (SSE) | During scan |

**Location**: `services/frontend-service/app/web/src/api/videos.ts`, `channels.ts`

## Sorting Options

| Sort Option | Field | Order | Use Case |
|-------------|-------|-------|----------|
| 🔥 Highest Risk (Priority) | `scan_priority` | DESC | Find highest-priority videos to scan |
| ⚠️ Channel Risk | `channel_risk` | DESC | Focus on high-risk channels |
| 📊 Video Risk | `video_risk` | DESC | Videos with high intrinsic risk |
| 👁️ Highest Views | `view_count` | DESC | Most popular videos |
| ⏱️ Longest Duration | `duration_seconds` | DESC | Longest videos |
| 🆕 Most Recently Found | `discovered_at` | DESC | Newest discoveries |
| 📅 Most Recently Uploaded | `published_at` | DESC | Recently uploaded to YouTube |

## Filtering

### By Channel
- Dropdown populated with all tracked channels (up to 500)
- Shows channel name + video count
- Selecting a channel filters to only videos from that channel
- URL updates: `/videos?channel=UC_channel_id`

### By Status
- **discovered**: Found but not yet scanned
- **processing**: Currently being analyzed by Gemini
- **analyzed**: Scan complete (success or no infringement)
- **failed**: Scan failed (error, timeout, etc.)

## Key Features

### Single Video Scanning
**How it works**:
1. User clicks "Scan Now" on video card
2. Frontend calls `/api/videos/{id}/scan`
3. Opens ScanProgressModal
4. Establishes SSE connection to `/api/videos/{id}/scan/status`
5. Shows real-time progress (queued → analyzing → complete)
6. Displays result or error
7. Refreshes video list on completion

### Analysis Detail Modal
**Shows full Gemini response**:
- Infringement detected (yes/no)
- Confidence score
- Characters detected with screen time
- Video type classification
- AI tools detected
- Reasoning
- Recommended action

### Active Scans Tracking
The `ActiveScansOverlay` component:
- Polls for videos with `status="processing"`
- Shows count in bottom-right corner
- Allows viewing progress of any active scan
- Auto-refreshes video list when scans complete

### Smart Card Borders
Video cards have color-coded borders:
- 🔴 **Red border**: Analyzed + Infringement detected
- 🟢 **Green border**: Analyzed + No infringement
- Gray border: Not yet analyzed

### Responsive Design
- Desktop: 4 columns
- Tablet: 2 columns
- Mobile: 1 column (stacked)

## Where to Look

**Change videos per page**:
```typescript
// VideoListPage.tsx line 45
const limit = 20  // Change to 50, 100, etc.
```

**Add new sort option**:
```typescript
// VideoListPage.tsx line 16-24
const SORT_OPTIONS: SortOption[] = [
  // Add new option here
  { label: '💰 Lowest Cost', field: 'estimated_cost', desc: false },
]
```

**Modify video card design**:
```typescript
// VideoListPage.tsx line 268-480
// Video card rendering with thumbnail, metadata, buttons
```

**Change filter options**:
```typescript
// VideoListPage.tsx line 217-265
// Filter panel with channel & status dropdowns
```

**Customize scan modal**:
```typescript
// ScanProgressModal component
// services/frontend-service/app/web/src/components/ScanProgressModal.tsx
```

**Modify analysis detail modal**:
```typescript
// AnalysisDetailModal component
// services/frontend-service/app/web/src/components/AnalysisDetailModal.tsx
```

## Common Issues

**Videos not loading**:
- Check `/api/videos/list` endpoint works
- Verify videos exist in Firestore
- Check pagination offset doesn't exceed total
- Look for errors in browser console

**Channels dropdown empty**:
- Check `/api/channels/list` endpoint works
- Verify channels are being created during discovery
- Check loadChannels() function (line 48-81)
- May need to increase pagination limit if >500 channels

**Scan button doesn't work**:
- Check `/api/videos/{id}/scan` endpoint
- Verify vision-analyzer-service is running
- Check PubSub topic exists and subscription is active
- Look for errors in scan modal

**SSE progress not updating**:
- Check `/api/videos/{id}/scan/status` endpoint
- Verify SSE headers are correct
- Check vision-analyzer is emitting progress events
- Look for CORS issues

**Analysis modal shows wrong data**:
- Check `vision_analysis` field structure in Firestore
- Verify Gemini response is being parsed correctly
- Check for nested `full_analysis` object (line 271)

**Thumbnail not displaying**:
- Check `thumbnail_url` field exists
- Verify YouTube thumbnail URLs are valid
- Check for CORS issues with YouTube images
- Consider using proxy if YouTube blocks requests

## URL Query Parameters

The page supports URL parameters for deep linking:

| Parameter | Value | Effect |
|-----------|-------|--------|
| `channel` | Channel ID | Filters to specific channel |
| `status` | Status value | Filters by status |

**Example**:
```
/videos?channel=UC123&status=discovered
```

## Related Files

- `services/frontend-service/app/web/src/api/videos.ts` - Video API client
- `services/frontend-service/app/web/src/components/ScanProgressModal.tsx` - Scan progress modal
- `services/frontend-service/app/web/src/components/AnalysisDetailModal.tsx` - Analysis detail modal
- `services/frontend-service/app/web/src/components/ActiveScansOverlay.tsx` - Active scans widget
- `services/api-service/app/routers/videos.py` - Backend video endpoints
- `services/vision-analyzer-service/app/worker.py` - Video scanning logic
