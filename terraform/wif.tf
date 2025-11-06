# Workload Identity Federation for GitHub Actions
# Allows GitHub Actions workflows to authenticate to GCP without service account keys

locals {
  wif_pool_id = "copycat-pool"
}

resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = local.wif_pool_id
  display_name              = "GitHub Actions Pool - Copycat"
  description               = "Workload Identity Pool for GitHub Actions deployments"
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider-copycat"
  display_name                       = "GitHub Provider - Copycat"
  description                        = "OIDC provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Only allow tokens from our repository
  attribute_condition = "attribute.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Service Account for GitHub Actions deployments
resource "google_service_account" "github_actions_deployer" {
  account_id   = "copycat-github-deployer"
  display_name = "Copycat GitHub Actions Deployer"
  description  = "Service account used by GitHub Actions to deploy Copycat services"
}

# Grant deployer permissions
resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "deployer_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "deployer_artifacts_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "deployer_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "deployer_cloud_build" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

# Allow GitHub Actions to impersonate the deployer service account
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.github_actions_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository}"
}
