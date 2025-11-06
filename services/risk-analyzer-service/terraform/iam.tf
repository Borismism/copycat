# ==============================================================================
# IAM - Service account and permissions
# ==============================================================================

# Service account for Cloud Run
resource "google_service_account" "risk_analyzer_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Risk Analyzer Service"
  description  = "Service account for risk analyzer service"
}

# Firestore access (read/write videos and channels)
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

# PubSub publisher (publish to scan-ready topic)
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

# PubSub subscriber (read from video-discovered and vision-feedback subscriptions)
resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

# Secret Manager access (for IP configs stored in secrets)
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}

# Monitoring viewer (for debugging and observability)
resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.risk_analyzer_service.email}"
}
