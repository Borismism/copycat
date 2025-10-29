locals {
  # Watch app and web folders for source code changes
  source_dir    = "${path.module}/.."
  exclude_regex = "(\\.venv/|node_modules/|__pycache__/|\\.git/|dist/|\\.DS_Store|Thumbs\\.db|desktop\\.ini|\\._.*|~$|\\.pyc$|\\.pytest_cache/|\\.ruff_cache/)"

  all_files = fileset(local.source_dir, "**/*")
  source_files = toset([
    for f in local.all_files : f
    if length(regexall(local.exclude_regex, f)) == 0
  ])

  # Hash of source files - triggers Cloud Run update when code changes
  source_code_hash = sha256(join("", [
    for f in sort(local.source_files) : filesha256("${local.source_dir}/${f}")
  ]))
}

# Service account for Cloud Run
resource "google_service_account" "frontend_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Frontend Service"
  description  = "Service account for frontend service"
}

# Get api-service URL from remote state
data "terraform_remote_state" "api_service" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/services/api-service/${var.environment}"
  }
}

# Grant frontend-service permission to invoke api-service
resource "google_cloud_run_service_iam_member" "frontend_invoke_api" {
  service  = data.terraform_remote_state.api_service.outputs.service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.frontend_service.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "frontend_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.frontend_service.email

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
        name  = "API_SERVICE_URL"
        value = data.terraform_remote_state.api_service.outputs.service_url
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "SOURCE_CODE_HASH"
        value = local.source_code_hash
      }
    }
  }

  depends_on = [
    google_cloud_run_service_iam_member.frontend_invoke_api,
  ]
}

# Allow unauthenticated access (public UI)
resource "google_cloud_run_service_iam_member" "frontend_noauth" {
  service  = google_cloud_run_v2_service.frontend_service.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
