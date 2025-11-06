# ==============================================================================
# IAM - Service accounts and permissions
# ==============================================================================

# Service account for Cloud Run
resource "google_service_account" "discovery_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Discovery Service"
  description  = "Service account for discovery service (YouTube API access)"
}

# Firestore access (read/write videos, channels, keyword_scan_state)
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

# PubSub publisher (publish to discovered-videos topic)
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

# Secret Manager access (YouTube API key)
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

# Monitoring viewer (for quota monitoring)
resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.discovery_service.email}"
}

# ==============================================================================
# CLOUD SCHEDULER SERVICE ACCOUNT
# ==============================================================================

# Service account for Cloud Scheduler (to invoke Cloud Run)
resource "google_service_account" "scheduler" {
  account_id   = "${var.service_name}-scheduler-sa"
  display_name = "Discovery Service Scheduler"
  description  = "Service account for Cloud Scheduler to invoke discovery service"
}

# Allow scheduler to invoke Cloud Run
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  name     = google_cloud_run_v2_service.discovery_service.name
  location = google_cloud_run_v2_service.discovery_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
