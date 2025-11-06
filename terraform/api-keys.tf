# API Keys for YouTube Data API
# This file manages restricted API keys that are stored in Secret Manager
#
# IMPORTANT: Quota is per PROJECT (not per key)
# - Default: 10,000 units/day per project
# - To increase: Request quota extension via GCP Console → IAM & Admin → Quotas
# - See HOW_TO_GET_YOUTUBE_API_KEY.md for detailed instructions

# YouTube Data API key - unrestricted for maximum compatibility
# This key is automatically created and stored in Secret Manager
resource "google_apikeys_key" "youtube_api_key" {
  name         = "copycat-youtube-api-key-v4"
  display_name = "Copycat YouTube API Key v4"
  project      = var.project_id

  # No restrictions - unrestricted API key
  # Note: Consider adding IP restrictions in production for better security

  # Ensure the API Keys API is enabled before creating keys
  depends_on = [google_project_service.apis]
}

# Store the API key in Secret Manager
resource "google_secret_manager_secret_version" "youtube_api_key" {
  secret = google_secret_manager_secret.youtube_api_key.id

  # Store as single key string
  secret_data = google_apikeys_key.youtube_api_key.key_string
}

# Note: The actual key value (key_string) is stored in Secret Manager
# See secrets.tf for the secret storage configuration
