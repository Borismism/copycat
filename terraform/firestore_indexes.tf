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

  # Index for: .where("status", "in", ["failed", "error"]).order_by("last_analyzed_at", ASC)
  # Required for fetching recent errors in analytics
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "last_analyzed_at"
    order      = "ASCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "ASCENDING"
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

# ==============================================================================
# scan_history collection indexes
# ==============================================================================

resource "google_firestore_index" "scan_history_status_started_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "scan_history"

  # Index for: .where("status", "==", "running").order_by("started_at", DESC)
  # Required for SSE stream to fetch running scans
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "started_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "scan_history_status_completed_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "scan_history"

  # Index for: .where("status", "in", ["completed", "failed"]).order_by("completed_at", DESC)
  # Required for SSE stream to fetch recently completed/failed scans
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "completed_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "scan_history_video_id_status" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "scan_history"

  # Index for: .where("video_id", "==", X).where("status", "==", "running")
  # Required for deduplication check in vision-analyzer worker
  fields {
    field_path = "video_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

# ==============================================================================
# discovery_history collection indexes
# ==============================================================================

resource "google_firestore_index" "discovery_history_status_started_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "discovery_history"

  # Index for: .where("status", "==", "running").order_by("started_at", DESC)
  # Required for SSE stream to fetch running discovery runs
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "started_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "discovery_history_status_completed_at" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "discovery_history"

  # Index for: .where("status", "in", ["completed", "failed"]).order_by("completed_at", DESC)
  # Required for SSE stream to fetch recently completed/failed discovery runs
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "completed_at"
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

# Index for infringement_status filter with scan_priority sort
resource "google_firestore_index" "videos_infringement_status_scan_priority" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "videos"

  # Index for: .where("infringement_status", "==", "actionable").where("matched_ips", "!=", []).order_by("scan_priority", DESC)
  fields {
    field_path = "infringement_status"
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

# ==============================================================================
# channels collection indexes for enforcement page
# ==============================================================================

# Index for: .where("action_status", "==", X).order_by("channel_risk", DESC)
resource "google_firestore_index" "channels_action_status_risk" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "action_status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "channel_risk"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

# Index for: .where("action_status", "==", X).order_by("last_seen_at", DESC)
resource "google_firestore_index" "channels_action_status_last_seen" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "action_status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "last_seen_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}

# Index for: .where("tier", "==", X).where("action_status", "==", Y).order_by("channel_risk", DESC)
resource "google_firestore_index" "channels_tier_action_status_risk" {
  project    = var.project_id
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "tier"
    order      = "ASCENDING"
  }

  fields {
    field_path = "action_status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "channel_risk"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }
}
