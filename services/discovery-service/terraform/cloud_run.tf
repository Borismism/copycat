# ==============================================================================
# CLOUD RUN SERVICE - Discovery Service
# ==============================================================================

resource "google_cloud_run_v2_service" "discovery_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # IAM-protected, accessible from scheduler

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

      # ==============================================================================
      # ENVIRONMENT VARIABLES (matches docker-compose.yml)
      # ==============================================================================

      # GCP Project Configuration
      # Note: In docker-compose we use TWO project IDs:
      # - GCP_PROJECT_ID: for emulators (Firestore/PubSub)
      # - YOUTUBE_PROJECT_ID: for YouTube API quota tracking
      # In Cloud Run, same project for both
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "YOUTUBE_PROJECT_ID"
        value = var.project_id # Same as GCP_PROJECT_ID in production
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      # Firestore Configuration
      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = data.terraform_remote_state.global.outputs.firestore_database
      }

      # PubSub Configuration
      env {
        name  = "PUBSUB_TOPIC_DISCOVERED_VIDEOS"
        value = "copycat-video-discovered"
      }

      env {
        name  = "PUBSUB_TIMEOUT_SECONDS"
        value = "30"
      }

      # YouTube API Configuration
      env {
        name = "YOUTUBE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = data.terraform_remote_state.global.outputs.secrets.youtube_api_key
            version = "latest"
          }
        }
      }

      env {
        name  = "YOUTUBE_QUOTA_LIMIT"
        value = var.youtube_daily_quota
      }

      env {
        name  = "YOUTUBE_DEFAULT_REGION"
        value = var.youtube_default_region
      }

      # Logging Configuration
      env {
        name  = "LOG_LEVEL"
        value = "DEBUG"
      }

      env {
        name  = "DEBUG"
        value = "true"
      }

      # Source code hash - triggers redeployment when app code changes
      env {
        name  = "SOURCE_HASH"
        value = local.app_source_hash
      }

      # Health probes with very long timeouts - allow up to 15 minutes of unresponsiveness
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        timeout_seconds       = 30
        period_seconds        = 240  # Check every 4 minutes
        failure_threshold     = 5    # Allow 20 minutes total (5 * 4min)
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 60
        timeout_seconds       = 30
        period_seconds        = 240  # Check every 4 minutes
        failure_threshold     = 5    # Allow 20 minutes total (5 * 4min)
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
# Deploy trigger Mon Nov 10 09:06:33 CET 2025
