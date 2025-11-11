# ==============================================================================
# CLOUD RUN SERVICE - Vision Analyzer (Gemini 2.5 Flash)
# ==============================================================================

resource "google_cloud_run_v2_service" "vision_analyzer_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # IAM-protected, accessible from PubSub

  template {
    service_account = google_service_account.vision_analyzer_service.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_concurrent_videos # Limit concurrent videos to control costs
    }

    timeout = "${var.timeout_seconds}s" # Long timeout for video analysis (20 minutes)

    # Note: During deployments, Cloud Run sends SIGTERM to old instances
    # Our signal handler (main.py) will:
    # 1. Reject new requests (return 503)
    # 2. Wait for active processing to complete
    # 3. Exit gracefully when done
    # Cloud Run respects the timeout above before sending SIGKILL

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
      # - VERTEX_AI_PROJECT_ID: for production Gemini API
      # In Cloud Run, same project for both
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "VERTEX_AI_PROJECT_ID"
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
        name  = "PUBSUB_SCAN_READY_SUBSCRIPTION"
        value = "scan-ready-vision-analyzer-sub"
      }

      env {
        name  = "PUBSUB_FEEDBACK_TOPIC"
        value = "vision-feedback"
      }

      # Gemini Configuration (Vertex AI)
      env {
        name  = "GEMINI_MODEL"
        value = "gemini-2.5-flash"
      }

      env {
        name  = "GEMINI_LOCATION"
        value = var.gemini_location # us-central1 or europe-west4
      }

      # Budget Configuration
      env {
        name  = "DAILY_BUDGET_EUR"
        value = var.daily_budget_eur
      }

      # IP Config Configuration (Story 006)
      env {
        name  = "IP_CONFIG_COLLECTION"
        value = "ip_configs"
      }

      env {
        name  = "CONFIG_CACHE_TTL_SECONDS"
        value = "300" # 5 minutes
      }

      env {
        name  = "MAX_IPS_PER_VIDEO"
        value = "3" # Prevent prompt explosion
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

      # Health check probes removed - long-running Gemini video analysis jobs can't respond to probes
      # and get killed prematurely. Cloud Run will monitor port availability instead.
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

# Note: IAM invoker permission is configured via dedicated push SA in iam.tf (Nexus pattern)
# The PubSub subscription uses this dedicated SA for OIDC authentication
# Deploy trigger Mon Nov 10 09:06:33 CET 2025
