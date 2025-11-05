output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.vision_analyzer_service.uri
}

output "service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.vision_analyzer_service.name
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.vision_analyzer_service.email
}

output "subscription_name" {
  description = "PubSub subscription name"
  value       = google_pubsub_subscription.scan_ready.name
}
