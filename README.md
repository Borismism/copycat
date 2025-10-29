# Copycat - AI Copyright Detection System

AI-powered copyright violation detection targeting AI-generated Justice League content at scale.

## 🚀 Quick Start

```bash
# Start local environment (from project root)
./scripts/dev-local.sh

# Access services
open http://localhost:8080/docs  # Discovery Service API
```

**That's it!** All emulators and services start automatically.

## 📋 Prerequisites

- **Docker Desktop** installed and running
- **YouTube API Key**: Already configured in `.env`

## 🏗️ Architecture

```
COPYCAT PIPELINE

1. Discovery Service (PORT 8080) ✅ COMPLETE
   ↓ Finds AI-generated Justice League videos
   ↓ Publishes to: discovered-videos topic

2. Risk Scorer Service (PORT 8081) [TODO]
3. Chapter Extractor Service (PORT 8082) [TODO]
4. Frame Extractor Service (PORT 8083) [TODO]
5. Vision Analyzer Service (PORT 8084) [TODO]
```

### Infrastructure (Shared Emulators)

- **Firestore** (port 8200) - Document database
- **PubSub** (port 8085) - Event messaging
- **Cloud Storage** (port 4443) - Frame storage

## 🔧 Development

```bash
# Start environment
./scripts/dev-local.sh

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Hot Reload

Edit any Python file in `services/*/app/` - service auto-restarts!

### Run Tests

```bash
cd services/discovery-service
uv run pytest -v --cov
# 165 tests, 95% coverage
```

### API Testing

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/discover
curl http://localhost:8080/discover/channels
```

## 📁 Structure

```
copycat/
├── docker-compose.yml       # All services + emulators
├── .env                     # API keys (gitignored)
├── scripts/
│   ├── dev-local.sh        # Start local environment
│   ├── init-pubsub.sh      # Initialize PubSub
│   └── deploy-service.sh   # Deploy to GCP
└── services/
    ├── discovery-service/  # ✅ COMPLETE (160 LOC, 95% coverage)
    └── [other services]    # 🚧 TODO
```

## 🎯 Discovery Service Features

- **Smart Orchestration**: 70% channels, 20% trending, 10% keywords
- **Channel Intelligence**: 5-tier system (Platinum → Ignore)
- **Quota Management**: 10,000 units/day with 80% warning
- **Deduplication**: 30-day Firestore lookback
- **View Velocity**: Trending score 0-100

## 🚀 Deployment

```bash
# Setup GCP (run once)
./scripts/setup-infra.sh

# Deploy to dev
./scripts/deploy-service.sh discovery-service dev

# Deploy to prod
./scripts/deploy-service.sh discovery-service prod
```

## 📚 Documentation

- [Discovery Service README](services/discovery-service/README.md)
- [Docker Setup Guide](services/discovery-service/README.docker.md)
- [Planning Docs](.planning/)

## 🛠️ Tech Stack

- Python 3.13 + UV
- FastAPI 0.119.1
- google-genai 1.46.0
- GCP Cloud Run + Firestore + PubSub
- Docker Compose

---

**Built with Claude Code** 🤖
