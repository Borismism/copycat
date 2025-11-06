# ==============================================================================
# COPYCAT - PRODUCTION TERRAFORM VARIABLES
# ==============================================================================
# This file contains production configuration
# Deployed to: your-prod-project-id
# ==============================================================================

# GCP Project Configuration
project_id = "your-prod-project-id"
region     = "europe-west4"

# GitHub Repository (for Workload Identity Federation)
github_repository = "your-org/copycat"

# Artifact Registry
artifact_repo_id = "copycat-docker"

# Frontend Domain & IAP
frontend_domain      = "copycat.yourcompany.com"
iap_support_email    = "support@yourcompany.com"
iap_authorized_users = [
  "user:admin@yourcompany.com",
  "group:copycat-admins@yourcompany.com"
]

# YouTube API Configuration
youtube_daily_quota        = "10000"  # Request increase via GCP Console
youtube_default_region     = "US"

# Discovery Schedule
discovery_schedule      = "0 * * * *"  # Every hour
hourly_quota_budget     = 417          # 10,000 / 24

# Gemini Configuration
gemini_location         = "us-central1"  # Best for Gemini 2.5 Flash
daily_budget_usd        = "260"          # €240 ≈ $260
