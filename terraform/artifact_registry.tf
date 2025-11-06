# Artifact Registry for Docker images

resource "google_artifact_registry_repository" "docker" {
  repository_id = "copycat-docker"
  location      = var.region
  format        = "DOCKER"
  description   = "Docker images for Copycat services"

  labels = {
    service = "copycat"
  }
}

# Python package repository removed - not currently used
