# Discovery Service

The first microservice in the Copycat pipeline - discovers YouTube videos containing AI-generated Justice League character content for copyright infringement analysis.

## 🚀 Quick Start

### Local Development (Docker - RECOMMENDED)

```bash
# One-command launch with emulators
./scripts/dev-local-docker.sh

# Or use Make
make dev-docker
```

**See [README.docker.md](README.docker.md) for complete Docker setup guide.**

### Local Development (Native)

```bash
# Install dependencies
uv sync

# Start emulators in separate terminals
gcloud beta emulators firestore start --host-port=0.0.0.0:8200
gcloud beta emulators pubsub start --host-port=0.0.0.0:8085

# Set environment
export FIRESTORE_EMULATOR_HOST=localhost:8200
export PUBSUB_EMULATOR_HOST=localhost:8085

# Run service
uv run python -m uvicorn app.main:app --reload --port 8080
```

## Purpose

The Discovery Service finds YouTube videos that contain AI-generated Justice League character content:
- **Target Characters**: Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern
- **AI Tools**: Sora, Runway, Kling, Pika, Luma, etc.
- **Strategy**: Intelligent quota-aware discovery with channel tracking

## Architecture

### New Design (Epic 3 - CURRENT)

**Clean, lean, intelligent orchestration:**

```
DiscoveryEngine (160 LOC, 95% coverage)
├── 70% quota: Channel tracking (most efficient - 3 units/channel)
├── 20% quota: Trending videos (cheap - 1 unit/50 videos)
└── 10% quota: Targeted keywords (expensive - 100 units/search)
```

**Components:**
- `DiscoveryEngine`: Smart orchestrator with quota allocation
- `ChannelTracker`: Tier-based channel intelligence (Platinum → Ignore)
- `VideoProcessor`: Deduplication, IP matching, save/publish
- `QuotaManager`: Real-time quota tracking with warnings
- `ViewVelocityTracker`: Trending score calculation

### API Endpoints

**4 clean endpoints (replaced 292-line router):**

```bash
# Main discovery - runs until quota exhausted
POST /discover

# List tracked channels
GET /discover/channels?tier=platinum&limit=50

# Performance metrics
GET /discover/analytics/discovery

# Quota status
GET /discover/quota
```

## Key Features

### 1. Configurable IP Targets

Define IP targets in `data/ip_targets.yaml`:

```yaml
targets:
  - name: "Superman"
    type: "character"
    keywords:
      - "Superman AI"
      - "Superman generated"
      - "AI Superman"
    owner: "Warner Bros. Discovery / DC Comics"
    enabled: true
    priority: "high"
```

**Only enabled IP targets are monitored**.

### 2. Channel Intelligence System

5-tier channel tracking based on infringement history:

| Tier | Scan Frequency | Criteria |
|------|---------------|----------|
| **PLATINUM** | Daily | >50% infringement rate, >10 violations |
| **GOLD** | Every 3 days | 25-50% infringement, >5 violations |
| **SILVER** | Weekly | 10-25% infringement |
| **BRONZE** | Monthly | <10% infringement |
| **IGNORE** | Never | 0% after 20+ videos |

### 3. Quota Management

Smart YouTube API quota allocation:
- Daily limit: 10,000 units (default, request increase)
- Real-time tracking with Firestore persistence
- 80% warning threshold
- Cost-aware operation selection

**Operation Costs:**
- Search: 100 units
- Video details: 1 unit (per 50 videos)
- Channel details: 3 units
- Trending: 1 unit (per 50 videos)

### 4. Discovery Strategy

**Priority order (quota-aware):**

1. **Channel Tracking** (70% quota)
   - Scan channels due for refresh based on tier
   - 3 units per channel
   - Most efficient: high hit rate on known infringers

2. **Trending Videos** (20% quota)
   - Broad, cheap discovery
   - 1 unit per 50 videos
   - Catches viral content early

3. **Targeted Keywords** (10% quota)
   - High-priority IP targets
   - 100 units per search
   - Expensive but precise

### 5. Deduplication

- Checks Firestore before processing
- Configurable max age (default: 30 days)
- Prevents duplicate API calls and storage

### 6. View Velocity Tracking

Trending score calculation:
- Tracks view count changes over time
- Calculates views per hour
- Scores 0-100 based on velocity
- Helps prioritize viral content

## Data Flow

```
1. DiscoveryEngine.discover()
   ↓
2. YouTube API (channels/trending/keywords)
   ↓
3. VideoProcessor.process_batch()
   ├── Deduplication check (Firestore)
   ├── IP matching (keywords in title/desc/tags)
   ├── Save to Firestore
   └── Publish to PubSub
```

## Development

### Run Tests

```bash
# All tests (165 passing)
make test

# With coverage
make test-cov

# Watch mode
make test-watch
```

### Code Quality

```bash
# Lint
make lint

# Format
make format

# Fix issues
make lint-fix
```

### API Testing

```bash
# Health check
make api-health

# Trigger discovery
make api-discover

# List channels
make api-channels

# Check quota
make api-quota

# View analytics
make api-analytics

# Open API docs
make api-docs
```

### Docker Commands

```bash
# Start environment
make dev-docker

# View logs
make dev-docker-logs

# Restart service
make dev-docker-restart

# Stop services
make dev-docker-down

# Clean everything
make dev-docker-clean
```

## Testing

**Coverage (Epic 3):**
- DiscoveryEngine: 95%
- VideoProcessor: 100%
- QuotaManager: 93%
- ChannelTracker: 86%
- **Overall new code: 95%**

**165 tests passing** with comprehensive coverage:
- Unit tests for all components
- Integration tests for discovery flow
- Quota enforcement tests
- Error handling tests

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_API_KEY` | *(required)* | YouTube Data API v3 key |
| `GCP_PROJECT_ID` | `copycat-local` | GCP project ID |
| `GCP_REGION` | `us-central1` | GCP region |
| `FIRESTORE_EMULATOR_HOST` | *(local only)* | Firestore emulator address |
| `PUBSUB_EMULATOR_HOST` | *(local only)* | PubSub emulator address |
| `FIRESTORE_DATABASE_ID` | `(default)` | Firestore database |
| `PUBSUB_TOPIC_DISCOVERED_VIDEOS` | `discovered-videos` | PubSub topic name |
| `ENVIRONMENT` | `local` | Environment (local/dev/prod) |

### IP Targets Configuration

Edit `data/ip_targets.yaml` to add/modify IP targets:

```yaml
targets:
  - name: "Character Name"
    type: "character"  # character, game, movie, etc.
    keywords:
      - "keyword 1"
      - "keyword 2"
    description: "Description"
    owner: "Rights Holder"
    enabled: true      # Set to false to disable
    priority: "high"   # high, medium, low
```

## Deployment

### Deploy to GCP

```bash
# Dev environment
make deploy-dev

# Production
make deploy-prod
```

### Manual Deployment

```bash
# Dev
./scripts/deploy-service.sh discovery-service dev

# Production
./scripts/deploy-service.sh discovery-service prod
```

## Monitoring

### Health Check

```bash
curl http://localhost:8080/health
```

### Metrics

```bash
# Quota status
curl http://localhost:8080/discover/quota

# Discovery analytics
curl http://localhost:8080/discover/analytics/discovery

# Channel statistics
curl http://localhost:8080/discover/channels
```

## Troubleshooting

### Common Issues

**Docker not starting:**
- Ensure Docker Desktop is running
- Check ports 8080, 8200, 8085 are available

**API key errors:**
- Verify `YOUTUBE_API_KEY` in `.env`
- Check API key has YouTube Data API v3 enabled

**Emulator connection errors:**
- Check `FIRESTORE_EMULATOR_HOST` and `PUBSUB_EMULATOR_HOST`
- Ensure emulators are running and healthy

**Tests failing:**
- Run `uv sync` to update dependencies
- Check Python version is 3.13+

### Debug Logs

```bash
# All services
make dev-docker-logs

# Discovery service only
make dev-docker-logs-service

# Firestore emulator
make logs-firestore

# PubSub emulator
make logs-pubsub
```

## Project Structure

```
services/discovery-service/
├── app/
│   ├── core/
│   │   ├── discovery_engine.py    # Main orchestrator (160 LOC)
│   │   ├── channel_tracker.py     # Channel intelligence
│   │   ├── video_processor.py     # Video processing
│   │   ├── quota_manager.py       # Quota management
│   │   ├── view_velocity_tracker.py
│   │   ├── youtube_client.py      # YouTube API wrapper
│   │   └── ip_loader.py           # IP targets loader
│   ├── routers/
│   │   ├── discover.py            # Discovery endpoints (63 LOC)
│   │   └── health.py              # Health check
│   ├── models.py                  # Pydantic models
│   ├── config.py                  # Configuration
│   └── main.py                    # FastAPI app
├── data/
│   └── ip_targets.yaml            # IP configuration
├── tests/                         # 165 tests, 95% coverage
├── scripts/
│   ├── dev-local-docker.sh       # Docker launch script
│   └── init-pubsub.sh            # PubSub initialization
├── docker-compose.yml             # Local environment
├── Dockerfile                     # Production build
├── Dockerfile.dev                 # Development build
├── Makefile                       # Convenience commands
└── README.docker.md               # Docker guide
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Firestore Documentation](https://cloud.google.com/firestore/docs)
- [PubSub Documentation](https://cloud.google.com/pubsub/docs)
- [Docker Compose](https://docs.docker.com/compose/)

---

**Built with Claude Code** 🤖
