# ==============================================================================
# Firestore Composite Indexes
# ==============================================================================
#
# Composite indexes are required for queries that:
# 1. Filter by one field AND order by another field
# 2. Use inequality filters on multiple fields
#
# Note: Single-field indexes are created automatically by Firestore

resource "google_firestore_index" "videos_status_processing_started_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "processing_started_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "videos_scan_priority_matched_ips" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "scan_priority"
    order      = "DESCENDING"
  }

  fields {
    field_path = "matched_ips"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}
