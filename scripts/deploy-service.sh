#!/bin/bash
set -e

# Single command deployment script for services
# Usage: ./scripts/deploy-service.sh <service-name> [environment]
#
# Examples:
#   ./scripts/deploy-service.sh my-service dev
#   ./scripts/deploy-service.sh my-service prod

SERVICE_NAME=$1
ENVIRONMENT=${2:-dev}

if [ -z "$SERVICE_NAME" ]; then
    echo "❌ Error: Service name required"
    echo "Usage: ./scripts/deploy-service.sh <service-name> [environment]"
    exit 1
fi

if [ ! -d "services/$SERVICE_NAME" ]; then
    echo "❌ Error: Service 'services/$SERVICE_NAME' not found"
    exit 1
fi

# Load configuration
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Validate required variables
: ${GCP_PROJECT_ID:?'GCP_PROJECT_ID not set in .env'}
: ${GCP_REGION:?'GCP_REGION not set in .env'}

# Configure Docker authentication for Artifact Registry
echo "🔐 Configuring Docker authentication..."
gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev --quiet

echo "🚀 Deploying $SERVICE_NAME to $ENVIRONMENT"
echo "   Project: $GCP_PROJECT_ID"
echo "   Region: $GCP_REGION"
echo ""

# Generate source hash (includes app/ and pyproject.toml)
echo "🔍 Calculating source hash..."
APP_DIR="services/$SERVICE_NAME/app"
PYPROJECT="services/$SERVICE_NAME/pyproject.toml"

# Find all relevant source files (exclude cache, venv, etc.) + pyproject.toml
SOURCE_HASH=$(
    (find "$APP_DIR" -type f \
        ! -path "*/.venv/*" \
        ! -path "*/__pycache__/*" \
        ! -path "*/.pytest_cache/*" \
        ! -path "*/.ruff_cache/*" \
        ! -path "*/.git/*" \
        ! -name "*.pyc" \
        ! -name ".DS_Store" \
        ! -name "Thumbs.db" \
        ! -name "desktop.ini" \
        ! -name "._*" \
        ! -name "*~" \
        -exec sha256sum {} + 2>/dev/null
     [ -f "$PYPROJECT" ] && sha256sum "$PYPROJECT" 2>/dev/null
    ) | sort | sha256sum | cut -d' ' -f1
)

GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
IMAGE_TAG="${GIT_SHA}-${SOURCE_HASH:0:12}"
IMAGE_NAME="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/copycat-docker/${SERVICE_NAME}:${IMAGE_TAG}"

echo "   Source hash: ${SOURCE_HASH:0:12}"
echo "   Image tag: $IMAGE_TAG"
echo ""

# Check if image already exists
echo "📦 Step 1/3: Checking if image needs to be built..."
IMAGE_EXISTS=$(gcloud artifacts docker images list \
    "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/copycat-docker/${SERVICE_NAME}" \
    --filter="tags:${IMAGE_TAG}" \
    --format="value(version)" 2>/dev/null | head -n1 || echo "")

if [ -n "$IMAGE_EXISTS" ]; then
    echo "   ✅ Image already exists with hash ${SOURCE_HASH:0:12}"
    echo "   Skipping build (no source changes detected)"
else
    echo "   Building new image: $IMAGE_NAME"

    # Build locally with Docker for linux/amd64 (Cloud Run requirement)
    cd services/$SERVICE_NAME
    docker build --platform linux/amd64 -t $IMAGE_NAME .

    # Push to Artifact Registry
    docker push $IMAGE_NAME

    cd ../..

    echo "   ✅ Image built and pushed"
fi

echo ""

echo "🏗️  Step 2/3: Deploying infrastructure with Terraform..."
cd services/$SERVICE_NAME/terraform

# Initialize if needed
if [ ! -d ".terraform" ]; then
    echo "   Initializing Terraform..."
    terraform init \
        -backend-config="bucket=${GCP_PROJECT_ID}-terraform-state" \
        -backend-config="prefix=copycat/services/${SERVICE_NAME}/${ENVIRONMENT}"
fi

# Apply infrastructure
echo "   Applying Terraform..."
terraform apply \
    -var="project_id=$GCP_PROJECT_ID" \
    -var="region=$GCP_REGION" \
    -var="environment=$ENVIRONMENT" \
    -var="service_name=$SERVICE_NAME" \
    -var="image_name=$IMAGE_NAME" \
    -auto-approve

# Get service URL
SERVICE_URL=$(terraform output -raw service_url 2>/dev/null || echo "N/A")

cd ../../..

echo ""
echo "✅ Infrastructure deployed"
echo ""

echo "🔍 Step 3/3: Verifying deployment..."

# Wait a bit for service to be ready
sleep 5

# Try to hit the health endpoint
if [ "$SERVICE_URL" != "N/A" ]; then
    echo "   Testing $SERVICE_URL/health"

    # Get auth token for Cloud Run
    TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")

    if [ -n "$TOKEN" ]; then
        HEALTH_CHECK=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/health" || echo "000")
        HTTP_CODE=$(echo "$HEALTH_CHECK" | tail -n1)
        RESPONSE=$(echo "$HEALTH_CHECK" | head -n-1)

        if [ "$HTTP_CODE" = "200" ]; then
            echo "   ✅ Health check passed"
            echo "   Response: $RESPONSE"
        else
            echo "   ⚠️  Health check returned HTTP $HTTP_CODE"
        fi
    else
        echo "   ⚠️  Skipping health check (no auth token)"
    fi
fi

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📊 Summary:"
echo "   Service:     $SERVICE_NAME"
echo "   Environment: $ENVIRONMENT"
echo "   Image:       $IMAGE_NAME"
echo "   URL:         $SERVICE_URL"
echo ""
echo "📝 Next steps:"
echo "   • View logs:   gcloud run services logs tail $SERVICE_NAME --project=$GCP_PROJECT_ID --region=$GCP_REGION"
echo "   • Open in browser: open $SERVICE_URL"
echo ""
