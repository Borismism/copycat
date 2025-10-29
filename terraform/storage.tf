# Cloud Storage bucket for frame images

resource "google_storage_bucket" "frames" {
  name          = "${var.project_id}-copycat-frames-${var.environment}"
  location      = var.region
  storage_class = "STANDARD"

  # Lifecycle rule to auto-delete old frames
  lifecycle_rule {
    condition {
      age = 30 # Delete frames older than 30 days
    }
    action {
      type = "Delete"
    }
  }

  # Lifecycle rule to move to cheaper storage after 7 days
  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  uniform_bucket_level_access = true

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Results bucket for reports/exports
resource "google_storage_bucket" "results" {
  name          = "${var.project_id}-copycat-results-${var.environment}"
  location      = var.region
  storage_class = "STANDARD"

  versioning {
    enabled = true
  }

  uniform_bucket_level_access = true

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}
