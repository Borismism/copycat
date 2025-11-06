# ==============================================================================
# IAM - Service account and permissions
# ==============================================================================

# Get project number for IAP service account
data "google_project" "project" {
  project_id = var.project_id
}

# Service account for Cloud Run
resource "google_service_account" "frontend_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Frontend Service"
  description  = "Service account for frontend service (React SPA)"
}

# Grant frontend-service permission to invoke api-service
resource "google_cloud_run_service_iam_member" "frontend_invoke_api" {
  service  = data.terraform_remote_state.api_service.outputs.service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.frontend_service.email}"
}

# Grant IAP service account permission to invoke frontend-service
# Required for IAP to work with Cloud Run
# See: https://cloud.google.com/iap/docs/enabling-cloud-run
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  name     = google_cloud_run_v2_service.frontend_service.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com"
}
