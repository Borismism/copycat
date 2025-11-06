# ==============================================================================
# COPYCAT GLOBAL INFRASTRUCTURE - TERRAFORM VARIABLES
# ==============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for regional resources"
  type        = string
  default     = "europe-west4"
}

variable "github_repository" {
  description = "GitHub repository in format 'owner/repo' (e.g., 'anthropics/copycat')"
  type        = string
}

variable "artifact_repo_id" {
  description = "Artifact Registry repository ID for Docker images"
  type        = string
  default     = "copycat-docker"
}

variable "frontend_domain" {
  description = "Custom domain for frontend service (e.g., 'copycat.example.com')"
  type        = string
}

variable "iap_support_email" {
  description = "Support email for IAP OAuth consent screen"
  type        = string
}

variable "iap_authorized_users" {
  description = "List of users/groups authorized to access IAP-protected frontend (e.g., ['user:alice@example.com', 'group:admins@example.com'])"
  type        = list(string)
  default     = []
}

# YouTube API Configuration
variable "youtube_daily_quota" {
  description = "YouTube API daily quota limit (units)"
  type        = string
  default     = "10000"
}

variable "firestore_database" {
  description = "Firestore database name"
  type        = string
  default     = "copycat"
}

variable "youtube_default_region" {
  description = "Default region for YouTube API queries"
  type        = string
  default     = "US"
}

# Discovery Configuration
variable "discovery_schedule" {
  description = "Cron schedule for discovery runs"
  type        = string
  default     = "0 * * * *"
}

variable "hourly_quota_budget" {
  description = "YouTube API quota budget per scheduled run"
  type        = number
  default     = 417
}

# Gemini Configuration
variable "gemini_location" {
  description = "GCP Region for Gemini/Vertex AI"
  type        = string
  default     = "us-central1"
}

variable "daily_budget_usd" {
  description = "Daily Gemini API budget in USD"
  type        = string
  default     = "260"
}

variable "environment" {
  description = "Environment (dev or prod) - used for log levels and debug settings"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}
