# ==============================================================================
# IAM - Service account and permissions
# ==============================================================================

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
