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

# Service account for Cloud Run
resource "google_service_account" "api_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "API Service"
  description  = "Service account for API gateway service"
}

# IAM roles for service account
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "bigquery_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# Get discovery-service URL from remote state
data "terraform_remote_state" "discovery_service" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/services/discovery-service/${var.environment}"
  }
}

# Get global infrastructure from remote state (Firestore, etc.)
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/global-infra"
  }
}

resource "google_cloud_run_service_iam_member" "api_invoke_discovery" {
  service  = data.terraform_remote_state.discovery_service.outputs.service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_service.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "api_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api_service.email

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
        name  = "FIRESTORE_DATABASE"
        value = data.terraform_remote_state.global.outputs.firestore_database
      }

      env {
        name  = "DISCOVERY_SERVICE_URL"
        value = data.terraform_remote_state.discovery_service.outputs.service_url
      }

      env {
        name  = "SOURCE_CODE_HASH"
        value = local.app_source_hash
      }
    }
  }

  depends_on = [
    google_project_iam_member.firestore_user,
    google_project_iam_member.bigquery_viewer,
    google_cloud_run_service_iam_member.api_invoke_discovery,
  ]
}

# Allow unauthenticated access (for now - can add IAP later)
resource "google_cloud_run_service_iam_member" "api_noauth" {
  service  = google_cloud_run_v2_service.api_service.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
