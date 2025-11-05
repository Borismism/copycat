# Dashboard Development - Quick Start Guide

**For:** Frontend & Backend Developers
**Last Updated:** 2025-01-31

---

## Project Structure

```
copycat/
├── services/
│   ├── api-service/
│   │   └── app/
│   │       ├── routers/
│   │       │   ├── status.py          # ✅ System health (existing)
│   │       │   ├── videos.py          # ✅ Video library (existing)
│   │       │   ├── channels.py        # ✅ Channel profiles (existing)
│   │       │   ├── discovery.py       # ✅ Discovery triggers (existing)
│   │       │   ├── analytics.py       # 🆕 NEW - Homepage metrics
│   │       │   ├── discovery_analytics.py  # 🆕 NEW - Discovery insights
│   │       │   ├── risk_analytics.py  # 🆕 NEW - Risk analysis metrics
│   │       │   └── vision_analytics.py # 🆕 NEW - Vision analysis metrics
│   │       └── core/
│   │           └── firestore_client.py # ✅ DB queries (extend)
│   │
│   └── frontend-service/
│       └── app/web/src/
│           ├── pages/
│           │   ├── Dashboard.tsx       # 🔄 ENHANCE - Homepage
│           │   ├── DiscoveryPage.tsx   # 🔄 ENHANCE - Discovery
│           │   ├── RiskAnalyzerPage.tsx # 🆕 NEW - Risk dashboard
│           │   └── VisionAnalyzerPage.tsx # 🆕 NEW - Vision dashboard
│           ├── components/
│           │   ├── charts/            # 🆕 NEW - Reusable charts
│           │   ├── metrics/           # 🆕 NEW - Metric cards
│           │   └── tables/            # 🆕 NEW - Data tables
│           ├── api/
│           │   ├── analytics.ts       # 🆕 NEW - Analytics API client
│           │   └── ...
│           └── types/
│               └── analytics.ts       # 🆕 NEW - Type definitions
```

---

## Backend Development

### Step 1: Install Dependencies

No new dependencies needed! Use existing FastAPI setup.

### Step 2: Create New Router

**Example: `app/routers/analytics.py`**

```python
"""Analytics endpoints for homepage dashboard."""

from datetime import datetime, timedelta
from fastapi import APIRouter

from app.core.firestore_client import firestore_client

router = APIRouter()


@router.get("/hourly-stats")
async def get_hourly_stats(hours: int = 24):
    """
    Get hourly activity statistics.

    Returns:
        - discoveries: Videos discovered per hour
        - analyses: Videos analyzed per hour
        - infringements: Infringements found per hour
    """
    now = datetime.now()
    start = now - timedelta(hours=hours)

    # Query Firestore (add indexes as needed)
    videos = firestore_client.videos_collection.where(
        "discovered_at", ">=", start
    ).stream()

    # Aggregate by hour
    hourly_data = {}
    for video in videos:
        data = video.to_dict()
        hour = data["discovered_at"].replace(minute=0, second=0, microsecond=0)
        hour_key = hour.isoformat()

        if hour_key not in hourly_data:
            hourly_data[hour_key] = {
                "timestamp": hour_key,
                "discoveries": 0,
                "analyses": 0,
                "infringements": 0,
            }

        hourly_data[hour_key]["discoveries"] += 1
        if data.get("status") == "analyzed":
            hourly_data[hour_key]["analyses"] += 1
            if data.get("vision_analysis", {}).get("contains_infringement"):
                hourly_data[hour_key]["infringements"] += 1

    return {
        "hours": sorted(hourly_data.values(), key=lambda x: x["timestamp"])
    }


@router.get("/system-health")
async def get_system_health():
    """
    Get aggregated system health metrics.

    Returns:
        - alerts: List of active alerts
        - warnings: List of warnings
        - info: List of info messages
    """
    alerts = []
    warnings = []
    info = []

    # Check quota usage
    quota_status = await firestore_client.get_quota_status()
    if quota_status["utilization"] > 0.95:
        alerts.append({
            "type": "critical",
            "message": f"Quota at {quota_status['utilization']*100:.1f}%",
            "action": "Reduce discovery frequency or request increase",
        })
    elif quota_status["utilization"] > 0.85:
        warnings.append({
            "type": "warning",
            "message": f"Quota at {quota_status['utilization']*100:.1f}%",
            "action": "Monitor usage closely",
        })

    # Check budget usage
    budget_status = await firestore_client.get_budget_status()
    if budget_status["utilization"] > 0.95:
        alerts.append({
            "type": "critical",
            "message": f"Budget at {budget_status['utilization']*100:.1f}%",
            "action": "Analysis will pause at limit",
        })

    return {
        "alerts": alerts,
        "warnings": warnings,
        "info": info,
    }
```

### Step 3: Register Router

**In `app/main.py`:**

```python
from app.routers import analytics

app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
```

### Step 4: Add Firestore Indexes

**Create `firestore.indexes.json`:**

```json
{
  "indexes": [
    {
      "collectionGroup": "videos",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "discovered_at", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "videos",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "status", "order": "ASCENDING"},
        {"fieldPath": "discovered_at", "order": "DESCENDING"}
      ]
    }
  ]
}
```

Deploy indexes:
```bash
gcloud firestore indexes create --file=firestore.indexes.json
```

---

## Frontend Development

### Step 1: Install Dependencies

```bash
cd services/frontend-service/app/web
npm install recharts react-table date-fns swr react-gauge-chart
npm install --save-dev @types/recharts
```

### Step 2: Create API Client

**Create `src/api/analytics.ts`:**

```typescript
import { apiClient } from './client'

export interface HourlyStats {
  timestamp: string
  discoveries: number
  analyses: number
  infringements: number
}

export interface SystemHealth {
  alerts: Alert[]
  warnings: Warning[]
  info: Info[]
}

export interface Alert {
  type: 'critical' | 'warning' | 'info'
  message: string
  action: string
}

export const analyticsAPI = {
  async getHourlyStats(hours: number = 24): Promise<HourlyStats[]> {
    const response = await apiClient.get(`/analytics/hourly-stats?hours=${hours}`)
    return response.data.hours
  },

  async getSystemHealth(): Promise<SystemHealth> {
    const response = await apiClient.get('/analytics/system-health')
    return response.data
  },
}
```

### Step 3: Create Reusable Chart Component

**Create `src/components/charts/ActivityTimeline.tsx`:**

```typescript
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { format } from 'date-fns'

interface ActivityTimelineProps {
  data: Array<{
    timestamp: string
    discoveries: number
    infringements: number
  }>
}

export function ActivityTimeline({ data }: ActivityTimelineProps) {
  // Format data for display
  const chartData = data.map(item => ({
    time: format(new Date(item.timestamp), 'HH:mm'),
    discoveries: item.discoveries,
    infringements: item.infringements,
  }))

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Activity Timeline (Last 24 Hours)
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis yAxisId="left" />
          <YAxis yAxisId="right" orientation="right" />
          <Tooltip />
          <Legend />
          <Bar yAxisId="left" dataKey="discoveries" fill="#3B82F6" name="Videos Discovered" />
          <Line yAxisId="right" type="monotone" dataKey="infringements" stroke="#EF4444" name="Infringements" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

### Step 4: Use SWR for Auto-Refresh

**Example in `Dashboard.tsx`:**

```typescript
import useSWR from 'swr'
import { analyticsAPI } from '../api/analytics'
import { ActivityTimeline } from '../components/charts/ActivityTimeline'

export default function Dashboard() {
  // Auto-refresh every 30 seconds
  const { data: hourlyStats, error } = useSWR(
    'hourly-stats',
    () => analyticsAPI.getHourlyStats(24),
    { refreshInterval: 30000 }  // 30 seconds
  )

  const { data: systemHealth } = useSWR(
    'system-health',
    () => analyticsAPI.getSystemHealth(),
    { refreshInterval: 30000 }
  )

  if (error) return <div>Error loading dashboard</div>
  if (!hourlyStats) return <div>Loading...</div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">System Dashboard</h1>

      {/* Alerts */}
      {systemHealth?.alerts.map((alert, i) => (
        <div key={i} className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          <strong>{alert.message}</strong>
          <p className="text-sm">{alert.action}</p>
        </div>
      ))}

      {/* Timeline */}
      <ActivityTimeline data={hourlyStats} />
    </div>
  )
}
```

### Step 5: Create Reusable Metric Card

**Create `src/components/metrics/MetricCard.tsx`:**

```typescript
interface MetricCardProps {
  title: string
  value: string | number
  trend?: {
    direction: 'up' | 'down' | 'flat'
    value: string
  }
  subtitle?: string
  icon?: React.ReactNode
}

export function MetricCard({ title, value, trend, subtitle, icon }: MetricCardProps) {
  const trendColors = {
    up: 'text-green-600',
    down: 'text-red-600',
    flat: 'text-gray-600',
  }

  const trendIcons = {
    up: '↑',
    down: '↓',
    flat: '→',
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {trend && (
            <p className={`text-sm mt-1 ${trendColors[trend.direction]}`}>
              {trendIcons[trend.direction]} {trend.value}
            </p>
          )}
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className="text-4xl">{icon}</div>
        )}
      </div>
    </div>
  )
}
```

**Usage:**

```typescript
<MetricCard
  title="Videos Discovered"
  value={2847}
  trend={{ direction: 'up', value: '+12%' }}
  subtitle="Last 24 hours"
  icon="🔍"
/>
```

---

## Common Patterns

### 1. Loading States

```typescript
if (!data) {
  return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>
  )
}
```

### 2. Error Handling

```typescript
if (error) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <p className="text-red-800">Error: {error.message}</p>
      <button
        onClick={() => mutate()}
        className="mt-2 text-red-600 hover:text-red-800 underline"
      >
        Retry
      </button>
    </div>
  )
}
```

### 3. Responsive Grid

```typescript
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {/* Cards will stack on mobile, 2 cols on tablet, 4 cols on desktop */}
</div>
```

### 4. Date Formatting

```typescript
import { format, formatDistanceToNow } from 'date-fns'

// Format timestamp
format(new Date(timestamp), 'MMM dd, yyyy HH:mm')  // "Jan 31, 2025 14:30"

// Relative time
formatDistanceToNow(new Date(timestamp), { addSuffix: true })  // "2 hours ago"
```

---

## Testing

### Backend Tests

```python
# tests/test_analytics.py

import pytest
from app.routers.analytics import get_hourly_stats


@pytest.mark.asyncio
async def test_hourly_stats(mock_firestore):
    """Test hourly stats aggregation."""
    result = await get_hourly_stats(hours=24)

    assert "hours" in result
    assert len(result["hours"]) <= 24
    assert all("timestamp" in h for h in result["hours"])
    assert all("discoveries" in h for h in result["hours"])
```

### Frontend Tests

```typescript
// Dashboard.test.tsx

import { render, screen } from '@testing-library/react'
import { SWRConfig } from 'swr'
import Dashboard from './Dashboard'

test('renders dashboard with metrics', async () => {
  const mockData = {
    hourlyStats: [
      { timestamp: '2025-01-31T10:00:00Z', discoveries: 100, infringements: 10 }
    ]
  }

  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <Dashboard />
    </SWRConfig>
  )

  // Wait for data to load
  expect(await screen.findByText('System Dashboard')).toBeInTheDocument()
})
```

---

## Performance Tips

### Backend
- ✅ Add Firestore indexes for frequently queried fields
- ✅ Use `.select()` to fetch only needed fields
- ✅ Cache aggregated metrics (Redis or in-memory)
- ✅ Paginate large result sets
- ✅ Use background jobs for expensive computations

### Frontend
- ✅ Use `React.memo()` for expensive components
- ✅ Lazy load charts: `const Chart = lazy(() => import('./Chart'))`
- ✅ Debounce auto-refresh: `{ refreshInterval: 30000, dedupingInterval: 5000 }`
- ✅ Use `react-window` for large tables (>1000 rows)
- ✅ Code split by route: `pages/` should use dynamic imports

---

## Deployment Checklist

### Before Deploying to Dev
- [ ] Backend tests pass: `uv run pytest`
- [ ] Frontend builds: `npm run build`
- [ ] API endpoints documented in OpenAPI
- [ ] Firestore indexes deployed
- [ ] Environment variables configured

### Before Deploying to Prod
- [ ] Load testing completed (Apache Bench or k6)
- [ ] Error handling tested (Sentry integrated)
- [ ] Accessibility audit passed (Lighthouse >90)
- [ ] Mobile responsive design tested
- [ ] User acceptance testing completed

---

## Troubleshooting

### Dashboard loads slowly
1. Check Firestore query performance in console
2. Add missing indexes
3. Reduce data fetched (pagination, field selection)
4. Enable caching on backend

### Charts not rendering
1. Check browser console for errors
2. Verify data format matches chart expectations
3. Ensure `ResponsiveContainer` has valid height
4. Check Recharts version compatibility

### Auto-refresh not working
1. Verify SWR configuration: `{ refreshInterval: 30000 }`
2. Check network tab for API calls
3. Ensure no stale closures in `fetcher` function
4. Add `console.log()` to debug refresh timing

---

## Resources

**Documentation:**
- Recharts: https://recharts.org/
- SWR: https://swr.vercel.app/
- FastAPI: https://fastapi.tiangolo.com/
- Firestore: https://firebase.google.com/docs/firestore

**Code Examples:**
- See existing `services/api-service/app/routers/status.py` for API patterns
- See existing `services/frontend-service/app/web/src/pages/Dashboard.tsx` for frontend patterns

**Need Help?**
- Slack: #copycat-dev
- Team Lead: [Your Name]
- Project Stories: `/planning/STORY-*.md`
