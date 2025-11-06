#!/bin/bash
# ==============================================================================
# DEPLOY COPYCAT TO BORIS-DEMO-453408
# ==============================================================================

set -e

echo "🚀 Starting Copycat deployment to boris-demo-453408..."
echo ""

# 1. Authenticate
echo "📝 Step 1: Authenticating..."
gcloud auth application-default login

# 2. Set project
echo "📝 Step 2: Setting project..."
gcloud config set project boris-demo-453408

# 3. Create state bucket
echo "📝 Step 3: Creating Terraform state bucket (copycat-state)..."
gsutil mb -p boris-demo-453408 -l europe-west4 gs://copycat-state 2>/dev/null || echo "Bucket already exists"
gsutil versioning set on gs://copycat-state
gsutil uniformbucketlevelaccess set on gs://copycat-state

# 4. Enable APIs
echo "📝 Step 4: Enabling required APIs (this takes ~3 minutes)..."
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

# 5. Create Firestore database
echo "📝 Step 5: Creating Firestore database..."
gcloud firestore databases create --location=europe-west4 2>/dev/null || echo "Firestore already exists"

# 6. Deploy global infrastructure
echo "📝 Step 6: Deploying global infrastructure..."
./deploy.sh infra dev

# 7. Get load balancer IP for DNS
echo ""
echo "=================================="
echo "🎉 INFRASTRUCTURE DEPLOYED!"
echo "=================================="
echo ""
echo "📍 Next Step: Configure DNS"
echo ""
echo "Run this command to get the load balancer IP:"
echo ""
echo "  gcloud compute addresses describe copycat-frontend-lb-ip \\"
echo "    --global \\"
echo "    --project=boris-demo-453408 \\"
echo "    --format='value(address)'"
echo ""
echo "Then add DNS A record:"
echo "  Domain: copycat-dev.borism.nl"
echo "  Type: A"
echo "  Value: <ip-from-above>"
echo ""
echo "After DNS is configured, deploy services with:"
echo "  ./deploy.sh all dev"
echo ""
