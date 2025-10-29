# PubSub Topics for the pipeline

# Topic 1: Video discovered
resource "google_pubsub_topic" "video_discovered" {
  name = "copycat-video-discovered"

  message_retention_duration = "86600s" # 24 hours

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Topic 2: Chapters extracted
resource "google_pubsub_topic" "chapters_extracted" {
  name = "copycat-chapters-extracted"

  message_retention_duration = "86600s"

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Topic 3: Frames extracted
resource "google_pubsub_topic" "frames_extracted" {
  name = "copycat-frames-extracted"

  message_retention_duration = "86600s"

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Topic 4: Analysis complete
resource "google_pubsub_topic" "analysis_complete" {
  name = "copycat-analysis-complete"

  message_retention_duration = "86600s"

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "dead_letter" {
  name = "copycat-dead-letter"

  message_retention_duration = "604800s" # 7 days

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}
