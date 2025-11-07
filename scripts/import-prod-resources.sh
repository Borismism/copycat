#!/bin/bash

# Import existing GCP resources into Terraform state for prod environment
# This fixes the "service account already exists" errors

set -e

PROJECT_ID="copycat-429012"
IMAGE_TAG="7a43a50"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Importing existing GCP resources into Terraform state...${NC}"

# Discovery Service
echo -e "\n${YELLOW}=== Discovery Service ===${NC}"
cd /Users/boris/copycat/services/discovery-service/terraform
echo -e "${BLUE}Importing service accounts...${NC}"
terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/discovery-service:${IMAGE_TAG}-586522d5" \
  google_service_account.discovery_service \
  projects/${PROJECT_ID}/serviceAccounts/discovery-service-sa@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/discovery-service:${IMAGE_TAG}-586522d5" \
  google_service_account.scheduler \
  projects/${PROJECT_ID}/serviceAccounts/discovery-service-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

# API Service
echo -e "\n${YELLOW}=== API Service ===${NC}"
cd /Users/boris/copycat/services/api-service/terraform
terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/api-service:${IMAGE_TAG}-c91aa95a" \
  google_service_account.api_service \
  projects/${PROJECT_ID}/serviceAccounts/api-service-sa@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

# Risk Analyzer Service
echo -e "\n${YELLOW}=== Risk Analyzer Service ===${NC}"
cd /Users/boris/copycat/services/risk-analyzer-service/terraform
terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/risk-analyzer-service:${IMAGE_TAG}-ca351804" \
  google_service_account.risk_analyzer_service \
  projects/${PROJECT_ID}/serviceAccounts/risk-analyzer-service-sa@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

# Vision Analyzer Service
echo -e "\n${YELLOW}=== Vision Analyzer Service ===${NC}"
cd /Users/boris/copycat/services/vision-analyzer-service/terraform
terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/vision-analyzer-service:${IMAGE_TAG}-d44a665e" \
  google_service_account.vision_analyzer_service \
  projects/${PROJECT_ID}/serviceAccounts/vision-analyzer-service-sa@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/vision-analyzer-service:${IMAGE_TAG}-d44a665e" \
  google_service_account.push_sa \
  projects/${PROJECT_ID}/serviceAccounts/vision-analyzer-service-push@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

# Frontend Service
echo -e "\n${YELLOW}=== Frontend Service ===${NC}"
cd /Users/boris/copycat/services/frontend-service/terraform
terraform import -var-file=../../../terraform_global_config/terraform.tfvars \
  -var="image_name=europe-west4-docker.pkg.dev/${PROJECT_ID}/copycat-docker/frontend-service:${IMAGE_TAG}-85ba58c1" \
  google_service_account.frontend_service \
  projects/${PROJECT_ID}/serviceAccounts/frontend-service-sa@${PROJECT_ID}.iam.gserviceaccount.com 2>/dev/null || echo "Already imported"

echo -e "\n${GREEN}✓ Import complete!${NC}"
echo -e "${BLUE}Now rerun the deployments${NC}"
