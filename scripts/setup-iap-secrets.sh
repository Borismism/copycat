#!/bin/bash
set -e

# Script to set up IAP OAuth credentials in Secret Manager
# These secrets are required for IAP authentication on the frontend

PROJECT_ID="${GCP_PROJECT_ID:-copycat-429012}"

echo "Setting up IAP OAuth credentials in Secret Manager..."
echo "Project: $PROJECT_ID"
echo ""

# Check if secrets already exist
if gcloud secrets describe iap-oauth-client-id --project="$PROJECT_ID" &>/dev/null; then
    echo "✓ Secret 'iap-oauth-client-id' already exists"
else
    echo "Creating secret 'iap-oauth-client-id'..."
    gcloud secrets create iap-oauth-client-id \
        --project="$PROJECT_ID" \
        --replication-policy="automatic"
    echo "✓ Created secret 'iap-oauth-client-id'"
fi

if gcloud secrets describe iap-oauth-client-secret --project="$PROJECT_ID" &>/dev/null; then
    echo "✓ Secret 'iap-oauth-client-secret' already exists"
else
    echo "Creating secret 'iap-oauth-client-secret'..."
    gcloud secrets create iap-oauth-client-secret \
        --project="$PROJECT_ID" \
        --replication-policy="automatic"
    echo "✓ Created secret 'iap-oauth-client-secret'"
fi

echo ""
echo "Now you need to add the secret values:"
echo ""
echo "1. Get your OAuth Client credentials from:"
echo "   https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"
echo ""
echo "2. Set the client ID:"
echo "   echo 'YOUR_CLIENT_ID' | gcloud secrets versions add iap-oauth-client-id --data-file=- --project=$PROJECT_ID"
echo ""
echo "3. Set the client secret:"
echo "   echo 'YOUR_CLIENT_SECRET' | gcloud secrets versions add iap-oauth-client-secret --data-file=- --project=$PROJECT_ID"
echo ""
