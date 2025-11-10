# ==============================================================================
# CLOUD SCHEDULER - Hourly discovery runs
# ==============================================================================

# Cloud Scheduler job - runs every hour with AUTO quota calculation
# Quota is dynamically calculated based on:
# - Remaining daily quota
# - Hours left until midnight UTC
# - Ensures perfect quota depletion by end of day
# Note: Cloud Scheduler location must be europe-west1 (different from Cloud Run region)
resource "google_cloud_scheduler_job" "hourly_discovery" {
  name             = "${var.service_name}-hourly"
  region           = var.scheduler_region # europe-west1 for Cloud Scheduler
  description      = "Trigger discovery service every hour with automatic quota optimization"
  schedule         = var.discovery_schedule
  time_zone        = "UTC"
  attempt_deadline = "1800s" # 30 minutes timeout

  retry_config {
    retry_count          = 1
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "60s"
  }

  http_target {
    http_method = "POST"
    # No max_quota parameter = auto-calculate optimal quota
    uri = "${google_cloud_run_v2_service.discovery_service.uri}/discover/run"

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
