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
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
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
  default     = 600
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 1 # Process one video at a time
}

# Budget configuration
variable "daily_budget_usd" {
  description = "Daily Gemini API budget in USD"
  type        = string
  default     = "260" # Production default: €240 ≈ $260
}

variable "state_bucket" {
  description = "GCS bucket for Terraform state"
  type        = string
}
