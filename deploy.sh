#!/bin/bash

# ==============================================================================
# COPYCAT DEPLOYMENT SCRIPT
# ==============================================================================
# Deploy global infrastructure or individual services to GCP Cloud Run
#
# Usage:
#   ./deploy.sh infra [dev|prod]           # Deploy global infrastructure
#   ./deploy.sh <service> [dev|prod]       # Deploy a specific service
#   ./deploy.sh all [dev|prod]             # Deploy all services
#
# Examples:
#   ./deploy.sh infra dev                  # Deploy global infra to dev
#   ./deploy.sh discovery-service prod     # Deploy discovery service to prod
#   ./deploy.sh all dev                    # Deploy all services to dev
# ==============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Available services
SERVICES=(
    "api-service"
    "discovery-service"
    "risk-analyzer-service"
    "vision-analyzer-service"
    "frontend-service"
)

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

show_usage() {
    cat << EOF
${BLUE}Copycat Deployment Script${NC}

${GREEN}Usage:${NC}
  ./deploy.sh infra [dev|prod]           Deploy global infrastructure
  ./deploy.sh <service> [dev|prod]       Deploy a specific service
  ./deploy.sh all [dev|prod]             Deploy all services

${GREEN}Available Services:${NC}
  - api-service
  - discovery-service
  - risk-analyzer-service
  - vision-analyzer-service
  - frontend-service

${GREEN}Examples:${NC}
  ./deploy.sh infra dev                  Deploy global infrastructure to dev
  ./deploy.sh discovery-service prod     Deploy discovery service to prod
  ./deploy.sh all dev                    Deploy all services to dev

${GREEN}Prerequisites:${NC}
  1. Fill in terraform_global_config/terraform.tfvars (prod)
  2. Fill in terraform_global_config/dev.tfvars (dev)
  3. Create GCS state buckets (run once per environment)
  4. Authenticate with gcloud: gcloud auth application-default login

EOF
    exit 0
}

check_gcloud_auth() {
    if ! gcloud auth application-default print-access-token &>/dev/null; then
        log_error "Not authenticated with gcloud"
        log_info "Run: gcloud auth application-default login"
        exit 1
    fi
    log_success "gcloud authentication verified"
}

load_env_config() {
    local env=$1

    if [[ "$env" == "dev" ]]; then
        TFVARS_FILE="terraform_global_config/dev.tfvars"
        BACKEND_CONFIG="terraform_global_config/backend_config_dev.hcl"
    else
        TFVARS_FILE="terraform_global_config/terraform.tfvars"
        BACKEND_CONFIG="terraform_global_config/backend_config.hcl"
    fi

    if [[ ! -f "$TFVARS_FILE" ]]; then
        log_error "Config file not found: $TFVARS_FILE"
        log_info "Copy terraform_global_config/terraform.tfvars and fill in your values"
        exit 1
    fi

    if [[ ! -f "$BACKEND_CONFIG" ]]; then
        log_error "Backend config not found: $BACKEND_CONFIG"
        exit 1
    fi

    # Extract project ID from tfvars
    PROJECT_ID=$(grep "^project_id" "$TFVARS_FILE" | cut -d'"' -f2)
    REGION=$(grep "^region" "$TFVARS_FILE" | cut -d'"' -f2 || echo "europe-west4")
    ARTIFACT_REPO=$(grep "^artifact_repo_id" "$TFVARS_FILE" | cut -d'"' -f2 || echo "copycat-docker")

    log_info "Environment: ${YELLOW}$env${NC}"
    log_info "Project ID:  ${YELLOW}$PROJECT_ID${NC}"
    log_info "Region:      ${YELLOW}$REGION${NC}"
}

build_and_push_image() {
    local service=$1
    local service_dir="services/$service"

    if [[ ! -d "$service_dir" ]]; then
        log_error "Service directory not found: $service_dir"
        exit 1
    fi

    log_info "Building Docker image for $service..."

    # Calculate source hash
    local source_hash=$(find "$service_dir/app" -type f -name "*.py" -exec sha256sum {} \; | sort | sha256sum | cut -d' ' -f1 | head -c 8)
    local git_sha=$(git rev-parse --short HEAD)
    local image_tag="${git_sha}-${source_hash}"
    local image_url="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${service}:${image_tag}"

    log_info "Image: $image_url"

    # Check if image already exists
    if gcloud artifacts docker images describe "$image_url" --project="$PROJECT_ID" &>/dev/null; then
        log_success "Image already exists, skipping build"
        echo "$image_url"
        return 0
    fi

    # Build and push with Cloud Build
    log_info "Building with Cloud Build..."
    gcloud builds submit "$service_dir" \
        --project="$PROJECT_ID" \
        --tag="$image_url" \
        --quiet

    # Get digest
    local digest=$(gcloud artifacts docker images describe "$image_url" \
        --project="$PROJECT_ID" \
        --format='value(image_summary.digest)')

    local image_url_with_digest="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${service}@${digest}"

    log_success "Image built: $image_url_with_digest"
    echo "$image_url_with_digest"
}

deploy_infrastructure() {
    local env=$1

    log_info "Deploying global infrastructure to ${YELLOW}$env${NC}..."

    cd terraform/

    # Initialize Terraform with backend config
    log_info "Initializing Terraform..."
    terraform init -backend-config="../$BACKEND_CONFIG" -reconfigure

    # Plan
    log_info "Planning deployment..."
    terraform plan -var-file="../$TFVARS_FILE" -out=tfplan

    # Apply
    log_info "Applying Terraform..."
    terraform apply tfplan

    rm -f tfplan
    cd ..

    log_success "Global infrastructure deployed to $env"
}

deploy_service() {
    local service=$1
    local env=$2

    log_info "Deploying ${YELLOW}$service${NC} to ${YELLOW}$env${NC}..."

    # Build and push Docker image
    local image_url=$(build_and_push_image "$service")

    # Deploy with Terraform
    local service_terraform="services/$service/terraform"

    if [[ ! -d "$service_terraform" ]]; then
        log_error "Terraform directory not found: $service_terraform"
        exit 1
    fi

    cd "$service_terraform"

    # Initialize Terraform
    log_info "Initializing Terraform..."
    terraform init -backend-config="../../../$BACKEND_CONFIG" -reconfigure

    # Plan with image URL
    log_info "Planning deployment..."
    terraform plan \
        -var-file="../../../$TFVARS_FILE" \
        -var="image_name=$image_url" \
        -out=tfplan

    # Apply
    log_info "Applying Terraform..."
    terraform apply tfplan

    rm -f tfplan
    cd ../../..

    # Verify deployment
    log_info "Verifying deployment..."
    local service_url=$(gcloud run services describe "$service" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format='value(status.url)' 2>/dev/null || echo "")

    if [[ -n "$service_url" ]]; then
        log_success "$service deployed successfully"
        log_info "Service URL: ${GREEN}$service_url${NC}"

        # Check health endpoint (if not internal-only)
        if [[ "$service" == "api-service" ]]; then
            log_info "Checking health endpoint..."
            if curl -sf "${service_url}/health" &>/dev/null; then
                log_success "Health check passed"
            else
                log_warning "Health check failed (this might be expected for internal services)"
            fi
        fi
    else
        log_warning "Could not retrieve service URL (might be internal-only)"
    fi
}

deploy_all_services() {
    local env=$1

    log_info "Deploying all services to ${YELLOW}$env${NC}..."

    for service in "${SERVICES[@]}"; do
        echo ""
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        deploy_service "$service" "$env"
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    done

    echo ""
    log_success "All services deployed to $env"
}

# ==============================================================================
# MAIN
# ==============================================================================

# Check arguments
if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    show_usage
fi

TARGET=$1
ENVIRONMENT=${2:-prod}

# Validate environment
if [[ "$ENVIRONMENT" != "dev" ]] && [[ "$ENVIRONMENT" != "prod" ]]; then
    log_error "Invalid environment: $ENVIRONMENT (must be 'dev' or 'prod')"
    exit 1
fi

# Check gcloud auth
check_gcloud_auth

# Load environment config
load_env_config "$ENVIRONMENT"

# Execute deployment
case "$TARGET" in
    infra|infrastructure)
        deploy_infrastructure "$ENVIRONMENT"
        ;;
    all)
        # Deploy infrastructure first
        deploy_infrastructure "$ENVIRONMENT"
        echo ""
        # Then deploy all services
        deploy_all_services "$ENVIRONMENT"
        ;;
    api-service|discovery-service|risk-analyzer-service|vision-analyzer-service|frontend-service)
        deploy_service "$TARGET" "$ENVIRONMENT"
        ;;
    *)
        log_error "Invalid target: $TARGET"
        echo ""
        show_usage
        ;;
esac

log_success "Deployment complete! 🚀"
