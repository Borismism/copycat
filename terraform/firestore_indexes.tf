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

  # Index for: .where("matched_ips", "!=", []).order_by("scan_priority", DESC)
  # Firestore requires: sort field, then inequality field
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

resource "google_firestore_index" "videos_status_scan_priority_matched_ips" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  # Index for: .where("status", "==", X).where("matched_ips", "!=", []).order_by("scan_priority", DESC)
  # Required when filtering by status + has_ip_match + sorting by scan_priority
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

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

resource "google_firestore_index" "videos_status_last_analyzed_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  # Index for: .where("status", "in", ["failed", "error"]).order_by("last_analyzed_at", DESC)
  # Required for fetching recent errors in analytics
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "last_analyzed_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "videos_status_updated_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  # Index for: .where("status", "in", ["failed", "error"]).order_by("updated_at", DESC)
  # Required for fetching recent errors in analytics (failed videos don't have last_analyzed_at)
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "updated_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "videos_channel_scan_priority_matched_ips" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  # Index for: .where("channel_id", "==", X).order_by("scan_priority", DESC).order_by("matched_ips", DESC)
  # Required for channel videos page with sorting
  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

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

# Note: Single-field index for discovered_at is automatically created by Firestore
# No composite index needed for: .where("discovered_at", ">=", start).order_by("discovered_at")
# Correct firestore index imported
