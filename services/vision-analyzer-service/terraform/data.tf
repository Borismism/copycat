# ==============================================================================
# DATA SOURCES - Remote state from global infrastructure
# ==============================================================================

# Get global infrastructure from remote state (Firestore, PubSub topics, BigQuery, etc.)
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/global-infra"
  }
}

# Get project number for PubSub service account
data "google_project" "project" {
  project_id = var.project_id
}
