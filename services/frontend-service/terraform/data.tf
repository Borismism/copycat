# ==============================================================================
# DATA SOURCES - Remote state from global infrastructure and other services
# ==============================================================================

# Get global infrastructure from remote state (IAP configuration)
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "irdeto-copycat-tf-state"
    prefix = "copycat/global-infra"
  }
}

# Get api-service URL from remote state
data "terraform_remote_state" "api_service" {
  backend = "gcs"
  config = {
    bucket = "irdeto-copycat-tf-state"
    prefix = "copycat/services/api-service"
  }
}
