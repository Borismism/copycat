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

# Get global infrastructure from remote state (Firestore, PubSub topics, etc.)
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/global-infra"
  }
}

# Service account for Cloud Run
resource "google_service_account" "vision_analyzer_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Vision Analyzer Service"
  description  = "Service account for vision analyzer service (Gemini API access)"
}

# IAM roles for service account

# Firestore access
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# PubSub publisher (for feedback)
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# PubSub subscriber (for scan-ready messages)
resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# BigQuery data editor (for analytics)
resource "google_project_iam_member" "bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# BigQuery job user (for running queries)
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# Vertex AI user (for Gemini API via Vertex AI)
resource "google_project_iam_member" "aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# Monitoring viewer
resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "vision_analyzer_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.vision_analyzer_service.email

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
        value = "copycat-${var.environment}"
      }

      # IP Config settings (Story 006)
      env {
        name  = "IP_CONFIG_COLLECTION"
        value = "ip_configs"
      }

      env {
        name  = "CONFIG_CACHE_TTL_SECONDS"
        value = "300"  # 5 minutes
      }

      env {
        name  = "MAX_IPS_PER_VIDEO"
        value = "3"  # Prevent prompt explosion
      }

      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      env {
        name  = "DEBUG"
        value = var.environment == "dev" ? "true" : "false"
      }

      # Gemini configuration
      env {
        name  = "GEMINI_PROJECT_ID"
        value = var.project_id  # Same project for Vertex AI/Gemini
      }

      env {
        name  = "GEMINI_MODEL"
        value = "gemini-2.5-flash"
      }

      env {
        name  = "GEMINI_LOCATION"
        value = var.region  # Same as service region
      }

      # Budget configuration
      env {
        name  = "DAILY_BUDGET_USD"
        value = "260"  # €240 ≈ $260
      }

      # PubSub configuration
      env {
        name  = "PUBSUB_SCAN_READY_SUBSCRIPTION"
        value = "scan-ready-vision-analyzer-sub"
      }

      env {
        name  = "PUBSUB_FEEDBACK_TOPIC"
        value = "vision-feedback"
      }

      # BigQuery configuration
      env {
        name  = "BIGQUERY_DATASET"
        value = "copycat_${var.environment}"
      }

      env {
        name  = "BIGQUERY_RESULTS_TABLE"
        value = "vision_analysis_results"
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
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 15
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 30
        timeout_seconds       = 5
        period_seconds        = 60
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
    google_project_iam_member.pubsub_subscriber,
    google_project_iam_member.bigquery_data_editor,
    google_project_iam_member.aiplatform_user,
  ]
}

# Allow unauthenticated access (adjust for production)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.vision_analyzer_service.name
  location = google_cloud_run_v2_service.vision_analyzer_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# PubSub subscription for scan-ready messages
resource "google_pubsub_subscription" "scan_ready" {
  name  = "scan-ready-vision-analyzer-sub"
  topic = "scan-ready"

  ack_deadline_seconds = 600  # 10 minutes for long video processing

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
