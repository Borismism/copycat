# ==============================================================================
# VISION ANALYZER SERVICE - TERRAFORM VARIABLES
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

variable "gemini_location" {
  description = "GCP Region for Gemini/Vertex AI (us-central1 recommended)"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Service name"
  type        = string
  default     = "vision-analyzer-service"
}

variable "image_name" {
  description = "Docker image URL from Artifact Registry"
  type        = string
}

# Scaling configuration
variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 1  # Keep at least 1 instance alive to prevent autoscaler killing active work
}

variable "max_instances" {
  description = "Maximum number of instances (DEPRECATED - use max_concurrent_videos)"
  type        = number
  default     = 1000
}

# Resource limits
variable "cpu" {
  description = "CPU allocation"
  type        = string
  default     = "2"
}

variable "memory" {
  description = "Memory allocation"
  type        = string
  default     = "2Gi"
}

# Request configuration
variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 1800  # 30 minutes - workers process videos in background, need long timeout
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 500 # Very high concurrency - requests return immediately, workers handle actual processing
}

# Budget configuration
variable "daily_budget_eur" {
  description = "Daily Gemini API budget in EUR"
  type        = string
  default     = "260" # Production default: €260
}

variable "max_concurrent_videos" {
  description = "Maximum number of videos to analyze concurrently (controls PubSub outstanding messages)"
  type        = number
  default     = 10 # Process 10 videos at a time to control costs
}

variable "state_bucket" {
  description = "GCS bucket for Terraform state"
  type        = string
}
