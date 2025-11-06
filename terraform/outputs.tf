output "pubsub_topics" {
  description = "PubSub topic names"
  value = {
    video_discovered = google_pubsub_topic.video_discovered.name
    scan_ready       = google_pubsub_topic.scan_ready.name
    vision_feedback  = google_pubsub_topic.vision_feedback.name
    dead_letter      = google_pubsub_topic.dead_letter.name
  }
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.copycat.name
}

output "storage_buckets" {
  description = "Cloud Storage bucket names"
  value = {
    frames  = google_storage_bucket.frames.name
    results = google_storage_bucket.results.name
  }
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.copycat.dataset_id
}

output "bigquery_tables" {
  description = "BigQuery table IDs"
  value = {
    results = google_bigquery_table.results.table_id
    metrics = google_bigquery_table.metrics.table_id
  }
}

output "artifact_registry_repos" {
  description = "Artifact Registry repository names"
  value = {
    docker = google_artifact_registry_repository.docker.name
    python = google_artifact_registry_repository.python.name
  }
}

output "docker_repo_url" {
  description = "Docker repository URL for pushing images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "secrets" {
  description = "Secret Manager secret names"
  value = {
    youtube_api_key  = google_secret_manager_secret.youtube_api_key.secret_id
    target_ip_config = google_secret_manager_secret.target_ip_config.secret_id
  }
}

output "youtube_api_key_info" {
  description = "YouTube API key information (auto-generated and stored in Secret Manager)"
  value = {
    key_name       = google_apikeys_key.youtube_api_key.name
    secret_id      = google_secret_manager_secret.youtube_api_key.secret_id
    secret_version = google_secret_manager_secret_version.youtube_api_key.name
    restrictions   = "No restrictions (unrestricted API key)"
    default_quota  = "10,000 units/day (request increase via GCP Console)"
  }
}

output "wif_provider" {
  description = "Workload Identity Federation provider name"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "wif_service_account" {
  description = "Service account email for GitHub Actions"
  value       = google_service_account.github_actions_deployer.email
}

output "iap_oauth_client_id" {
  description = "IAP OAuth client ID"
  value       = google_iap_client.oauth_client.client_id
}

output "frontend_lb_ip" {
  description = "Frontend load balancer IP address"
  value       = google_compute_global_address.frontend_lb_ip.address
}

output "frontend_domain_dns" {
  description = "DNS record to configure for frontend domain"
  value = {
    domain = var.frontend_domain
    type   = "A"
    value  = google_compute_global_address.frontend_lb_ip.address
  }
}

output "setup_instructions" {
  description = "Post-deployment setup instructions"
  value       = <<-EOT

  ╔════════════════════════════════════════════════════════════════╗
  ║               Copycat Infrastructure Deployed                  ║
  ╚════════════════════════════════════════════════════════════════╝

  ✅ YouTube API Key: Auto-generated and stored in Secret Manager
     Secret: projects/${var.project_id}/secrets/youtube-api-key
     Restrictions: None (unrestricted for maximum compatibility)
     Default Quota: 10,000 units/day
     Status: Ready to use!

     💡 To increase quota:
        GCP Console → IAM & Admin → Quotas → YouTube Data API v3
        See HOW_TO_GET_YOUTUBE_API_KEY.md for details

  ✅ Gemini via Vertex AI: IAM authentication (no API key needed)
     API: aiplatform.googleapis.com
     Models: gemini-2.0-flash-exp, gemini-pro-vision
     Auth: Service accounts with aiplatform.user role
     Status: Ready to use!

  ✅ Workload Identity Federation: Configured for GitHub Actions
     Provider: ${google_iam_workload_identity_pool_provider.github_provider.name}
     Service Account: ${google_service_account.github_actions_deployer.email}
     Repository: ${var.github_repository}

     🔒 Add these secrets to your GitHub repository:
        GCP_WORKLOAD_IDENTITY_PROVIDER: ${google_iam_workload_identity_pool_provider.github_provider.name}
        GCP_SERVICE_ACCOUNT: ${google_service_account.github_actions_deployer.email}

  ✅ Identity-Aware Proxy (IAP): Frontend authentication configured
     Domain: ${var.frontend_domain}
     Load Balancer IP: ${google_compute_global_address.frontend_lb_ip.address}
     OAuth Client ID: ${google_iap_client.oauth_client.client_id}
     Authorized Users: ${length(var.iap_authorized_users)} configured

     🌐 DNS Configuration Required:
        Add an A record in your DNS provider:
        Name: ${var.frontend_domain}
        Type: A
        Value: ${google_compute_global_address.frontend_lb_ip.address}
        TTL: 300

     ⚠️  SSL Certificate will provision automatically after DNS is configured
        (may take 15-30 minutes)

  📋 Next Steps:
     1. Configure DNS A record (see above)
     2. Add GitHub secrets (see WIF section)
     3. Wait for SSL certificate to provision (~15-30 min after DNS)
     4. Access frontend at: https://${var.frontend_domain}
     5. Request quota increase (if needed): See HOW_TO_GET_YOUTUBE_API_KEY.md
     6. Deploy services: Push to main/develop branch (CI/CD) or run ./scripts/deploy-service.sh
     7. Monitor quota usage: GCP Console → APIs & Services → Dashboard

  EOT
}
