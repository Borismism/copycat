# Discovery Service

> Part of [Copycat](../../README.md) | Next: [Risk Analyzer](../risk-analyzer-service/README.md)

Finds YouTube videos that might contain AI-generated Justice League content. This is the first step in the Copycat pipeline.

## What It Does

- Searches YouTube for videos matching target keywords
- Tracks channels known to post infringing content
- Monitors trending videos for early detection
- Manages YouTube API quota (10k units/day)
- Publishes discovered videos to Pub/Sub for downstream processing

## Discovery Strategy

The service allocates quota across three discovery methods:

1. **Channel tracking (70%)** - Scan channels with history of infringements. Most efficient at 3 units per channel.
2. **Trending videos (20%)** - Check trending/popular videos. Cheap at 1 unit per 50 videos.
3. **Keyword search (10%)** - Direct searches for target keywords. Expensive at 100 units per search.

## Channel Tiers

Channels are automatically categorized based on their infringement history:

| Tier | Scan Frequency | Criteria |
|------|----------------|----------|
| PLATINUM | Daily | >50% infringement rate |
| GOLD | Every 3 days | 25-50% infringement |
| SILVER | Weekly | 10-25% infringement |
| BRONZE | Monthly | <10% infringement |
| IGNORE | Never | Clean after 20+ videos |

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /discover` | Run discovery cycle |
| `GET /discover/channels` | List tracked channels |
| `GET /discover/quota` | Current quota usage |

## Configuration

Keywords and IP targets are configured in Firestore under `discovery_config`. Cloud Scheduler triggers discovery runs hourly.

## Deployment

```bash
./deploy.sh discovery-service dev   # Deploy to dev
./deploy.sh discovery-service prod  # Deploy to prod
```

## Environment Variables

Set via Terraform:

```
YOUTUBE_API_KEY         - YouTube API key (from Secret Manager)
GCP_PROJECT_ID          - GCP project
PUBSUB_TOPIC            - Topic to publish discovered videos
```
