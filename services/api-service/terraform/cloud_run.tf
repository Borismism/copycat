# ==============================================================================
# CLOUD RUN SERVICE - API Service (Public HTTP Gateway)
# ==============================================================================

resource "google_cloud_run_v2_service" "api_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # Public API - accessible from anywhere

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

      # ==============================================================================
      # ENVIRONMENT VARIABLES (matches docker-compose.yml)
      # ==============================================================================

      # GCP Project Configuration
      # Note: In docker-compose we use TWO project IDs:
      # - GCP_PROJECT_ID: for emulators (Firestore/PubSub)
      # - GEMINI_PROJECT_ID: for production Gemini API (via discovery service)
      # In Cloud Run, same project for both
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GEMINI_PROJECT_ID"
        value = var.project_id # Same as GCP_PROJECT_ID in production
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      # Firestore Configuration
      env {
        name  = "FIRESTORE_DATABASE"
        value = data.terraform_remote_state.global.outputs.firestore_database
      }

      # PubSub Configuration
      env {
        name  = "PUBSUB_TOPIC_SCAN_READY"
        value = "scan-ready"
      }

      # Environment (dev/prod)
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      # Discovery Service URL
      env {
        name  = "DISCOVERY_SERVICE_URL"
        value = data.terraform_remote_state.discovery_service.outputs.service_url
      }

      # Vision Analyzer Service URL
      env {
        name  = "VISION_ANALYZER_SERVICE_URL"
        value = data.terraform_remote_state.vision_analyzer_service.outputs.service_url
      }

      # Gemini Configuration
      env {
        name  = "GEMINI_LOCATION"
        value = var.gemini_location
      }

      # Source code hash - triggers redeployment when app code changes
      env {
        name  = "SOURCE_CODE_HASH"
        value = local.app_source_hash
      }

      # Health check probes
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
    google_project_iam_member.bigquery_viewer,
    google_project_iam_member.pubsub_publisher,
    google_cloud_run_v2_service_iam_member.api_invoke_discovery,
  ]
}

# Removed public access - API service is now protected by IAP
# Only frontend-service can invoke (configured in frontend-service/terraform/iam.tf)
