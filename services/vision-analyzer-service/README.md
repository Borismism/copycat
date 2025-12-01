# Vision Analyzer Service

> Part of [Copycat](../../README.md) | Prev: [Risk Analyzer](../risk-analyzer-service/README.md)

Uses Gemini 2.5 Flash to analyze videos for Justice League character appearances. This is where the actual AI detection happens.

## What It Does

- Receives high-priority videos from the scan-ready Pub/Sub topic
- Analyzes videos using Gemini's video understanding capabilities
- Detects specific characters (Superman, Batman, Wonder Woman, etc.)
- Identifies AI generation markers (Sora, Runway, Kling, Pika artifacts)
- Stores detailed analysis results in Firestore
- Manages daily budget (~$260/day for Gemini)

## How Analysis Works

1. Video URL is passed to Gemini 2.5 Flash
2. Model analyzes frames at configurable FPS
3. Prompts are tailored to detect specific characters and AI artifacts
4. Results include character detections, confidence scores, and timestamps
5. Results feed back to risk analyzer to improve channel scoring

## FPS Strategy

Longer videos get lower FPS to manage costs:

| Duration | FPS | Rationale |
|----------|-----|-----------|
| 0-2 min | 1.0 | Short clips, full coverage |
| 2-5 min | 0.5 | Balanced |
| 5-10 min | 0.33 | Reduced sampling |
| 10-20 min | 0.25 | Key frames only |
| 20+ min | 0.1-0.2 | Minimal sampling |

High-risk videos get a 1.5-2x multiplier on FPS.

## Budget Management

The service tracks daily spending against a configurable budget:

- Default: ~$260/day (EUR 240)
- Pauses processing when budget is exhausted
- Resets at midnight UTC
- Prioritizes high-risk videos when budget is limited
- Capacity: 20-30k videos/day depending on length mix

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /analyze` | Pub/Sub push endpoint for scan requests |
| `GET /admin/budget` | Current budget usage |
| `GET /admin/stats` | Analysis statistics |

## Deployment

```bash
./deploy.sh vision-analyzer-service dev   # Deploy to dev
./deploy.sh vision-analyzer-service prod  # Deploy to prod
```

## Environment Variables

Set via Terraform:

```
GCP_PROJECT_ID          - GCP project
FIRESTORE_DATABASE      - Database name
GEMINI_MODEL            - Model to use (default: gemini-2.0-flash-exp)
DAILY_BUDGET_EUR        - Daily budget limit
```
