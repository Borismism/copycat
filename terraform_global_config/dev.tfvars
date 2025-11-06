# ==============================================================================
# COPYCAT - DEVELOPMENT TERRAFORM VARIABLES
# ==============================================================================
# This file contains development/staging configuration
# Deployed to: your-dev-project-id
# ==============================================================================

# GCP Project Configuration
project_id = "your-dev-project-id"
region     = "europe-west4"

# GitHub Repository (for Workload Identity Federation)
github_repository = "your-org/copycat"

# Artifact Registry
artifact_repo_id = "copycat-docker"

# Frontend Domain & IAP
frontend_domain      = "copycat-dev.yourcompany.com"
iap_support_email    = "dev@yourcompany.com"
iap_authorized_users = [
  "user:dev@yourcompany.com",
  "user:boris@yourcompany.com"
]

# YouTube API Configuration (dev has separate quota)
youtube_daily_quota        = "10000"
youtube_default_region     = "US"

# Discovery Schedule (less frequent in dev to save quota)
discovery_schedule      = "0 */3 * * *"  # Every 3 hours
hourly_quota_budget     = 139            # 10,000 / 72 (3-hour intervals)

# Gemini Configuration
gemini_location         = "us-central1"
daily_budget_usd        = "50"  # Lower budget for dev
