# ==============================================================================
# CLOUD RUN SERVICE - Risk Analyzer
# ==============================================================================

resource "google_cloud_run_v2_service" "risk_analyzer_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Only accessible from PubSub and other services

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

      # ==============================================================================
      # ENVIRONMENT VARIABLES
      # ==============================================================================

      # GCP Configuration
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

      # Firestore Configuration
      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = data.terraform_remote_state.global.outputs.firestore_database
      }

      # PubSub Configuration - Subscriptions
      env {
        name  = "PUBSUB_SUBSCRIPTION_VIDEO_DISCOVERED"
        value = "risk-analyzer-video-discovered-sub"
      }

      env {
        name  = "PUBSUB_SUBSCRIPTION_VISION_FEEDBACK"
        value = "risk-analyzer-vision-feedback-sub"
      }

      env {
        name  = "PUBSUB_TIMEOUT_SECONDS"
        value = "30"
      }

      # PubSub Configuration - Topics (for publishing)
      env {
        name  = "PUBSUB_TOPIC_SCAN_READY"
        value = "scan-ready"
      }

      # Logging Configuration
      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      env {
        name  = "DEBUG"
        value = var.environment == "dev" ? "true" : "false"
      }

      # Source code hash - triggers redeployment when app code changes
      env {
        name  = "SOURCE_HASH"
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
    google_project_iam_member.pubsub_publisher,
    google_project_iam_member.pubsub_subscriber,
    google_project_iam_member.secret_accessor,
  ]
}

# Allow PubSub to invoke this service
resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker" {
  name     = google_cloud_run_v2_service.risk_analyzer_service.name
  location = google_cloud_run_v2_service.risk_analyzer_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Get project number for PubSub service account
data "google_project" "project" {
  project_id = var.project_id
}
