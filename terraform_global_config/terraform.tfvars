# ==============================================================================
# COPYCAT - PRODUCTION TERRAFORM VARIABLES
# ==============================================================================
# Fill this in when you're ready to deploy to production
# ==============================================================================

# GCP Project Configuration
project_id  = "copycat-429012"
region      = "europe-west4"
environment = "prod"

# GitHub Repository (for Workload Identity Federation)
github_repository = "Borismism/copycat"

# Artifact Registry
artifact_repo_id = "copycat-docker"

# Terraform State Bucket
state_bucket = "tf-state-copycat-429012"

# Frontend Domain & IAP
frontend_domain      = "copycat.borism.nl"        # ← FILL THIS
iap_support_email    = "boris@nextnovate.com"        # ← FILL THIS
iap_authorized_users = [
  "user:boris@nextnovate.com",
  "user:irdeto.poc@gmail.com"
]

# Firestore Configuration
firestore_database = "copycat"

# YouTube API Configuration
youtube_daily_quota        = "10000"  # Request increase via GCP Console if needed
youtube_default_region     = "EU"

# Discovery Schedule (every hour, quota auto-calculated)
discovery_schedule = "0 * * * *"  # Every hour (quota distributed optimally per run)

# Gemini Configuration
gemini_location         = "us-central1"  # Primary region for Gemini models
daily_budget_eur        = "260"  # €260 for full production
