#!/bin/bash
set -e

# Setup global infrastructure (run once)
# Usage: ./scripts/setup-infra.sh

echo "🏗️  Setting up global infrastructure"
echo ""

# Load configuration
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Validate required variables
: ${GCP_PROJECT_ID:?'GCP_PROJECT_ID not set in .env'}
: ${GCP_REGION:?'GCP_REGION not set in .env'}

echo "📋 Configuration:"
echo "   Project: $GCP_PROJECT_ID"
echo "   Region: $GCP_REGION"
echo ""

# Set quota project for Application Default Credentials
echo "🔐 Setting quota project for ADC..."
gcloud auth application-default set-quota-project $GCP_PROJECT_ID 2>&1 | grep -v "Credentials saved" || true
echo "   ✅ Quota project set to: $GCP_PROJECT_ID"
echo ""

# Create Terraform state bucket if it doesn't exist
STATE_BUCKET="${GCP_PROJECT_ID}-terraform-state"
echo "📦 Checking Terraform state bucket..."

if ! gcloud storage buckets describe gs://$STATE_BUCKET &>/dev/null; then
    echo "   Creating bucket gs://$STATE_BUCKET"
    gcloud storage buckets create gs://$STATE_BUCKET \
        --project=$GCP_PROJECT_ID \
        --location=$GCP_REGION \
        --enable-autoclass
    gcloud storage buckets update gs://$STATE_BUCKET --versioning
    echo "   ✅ Bucket created with versioning enabled"
else
    echo "   ✅ Bucket exists"
fi

echo ""
# Deploy global Terraform (Terraform handles API enablement in api.tf)
echo "🏗️  Deploying global infrastructure with Terraform..."
cd terraform

if [ ! -d ".terraform" ]; then
    echo "   Initializing Terraform..."
    terraform init -backend-config="bucket=$STATE_BUCKET" -backend-config="prefix=copycat/global-infra"
fi

echo "   Planning Terraform..."
terraform plan \
    -var="project_id=$GCP_PROJECT_ID" \
    -var="region=$GCP_REGION" \
    -out=tfplan

echo ""
echo "   Applying Terraform plan..."
terraform apply tfplan
rm tfplan
echo "   ✅ Global infrastructure deployed"

cd ..

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Deploy a service: ./scripts/deploy-service.sh discovery-service prod"
echo ""
