output "service_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.risk_analyzer_service.uri
}

output "service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_v2_service.risk_analyzer_service.name
}

output "service_account_email" {
  description = "Email of the service account"
  value       = google_service_account.risk_analyzer_service.email
}

output "environment" {
  description = "Deployment environment"
  value       = var.environment
}

output "image_name" {
  description = "Deployed Docker image"
  value       = var.image_name
}
