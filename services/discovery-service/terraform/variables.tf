# ==============================================================================
# DISCOVERY SERVICE - TERRAFORM VARIABLES
# ==============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Run"
  type        = string
  default     = "europe-west4"
}

variable "scheduler_region" {
  description = "GCP Region for Cloud Scheduler (must be different from Cloud Run)"
  type        = string
  default     = "europe-west1"
}

variable "service_name" {
  description = "Service name"
  type        = string
  default     = "discovery-service"
}

variable "image_name" {
  description = "Docker image URL from Artifact Registry"
  type        = string
}

# Scaling configuration
variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 5
}

# Resource limits
variable "cpu" {
  description = "CPU allocation"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory allocation"
  type        = string
  default     = "512Mi"
}

# Request configuration
variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 1800 # 30 minutes for full discovery run
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 10 # Allow health checks + multiple API calls while discovery runs in background
}

# YouTube API Configuration
variable "youtube_daily_quota" {
  description = "YouTube API daily quota limit (units)"
  type        = string
  default     = "10000" # Default quota
}

variable "youtube_default_region" {
  description = "Default region for YouTube API queries"
  type        = string
  default     = "US"
}

# Cloud Scheduler Configuration
variable "discovery_schedule" {
  description = "Cron schedule for discovery runs (quota auto-calculated per run)"
  type        = string
  default     = "0 * * * *" # Every hour at minute 0
}

variable "state_bucket" {
  description = "GCS bucket for Terraform state"
  type        = string
}
