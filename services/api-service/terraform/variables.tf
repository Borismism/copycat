variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west4"
}

variable "environment" {
  description = "Environment (dev/prod)"
  type        = string
  default     = "dev"
}

variable "service_name" {
  description = "Service name"
  type        = string
  default     = "api-service"
}

variable "image_name" {
  description = "Docker image name with tag"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 1  # Keep 1 instance warm to avoid cold starts
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "cpu" {
  description = "CPU allocation (1000m = 1 vCPU)"
  type        = string
  default     = "1000m"
}

variable "memory" {
  description = "Memory allocation"
  type        = string
  default     = "512Mi"
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 80
}

variable "gemini_location" {
  description = "GCP Region for Gemini/Vertex AI"
  type        = string
  default     = "europe-west1"
}

variable "state_bucket" {
  description = "GCS bucket for Terraform state"
  type        = string
}
