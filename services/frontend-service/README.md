# Frontend Service

> Part of [Copycat](../../README.md) | Related: [API Service](../api-service/README.md)

A React dashboard served by a FastAPI backend. The backend handles IAP authentication and proxies API requests to the api-service.

## What It Does

- Serves the React SPA (built static files)
- Proxies `/api/*` requests to api-service with IAM authentication
- Forwards IAP headers for user identification
- Handles SSE streaming for real-time updates

## Architecture

```
Browser → IAP → Frontend Service (FastAPI) → API Service → Firestore
                       ↓
                  React SPA
```

The frontend service exists to:
1. Handle service-to-service authentication (IAM tokens)
2. Forward IAP user identity headers
3. Serve static files with proper caching

## Pages

- **Dashboard** - KPI cards, activity charts, system health
- **Videos** - Browse and scan individual videos
- **Channels** - Channel management and bulk scanning
- **Scan History** - Real-time scan progress and history
- **Discovery** - Trigger discovery runs manually
- **Config** - IP configuration management (admin)
- **User Roles** - Role assignment (admin)

## Authentication

Users access the frontend through Google IAP. IAP validates their Google account and sets headers that identify the user. The frontend reads these headers and fetches the user's role from Firestore.

## Deployment

```bash
./deploy.sh frontend-service dev   # Deploy to dev
./deploy.sh frontend-service prod  # Deploy to prod
```

## Environment Variables

Set via Terraform:

```
API_SERVICE_URL     - URL to api-service
ENVIRONMENT         - dev/prod
```
