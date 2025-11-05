# Frontend Documentation

This directory contains detailed documentation for each page in the Copycat frontend.

## Documentation Index

| # | Page | Route | Purpose |
|---|------|-------|---------|
| 0 | [Overview](00-OVERVIEW.md) | - | Architecture, routing, data fetching patterns |
| 1 | [Dashboard](01-Dashboard.md) | `/` | System overview and real-time metrics |
| 2 | [Discovery Page](02-DiscoveryPage.md) | `/discovery` | YouTube discovery control and quota management |
| 3 | [Risk Analyzer](03-RiskAnalyzerPage.md) | `/risk` | Risk scoring dashboard and velocity tracking |
| 4 | [Vision Analyzer](04-VisionAnalyzerPage.md) | `/vision` | Gemini analysis control and budget management |
| 5 | [Video List](05-VideoListPage.md) | `/videos` | Video browser with filtering and scanning |
| 6 | [Channel List](06-ChannelListPage.md) | `/channels` | Channel tracking and risk profiles |
| 7 | [Config Generator](07-ConfigGeneratorPage.md) | `/config` | AI-powered IP configuration manager |

## Quick Start

**New to the frontend?** Start here:
1. Read [00-OVERVIEW.md](00-OVERVIEW.md) for architecture and patterns
2. Explore individual page docs based on what you're working on
3. Use "Where to Look" sections to find specific functionality

## Documentation Structure

Each page document follows this structure:

### 1. Header
- Route path
- File location

### 2. Purpose
- What the page does
- Why it exists

### 3. What It Shows
- UI components breakdown
- Data visualizations
- Interactive elements

### 4. Data Sources
- API endpoints used
- Refresh rates
- Data models

### 5. Key Features
- Important functionality
- User interactions
- Real-time updates

### 6. Where to Look
- Code locations for common modifications
- Examples of how to change things
- File paths and line numbers

### 7. Common Issues
- Known problems
- Debugging tips
- Solutions

### 8. Related Files
- Component files
- API clients
- Backend endpoints

## Finding What You Need

### Adding a New Feature

**I want to add a new metric to the Dashboard**:
→ See [01-Dashboard.md](01-Dashboard.md) → "Where to Look" → "Add new metric card"

**I want to add a new filter to Videos**:
→ See [05-VideoListPage.md](05-VideoListPage.md) → "Where to Look" → "Change filter options"

**I want to add a new AI suggestion type**:
→ See [07-ConfigGeneratorPage.md](07-ConfigGeneratorPage.md) → "Where to Look" → "Add new section type"

### Fixing a Bug

**Dashboard not loading**:
→ See [01-Dashboard.md](01-Dashboard.md) → "Common Issues" → "Failed to load dashboard"

**SSE progress not updating**:
→ See [02-DiscoveryPage.md](02-DiscoveryPage.md) → "Common Issues" → "SSE connection fails"

**Video scan button doesn't work**:
→ See [05-VideoListPage.md](05-VideoListPage.md) → "Common Issues" → "Scan button doesn't work"

### Understanding Data Flow

**How does discovery work?**:
→ See [02-DiscoveryPage.md](02-DiscoveryPage.md) → "How Discovery Works"

**How does risk scoring work?**:
→ See [03-RiskAnalyzerPage.md](03-RiskAnalyzerPage.md) → "How Risk Scoring Works"

**How does Gemini analysis work?**:
→ See [04-VisionAnalyzerPage.md](04-VisionAnalyzerPage.md) → "How Vision Analysis Works"

**How does config generation work?**:
→ See [07-ConfigGeneratorPage.md](07-ConfigGeneratorPage.md) → "How It Works Internally"

## Tech Stack Reference

**Framework**: React 18 + TypeScript
**Routing**: React Router v6
**Data Fetching**: SWR (stale-while-revalidate)
**Styling**: Tailwind CSS 3
**Build Tool**: Vite 5
**Real-Time**: Server-Sent Events (SSE)

## Common Patterns

### Data Fetching with SWR
```typescript
const { data, error, mutate } = useSWR(
  'cache-key',
  () => apiClient.getData(),
  { refreshInterval: 30000 } // 30 seconds
)
```

### Loading States
```typescript
if (!data) return <div>Loading...</div>
if (error) return <div>Error: {error.message}</div>
```

### Navigation
```typescript
import { Link } from 'react-router-dom'
<Link to="/videos">View Videos</Link>
```

### Server-Sent Events
```typescript
const eventSource = new EventSource('/api/endpoint')
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  // Handle data
}
```

## File Locations

### Pages
`services/frontend-service/app/web/src/pages/`
- Dashboard.tsx
- DiscoveryPage.tsx
- RiskAnalyzerPage.tsx
- VisionAnalyzerPage.tsx
- VideoListPage.tsx
- ChannelListPage.tsx
- ConfigGeneratorPage.tsx

### Components
`services/frontend-service/app/web/src/components/`
- SystemHealthBanner.tsx
- MetricsGrid.tsx
- ActivityTimeline.tsx
- ScanProgressModal.tsx
- AnalysisDetailModal.tsx
- EditableTagsSection.tsx
- etc.

### API Clients
`services/frontend-service/app/web/src/api/`
- status.ts
- discovery.ts
- videos.ts
- channels.ts
- vision.ts
- analytics.ts

### Types
`services/frontend-service/app/web/src/types/index.ts`

## Contributing to Docs

When adding new features, please update the relevant documentation:
1. Find the appropriate page doc (or create a new one)
2. Add to "What It Shows" section
3. Update "Data Sources" if using new API
4. Add to "Key Features" if significant
5. Document in "Where to Look" with file paths
6. Add common issues you encountered

## Questions?

If something is unclear or missing:
1. Check the [CLAUDE.md](../../CLAUDE.md) for system-level documentation
2. Review the code directly (use the file paths in docs)
3. Ask in team chat or open an issue
