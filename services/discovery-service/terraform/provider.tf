terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    # Configured via init command:
    # terraform init -backend-config="bucket=PROJECT_ID-terraform-state" \
    #                -backend-config="prefix=copycat/services/discovery-service/ENV"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
