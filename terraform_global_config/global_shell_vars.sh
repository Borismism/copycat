# ==============================================================================
# COPYCAT - GLOBAL SHELL VARIABLES
# ==============================================================================
# Used by CI/CD workflows to load common values across all deployments
# ==============================================================================

# Production configuration (update when deploying to prod)
GCP_PROJECT_ID="your-prod-project-id"
GCP_REGION="europe-west4"
REPO_NAME="copycat-docker"
TF_STATE_BUCKET="tf-state-your-prod-project-id"

# Note: For dev (boris-demo-453408), use dev.tfvars which overrides these values
