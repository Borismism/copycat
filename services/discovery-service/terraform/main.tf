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
resource "google_service_account" "discovery_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Discovery Service"
  description  = "Service account for discovery service"
}

# IAM roles for service account
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "discovery_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.discovery_service.email

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
        name  = "PUBSUB_TOPIC_DISCOVERED_VIDEOS"
        value = "copycat-video-discovered"
      }

      # YouTube API configuration
      env {
        name  = "YOUTUBE_PROJECT_ID"
        value = var.project_id  # Same project for YouTube API quota tracking
      }

      env {
        name = "YOUTUBE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "projects/${var.project_id}/secrets/youtube-api-key"
            version = "latest"
          }
        }
      }

      env {
        name  = "YOUTUBE_QUOTA_LIMIT"
        value = "10000"
      }

      env {
        name  = "YOUTUBE_DEFAULT_REGION"
        value = "US"
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
  name     = google_cloud_run_v2_service.discovery_service.name
  location = google_cloud_run_v2_service.discovery_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Service account for Cloud Scheduler
resource "google_service_account" "scheduler" {
  account_id   = "${var.service_name}-scheduler-sa"
  display_name = "Discovery Service Scheduler"
  description  = "Service account for Cloud Scheduler to invoke discovery service"
}

# Allow scheduler to invoke Cloud Run
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  name     = google_cloud_run_v2_service.discovery_service.name
  location = google_cloud_run_v2_service.discovery_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Cloud Scheduler job - runs every hour
# Budget: 10,000 quota units/day ÷ 24 hours = 417 units/hour
# Note: Cloud Scheduler location must be europe-west1 (different from Cloud Run region)
resource "google_cloud_scheduler_job" "hourly_discovery" {
  name             = "${var.service_name}-hourly"
  region           = "europe-west1"  # Cloud Scheduler uses different regions
  description      = "Trigger discovery service every hour with quota budget of 417 units"
  schedule         = "0 * * * *"  # Every hour at minute 0
  time_zone        = "UTC"
  attempt_deadline = "1800s"  # 30 minutes timeout

  retry_config {
    retry_count = 1
    max_retry_duration = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "60s"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.discovery_service.uri}/discover/run?max_quota=417"

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.discovery_service.uri
    }

    headers = {
      "Content-Type" = "application/json"
    }
  }

  depends_on = [
    google_cloud_run_v2_service.discovery_service,
    google_cloud_run_v2_service_iam_member.scheduler_invoker,
  ]
}
