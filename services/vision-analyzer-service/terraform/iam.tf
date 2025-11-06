# ==============================================================================
# IAM - Service account and permissions
# ==============================================================================

# Service account for Cloud Run
resource "google_service_account" "vision_analyzer_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Vision Analyzer Service"
  description  = "Service account for vision analyzer service (Gemini API access via Vertex AI)"
}

# Firestore access (read/write videos, channels, results)
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# PubSub publisher (publish to vision-feedback topic)
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# PubSub subscriber (read from scan-ready subscription)
resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# BigQuery data editor (write analysis results)
resource "google_project_iam_member" "bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# BigQuery job user (run queries)
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# Vertex AI user (Gemini 2.5 Flash API via Vertex AI - NO API KEY NEEDED!)
resource "google_project_iam_member" "aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# Monitoring viewer (debugging and observability)
resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# Secret Manager access (for IP configs)
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.vision_analyzer_service.email}"
}

# ==============================================================================
# PUSH SUBSCRIPTION SERVICE ACCOUNT (Nexus pattern)
# ==============================================================================

# Dedicated service account for PubSub push subscriptions
resource "google_service_account" "push_sa" {
  account_id   = "${var.service_name}-push"
  display_name = "Pub/Sub Push SA for ${var.service_name}"
  description  = "Service account used by PubSub to push messages to Cloud Run"
}

# Grant the push SA permission to invoke this Cloud Run service
resource "google_cloud_run_v2_service_iam_member" "run_invoker_push_sa" {
  name     = var.service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.push_sa.email}"
}
