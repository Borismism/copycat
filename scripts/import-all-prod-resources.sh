#!/bin/bash

set -e

PROJECT_ID="copycat-429012"
REGION="europe-west4"

echo "Importing all existing production resources into Terraform state..."

# Import global infrastructure resources
echo "=== Importing global infrastructure ==="
cd terraform

# Import IAP OAuth Brand (already exists)
echo "Importing IAP OAuth Brand..."
terraform import google_iap_brand.oauth_brand "projects/297485357024/brands/297485357024" || echo "Already imported or doesn't exist"

cd ..

# Import service accounts for each service
declare -a services=("api-service" "discovery-service" "risk-analyzer-service" "vision-analyzer-service" "frontend-service")

for service in "${services[@]}"; do
    echo "=== Importing $service resources ==="
    cd "services/$service/terraform"

    # Import service account
    case $service in
        "api-service")
            SA_NAME="api-service-sa"
            terraform import google_service_account.api_service "projects/$PROJECT_ID/serviceAccounts/$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"
            ;;
        "discovery-service")
            SA_NAME="discovery-service-sa"
            terraform import google_service_account.discovery_service "projects/$PROJECT_ID/serviceAccounts/$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"

            # Import scheduler service account
            SCHEDULER_SA="discovery-service-scheduler-sa"
            terraform import google_service_account.scheduler "projects/$PROJECT_ID/serviceAccounts/$SCHEDULER_SA@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"
            ;;
        "risk-analyzer-service")
            SA_NAME="risk-analyzer-service-sa"
            terraform import google_service_account.risk_analyzer_service "projects/$PROJECT_ID/serviceAccounts/$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"

            # Import push service account
            PUSH_SA="risk-analyzer-service-push"
            terraform import google_service_account.push_sa "projects/$PROJECT_ID/serviceAccounts/$PUSH_SA@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"
            ;;
        "vision-analyzer-service")
            SA_NAME="vision-analyzer-service-sa"
            terraform import google_service_account.vision_analyzer_service "projects/$PROJECT_ID/serviceAccounts/$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"

            # Import push service account
            PUSH_SA="vision-analyzer-service-push"
            terraform import google_service_account.push_sa "projects/$PROJECT_ID/serviceAccounts/$PUSH_SA@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"
            ;;
        "frontend-service")
            SA_NAME="frontend-service-sa"
            terraform import google_service_account.frontend_service "projects/$PROJECT_ID/serviceAccounts/$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" || echo "Already imported"
            ;;
    esac

    cd ../../..
done

echo ""
echo "✓ All resources imported successfully!"
echo ""
echo "You can now run: ./deploy.sh <service> prod"
