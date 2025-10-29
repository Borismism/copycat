variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for regional resources"
  type        = string
  default     = "europe-west4"
}

variable "environment" {
  description = "Environment (dev/prod)"
  type        = string
  default     = "dev"
}
