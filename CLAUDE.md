# CLAUDE.md

Guidelines for Claude Code when working with this repository.

## ⚠️ CRITICAL: Python Execution

**ALWAYS use:**
- `uv run python3 <script>` - Local scripts
- `docker-compose exec <service> python <script>` - Service scripts
- `FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 <script>` - Scripts needing Firestore

**NEVER:** `python3 <script>` directly - system Python doesn't have dependencies!

## Troubleshooting

**Stuck videos (>5 min processing):**
```bash
FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 scripts/reset-stuck-video.py <video_id>
```

**Unhealthy service:** Check logs first: `docker-compose logs <service> --tail 50`

**Firestore errors:** `docker-compose restart firestore`

## Project Overview

AI-generated content detection system targeting Justice League characters (Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern) in AI-generated videos (Sora, Runway, Kling, Pika).

**Pipeline:**
1. **discovery-service** → Finds videos via YouTube API + channel tracking
2. **risk-analyzer-service** → Adaptive risk scoring with view velocity
3. **vision-analyzer-service** → Gemini 2.5 Flash analysis (€240/day budget)

**Key Features:**
- Intelligent channel tracking (Platinum/Gold/Silver/Bronze tiers)
- View velocity tracking for viral detection
- Budget exhaustion model (20k-32k videos/day)
- Length-based FPS optimization

## Quick Start

**Setup:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && uv sync --group dev
./scripts/setup-infra.sh  # Deploy GCP infrastructure (once)
```

**Development:**
```bash
./scripts/dev-local.sh <service>     # Run with emulators
uv run pytest --cov=app              # Test with coverage
uv run ruff format . && uv run ruff check .  # Lint
```

**Deployment:**
```bash
./deploy.sh <service-name> dev   # Deploy to dev
./deploy.sh <service-name> prod  # Deploy to prod
# Or: push to develop→dev, main→prod (auto)
```

**Docker Compose:**
```bash
docker-compose up -d                         # Start all
docker-compose logs -f <service>             # View logs
```

**Ports:** api:8080, discovery:8081, risk-analyzer:8082, vision-analyzer:8083, frontend:5173, firestore:8200, pubsub:8085

## Architecture

**Pipeline:**
- discovery-service → discovered-videos topic → risk-analyzer-service → scan-ready topic → vision-analyzer-service → Firestore/BigQuery

**Tech Stack:**
- Python 3.13 + UV package manager
- FastAPI 0.119.1
- google-genai 1.46.0 (Vertex AI)
- GCP: Cloud Run, Firestore, PubSub, Storage, BigQuery

**Infrastructure:**
- `terraform/` - Shared (Artifact Registry, PubSub, Firestore, BigQuery, IAM)
- `services/*/terraform/` - Per-service (Cloud Run, subscriptions, env vars)

## Service Structure

```
services/<service>/
├── app/{main.py, core/, routers/, models.py}
├── terraform/{provider.tf, main.tf, variables.tf}
├── tests/
└── {Dockerfile, cloudbuild.yaml, pyproject.toml}
```

## Key Implementation Details

**Gemini SDK (Vertex AI with IAM):**
```python
from google import genai
from google.auth import default

credentials, project = default()
client = genai.Client(vertexai=True, project=project, location='us-central1')
response = client.models.generate_content(model='gemini-2.0-flash-exp', contents=[prompt, image])

# ❌ Don't use: genai.Client(api_key=...) or google.generativeai (EOL Aug 2025)
```

**Config:** Use `pydantic-settings` with `.env` (local) / env vars (Cloud Run). YouTube API key in Secret Manager.


## Discovery Service

**Channel Tier System:** PLATINUM (daily), GOLD (3d), SILVER (weekly), BRONZE (monthly), IGNORE (never)

**YouTube API Quota (10k units/day):**
- Channel tracking: 3 units (70% allocation, 30x more efficient than keyword search)
- Trending check: 1 unit (20%)
- Keyword search: 100 units (10%)

**View Velocity:** Trending score 0-100 based on views/hour for viral detection

**Budget:** €240/day ($260), Gemini 2.5 Flash, 20k-32k videos/day capacity

**Pricing (Vertex AI):**
- Input: $0.30/1M tokens (100 tokens/sec @ 1 FPS: 66 frames + 32 audio)
- Output: $2.50/1M tokens

**Length-Based FPS Optimization:**
- 0-2min: 1.0 FPS | 2-5min: 0.5 FPS | 5-10min: 0.33 FPS
- 10-20min: 0.25 FPS | 20-30min: 0.2 FPS | 30-60min: 0.1 FPS | 60+min: 0.05 FPS
- Risk multipliers: CRITICAL 2.0x, HIGH 1.5x, MEDIUM 1.0x, LOW 0.75x, VERY_LOW 0.5x

**Cost:** 5min video @ 0.5 FPS = $0.008, 30min @ 0.2 FPS = $0.017

**Prompt Focus:** Justice League only (Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern), fast-reject non-target characters, detect AI-gen markers (Sora, Runway, Kling, Pika)
