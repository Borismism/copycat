# PubSub Topics for the Copycat pipeline
#
# Pipeline flow:
# 1. discovery-service → copycat-video-discovered → risk-analyzer-service
# 2. risk-analyzer-service → scan-ready → vision-analyzer-service
# 3. vision-analyzer-service → vision-feedback → risk-analyzer-service (adaptive learning)

# Topic 1: Video discovered (discovery → risk-analyzer)
resource "google_pubsub_topic" "video_discovered" {
  name = "copycat-video-discovered"

  message_retention_duration = "86600s" # 24 hours

  labels = {
    service = "copycat"
    purpose = "video-discovery"
  }
}

# Topic 2: Scan ready (risk-analyzer/api → vision-analyzer)
resource "google_pubsub_topic" "scan_ready" {
  name = "scan-ready"

  message_retention_duration = "86600s" # 24 hours

  labels = {
    service = "copycat"
    purpose = "vision-analysis"
  }
}

# Topic 3: Vision feedback (vision-analyzer → risk-analyzer)
resource "google_pubsub_topic" "vision_feedback" {
  name = "vision-feedback"

  message_retention_duration = "86600s" # 24 hours

  labels = {
    service = "copycat"
    purpose = "adaptive-learning"
  }
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "dead_letter" {
  name = "copycat-dead-letter"

  message_retention_duration = "604800s" # 7 days

  labels = {
    service = "copycat"
    purpose = "error-handling"
  }
}
