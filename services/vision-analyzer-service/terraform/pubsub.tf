# ==============================================================================
# PUBSUB SUBSCRIPTION - Vision Analyzer Service
# ==============================================================================

# Subscription: Scan-ready videos (from risk-analyzer-service or api-service)
resource "google_pubsub_subscription" "scan_ready" {
  name  = "scan-ready-vision-analyzer-sub"
  topic = "projects/${var.project_id}/topics/scan-ready"

  ack_deadline_seconds = 600 # 10 minutes for long video processing

  # Limit concurrent video processing to control Gemini costs
  # This controls how many videos are analyzed concurrently
  enable_exactly_once_delivery = false

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.vision_analyzer_service.uri}/analyze"

    attributes = {
      x-goog-version = "v1"
    }

    oidc_token {
      service_account_email = google_service_account.push_sa.email
      audience              = google_cloud_run_v2_service.vision_analyzer_service.uri
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = "projects/${var.project_id}/topics/copycat-dead-letter"
    max_delivery_attempts = 5 # GCP minimum is 5
  }

  expiration_policy {
    ttl = "" # Never expire
  }

  depends_on = [
    google_cloud_run_v2_service.vision_analyzer_service,
    google_cloud_run_v2_service_iam_member.run_invoker_push_sa,
  ]
}
