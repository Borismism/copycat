# ==============================================================================
# IAM - Service account and permissions
# ==============================================================================

# Service account for Cloud Run
resource "google_service_account" "api_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "API Service"
  description  = "Service account for API gateway service"
}

# Firestore access (read/write all collections)
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# BigQuery viewer (read analytics/results)
resource "google_project_iam_member" "bigquery_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# BigQuery job user (run queries)
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# PubSub publisher (publish to scan-ready topic)
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# Allow API service to invoke discovery service
resource "google_cloud_run_service_iam_member" "api_invoke_discovery" {
  service  = data.terraform_remote_state.discovery_service.outputs.service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_service.email}"
}
