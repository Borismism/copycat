# Copycat - Setup & Deployment Checklist

## 📋 Prerequisites

### 1. Create GCP Projects

Create two separate GCP projects:
- **Development**: `your-dev-project-id`
- **Production**: `your-prod-project-id`

### 2. Enable Billing

Ensure billing is enabled on both projects:
```bash
# Check billing status
gcloud beta billing projects describe your-dev-project-id
gcloud beta billing projects describe your-prod-project-id
```

### 3. Install Required Tools

```bash
# Google Cloud SDK
curl https://sdk.cloud.google.com | bash

# Terraform
brew install terraform  # macOS
# or download from https://www.terraform.io/downloads

# Authenticate
gcloud auth application-default login
```

---

## 🔧 Configuration Files to Fill In

### 1. terraform_global_config/terraform.tfvars (Production)

```hcl
# GCP Project Configuration
project_id = "your-prod-project-id"              # ← FILL THIS
region     = "europe-west4"                       # ← Change if needed

# GitHub Repository (for Workload Identity Federation)
github_repository = "your-org/copycat"            # ← FILL THIS (e.g., "acme/copycat")

# Artifact Registry
artifact_repo_id = "copycat-docker"               # ← Can change if needed

# Frontend Domain & IAP
frontend_domain      = "copycat.yourcompany.com"  # ← FILL THIS
iap_support_email    = "support@yourcompany.com"  # ← FILL THIS
iap_authorized_users = [
  "user:admin@yourcompany.com",                   # ← FILL THIS
  "group:copycat-admins@yourcompany.com"          # ← FILL THIS (optional)
]

# YouTube API Configuration
youtube_daily_quota        = "10000"              # Default quota (can request increase)
youtube_default_region     = "US"                 # Target region

# Discovery Schedule
discovery_schedule      = "0 * * * *"             # Every hour
hourly_quota_budget     = 417                     # 10,000 / 24

# Gemini Configuration
gemini_location         = "us-central1"           # Best for Gemini 2.5 Flash
daily_budget_usd        = "260"                   # €240 ≈ $260
```

### 2. terraform_global_config/dev.tfvars (Development)

```hcl
# GCP Project Configuration
project_id = "your-dev-project-id"                # ← FILL THIS
region     = "europe-west4"                       # ← Change if needed

# GitHub Repository (for Workload Identity Federation)
github_repository = "your-org/copycat"            # ← FILL THIS (same as prod)

# Artifact Registry
artifact_repo_id = "copycat-docker"               # ← Can change if needed

# Frontend Domain & IAP
frontend_domain      = "copycat-dev.yourcompany.com"  # ← FILL THIS
iap_support_email    = "dev@yourcompany.com"          # ← FILL THIS
iap_authorized_users = [
  "user:dev@yourcompany.com",                         # ← FILL THIS
  "user:yourname@yourcompany.com"                     # ← FILL THIS
]

# YouTube API Configuration (dev has separate quota)
youtube_daily_quota        = "10000"
youtube_default_region     = "US"

# Discovery Schedule (less frequent in dev to save quota)
discovery_schedule      = "0 */3 * * *"           # Every 3 hours
hourly_quota_budget     = 139                     # 10,000 / 72

# Gemini Configuration
gemini_location         = "us-central1"
daily_budget_usd        = "50"                    # Lower budget for dev
```

### 3. terraform_global_config/backend_config.hcl (Production)

```hcl
bucket = "tf-state-your-prod-project-id"          # ← FILL THIS
```

### 4. terraform_global_config/backend_config_dev.hcl (Development)

```hcl
bucket = "tf-state-your-dev-project-id"           # ← FILL THIS
```

### 5. terraform_global_config/global_shell_vars.sh (Production)

```bash
GCP_PROJECT_ID="your-prod-project-id"             # ← FILL THIS
GCP_REGION="europe-west4"                         # ← Change if needed
REPO_NAME="copycat-docker"                        # ← Can change if needed
TF_STATE_BUCKET="tf-state-your-prod-project-id"   # ← FILL THIS
```

---

## 🚀 One-Time Setup (Per Environment)

### Development Environment

```bash
# 1. Set your dev project
export DEV_PROJECT_ID="your-dev-project-id"
gcloud config set project $DEV_PROJECT_ID

# 2. Create Terraform state bucket
gsutil mb -p $DEV_PROJECT_ID -l europe-west4 gs://tf-state-${DEV_PROJECT_ID}
gsutil versioning set on gs://tf-state-${DEV_PROJECT_ID}
gsutil uniformbucketlevelaccess set on gs://tf-state-${DEV_PROJECT_ID}

# 3. Enable required APIs (takes 2-3 minutes)
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  youtube.googleapis.com \
  apikeys.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  aiplatform.googleapis.com \
  cloudscheduler.googleapis.com \
  iap.googleapis.com

# 4. Create Firestore database (takes 30-60 seconds)
gcloud firestore databases create --location=europe-west4
```

### Production Environment

```bash
# 1. Set your prod project
export PROD_PROJECT_ID="your-prod-project-id"
gcloud config set project $PROD_PROJECT_ID

# 2. Create Terraform state bucket
gsutil mb -p $PROD_PROJECT_ID -l europe-west4 gs://tf-state-${PROD_PROJECT_ID}
gsutil versioning set on gs://tf-state-${PROD_PROJECT_ID}
gsutil uniformbucketlevelaccess set on gs://tf-state-${PROD_PROJECT_ID}

# 3. Enable required APIs (takes 2-3 minutes)
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  youtube.googleapis.com \
  apikeys.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  aiplatform.googleapis.com \
  cloudscheduler.googleapis.com \
  iap.googleapis.com

# 4. Create Firestore database (takes 30-60 seconds)
gcloud firestore databases create --location=europe-west4
```

---

## 📝 GitHub Repository Setup

### Add GitHub Secrets (After Infrastructure Deployment)

After running `./deploy.sh infra dev` and `./deploy.sh infra prod`, you'll get WIF outputs.

Add these secrets to your GitHub repository:

**Settings → Secrets and variables → Actions → New repository secret**

```
GCP_WORKLOAD_IDENTITY_PROVIDER
  Value: (from terraform output wif_provider)

GCP_SERVICE_ACCOUNT
  Value: (from terraform output wif_service_account)
```

---

## 🌐 DNS Configuration (After Infrastructure Deployment)

After deploying infrastructure, configure DNS:

### Get Load Balancer IP

```bash
# For production
gcloud compute addresses describe copycat-frontend-lb-ip \
  --global \
  --project=your-prod-project-id \
  --format='value(address)'

# For development
gcloud compute addresses describe copycat-frontend-lb-ip \
  --global \
  --project=your-dev-project-id \
  --format='value(address)'
```

### Add DNS A Record

In your DNS provider (Cloudflare, Route53, etc.):

**Production:**
- Name: `copycat.yourcompany.com`
- Type: `A`
- Value: `<load-balancer-ip>`
- TTL: `300`

**Development:**
- Name: `copycat-dev.yourcompany.com`
- Type: `A`
- Value: `<load-balancer-ip>`
- TTL: `300`

**Note**: SSL certificate will auto-provision within 15-30 minutes after DNS is configured.

---

## 🎯 Deployment Order

### First Time Deployment

```bash
# 1. Deploy global infrastructure to dev
./deploy.sh infra dev

# 2. Add GitHub secrets (see above)

# 3. Configure DNS (see above)

# 4. Wait 15-30 minutes for SSL cert to provision

# 5. Deploy all services to dev
./deploy.sh all dev

# 6. Test dev environment

# 7. Deploy to production
./deploy.sh infra prod
./deploy.sh all prod
```

### Subsequent Deployments

```bash
# Deploy a single service
./deploy.sh discovery-service dev
./deploy.sh api-service prod

# Deploy all services
./deploy.sh all dev
```

---

## ✅ Verification Checklist

After deployment, verify:

### Infrastructure
- [ ] Firestore database exists
- [ ] PubSub topics created (4 topics)
- [ ] BigQuery dataset created
- [ ] Cloud Storage buckets created (2 buckets)
- [ ] Artifact Registry created
- [ ] YouTube API key in Secret Manager
- [ ] WIF configured for GitHub Actions
- [ ] IAP load balancer created
- [ ] SSL certificate provisioned

### Services
- [ ] All 5 Cloud Run services deployed
- [ ] Discovery service has Cloud Scheduler job
- [ ] Risk analyzer has 2 PubSub subscriptions
- [ ] Vision analyzer has 1 PubSub subscription
- [ ] API service is publicly accessible
- [ ] Frontend accessible via IAP

### Test
```bash
# Check API service health
curl https://api-service-xxx.a.run.app/health

# Check frontend (requires IAP login)
open https://copycat.yourcompany.com
```

---

## 💰 Cost Estimates

### Infrastructure (per month)
- Cloud Run services: $30-60
- Firestore: $1-5
- Cloud Storage: $1-2
- PubSub: $1-2
- BigQuery: $1-5
- **Total Infrastructure**: ~$35-75/month

### API Costs (per day)
- YouTube API: **Free** (10k units/day)
- Gemini API: **$260/day** (€240) - main cost
- **Total Daily**: ~$260

### Annual Cost Estimate
- Infrastructure: $420-900/year
- Gemini API: $94,900/year
- **Total**: ~$95,000-96,000/year

---

## 🔥 Quick Start Commands

```bash
# 1. Fill in all config files above
# 2. Run one-time setup for dev project
# 3. Deploy:

./deploy.sh infra dev        # Deploy global infrastructure
./deploy.sh all dev          # Deploy all services

# 4. Access frontend at https://copycat-dev.yourcompany.com
```

---

## 📚 Next Steps

After successful deployment:
1. Request YouTube API quota increase (if needed)
2. Monitor Gemini budget usage
3. Set up alerting and monitoring
4. Configure backup policies
5. Review IAP authorized users
