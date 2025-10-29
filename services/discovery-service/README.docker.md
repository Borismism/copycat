# Discovery Service - Local Development with Docker

Complete local development environment using Docker Compose with GCP emulators.

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** installed and running
- **YouTube API Key** (get from [Google Cloud Console](https://console.cloud.google.com/apis/credentials))

### One-Command Launch

```bash
./scripts/dev-local-docker.sh
```

That's it! The script will:
1. ✅ Check Docker is running
2. ✅ Create `.env` file from template (if missing)
3. ✅ Build Docker images
4. ✅ Start all services (Firestore, PubSub, Discovery Service)
5. ✅ Initialize PubSub topics and subscriptions
6. ✅ Wait for all services to be healthy
7. ✅ Display service URLs

## 📋 First Time Setup

### 1. Get YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new API key
3. Enable YouTube Data API v3

### 2. Configure Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env and add your API key
YOUTUBE_API_KEY=your-actual-key-here
```

### 3. Launch

```bash
./scripts/dev-local-docker.sh
```

## 🏗️ Architecture

The Docker Compose setup includes:

### Services

1. **Firestore Emulator** (port 8200)
   - Official Google Cloud emulator
   - Persistent data storage for videos, channels
   - Healthcheck enabled

2. **PubSub Emulator** (port 8085)
   - Official Google Cloud emulator
   - Event-driven messaging
   - Automatic topic/subscription creation

3. **PubSub Initializer**
   - One-time setup container
   - Creates all required topics and subscriptions
   - Dead letter queue configuration

4. **Discovery Service** (port 8080)
   - FastAPI application
   - Hot-reload enabled (code changes auto-reload)
   - Connected to emulators

### Network

All services run on the `copycat-network` bridge network, allowing seamless communication.

## 🔧 Development Workflow

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f discovery-service
docker-compose logs -f firestore
docker-compose logs -f pubsub
```

### Restart Service

```bash
# Restart discovery service after code changes
docker-compose restart discovery-service

# Or rebuild if dependencies changed
docker-compose up -d --build discovery-service
```

### Stop Everything

```bash
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

### Access Services

- **Discovery API**: http://localhost:8080
- **API Docs**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health
- **Firestore Emulator**: http://localhost:8200
- **PubSub Emulator**: http://localhost:8085

## 🧪 Testing the API

### Health Check

```bash
curl http://localhost:8080/health
```

### Run Discovery

```bash
# Start intelligent discovery
curl -X POST http://localhost:8080/discover

# View channels
curl http://localhost:8080/discover/channels

# Check quota status
curl http://localhost:8080/discover/quota

# View analytics
curl http://localhost:8080/discover/analytics/discovery
```

### Interactive API Docs

Visit http://localhost:8080/docs for Swagger UI with interactive API testing.

## 📊 Monitoring

### Check Service Status

```bash
docker-compose ps
```

### Health Checks

All services have health checks:
- Firestore: `curl http://localhost:8200`
- PubSub: `curl http://localhost:8085`
- Discovery: `curl http://localhost:8080/health`

### PubSub Topics

```bash
# List topics
docker-compose exec pubsub gcloud pubsub topics list --project=copycat-local

# List subscriptions
docker-compose exec pubsub gcloud pubsub subscriptions list --project=copycat-local
```

## 🔄 Hot Reload

The discovery service is configured with `--reload` flag:

1. Edit any Python file in `app/`
2. Save the file
3. Service automatically restarts
4. Changes take effect immediately

**Note:** If you change `pyproject.toml`, rebuild the image:

```bash
docker-compose up -d --build discovery-service
```

## 🐛 Troubleshooting

### "Docker is not running"

Start Docker Desktop and wait for it to be ready.

### "YouTube API key not configured"

Edit `.env` and add your real YouTube API key:
```bash
YOUTUBE_API_KEY=AIza...your-key-here
```

### Service won't start

Check logs:
```bash
docker-compose logs discovery-service
```

Common issues:
- Missing API key in `.env`
- Port 8080, 8200, or 8085 already in use
- Docker resource limits (increase in Docker Desktop settings)

### Clean Slate

```bash
# Stop everything
docker-compose down -v

# Remove all images
docker-compose down --rmi all

# Start fresh
./scripts/dev-local-docker.sh
```

### Firestore Connection Issues

Ensure `FIRESTORE_EMULATOR_HOST` is set:
```bash
docker-compose exec discovery-service env | grep FIRESTORE
```

Should show: `FIRESTORE_EMULATOR_HOST=firestore:8200`

### PubSub Connection Issues

Ensure `PUBSUB_EMULATOR_HOST` is set:
```bash
docker-compose exec discovery-service env | grep PUBSUB
```

Should show: `PUBSUB_EMULATOR_HOST=pubsub:8085`

## 📁 Directory Structure

```
services/discovery-service/
├── docker-compose.yml          # Service definitions
├── Dockerfile                  # Production build
├── Dockerfile.dev              # Development build (hot-reload)
├── .dockerignore              # Files to exclude from build
├── .env.example               # Environment template
├── .env                       # Your local config (gitignored)
├── scripts/
│   ├── dev-local-docker.sh    # Launch script
│   └── init-pubsub.sh         # PubSub initialization
├── app/                       # Application code (mounted)
└── data/
    └── ip_targets.yaml        # IP configuration
```

## 🔐 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_API_KEY` | *(required)* | YouTube Data API v3 key |
| `GCP_PROJECT_ID` | `copycat-local` | Project ID for emulators |
| `GCP_REGION` | `us-central1` | GCP region |
| `FIRESTORE_EMULATOR_HOST` | `firestore:8200` | Firestore emulator address |
| `PUBSUB_EMULATOR_HOST` | `pubsub:8085` | PubSub emulator address |
| `ENVIRONMENT` | `local` | Environment name |

## 🎯 Next Steps

1. **Add IP Targets**: Edit `data/ip_targets.yaml`
2. **Run Tests**: `uv run pytest`
3. **Deploy to GCP**: `./scripts/deploy-service.sh discovery-service dev`

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Firestore Emulator](https://cloud.google.com/firestore/docs/emulator)
- [PubSub Emulator](https://cloud.google.com/pubsub/docs/emulator)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Happy coding! 🚀**
