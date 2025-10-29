output "pubsub_topics" {
  description = "PubSub topic names"
  value = {
    video_discovered   = google_pubsub_topic.video_discovered.name
    chapters_extracted = google_pubsub_topic.chapters_extracted.name
    frames_extracted   = google_pubsub_topic.frames_extracted.name
    analysis_complete  = google_pubsub_topic.analysis_complete.name
    dead_letter        = google_pubsub_topic.dead_letter.name
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

  📋 Next Steps:
     1. Request quota increase (if needed): See HOW_TO_GET_YOUTUBE_API_KEY.md
     2. Deploy services: ./scripts/deploy-service.sh <service-name> dev
     3. Monitor quota usage: GCP Console → APIs & Services → Dashboard
     4. View logs: gcloud run services logs tail <service-name>

  EOT
}
