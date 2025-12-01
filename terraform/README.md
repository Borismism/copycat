# Terraform Infrastructure

> Part of [Copycat](../README.md)

This directory contains the shared GCP infrastructure for Copycat. Each service also has its own `terraform/` directory for service-specific resources (Cloud Run, subscriptions, etc.).

## GCP Services Used

### Firestore (firestore.tf)
**Purpose**: Primary database for all application data.

We use Firestore in Native mode for:
- Video metadata and analysis results
- Channel profiles and risk scores
- Discovery configuration (keywords, IP targets)
- User roles and authentication
- Budget tracking and system stats

Why Firestore: Real-time updates, automatic scaling, good integration with Cloud Run. The document model fits our data well (videos, channels, configs).

### Pub/Sub (pubsub.tf)
**Purpose**: Async communication between services.

Topics:
- `copycat-video-discovered` - Discovery → Risk Analyzer
- `scan-ready` - Risk Analyzer → Vision Analyzer
- `vision-feedback` - Vision Analyzer → Risk Analyzer (feedback loop)
- `copycat-dead-letter` - Failed messages

Why Pub/Sub: Decouples services, handles retries automatically, scales with load. Push subscriptions integrate nicely with Cloud Run.

### Artifact Registry (artifact_registry.tf)
**Purpose**: Docker image storage.

Repository: `copycat-docker`

All service images are pushed here during CI/CD, then deployed to Cloud Run.

### Cloud Scheduler (scheduler.tf)
**Purpose**: Scheduled jobs.

Jobs:
- Discovery runs (hourly by default)
- Daily stats aggregation
- Stuck video cleanup

### IAP - Identity-Aware Proxy (iap.tf)
**Purpose**: Authentication for the frontend.

Protects the frontend with Google login. Users must be in the authorized list to access the dashboard. The frontend service receives IAP headers with user identity.

### Secrets Manager (secrets.tf)
**Purpose**: API keys and sensitive config.

Stores:
- YouTube API key
- Any other secrets needed by services

Services access secrets via environment variables injected by Cloud Run.

### Workload Identity Federation (wif.tf)
**Purpose**: Keyless authentication for CI/CD.

Allows GitHub Actions / GitLab CI to deploy without storing service account keys. The CI runner authenticates via OIDC and gets temporary credentials.

## File Overview

| File | What it creates |
|------|-----------------|
| `firestore.tf` | Database + all indexes |
| `firestore_indexes.tf` | Additional composite indexes |
| `pubsub.tf` | Topics for service communication |
| `artifact_registry.tf` | Docker image repository |
| `scheduler.tf` | Cron jobs |
| `iap.tf` | OAuth consent + IAP configuration |
| `secrets.tf` | Secret Manager secrets |
| `wif.tf` | Workload Identity for CI/CD |
| `api-keys.tf` | API key management |
| `gitlab-ci.tf` | GitLab-specific CI resources |

## Usage

### Initial Setup

```bash
cd terraform

# Initialize (first time or after provider changes)
terraform init \
  -backend-config="bucket=YOUR_PROJECT-terraform-state"

# Plan changes
terraform plan -var-file="../terraform_global_config/dev.tfvars"

# Apply
terraform apply -var-file="../terraform_global_config/dev.tfvars"
```

### Environment-Specific Config

Config files live in `terraform_global_config/`:
- `dev.tfvars` - Development environment
- `prod.tfvars` - Production environment

### State Storage

Terraform state is stored in GCS bucket `{project_id}-terraform-state`. This bucket must exist before running terraform init.

## Variables

Key variables (see `variables.tf` for full list):

| Variable | Description |
|----------|-------------|
| `project_id` | GCP project ID |
| `region` | Primary region (default: europe-west4) |
| `environment` | dev or prod |
| `firestore_database` | Database name (default: copycat) |
| `youtube_daily_quota` | YouTube API quota limit |
| `daily_budget_usd` | Gemini daily budget |
| `frontend_domain` | Custom domain for IAP |
| `iap_authorized_users` | List of authorized users |

## Adding New Resources

1. Create a new `.tf` file or add to existing one
2. Run `terraform plan` to preview changes
3. Run `terraform apply` to create resources
4. If adding indexes, they take a few minutes to build

## Notes

- Firestore indexes can take several minutes to create
- IAP changes require OAuth consent screen configuration
- Some resources (like Workload Identity pools) have naming restrictions
- Deleting Firestore indexes requires manual intervention in some cases
