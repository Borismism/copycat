# BigQuery dataset for analytics

resource "google_bigquery_dataset" "copycat" {
  dataset_id  = "copycat_${var.environment}"
  location    = var.region
  description = "Analytics data for Copycat YouTube IP detection pipeline"

  labels = {
    environment = var.environment
    service     = "copycat"
  }

  # Prevent accidental deletion
  delete_contents_on_destroy = var.environment != "prod"
}

# Results table
resource "google_bigquery_table" "results" {
  dataset_id = google_bigquery_dataset.copycat.dataset_id
  table_id   = "results"

  time_partitioning {
    type  = "DAY"
    field = "analyzed_at"
  }

  clustering = ["match_found", "target_ip", "video_id"]

  schema = jsonencode([
    {
      name        = "video_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "YouTube video ID"
    },
    {
      name        = "title"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Video title"
    },
    {
      name        = "channel_id"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "YouTube channel ID"
    },
    {
      name        = "frame_gcs_path"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "GCS path to analyzed frame"
    },
    {
      name        = "chapter"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Chapter title where frame was extracted"
    },
    {
      name        = "timestamp_seconds"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Timestamp in video (seconds)"
    },
    {
      name        = "match_found"
      type        = "BOOLEAN"
      mode        = "REQUIRED"
      description = "Whether target IP was found"
    },
    {
      name        = "confidence"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Confidence score (0-100)"
    },
    {
      name        = "target_ip"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Target IP being searched for"
    },
    {
      name        = "gemini_response"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Full Gemini API response"
    },
    {
      name        = "analyzed_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "When the analysis was performed"
    },
    {
      name        = "processing_time_ms"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Processing time in milliseconds"
    }
  ])

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}

# Pipeline metrics table
resource "google_bigquery_table" "metrics" {
  dataset_id = google_bigquery_dataset.copycat.dataset_id
  table_id   = "metrics"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = jsonencode([
    {
      name        = "timestamp"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "Metric timestamp"
    },
    {
      name        = "service"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Service name"
    },
    {
      name        = "phase"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Pipeline phase"
    },
    {
      name        = "videos_processed"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Number of videos processed"
    },
    {
      name        = "frames_extracted"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Number of frames extracted"
    },
    {
      name        = "matches_found"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Number of matches found"
    },
    {
      name        = "processing_time_ms"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Average processing time"
    },
    {
      name        = "cost_usd"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Estimated cost in USD"
    }
  ])

  labels = {
    environment = var.environment
    service     = "copycat"
  }
}
