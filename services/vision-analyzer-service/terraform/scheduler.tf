# ==============================================================================
# CLOUD SCHEDULER - Cleanup stuck videos cron job
# ==============================================================================

# Service account for Cloud Scheduler
resource "google_service_account" "scheduler" {
  account_id   = "vision-analyzer-scheduler"
  display_name = "Cloud Scheduler for ${var.service_name}"
  description  = "Runs cleanup cron jobs for vision-analyzer-service"
}

# Grant Cloud Scheduler permission to invoke Cloud Run
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  name   = google_cloud_run_v2_service.vision_analyzer_service.name
  location = google_cloud_run_v2_service.vision_analyzer_service.location
  role   = "roles/run.invoker"
  member = "serviceAccount:${google_service_account.scheduler.email}"
}

# Cloud Scheduler job - runs every 10 minutes to cleanup stuck videos
resource "google_cloud_scheduler_job" "cleanup_stuck_videos" {
  name             = "vision-analyzer-cleanup"
  region           = var.scheduler_region  # europe-west1 for Cloud Scheduler
  description      = "Cleanup videos stuck in processing status every 10 minutes"
  schedule         = "*/10 * * * *"  # Every 10 minutes
  time_zone        = "UTC"
  attempt_deadline = "300s"  # 5 minutes timeout

  retry_config {
    retry_count          = 2  # Retry twice if failed
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "60s"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.vision_analyzer_service.uri}/admin/cleanup-stuck-videos"

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.vision_analyzer_service.uri
    }

    headers = {
      "Content-Type" = "application/json"
    }
  }

  depends_on = [
    google_cloud_run_v2_service.vision_analyzer_service,
    google_cloud_run_v2_service_iam_member.scheduler_invoker,
  ]
}
