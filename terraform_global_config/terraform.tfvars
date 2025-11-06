# ==============================================================================
# COPYCAT - PRODUCTION TERRAFORM VARIABLES
# ==============================================================================
# Fill this in when you're ready to deploy to production
# ==============================================================================

# GCP Project Configuration
project_id = "your-prod-project-id"              # ← FILL THIS
region     = "europe-west4"

# GitHub Repository (for Workload Identity Federation)
github_repository = "Borismism/copycat"

# Artifact Registry
artifact_repo_id = "copycat-docker"

# Frontend Domain & IAP
frontend_domain      = "copycat.borism.nl"        # ← FILL THIS
iap_support_email    = "support@borism.nl"        # ← FILL THIS
iap_authorized_users = [
  "user:boris@nextnovate.com",                    # ← UPDATE THIS
]

# YouTube API Configuration
youtube_daily_quota        = "10000"  # Request increase via GCP Console if needed
youtube_default_region     = "EU"

# Discovery Schedule (every hour for production)
discovery_schedule      = "0 * * * *"  # Every hour
hourly_quota_budget     = 417          # 10,000 / 24

# Gemini Configuration
gemini_location         = "us-central1"
daily_budget_usd        = "260"  # €240 ≈ $260 for full production
