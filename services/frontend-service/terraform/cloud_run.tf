# ==============================================================================
# CLOUD RUN SERVICE - Frontend Service (React SPA)
# ==============================================================================

resource "google_cloud_run_v2_service" "frontend_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" # Only accessible via IAP load balancer

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

      # ==============================================================================
      # ENVIRONMENT VARIABLES (matches docker-compose.yml)
      # ==============================================================================

      # API Service URL (for React app to fetch data)
      env {
        name  = "API_SERVICE_URL"
        value = data.terraform_remote_state.api_service.outputs.service_url
      }

      # Environment (dev/prod)
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      # Source code hash - triggers redeployment when app code changes
      env {
        name  = "SOURCE_CODE_HASH"
        value = local.source_code_hash
      }

      # Health check probes
      startup_probe {
        http_get {
          path = "/"
          port = 8080
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/"
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
    google_cloud_run_service_iam_member.frontend_invoke_api,
  ]
}

# Note: IAP authentication is configured in global infrastructure (terraform/iap.tf)
# This service is only accessible via the IAP-protected load balancer
