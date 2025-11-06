# Secret Manager for API keys and sensitive configuration
# This file manages secrets storage - API key creation is in api-keys.tf

# =============================================================================
# YouTube Data API Key Secret
# =============================================================================
# The API key itself is created in api-keys.tf
# This resource creates the secret container in Secret Manager
#
# IMPORTANT: Request quota increase via GCP Console for higher limits
# Default: 10,000 units/day per project

resource "google_secret_manager_secret" "youtube_api_key" {
  secret_id = "youtube-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    service    = "copycat"
    managed_by = "terraform"
  }

  depends_on = [google_project_service.apis]
}

# The secret version is created in api-keys.tf to avoid circular dependency
# It stores the API key string

# =============================================================================
# Gemini via Vertex AI - No API Key Needed!
# =============================================================================
# Copycat uses Vertex AI for Gemini models, which uses IAM authentication
# instead of API keys. Service accounts get the aiplatform.user role.
#
# API: aiplatform.googleapis.com (enabled in api.tf)
# Models: gemini-2.0-flash-exp, gemini-pro-vision
# Region: Set via GCP_REGION environment variable
#
# No secrets needed for Vertex AI!

# =============================================================================
# Target IP Configuration (Optional)
# =============================================================================
# This secret can store IP target configuration if you want to manage it
# separately from the ip_targets.yaml file in the discovery service

resource "google_secret_manager_secret" "target_ip_config" {
  secret_id = "target-ip-config"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    service    = "copycat"
    managed_by = "terraform"
    optional   = "true"
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# Setup Summary
# =============================================================================
# ✅ YouTube API Key: Auto-generated and stored in Secret Manager
#    - Restricted to youtube.googleapis.com only
#    - Key value automatically populated
#    - Ready to use immediately
#
# ✅ Gemini Models: Use Vertex AI with IAM authentication
#    - No API key needed
#    - Service accounts get aiplatform.user role
#    - Models: gemini-2.0-flash-exp, gemini-pro-vision
#
# 🔧 Target IP Config: Optional secret for IP target configuration
#    - Can be used to override ip_targets.yaml
#    - Managed in services/discovery-service/app/ip_targets.yaml
