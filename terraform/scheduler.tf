# ==============================================================================
# CLOUD SCHEDULER - Daily Stats Aggregation Job
# ==============================================================================

# Service account for Cloud Scheduler jobs
resource "google_service_account" "scheduler" {
  account_id   = "cloud-scheduler"
  display_name = "Cloud Scheduler Service Account"
  description  = "Service account for Cloud Scheduler jobs"
}

# Grant scheduler permission to invoke api-service
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoke_api" {
  project  = var.project_id
  location = var.region
  name     = "api-service"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Daily stats aggregation job (runs at 2 AM UTC daily)
resource "google_cloud_scheduler_job" "daily_stats_aggregation" {
  name             = "daily-stats-aggregation"
  description      = "Aggregate yesterday's statistics into daily_stats collection"
  schedule         = "0 2 * * *" # 2 AM UTC daily
  time_zone        = "UTC"
  attempt_deadline = "320s" # 5 minutes max runtime
  region           = "europe-west1" # Cloud Scheduler supported region

  retry_config {
    retry_count          = 3
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  http_target {
    http_method = "POST"
    uri         = "${data.google_cloud_run_v2_service.api_service.uri}/api/admin/jobs/aggregate-daily-stats"

    headers = {
      "Content-Type" = "application/json"
    }

    # Authenticate as the scheduler service account
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = data.google_cloud_run_v2_service.api_service.uri
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_service_iam_member.scheduler_invoke_api,
  ]
}

# Data source to get api-service URL
data "google_cloud_run_v2_service" "api_service" {
  name     = "api-service"
  location = var.region
  project  = var.project_id
}
