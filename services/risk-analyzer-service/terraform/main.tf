locals {
  # Watch only the app folder for source code changes
  app_dir       = "${path.module}/../app"
  exclude_regex = "(\\.venv/|__pycache__/|\\.git/|\\.DS_Store|Thumbs\\.db|desktop\\.ini|\\._.*|~$|\\.pyc$|\\.pytest_cache/|__pycache__|\\.ruff_cache/)"

  all_app_files = fileset(local.app_dir, "**/*")
  app_files = toset([
    for f in local.all_app_files : f
    if length(regexall(local.exclude_regex, f)) == 0
  ])

  # Hash of app source files - triggers Cloud Run update when app code changes
  app_source_hash = sha256(join("", [
    for f in sort(local.app_files) : filesha256("${local.app_dir}/${f}")
  ]))
}

# Get global infrastructure from remote state (Firestore, etc.)
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/global-infra"
  }
}

# Service account for Cloud Run
resource "google_service_account" "risk_analyzer_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Risk Analyzer Service"
  description  = "Service account for risk analyzer service"
}

# IAM roles for service account
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "risk_analyzer_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.risk_analyzer_service.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    timeout = "${var.timeout_seconds}s"

    containers {
      image = var.image_name

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle = true
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = data.terraform_remote_state.global.outputs.firestore_database
      }

      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      env {
        name  = "DEBUG"
        value = var.environment == "dev" ? "true" : "false"
      }

      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = "copycat-${var.environment}"
      }

      env {
        name  = "PUBSUB_SUBSCRIPTION_VIDEO_DISCOVERED"
        value = "risk-analyzer-video-discovered-sub"
      }

      env {
        name  = "PUBSUB_SUBSCRIPTION_VISION_FEEDBACK"
        value = "risk-analyzer-vision-feedback-sub"
      }

      # Source code hash - triggers redeployment when app code changes
      env {
        name  = "SOURCE_HASH"
        value = local.app_source_hash
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 30
        failure_threshold     = 3
      }
    }

    max_instance_request_concurrency = var.concurrency
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_iam_member.firestore_user,
    google_project_iam_member.pubsub_publisher,
    google_project_iam_member.secret_accessor,
  ]
}

# Allow unauthenticated access (adjust for production)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.risk_analyzer_service.name
  location = google_cloud_run_v2_service.risk_analyzer_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# PubSub subscription for discovered videos
resource "google_pubsub_subscription" "video_discovered" {
  name  = "risk-analyzer-video-discovered-sub"
  topic = "projects/${var.project_id}/topics/copycat-video-discovered"

  ack_deadline_seconds = 600  # 10 minutes

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = "projects/${var.project_id}/topics/copycat-dead-letter"
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = ""  # Never expire
  }
}

# PubSub subscription for vision feedback
resource "google_pubsub_subscription" "vision_feedback" {
  name  = "risk-analyzer-vision-feedback-sub"
  topic = "projects/${var.project_id}/topics/copycat-vision-feedback"

  ack_deadline_seconds = 600  # 10 minutes

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = "projects/${var.project_id}/topics/copycat-dead-letter"
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = ""  # Never expire
  }
}
