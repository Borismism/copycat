# Service Account for GitLab CI/CD deployments
# Unlike GitHub Actions (which uses Workload Identity Federation),
# GitLab requires a service account key for authentication

resource "google_service_account" "gitlab_ci_deployer" {
  account_id   = "copycat-gitlab-deployer"
  display_name = "Copycat GitLab CI Deployer"
  description  = "Service account used by GitLab CI/CD to deploy Copycat services"
}

# Grant deployer permissions (Owner role for full IAM management)
resource "google_project_iam_member" "gitlab_deployer_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.gitlab_ci_deployer.email}"
}

# Create service account key for GitLab CI/CD
resource "google_service_account_key" "gitlab_ci_key" {
  service_account_id = google_service_account.gitlab_ci_deployer.name
}

# Output the key (base64 encoded) - add this to GitLab CI/CD variables as GCP_SERVICE_ACCOUNT_KEY
output "gitlab_ci_service_account_key" {
  value       = google_service_account_key.gitlab_ci_key.private_key
  sensitive   = true
  description = "Base64-encoded service account key for GitLab CI/CD. Add to GitLab as GCP_SERVICE_ACCOUNT_KEY variable."
}

output "gitlab_ci_service_account_email" {
  value       = google_service_account.gitlab_ci_deployer.email
  description = "GitLab CI deployer service account email"
}
