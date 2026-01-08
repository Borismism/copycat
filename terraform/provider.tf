terraform {
  backend "gcs" {
    # Configured via -backend-config flags
    # bucket = "PROJECT_ID-terraform-state"
    prefix = "copycat/global-infra"
  }

  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.10"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}
