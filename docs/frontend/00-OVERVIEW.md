# Frontend Overview

## Architecture

The Copycat frontend is a **React + TypeScript** single-page application built with:
- **React 18** with hooks
- **React Router** for navigation
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **SWR** for data fetching and caching

## Project Structure

```
services/frontend-service/app/web/src/
├── api/              # API client modules (one per backend service)
├── components/       # Reusable UI components
├── pages/            # Page components (one per route)
├── types/            # TypeScript type definitions
├── App.tsx           # Main app with routing
└── main.tsx          # Entry point
```

## Routing

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Dashboard | System overview and metrics |
| `/discovery` | DiscoveryPage | YouTube discovery controls |
| `/risk` | RiskAnalyzerPage | Risk scoring dashboard |
| `/vision` | VisionAnalyzerPage | Gemini analysis dashboard |
| `/videos` | VideoListPage | Video library browser |
| `/channels` | ChannelListPage | Channel tracker |
| `/config` | ConfigGeneratorPage | IP configuration manager |

## API Communication

The frontend communicates with the backend API (api-service) on port **8080**. Each API module in `src/api/` corresponds to a backend router:

- `status.ts` → `/api/status/*` (system health)
- `discovery.ts` → `/api/discovery/*` (discovery service)
- `analytics.ts` → `/api/analytics/*` (metrics)
- `videos.ts` → `/api/videos/*` (video CRUD)
- `channels.ts` → `/api/channels/*` (channel CRUD)
- `vision.ts` → `/api/vision/*` (vision analyzer)

## Data Fetching Pattern

All pages use **SWR** for data fetching:

```typescript
const { data, error } = useSWR(
  'key',
  () => apiFunction(),
  { refreshInterval: 30000 } // Auto-refresh every 30s
)
```

Benefits:
- Automatic caching
- Auto-refresh
- Loading/error states
- Optimistic updates

## Key Features

### Real-Time Updates
- **SWR auto-refresh** (every 30 seconds)
- **Server-Sent Events (SSE)** for discovery progress
- **Manual refresh** buttons on demand

### Video Scanning
- **Single video scan**: Click "Scan Now" on video card
- **Batch scan**: Vision Analyzer page batch controls
- **Progress tracking**: Real-time modal with SSE updates

### Filtering & Sorting
- **Videos**: Filter by channel, status; sort by priority, views, date
- **Channels**: Sort by risk, videos, last scanned

### Interactive Components
- **Editable tags** (Config Generator)
- **AI suggestions** (Config Generator)
- **Modals** (scan progress, analysis details)
- **Active scans overlay** (bottom-right corner)

## Navigation Flow

```
Dashboard (overview)
   ├→ Discovery Page (trigger discovery runs)
   ├→ Risk Analyzer (view risk scoring)
   ├→ Vision Analyzer (view Gemini analysis)
   ├→ Videos (browse/scan videos)
   ├→ Channels (view channel profiles)
   └→ Config Generator (manage IP configs)
```

All pages have "Back to Overview" button to return to dashboard.

## Where to Look

**Add a new page**:
1. Create `services/frontend-service/app/web/src/pages/NewPage.tsx`
2. Add route in `App.tsx`
3. Add navigation link in `Layout.tsx`

**Add a new API endpoint**:
1. Add function to appropriate API module in `src/api/`
2. Use in page component with SWR

**Change styling**:
- All pages use **Tailwind utility classes**
- Consistent color scheme: blue (primary), red (error), green (success), orange (warning)

**Debug data fetching**:
- Check browser DevTools Network tab
- SWR devtools available
- Console logs show API responses

## Common Patterns

### Loading State
```typescript
if (loading && !data) {
  return <div>Loading...</div>
}
```

### Error Handling
```typescript
if (error) {
  return <div>Error: {error.message}</div>
}
```

### Refresh Data
```typescript
const { data, mutate } = useSWR(...)
await mutate() // Trigger refresh
```

### Navigate Programmatically
```typescript
import { useNavigate } from 'react-router-dom'
const navigate = useNavigate()
navigate('/videos')
```

## Development

**Run frontend locally**:
```bash
cd services/frontend-service/app/web
npm install
npm run dev
```

Frontend runs on **http://localhost:5173** (Vite default port).

**Build for production**:
```bash
npm run build
```

Output: `dist/` directory with static assets.
