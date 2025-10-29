# Artifact Registry for Docker images

resource "google_artifact_registry_repository" "docker" {
  repository_id = "copycat-docker"
  location      = var.region
  format        = "DOCKER"
  description   = "Docker images for Copycat services"

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Python package repository (for shared libraries if needed)
resource "google_artifact_registry_repository" "python" {
  repository_id = "copycat-python"
  location      = var.region
  format        = "PYTHON"
  description   = "Python packages for Copycat shared libraries"

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}
