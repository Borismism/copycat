# Risk Analyzer Service

> Part of [Copycat](../../README.md) | Prev: [Discovery](../discovery-service/README.md) | Next: [Vision Analyzer](../vision-analyzer-service/README.md)

Scores and prioritizes videos for analysis. Sits between discovery and vision analysis to ensure we spend our Gemini budget on the highest-value videos first.

## What It Does

- Receives discovered videos from Pub/Sub
- Calculates risk scores based on multiple factors
- Maintains channel risk profiles
- Prioritizes videos for vision analysis
- Tracks view velocity to catch viral content early

## How Risk Scoring Works

Each video gets a composite score (0-100) based on:

- **Channel history** - Has this channel posted infringing content before?
- **Metadata signals** - Keywords in title, description, tags
- **View velocity** - How fast is the video gaining views?
- **Video characteristics** - Duration, upload time, etc.

The formula weights channel risk (40%) and video risk (60%) to produce a final `scan_priority` score. High-scoring videos get analyzed first.

## Priority Tiers

| Tier | Score | Action |
|------|-------|--------|
| CRITICAL | 80+ | Analyze immediately |
| HIGH | 60-79 | Analyze within hours |
| MEDIUM | 40-59 | Analyze within days |
| LOW | 20-39 | Lower priority |
| VERY_LOW | <20 | Only if budget allows |

## Adaptive Learning

When the vision analyzer completes, it sends feedback back here. We update the channel's risk profile based on whether infringement was found, then rescore all pending videos from that channel. This creates a feedback loop where known-bad channels get prioritized higher over time.

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /webhook/discovered-video` | Pub/Sub push for new videos |
| `POST /webhook/vision-feedback` | Receives analysis results |
| `GET /admin/stats` | Risk scoring statistics |

## Deployment

```bash
./deploy.sh risk-analyzer-service dev   # Deploy to dev
./deploy.sh risk-analyzer-service prod  # Deploy to prod
```

## Environment Variables

Set via Terraform:

```
GCP_PROJECT_ID          - GCP project
FIRESTORE_DATABASE      - Database name
SCAN_READY_TOPIC        - Pub/Sub topic for queuing analysis
```
