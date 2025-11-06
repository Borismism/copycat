# ==============================================================================
# DATA SOURCES - Remote state from global infrastructure and other services
# ==============================================================================

# Get global infrastructure from remote state (Firestore, PubSub topics, BigQuery, etc.)
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/global-infra"
  }
}

# Get discovery-service URL from remote state
data "terraform_remote_state" "discovery_service" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/services/discovery-service/${var.environment}"
  }
}
