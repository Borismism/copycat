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
  description = "Environment (dev, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

variable "service_name" {
  description = "Service name"
  type        = string
  default     = "vision-analyzer-service"
}

variable "image_name" {
  description = "Docker image name with tag"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0  # Scale to zero when idle
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 5  # Lower than other services (expensive operations)
}

variable "cpu" {
  description = "CPU allocation (1000m = 1 vCPU)"
  type        = string
  default     = "2000m"  # 2 vCPU for Gemini API calls
}

variable "memory" {
  description = "Memory allocation"
  type        = string
  default     = "1Gi"  # More memory for video processing
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 600  # 10 minutes for long videos
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 10  # Lower concurrency for expensive operations
}
