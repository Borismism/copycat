# Dashboard Page

**Route**: `/`
**File**: `services/frontend-service/app/web/src/pages/Dashboard.tsx`

## Purpose

The Dashboard is the **main landing page** that provides a real-time overview of the entire Copycat system. It displays key metrics, service health, recent activity, and performance gauges.

## What It Shows

### 1. System Health Banner
**Component**: `SystemHealthBanner`
**Shows**: Status of all 4 microservices (discovery, risk-analyzer, vision-analyzer, api)
**Colors**:
- 🟢 Green = Healthy
- 🟡 Yellow = Degraded
- 🔴 Red = Down

### 2. Alert Center
**Component**: `AlertCenter`
**Shows**: System alerts categorized by severity:
- 🔴 **Alerts** (critical issues)
- 🟡 **Warnings** (potential problems)
- 🔵 **Info** (general notifications)

### 3. Key Metrics Grid
**Component**: `MetricsGrid`
**Shows 24-hour metrics**:
- Videos discovered
- Channels tracked
- Quota used
- Videos analyzed
- Infringements found
- Budget spent

### 4. Activity Timeline
**Component**: `ActivityTimeline`
**Shows**: Hourly activity graph for the last 24 hours:
- Videos discovered per hour
- Scans completed per hour
- Visual line chart with tooltips

### 5. Performance Gauges
**Component**: `PerformanceGauges`
**Shows circular gauges for**:
- Discovery efficiency
- Risk model accuracy
- Vision success rate
- System uptime

### 6. Last Discovery Run
**Shows**:
- Timestamp
- Duration
- Videos/channels/quota used
- Tier breakdown (channel tracking, trending, keywords)

### 7. Recent Activity Feed
**Component**: `RecentActivityFeed`
**Shows**: Last 20 system events:
- Video discoveries
- Scan completions
- Infringement detections
- Channel updates

## Data Sources

The Dashboard fetches data from **5 API endpoints** using SWR:

| Endpoint | Data | Refresh Rate |
|----------|------|--------------|
| `/api/status/services` | Service health status | 30s |
| `/api/status/summary` | System-wide summary stats | 30s |
| `/api/analytics/hourly` | Hourly activity stats (24h) | 30s |
| `/api/analytics/health` | System health & alerts | 30s |
| `/api/analytics/performance` | Performance metrics | 30s |
| `/api/analytics/events` | Recent events (20) | 30s |

**Location**: `services/frontend-service/app/web/src/api/status.ts`, `analytics.ts`

## Key Features

### Auto-Refresh
All data **auto-refreshes every 30 seconds** via SWR. The "Last updated" timestamp shows when data was last fetched.

### Loading States
- Shows spinner while initial data loads
- Displays error message with retry button if API fails

### Responsive Design
- Desktop: Multi-column grid layout
- Tablet/Mobile: Stacks vertically

## Where to Look

**Change refresh interval**:
```typescript
// Dashboard.tsx line 15-51
{ refreshInterval: 30000 } // Change to desired milliseconds
```

**Add new metric card**:
```typescript
// MetricsGrid.tsx
<div className="bg-white rounded-lg shadow-md p-6">
  <p className="text-sm font-medium text-gray-600">New Metric</p>
  <p className="text-3xl font-bold text-blue-600 mt-2">
    {data.newMetric}
  </p>
</div>
```

**Modify service health logic**:
```typescript
// SystemHealthBanner.tsx
// services/frontend-service/app/web/src/components/SystemHealthBanner.tsx
```

**Customize alert types**:
```typescript
// AlertCenter.tsx
// services/frontend-service/app/web/src/components/AlertCenter.tsx
```

## Common Issues

**"Failed to load dashboard" error**:
- Check api-service is running on port 8080
- Verify `/api/status/services` and `/api/status/summary` endpoints work
- Check browser console for CORS errors

**Stale data**:
- SWR caches data - hard refresh (Cmd+Shift+R) clears cache
- Check refreshInterval is not too long
- Verify API endpoints are returning fresh data

**Missing metrics**:
- Check backend is writing to Firestore correctly
- Verify analytics aggregation is running
- Check date range filters in analytics queries

## Related Files

- `services/frontend-service/app/web/src/components/SystemHealthBanner.tsx`
- `services/frontend-service/app/web/src/components/MetricsGrid.tsx`
- `services/frontend-service/app/web/src/components/ActivityTimeline.tsx`
- `services/frontend-service/app/web/src/components/AlertCenter.tsx`
- `services/frontend-service/app/web/src/components/RecentActivityFeed.tsx`
- `services/frontend-service/app/web/src/components/PerformanceGauges.tsx`
- `services/frontend-service/app/web/src/api/status.ts`
- `services/frontend-service/app/web/src/api/analytics.ts`
