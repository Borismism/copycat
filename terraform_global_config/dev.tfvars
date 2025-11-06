# ==============================================================================
# COPYCAT - DEVELOPMENT TERRAFORM VARIABLES (Irdeto Internal Dev)
# ==============================================================================
# Deployed to: irdeto-copycat-internal-dev
# ==============================================================================

# GCP Project Configuration
project_id  = "irdeto-copycat-internal-dev"
region      = "europe-west4"
environment = "dev"  # For log levels, debug settings, etc.

# GitHub Repository (for Workload Identity Federation)
github_repository = "Borismism/copycat"

# Artifact Registry
artifact_repo_id = "copycat-docker"

# Frontend Domain & IAP
frontend_domain      = "copycat-dev.borism.nl"
iap_support_email    = "boris@nextnovate.com"
iap_authorized_users = [
  "user:boris@nextnovate.com",
  "user:bartjan@nextnovate.com",
  "user:bart@nextnovate.com"
]

# Firestore Configuration
firestore_database         = "copycat"  # Use copycat Firestore database

# YouTube API Configuration
youtube_daily_quota        = "10000"  # Default quota
youtube_default_region     = "EU"     # Europe

# Discovery Schedule (every 2 hours with adaptive budget)
discovery_schedule      = "0 */2 * * *"  # Every 2 hours
hourly_quota_budget     = 833            # 10,000 / 12 (adaptive based on usage)

# Gemini Configuration
gemini_location         = "europe-west1"  # Belgium - Full Gemini 2.5 Flash support
daily_budget_usd        = "5"             # €5 for demo testing
