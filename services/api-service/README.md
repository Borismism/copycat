# API Service

> Part of [Copycat](../../README.md) | Related: [Frontend](../frontend-service/README.md), [Discovery](../discovery-service/README.md)

The central gateway for all Copycat operations. Handles authentication, authorization, and routes requests to backend services.

## What It Does

- Serves as the single entry point for the frontend
- Authenticates users via Google IAP (Identity-Aware Proxy)
- Manages role-based access control (RBAC)
- Aggregates data from Firestore for dashboards
- Proxies requests to discovery and vision services

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | System overview with activity summary |
| `GET /api/videos` | List videos with filtering/pagination |
| `POST /api/videos/{id}/scan` | Queue a video for analysis |
| `GET /api/channels` | List channels (cursor-based pagination) |
| `GET /api/analytics/hourly-stats` | Chart data for dashboards |
| `POST /api/discovery/trigger` | Start a discovery run |
| `GET /api/users/me` | Current user info |

Full API docs available at `/docs` when running.

## User Roles

| Role | Access |
|------|--------|
| ADMIN | Everything, plus user management |
| EDITOR | Trigger scans, manage configs |
| LEGAL | Edit enforcement status fields |
| READ | View-only |
| CLIENT | Limited view (no internal metrics) |
| BLOCKED | No access |

Roles are assigned per email or domain in Firestore's `user_roles` collection.

## Deployment

```bash
./deploy.sh api-service dev   # Deploy to dev
./deploy.sh api-service prod  # Deploy to prod
```

## Environment Variables

Set via Terraform:

```
GCP_PROJECT_ID          - GCP project
GCP_REGION              - Region (default: europe-west4)
FIRESTORE_DATABASE      - Database name
DISCOVERY_SERVICE_URL   - URL to discovery service
```
