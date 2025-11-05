# Channel List Page

**Route**: `/channels`
**File**: `services/frontend-service/app/web/src/pages/ChannelListPage.tsx`

## Purpose

The Channel List Page displays **all tracked YouTube channels** with their risk profiles, infringement history, and tier assignments. It helps identify which channels are most likely to produce infringing content.

## What It Shows

### 1. Page Header
- Title: "Channels"
- Total count: "{X} channels tracked"
- **Sort dropdown**: 4 sorting options

### 2. Risk Tier Distribution Stats
Color-coded summary cards:

| Tier | Score Range | Count | Color |
|------|-------------|-------|-------|
| 🔴 Critical | 80-100 | X | Red |
| 🟠 High | 60-79 | X | Orange |
| 🟡 Medium | 40-59 | X | Yellow |
| 🟢 Low | 20-39 | X | Green |
| ⚪ Minimal | 0-19 | X | Gray |

### 3. Channel List
List view (not grid) with detailed channel profiles:

**Each Channel Row Shows**:
- **Avatar**: Colored circle with first letter of channel name
- **Tier Icon**: 🔴🟠🟡🟢⚪
- **Channel Name**: Clickable → YouTube channel page
- **Tier Badge**: Color-coded pill (critical/high/medium/low/minimal)
- **Metrics Grid** (4 columns):
  - **Risk Score**: 0-100 score
  - **Videos**: Total videos found from this channel
  - **Infringements**: Confirmed violations (red text)
  - **Infringement Rate**: Percentage (orange text)
- **Last Scanned**: Timestamp
- **Action Buttons**:
  - "View on YouTube" → Channel YouTube page
  - "View Videos" → VideoListPage filtered to this channel

### 4. Pagination
- Previous / Next buttons
- "Page X of Y" display
- 20 channels per page

## Data Sources

| Endpoint | Data | When |
|----------|------|------|
| `/api/channels/list` | Paginated channel list | On load, sort, page change |
| `/api/channels/stats` | Tier distribution stats | On load |

**Location**: `services/frontend-service/app/web/src/api/channels.ts`

## Sorting Options

| Sort Option | Field | Order | Use Case |
|-------------|-------|-------|----------|
| Highest Risk Score | `risk_score` | DESC | Find most dangerous channels |
| Most Videos Found | `total_videos_found` | DESC | Most prolific channels |
| Most Recently Scanned | `last_scanned_at` | DESC | Check recent activity |
| Most Recently Discovered | `discovered_at` | DESC | Newest channels |

## Channel Tiers

Channels are automatically assigned tiers based on their infringement history:

### Tier Assignment Logic

| Tier | Criteria | Scan Frequency |
|------|----------|----------------|
| **CRITICAL** | >50% infringement rate, >10 violations | Daily (24h) |
| **HIGH** | 25-50% infringement, >5 violations | Every 3 days (72h) |
| **MEDIUM** | 10-25% infringement | Weekly (7 days) |
| **LOW** | <10% infringement | Monthly (30 days) |
| **MINIMAL** | 0% infringement after 20+ videos | Rarely |

**Why it matters**:
- High-risk channels scanned more frequently
- Focuses resources on repeat offenders
- Builds institutional knowledge over time

### How Tiers Are Calculated

1. Discovery service finds videos from channel
2. Risk analyzer scores videos
3. Vision analyzer scans videos
4. Backend calculates:
   - `infringement_rate = confirmed_infringements / total_videos`
   - `risk_score = base_score + (infringement_rate * 50)`
5. Tier assigned based on score + infringement count
6. Next scan scheduled based on tier

## Key Features

### Color-Coded Risk Visualization
Each channel row uses colors to indicate risk level:
- Avatar gradient (red → pink)
- Tier badge color
- Tier icon emoji

### Quick Navigation to Videos
"View Videos" button links to `/videos?channel={channel_id}`, showing only videos from that channel.

### Channel Reputation Tracking
The system learns which channels consistently produce infringing content and prioritizes scanning them.

### Stats Overview
The tier distribution cards at the top give a quick overview of channel risk distribution across the system.

## Where to Look

**Change channels per page**:
```typescript
// ChannelListPage.tsx line 26
const limit = 20  // Change to 50, 100, etc.
```

**Add new sort option**:
```typescript
// ChannelListPage.tsx line 11-16
const SORT_OPTIONS: SortOption[] = [
  // Add new option here
  { label: 'Most Infringements', field: 'confirmed_infringements', desc: true },
]
```

**Modify tier colors**:
```typescript
// ChannelListPage.tsx line 55-68
const getTierColor = (tier: ChannelTier) => {
  switch (tier) {
    case 'critical': return 'bg-red-100 text-red-800'  // Change colors here
    // ...
  }
}
```

**Customize channel card design**:
```typescript
// ChannelListPage.tsx line 149-232
// Channel row rendering with avatar, metrics, buttons
```

**Change tier icons**:
```typescript
// ChannelListPage.tsx line 70-83
const getTierIcon = (tier: ChannelTier) => {
  switch (tier) {
    case 'critical': return '🔴'  // Change emoji here
    // ...
  }
}
```

## Common Issues

**Channels not loading**:
- Check `/api/channels/list` endpoint works
- Verify channels exist in Firestore
- Check pagination offset doesn't exceed total
- Look for errors in browser console

**Stats card shows 0 for all tiers**:
- Check `/api/channels/stats` endpoint works
- Verify channel documents have `tier` field
- Check tier calculation logic in backend
- May need to run backfill script to populate tiers

**Infringement rate wrong**:
- Check `confirmed_infringements` field in Firestore
- Verify `total_videos_found` is accurate
- Check if vision analysis results are updating channel stats
- May need to recalculate from vision_analysis documents

**"View Videos" button broken**:
- Check URL encoding of channel_id
- Verify VideoListPage accepts `channel` query param
- Check channel_id format (should be YouTube channel ID like "UC...")

**Last scanned timestamp not showing**:
- Check `last_scanned_at` field exists in channel documents
- Verify discovery service updates this field after scanning
- Check date formatting (should be ISO 8601)

## Channel Tracking Strategy

### Discovery Flow

```
1. Discovery Service finds video
   ↓
2. Extracts channel_id from video
   ↓
3. Creates/updates channel document in Firestore
   ↓
4. Increments total_videos_found
   ↓
5. Calculates risk_score
   ↓
6. Assigns tier
   ↓
7. Schedules next scan based on tier
```

### Adaptive Scanning

The system learns from scan results:
- **Infringement found** → Increase channel risk, scan more frequently
- **Clean scans** → Decrease channel risk, scan less frequently
- **New channel** → Start with medium tier, adjust based on results

### Efficiency Gains

Channel tracking is **30x more efficient** than keyword search:
- **Keyword search**: 100 API units → 50 videos (2 units/video)
- **Channel tracking**: 3 API units → 17 videos (0.18 units/video)

## Related Files

- `services/frontend-service/app/web/src/api/channels.ts` - Channel API client
- `services/discovery-service/app/core/channel_tracker.py` - Channel tracking logic (REMOVED)
- `services/risk-analyzer-service/app/core/channel_risk_calculator.py` - Channel risk scoring
- `services/api-service/app/routers/analytics.py` - Channel stats aggregation
