# Copycat - Quick Start Guide

## 📝 What You Need to Fill In

### 1. Create Two GCP Projects
- Development: `your-dev-project-id`
- Production: `your-prod-project-id`

### 2. Fill In Configuration Files

**terraform_global_config/terraform.tfvars** (Production):
```hcl
project_id            = "your-prod-project-id"        # ← YOUR PROJECT
github_repository     = "your-org/copycat"            # ← YOUR GITHUB REPO
frontend_domain       = "copycat.yourcompany.com"     # ← YOUR DOMAIN
iap_support_email     = "support@yourcompany.com"     # ← YOUR EMAIL
iap_authorized_users  = ["user:you@yourcompany.com"] # ← YOUR USERS
```

**terraform_global_config/dev.tfvars** (Development):
```hcl
project_id            = "your-dev-project-id"         # ← YOUR DEV PROJECT
github_repository     = "your-org/copycat"            # ← SAME GITHUB REPO
frontend_domain       = "copycat-dev.yourcompany.com" # ← YOUR DEV DOMAIN
iap_support_email     = "dev@yourcompany.com"         # ← YOUR DEV EMAIL
iap_authorized_users  = ["user:you@yourcompany.com"] # ← YOUR USERS
```

**terraform_global_config/backend_config.hcl** (Production):
```hcl
bucket = "tf-state-your-prod-project-id"              # ← YOUR STATE BUCKET
```

**terraform_global_config/backend_config_dev.hcl** (Development):
```hcl
bucket = "tf-state-your-dev-project-id"               # ← YOUR DEV STATE BUCKET
```

**terraform_global_config/global_shell_vars.sh**:
```bash
GCP_PROJECT_ID="your-prod-project-id"                 # ← YOUR PROD PROJECT
TF_STATE_BUCKET="tf-state-your-prod-project-id"       # ← YOUR STATE BUCKET
```

---

## 🚀 One-Time Setup (Dev Project)

```bash
# Set variables
export DEV_PROJECT="your-dev-project-id"

# Switch to dev project
gcloud config set project $DEV_PROJECT

# Create state bucket
gsutil mb -p $DEV_PROJECT -l europe-west4 gs://tf-state-${DEV_PROJECT}
gsutil versioning set on gs://tf-state-${DEV_PROJECT}

# Enable APIs (takes ~3 minutes)
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

# Create Firestore database (takes ~60 seconds)
gcloud firestore databases create --location=europe-west4
```

---

## 🚀 One-Time Setup (Prod Project)

```bash
# Set variables
export PROD_PROJECT="your-prod-project-id"

# Switch to prod project
gcloud config set project $PROD_PROJECT

# Create state bucket
gsutil mb -p $PROD_PROJECT -l europe-west4 gs://tf-state-${PROD_PROJECT}
gsutil versioning set on gs://tf-state-${PROD_PROJECT}

# Enable APIs (takes ~3 minutes)
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

# Create Firestore database (takes ~60 seconds)
gcloud firestore databases create --location=europe-west4
```

---

## 🎯 Deploy Everything

```bash
# Authenticate
gcloud auth application-default login

# Deploy to dev
./deploy.sh infra dev        # Deploy global infrastructure
./deploy.sh all dev          # Deploy all services

# Deploy to prod (after testing dev)
./deploy.sh infra prod       # Deploy global infrastructure
./deploy.sh all prod         # Deploy all services
```

---

## 🌐 Post-Deployment DNS Setup

```bash
# Get load balancer IP
gcloud compute addresses describe copycat-frontend-lb-ip \
  --global \
  --project=your-dev-project-id \
  --format='value(address)'
```

**Add DNS A Record:**
- Name: `copycat-dev.yourcompany.com`
- Type: `A`
- Value: `<ip-from-above>`
- TTL: `300`

**Wait 15-30 minutes for SSL certificate to auto-provision**

---

## 📊 Verify Deployment

```bash
# Check Cloud Run services
gcloud run services list --project=your-dev-project-id

# Check API health
curl https://api-service-xxx.a.run.app/health

# Check frontend (requires IAP login)
open https://copycat-dev.yourcompany.com
```

---

## 🔄 Deploy Single Service

```bash
# Deploy just one service
./deploy.sh discovery-service dev
./deploy.sh vision-analyzer-service prod
```

---

## 💰 Costs

- **Infrastructure**: ~$35-75/month
- **Gemini API**: ~$260/day (€240)
- **YouTube API**: Free (10k units/day)

**Total**: ~$8,000/month

---

## 🎉 You're Done!

Frontend: https://copycat-dev.yourcompany.com (IAP protected)
API: https://api-service-xxx.a.run.app

**Next Steps:**
1. Request YouTube API quota increase (if needed)
2. Monitor Gemini budget usage
3. Set up GitHub Actions CI/CD
4. Add monitoring/alerting
