# ==============================================================================
# PUBSUB SUBSCRIPTIONS - Risk Analyzer Service
# ==============================================================================

# Subscription 1: Discovered videos (from discovery-service)
resource "google_pubsub_subscription" "video_discovered" {
  name  = "risk-analyzer-video-discovered-sub"
  topic = "projects/${var.project_id}/topics/copycat-video-discovered"

  ack_deadline_seconds = 600 # 10 minutes

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.risk_analyzer_service.uri}/process/video-discovered"

    oidc_token {
      service_account_email = google_service_account.push_sa.email
      audience              = google_cloud_run_v2_service.risk_analyzer_service.uri
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = "projects/${var.project_id}/topics/copycat-dead-letter"
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "" # Never expire
  }

  depends_on = [
    google_cloud_run_v2_service.risk_analyzer_service,
    google_cloud_run_v2_service_iam_member.run_invoker_push_sa,
  ]
}

# Subscription 2: Vision feedback (from vision-analyzer-service)
resource "google_pubsub_subscription" "vision_feedback" {
  name  = "risk-analyzer-vision-feedback-sub"
  topic = "projects/${var.project_id}/topics/vision-feedback"

  ack_deadline_seconds = 600 # 10 minutes

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.risk_analyzer_service.uri}/process/vision-feedback"

    oidc_token {
      service_account_email = google_service_account.push_sa.email
      audience              = google_cloud_run_v2_service.risk_analyzer_service.uri
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = "projects/${var.project_id}/topics/copycat-dead-letter"
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "" # Never expire
  }

  depends_on = [
    google_cloud_run_v2_service.risk_analyzer_service,
    google_cloud_run_v2_service_iam_member.run_invoker_push_sa,
  ]
}
