# Copycat Management UI - Frontend & Backend Plan

## Overview
Build a web-based management UI for monitoring and controlling Copycat services. Starting with Discovery Service integration, expandable to all pipeline services.

---

## Architecture

### High-Level Design
```
User Browser
    ↓
[Cloud Run: frontend-service]
    ├── React SPA (Vite) - UI components
    └── FastAPI Proxy - IAM auth + API routing
        ↓
[Cloud Run: api-service]
    ├── Discovery Service API
    ├── System Status API
    ├── Video Library API
    └── Analytics API
        ↓
    [Firestore] [BigQuery] [PubSub] [Discovery Service]
```

### Key Design Decisions

**Single Region** (unlike catalyst-gcp multi-region):
- Deploy to `us-central1` (or `europe-west4` based on project config)
- No subdomain routing needed
- Simpler load balancer setup (or direct Cloud Run URLs)

**Hybrid Frontend Service** (reuse catalyst pattern):
- FastAPI serves React SPA from `/app/static/`
- FastAPI proxy at `/api/*` handles IAM auth to backend
- Single deployment unit, no CORS issues
- Multi-stage Dockerfile: Node build → Python serve

**Backend API Service** (new microservice):
- Central API gateway for all Copycat operations
- Orchestrates discovery runs
- Queries Firestore/BigQuery for dashboards
- Proxies requests to individual services (discovery, etc.)
- Handles service health checks

**Technology Stack**:
- Frontend: React 18 + TypeScript + Vite + TailwindCSS + Zustand
- Backend: FastAPI 0.119 + Python 3.13 + UV package manager
- Deployment: Cloud Run (both services)
- CI/CD: GitHub Actions with Workload Identity Federation

---

## Phase 1: Core Infrastructure & Discovery Integration

### Milestone 1.1: Backend API Service

**Goal**: Create central API gateway that can talk to discovery-service and query Firestore/BigQuery.

**Endpoints**:

```python
# System Status
GET  /api/health                    # API service health check
GET  /api/status/services           # All services status (health checks)
GET  /api/status/summary            # 24h summary stats

# Discovery Service Integration
POST /api/discovery/trigger         # Trigger discovery run
GET  /api/discovery/status          # Current discovery run status
GET  /api/discovery/quota           # YouTube API quota status
GET  /api/discovery/analytics       # Discovery performance metrics

# Channel Management
GET  /api/channels                  # List channels (paginated, filterable)
GET  /api/channels/{channel_id}     # Channel details + video list

# Video Library
GET  /api/videos                    # List videos (paginated, filterable, sortable)
GET  /api/videos/{video_id}         # Video details

# Analytics (future)
GET  /api/analytics/overview        # High-level KPIs
GET  /api/analytics/trends          # Historical trends (7d/30d)
```

**Service Structure**:
```
services/api-service/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── core/
│   │   ├── discovery_client.py    # HTTP client for discovery-service
│   │   ├── firestore_client.py    # Firestore queries
│   │   ├── bigquery_client.py     # BigQuery analytics queries
│   │   └── service_health.py      # Health check aggregator
│   ├── routers/
│   │   ├── discovery.py           # /api/discovery/*
│   │   ├── channels.py            # /api/channels/*
│   │   ├── videos.py              # /api/videos/*
│   │   ├── status.py              # /api/status/*
│   │   └── analytics.py           # /api/analytics/*
│   └── models.py                  # Pydantic models
├── terraform/
│   ├── provider.tf
│   ├── variables.tf
│   ├── main.tf                    # Cloud Run service
│   ├── iam.tf                     # Service account + permissions
│   └── locals.tf                  # Source hash tracking
├── Dockerfile
├── pyproject.toml                 # UV dependencies
└── cloudbuild.yaml
```

**IAM Permissions** (api-service service account):
- `roles/run.invoker` on discovery-service (internal HTTP calls)
- `roles/datastore.user` (Firestore read/write)
- `roles/bigquery.dataViewer` (BigQuery queries)
- `roles/pubsub.publisher` (trigger pipeline manually in future)

**Dependencies** (pyproject.toml):
```toml
[project]
dependencies = [
    "fastapi==0.119.1",
    "uvicorn[standard]==0.34.0",
    "pydantic-settings==2.7.1",
    "google-cloud-firestore==2.20.1",
    "google-cloud-bigquery==3.29.0",
    "google-auth==2.37.0",
    "httpx==0.28.1",  # For HTTP client to discovery-service
]
```

---

### Milestone 1.2: Frontend Service

**Goal**: Create React SPA with FastAPI proxy serving it.

**Pages/Routes**:

```
/                              # Dashboard (system overview)
/discovery                     # Discovery service control panel
/channels                      # Channel list + risk tiers
/channels/:channelId           # Channel detail page
/videos                        # Video library browser
/videos/:videoId               # Video detail page
/analytics                     # Analytics dashboard (future)
```

**Component Structure**:
```
services/frontend-service/
├── app/
│   ├── main.py                              # FastAPI proxy
│   ├── web/                                 # React SPA
│   │   ├── src/
│   │   │   ├── main.tsx                     # React entry point
│   │   │   ├── App.tsx                      # Router + layout
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx            # System overview
│   │   │   │   ├── DiscoveryPage.tsx        # Discovery control panel
│   │   │   │   ├── ChannelListPage.tsx      # Channel browser
│   │   │   │   ├── ChannelDetailPage.tsx    # Single channel view
│   │   │   │   ├── VideoListPage.tsx        # Video library
│   │   │   │   └── VideoDetailPage.tsx      # Single video view
│   │   │   ├── components/
│   │   │   │   ├── layout/
│   │   │   │   │   ├── Header.tsx           # Top nav
│   │   │   │   │   ├── Sidebar.tsx          # Service nav
│   │   │   │   │   └── Layout.tsx           # Main layout wrapper
│   │   │   │   ├── discovery/
│   │   │   │   │   ├── TriggerButton.tsx    # Start discovery run
│   │   │   │   │   ├── QuotaDisplay.tsx     # API quota meter
│   │   │   │   │   ├── StatsCards.tsx       # Discovery metrics
│   │   │   │   │   └── PerformanceChart.tsx # Efficiency chart
│   │   │   │   ├── channels/
│   │   │   │   │   ├── ChannelCard.tsx      # Channel summary card
│   │   │   │   │   ├── ChannelList.tsx      # Grid/list view
│   │   │   │   │   ├── RiskTierBadge.tsx    # Risk level indicator
│   │   │   │   │   └── ChannelFilters.tsx   # Filter controls
│   │   │   │   ├── videos/
│   │   │   │   │   ├── VideoCard.tsx        # Video thumbnail + meta
│   │   │   │   │   ├── VideoList.tsx        # Grid/list view
│   │   │   │   │   ├── VideoPlayer.tsx      # YouTube embed
│   │   │   │   │   ├── VideoFilters.tsx     # Filter/sort controls
│   │   │   │   │   └── IPMatchBadge.tsx     # IP target indicator
│   │   │   │   ├── status/
│   │   │   │   │   ├── ServiceStatus.tsx    # Service health card
│   │   │   │   │   ├── ServiceList.tsx      # All services grid
│   │   │   │   │   └── ActivitySummary.tsx  # 24h activity widget
│   │   │   │   └── common/
│   │   │   │       ├── Button.tsx
│   │   │   │       ├── Card.tsx
│   │   │   │       ├── Table.tsx
│   │   │   │       ├── Pagination.tsx
│   │   │   │       ├── LoadingSpinner.tsx
│   │   │   │       └── ErrorBoundary.tsx
│   │   │   ├── stores/
│   │   │   │   ├── discoveryStore.ts        # Zustand store
│   │   │   │   ├── channelsStore.ts
│   │   │   │   ├── videosStore.ts
│   │   │   │   └── statusStore.ts
│   │   │   ├── api/
│   │   │   │   ├── client.ts                # Base fetch wrapper
│   │   │   │   ├── discovery.ts             # Discovery API calls
│   │   │   │   ├── channels.ts
│   │   │   │   ├── videos.ts
│   │   │   │   └── status.ts
│   │   │   ├── types/
│   │   │   │   ├── discovery.ts             # TypeScript interfaces
│   │   │   │   ├── channels.ts
│   │   │   │   ├── videos.ts
│   │   │   │   └── status.ts
│   │   │   └── utils/
│   │   │       ├── format.ts                # Date/number formatting
│   │   │       └── constants.ts             # App constants
│   │   ├── public/
│   │   │   └── favicon.ico
│   │   ├── index.html
│   │   ├── vite.config.ts                   # Vite config + proxy
│   │   ├── tailwind.config.js
│   │   ├── tsconfig.json
│   │   └── package.json
│   └── static/                              # Built SPA (created by Dockerfile)
├── terraform/
│   ├── provider.tf
│   ├── variables.tf
│   ├── main.tf                              # Cloud Run service
│   ├── iam.tf                               # Service account + invoker role
│   ├── remote.tf                            # Reference api-service URL
│   └── locals.tf                            # Source hash tracking
├── Dockerfile                               # Multi-stage: Node → Python
├── cloudbuild.yaml
└── pyproject.toml                           # FastAPI dependencies
```

**Frontend Dependencies** (package.json):
```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "zustand": "^4.5.0",
    "immer": "^10.1.1",
    "zod": "^3.23.8",
    "@tanstack/react-query": "^5.62.11"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "tailwindcss": "^3.4.16",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20"
  }
}
```

**Backend Proxy** (app/main.py):
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
from google.auth import default
from google.auth.transport.requests import Request
import google.oauth2.id_token

app = FastAPI()

# Get API service URL from env (set via Terraform remote state)
API_SERVICE_URL = os.getenv("API_SERVICE_URL")

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_api(path: str, request: Request):
    """Proxy all /api/* requests to api-service with IAM auth."""

    # Fetch service account ID token for api-service audience
    auth_req = Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, API_SERVICE_URL)

    # Forward request with IAM token
    url = f"{API_SERVICE_URL}/{path}"
    headers = {
        "authorization": f"Bearer {id_token}",
        "content-type": request.headers.get("content-type", "application/json"),
    }

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            json=await request.json() if request.method in ["POST", "PUT"] else None,
            headers=headers,
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )

# Serve React SPA (all other routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve index.html for all non-API routes (SPA routing)."""
    return FileResponse("static/index.html")
```

**Vite Proxy** (vite.config.ts - for local dev):
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',  // Local api-service
        changeOrigin: true,
      },
    },
  },
})
```

---

### Milestone 1.3: Dashboard Page

**Goal**: System overview showing service health + 24h activity.

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│  Copycat Management                    [User Menu]  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  System Status                                       │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │Discovery │Risk      │Chapter   │Frame     │     │
│  │🟢 Healthy│🟡 Unknown│🟡 Unknown│🟡 Unknown│     │
│  │Last: 2m  │   -      │    -     │    -     │     │
│  └──────────┴──────────┴──────────┴──────────┘     │
│                                                      │
│  24-Hour Activity Summary                            │
│  ┌─────────────────────────────────────────────┐   │
│  │ Videos Discovered:        2,847             │   │
│  │ Channels Tracked:           423             │   │
│  │ YouTube Quota Used:      8,432 / 10,000    │   │
│  │ Videos Analyzed:              0 (pending)   │   │
│  │ Infringements Found:          0 (pending)   │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Quick Actions                                       │
│  [Trigger Discovery] [View Channels] [Browse Videos]│
│                                                      │
└─────────────────────────────────────────────────────┘
```

**API Calls**:
- `GET /api/status/services` → Service health checks
- `GET /api/status/summary` → 24h stats from Firestore aggregation

**Components**:
- `ServiceStatus.tsx` → Individual service health card
- `ServiceList.tsx` → Grid of all services
- `ActivitySummary.tsx` → 24h stats widget
- `QuickActions.tsx` → Shortcut buttons

---

### Milestone 1.4: Discovery Page

**Goal**: Control panel for discovery-service with manual trigger, quota display, and performance metrics.

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│  Discovery Service                                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Control Panel                                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ [▶ Trigger Discovery Run]                   │   │
│  │                                              │   │
│  │ Max Quota Limit: [1000] units               │   │
│  │ Priority: [All IPs ▾]                       │   │
│  │ Discovery Mode: [Smart Auto ▾]              │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  YouTube API Quota                                   │
│  ┌─────────────────────────────────────────────┐   │
│  │ ████████████████░░░░ 8,432 / 10,000 (84%)  │   │
│  │ Remaining: 1,568 units                      │   │
│  │ Resets: Today 11:59 PM (in 7h 23m)         │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Discovery Statistics (Last 24h)                     │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │Videos    │Channels  │Quota     │Efficiency│     │
│  │Discovered│Tracked   │Used      │          │     │
│  │  2,847   │   423    │ 8,432    │ 0.34 v/u │     │
│  └──────────┴──────────┴──────────┴──────────┘     │
│                                                      │
│  Performance (7 days)                                │
│  ┌─────────────────────────────────────────────┐   │
│  │     [Line chart: Videos/day, Efficiency]    │   │
│  │   3000 ┤     ╭─╮                             │   │
│  │   2000 ┤   ╭─╯ ╰╮  ╭╮                        │   │
│  │   1000 ┤  ╭╯    ╰──╯╰──╮                     │   │
│  │      0 ┴──────────────────────              │   │
│  │        Mon Tue Wed Thu Fri Sat Sun          │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Recent Discoveries                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ Superman AI Battle (5.2M views) - 2m ago    │   │
│  │ Batman Sora Movie (1.3M views) - 5m ago     │   │
│  │ Justice League AI Trailer - 8m ago          │   │
│  │ [View All Videos]                           │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**API Calls**:
- `POST /api/discovery/trigger` → Start discovery run
- `GET /api/discovery/quota` → YouTube quota status
- `GET /api/discovery/analytics` → Stats + performance data
- `GET /api/videos?limit=5&sort=discovered_at:desc` → Recent discoveries

**Components**:
- `TriggerButton.tsx` → Discovery run trigger with options
- `QuotaDisplay.tsx` → API quota meter (progress bar + stats)
- `StatsCards.tsx` → 4-card grid (videos, channels, quota, efficiency)
- `PerformanceChart.tsx` → Line chart (7d/30d trends)
- `RecentDiscoveries.tsx` → List of latest videos

**State Management** (Zustand):
```typescript
interface DiscoveryStore {
  quota: QuotaStatus | null;
  stats: DiscoveryStats | null;
  isRunning: boolean;
  lastRun: Date | null;

  fetchQuota: () => Promise<void>;
  fetchStats: () => Promise<void>;
  triggerRun: (options: RunOptions) => Promise<void>;
}
```

---

### Milestone 1.5: Channels Page

**Goal**: Browse and filter tracked channels by risk tier, view count, etc.

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│  Channels                                            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Filters                                             │
│  Risk Tier: [All ▾] | Sort: [Risk Score ▾]         │
│  Search: [________________] 🔍                      │
│                                                      │
│  Risk Tier Distribution                              │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🔴 Critical (80-100):    8 channels         │   │
│  │ 🟠 High (60-79):       37 channels          │   │
│  │ 🟡 Medium (40-59):     92 channels          │   │
│  │ 🟢 Low (20-39):       130 channels          │   │
│  │ ⚪ Minimal (0-19):      97 channels         │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🔴 AI Movie Studio                          │   │
│  │    Risk: 95 | Videos: 47 | Infractions: 42 │   │
│  │    Last scan: 2h ago | Next: in 4h         │   │
│  │    [View Details]                           │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 🔴 Sora Justice League                      │   │
│  │    Risk: 87 | Videos: 23 | Infractions: 18 │   │
│  │    Last scan: 5h ago | Next: in 1h         │   │
│  │    [View Details]                           │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 🟠 DC AI Content Creator                    │   │
│  │    Risk: 72 | Videos: 68 | Infractions: 41 │   │
│  │    Last scan: 1d ago | Next: tomorrow      │   │
│  │    [View Details]                           │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  [< Prev] Page 1 of 12 [Next >]                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**API Calls**:
- `GET /api/channels?min_risk=60&sort=risk_score:desc&limit=20&offset=0` → Paginated channel list
- `GET /api/channels/stats` → Risk tier distribution

**Components**:
- `ChannelCard.tsx` → Individual channel summary
- `ChannelList.tsx` → Paginated grid/list
- `ChannelFilters.tsx` → Risk tier filter + sort + search
- `RiskTierBadge.tsx` → Colored risk indicator
- `RiskDistribution.tsx` → Tier breakdown widget

**Channel Detail Page** (click "View Details"):
```
┌─────────────────────────────────────────────────────┐
│  Channel: AI Movie Studio                           │
│  Risk Score: 95 🔴 Critical                         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Profile                                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ Channel ID: UCxxx...                        │   │
│  │ Videos Found: 47                            │   │
│  │ Confirmed Infractions: 42 (89% rate)        │   │
│  │ Discovered: Jan 15, 2025                    │   │
│  │ Last Scanned: 2 hours ago                   │   │
│  │ Next Scan: in 4 hours (6-hour interval)    │   │
│  │ Posting Frequency: 2.3 days                 │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Videos from this Channel (47)                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ [Thumbnail] Superman vs Doomsday AI Movie   │   │
│  │             5.2M views | Jan 20, 2025       │   │
│  │             Status: Analyzed | Match: ✓     │   │
│  ├─────────────────────────────────────────────┤   │
│  │ [Thumbnail] Batman: The Dark AI Returns     │   │
│  │             3.1M views | Jan 18, 2025       │   │
│  │             Status: Analyzed | Match: ✓     │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  [View All Videos from Channel]                     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**API Calls**:
- `GET /api/channels/{channel_id}` → Channel profile
- `GET /api/videos?channel_id={channel_id}&limit=20` → Videos from channel

---

### Milestone 1.6: Videos Page

**Goal**: Browse video library with filters, sorting, and search.

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│  Video Library                                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Filters & Sort                                      │
│  Status: [All ▾] | IP Match: [All ▾] | Sort: [Views ▾]│
│  Search: [________________] 🔍                      │
│                                                      │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │[Thumb]   │[Thumb]   │[Thumb]   │[Thumb]   │     │
│  │Superman  │Batman AI │Wonder    │Flash Sora│     │
│  │AI Battle │Movie     │Woman AI  │Short     │     │
│  │5.2M views│3.1M views│1.8M views│892K views│     │
│  │🟢 Match  │🟢 Match  │🟡 Pending│🟢 Match  │     │
│  ├──────────┼──────────┼──────────┼──────────┤     │
│  │[Thumb]   │[Thumb]   │[Thumb]   │[Thumb]   │     │
│  │Justice   │Aquaman   │Cyborg    │Green     │     │
│  │League AI │Runway    │AI Origin │Lantern   │     │
│  │2.3M views│654K views│421K views│387K views│     │
│  │🟢 Match  │🟢 Match  │🔴 Failed │🟡 Pending│     │
│  └──────────┴──────────┴──────────┴──────────┘     │
│                                                      │
│  [< Prev] Page 1 of 87 [Next >]                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**API Calls**:
- `GET /api/videos?status=discovered&ip_match=true&sort=view_count:desc&limit=20&offset=0` → Paginated video list

**Components**:
- `VideoCard.tsx` → Thumbnail + title + stats
- `VideoList.tsx` → Responsive grid (4 cols desktop, 2 mobile)
- `VideoFilters.tsx` → Status, IP match, sort, search
- `IPMatchBadge.tsx` → Match status indicator

**Video Detail Page** (click video):
```
┌─────────────────────────────────────────────────────┐
│  Superman AI Battle - Epic Sora Generated Movie     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │                                              │   │
│  │        [YouTube Embed Player]                │   │
│  │                                              │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Video Information                                   │
│  ┌─────────────────────────────────────────────┐   │
│  │ Video ID: abc123xyz                         │   │
│  │ Channel: AI Movie Studio                    │   │
│  │ Published: Jan 20, 2025                     │   │
│  │ Duration: 10:47                             │   │
│  │ Views: 5,234,892                            │   │
│  │ View Velocity: 12,500 views/hour 🔥        │   │
│  │ Status: Analyzed ✓                          │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  IP Matches                                          │
│  ┌─────────────────────────────────────────────┐   │
│  │ ✓ Superman AI Content (High Priority)      │   │
│  │ ✓ Justice League AI Content                │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Analysis Results (Pending Implementation)           │
│  ┌─────────────────────────────────────────────┐   │
│  │ Status: Queued for analysis                 │   │
│  │ Priority: High (view velocity)              │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Actions                                             │
│  [Open in YouTube] [Flag for Review] [View Channel] │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**API Calls**:
- `GET /api/videos/{video_id}` → Full video details

---

## Phase 2: Advanced Features (Future)

### Milestone 2.1: Real-Time Updates (SSE)

**Goal**: Live updates when discovery runs or analysis completes.

**Implementation**:
- Add SSE endpoint in api-service: `GET /api/events/stream`
- Subscribe to Firestore changes via Eventarc
- Broadcast updates to connected clients
- Frontend listens to SSE and updates UI

**Use Cases**:
- Live discovery run progress (videos found counter)
- Service status changes (health checks)
- New video discoveries appear in real-time

---

### Milestone 2.2: Analytics Dashboard

**Goal**: Historical trends and cost analysis.

**Charts**:
- Discovery efficiency over time (videos/quota unit)
- Channel risk tier distribution trends
- View velocity top 10 (trending videos)
- Cost projections (Gemini budget utilization)

**Data Source**: BigQuery `metrics` table

---

### Milestone 2.3: Pipeline Monitoring

**Goal**: Visualize entire pipeline flow.

**Features**:
- Service dependency graph
- PubSub message queue depths
- Processing latency metrics (discovery → analysis)
- Dead letter queue monitoring

**Implementation**:
- Query PubSub subscription metrics
- Track message age in Firestore
- Display pipeline stages with status indicators

---

### Milestone 2.4: Manual Video Analysis Trigger

**Goal**: Manually trigger analysis for specific videos.

**Implementation**:
- Button on video detail page: "Analyze Now"
- API endpoint: `POST /api/videos/{video_id}/analyze`
- Publishes to `copycat-video-discovered` PubSub topic
- Bypasses discovery queue

---

### Milestone 2.5: Multi-User Authentication (Optional)

**Goal**: Add user authentication via IAP.

**Implementation**:
- Enable IAP on load balancer (reuse catalyst pattern)
- Create OAuth2 client in GCP Console
- Store in Secret Manager
- Add user management (authorized users list)

**Benefits**:
- Audit logs (who triggered what)
- Role-based access (view-only vs admin)

---

## Terraform Structure

### Global Resources (terraform/global_resources/)
Already exists, may need additions:
- Add WIF for GitHub Actions (if not present)
- Ensure Artifact Registry exists

### New Services

**services/api-service/terraform/**:
```hcl
# main.tf
resource "google_cloud_run_v2_service" "api_service" {
  name     = "api-service"
  location = var.region

  template {
    service_account = google_service_account.api_service.email

    containers {
      image = "us-docker.pkg.dev/${var.project_id}/copycat/api-service:latest"

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "DISCOVERY_SERVICE_URL"
        value = data.terraform_remote_state.discovery_service.outputs.service_url
      }
      env {
        name  = "SOURCE_CODE_HASH"
        value = local.source_code_hash
      }
    }
  }
}

# iam.tf
resource "google_service_account" "api_service" {
  account_id   = "api-service-sa"
  display_name = "API Service Account"
}

resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "api_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_cloud_run_service_iam_member" "api_invoke_discovery" {
  service  = "discovery-service"
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_service.email}"
}

# remote.tf
data "terraform_remote_state" "discovery_service" {
  backend = "gcs"
  config = {
    bucket = var.terraform_state_bucket
    prefix = "discovery-service"
  }
}

# locals.tf (source hash tracking)
locals {
  source_dir    = "${path.module}/.."
  exclude_regex = "(\\.venv/|__pycache__/|\\.git/|\\.pytest_cache/|\\.DS_Store)"

  all_files = fileset(local.source_dir, "**/*")
  source_files = toset([
    for f in local.all_files : f if length(regexall(local.exclude_regex, f)) == 0
  ])

  source_code_hash = sha256(join("", [
    for f in sort(local.source_files) : filesha256("${local.source_dir}/${f}")
  ]))
}
```

**services/frontend-service/terraform/**:
```hcl
# main.tf
resource "google_cloud_run_v2_service" "frontend_service" {
  name     = "frontend-service"
  location = var.region

  template {
    service_account = google_service_account.frontend_service.email

    containers {
      image = "us-docker.pkg.dev/${var.project_id}/copycat/frontend-service:latest"

      env {
        name  = "API_SERVICE_URL"
        value = data.terraform_remote_state.api_service.outputs.service_url
      }
      env {
        name  = "SOURCE_CODE_HASH"
        value = local.source_code_hash
      }
    }
  }
}

# Allow unauthenticated access (or add IAP later)
resource "google_cloud_run_service_iam_member" "frontend_noauth" {
  service  = google_cloud_run_v2_service.frontend_service.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# iam.tf
resource "google_service_account" "frontend_service" {
  account_id   = "frontend-service-sa"
  display_name = "Frontend Service Account"
}

resource "google_cloud_run_service_iam_member" "frontend_invoke_api" {
  service  = "api-service"
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.frontend_service.email}"
}

# remote.tf
data "terraform_remote_state" "api_service" {
  backend = "gcs"
  config = {
    bucket = var.terraform_state_bucket
    prefix = "api-service"
  }
}

# locals.tf (source hash tracking - includes web/ files)
locals {
  source_dir    = "${path.module}/.."
  exclude_regex = "(\\.venv/|node_modules/|__pycache__/|\\.git/|dist/|\\.DS_Store)"

  all_files = fileset(local.source_dir, "**/*")
  source_files = toset([
    for f in all_files : f if length(regexall(local.exclude_regex, f)) == 0
  ])

  source_code_hash = sha256(join("", [
    for f in sort(local.source_files) : filesha256("${local.source_dir}/${f}")
  ]))
}
```

---

## Dockerfiles

### api-service/Dockerfile
```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### frontend-service/Dockerfile (Multi-stage)
```dockerfile
# Stage 1: Build React SPA
FROM node:20 AS frontend-build

WORKDIR /web

COPY app/web/package.json app/web/package-lock.json ./
RUN npm ci

COPY app/web/ ./
RUN npm run build

# Stage 2: FastAPI proxy + serve built SPA
FROM python:3.13-slim

WORKDIR /app

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy FastAPI proxy code
COPY app/main.py ./

# Copy built React SPA from stage 1
COPY --from=frontend-build /web/dist ./static

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Deployment Scripts

### scripts/deploy-service.sh (Enhancement)
Update existing script to support new services:
```bash
# Add to service list
VALID_SERVICES=(
  "discovery-service"
  "api-service"         # NEW
  "frontend-service"    # NEW
  "risk-scorer-service"
  "chapter-extractor-service"
  "frame-extractor-service"
  "vision-analyzer-service"
)
```

**Deploy Order** (dependencies):
1. Deploy api-service first (backend)
2. Deploy frontend-service second (needs api-service URL)

---

## Development Workflow

### Local Development

**Terminal 1: API Service**
```bash
cd services/api-service
./scripts/dev-local.sh api-service
# Runs on http://localhost:8080
```

**Terminal 2: Discovery Service**
```bash
cd services/discovery-service
./scripts/dev-local.sh discovery-service
# Runs on http://localhost:8081 (update port in dev-local.sh)
```

**Terminal 3: Frontend**
```bash
cd services/frontend-service/app/web
npm install
npm run dev
# Runs on http://localhost:5173
# Vite proxy forwards /api/* to http://localhost:8080
```

**Access UI**: http://localhost:5173

---

### Testing

**Backend Tests**:
```bash
cd services/api-service
uv run pytest --cov=app --cov-report=term-missing
```

**Frontend Tests** (future):
```bash
cd services/frontend-service/app/web
npm run test
```

---

### Deployment

**Deploy Backend**:
```bash
./scripts/deploy-service.sh api-service dev
```

**Deploy Frontend** (after backend):
```bash
./scripts/deploy-service.sh frontend-service dev
```

**GitHub Actions** (future):
- Auto-detect changes in `services/api-service/` or `services/frontend-service/`
- Build + deploy on push to `develop` (dev) or `main` (prod)

---

## Success Criteria

### Phase 1 Complete When:
- [ ] api-service deployed and healthy
- [ ] frontend-service deployed and serving UI
- [ ] Dashboard page shows system status
- [ ] Discovery page can trigger discovery runs
- [ ] Discovery page shows quota + stats
- [ ] Channels page lists channels with filters
- [ ] Videos page lists videos with filters
- [ ] Video detail page shows full metadata
- [ ] All pages responsive (mobile + desktop)
- [ ] 80%+ test coverage on api-service

### Future Phase 2:
- [ ] Real-time updates via SSE
- [ ] Analytics dashboard with BigQuery charts
- [ ] Pipeline monitoring visualization
- [ ] Manual video analysis trigger
- [ ] Multi-user authentication (IAP)

---

## Timeline Estimate

**Phase 1 (MVP)**:
- Milestone 1.1 (API Service): 2-3 days
- Milestone 1.2 (Frontend Service): 2-3 days
- Milestone 1.3 (Dashboard): 1 day
- Milestone 1.4 (Discovery Page): 2 days
- Milestone 1.5 (Channels Page): 1-2 days
- Milestone 1.6 (Videos Page): 1-2 days

**Total**: ~10-15 days for full MVP

---

## Next Steps

1. **Review this plan** - confirm scope and priorities
2. **Set up api-service** - create directory structure, FastAPI skeleton
3. **Set up frontend-service** - create React project with Vite
4. **Implement API endpoints** - discovery integration first
5. **Build UI components** - dashboard → discovery → channels → videos
6. **Test locally** - verify full stack works
7. **Deploy to dev** - Terraform + Cloud Run
8. **Iterate** - add features, polish UI, improve performance

---

## Questions to Resolve

1. **Custom domain?** Do we need a custom domain (e.g., copycat.borism.nl) or use Cloud Run URLs?
2. **Authentication?** Do we need IAP/OAuth or open to all (internal tool)?
3. **Region?** Deploy to `us-central1` or `europe-west4`?
4. **Budget alerts?** Set up cost monitoring/alerts for Cloud Run?
5. **CI/CD priority?** Manual deploy first or GitHub Actions immediately?

---

This plan provides a complete roadmap for building the Copycat management UI, starting with discovery-service integration and expandable to the full pipeline.