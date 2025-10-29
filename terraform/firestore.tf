# ==============================================================================
# FIRESTORE DATABASE & COMPREHENSIVE INDEXES
# ==============================================================================
# Complete index configuration for all current and future query patterns
# covering discovery, analytics, reporting, and trending detection.
# ==============================================================================

resource "google_firestore_database" "copycat" {
  name        = "copycat-${var.environment}"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Prevent accidental deletion in production
  deletion_policy = var.environment == "prod" ? "ABANDON" : "DELETE"
}

# ==============================================================================
# VIDEOS COLLECTION INDEXES
# ==============================================================================

# Index 1: Videos by status and discovery time
# Use case: Filter videos by processing status, sorted by when discovered
# Query: .where("status", "==", "pending").order_by("discovered_at", DESC)
resource "google_firestore_index" "videos_by_status" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "discovered_at"
    order      = "DESCENDING"
  }
}

# Index 2: Video rescanning - detect trending videos (original query)
# Use case: Find recently discovered videos with low views (may be going viral)
# Query: .where("view_count", "<", 10000)
#        .where("discovered_at", ">=", cutoff)
#        .order_by("view_count", DESC)
#        .order_by("discovered_at", ASC)
# CRITICAL: Field order matters for inequality filters
resource "google_firestore_index" "videos_rescan_trending" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "view_count"
    order      = "ASCENDING"  # Must be ASC for "<" inequality
  }

  fields {
    field_path = "discovered_at"
    order      = "ASCENDING"
  }
}

# Index 2b: Video rescanning - alternative query pattern
# Use case: Recently discovered videos sorted by view count
# Query: .where("discovered_at", ">=", cutoff).order_by("view_count", DESC)
resource "google_firestore_index" "videos_rescan_by_views" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "discovered_at"
    order      = "ASCENDING"
  }

  fields {
    field_path = "view_count"
    order      = "DESCENDING"
  }
}

# Index 3: Top videos by view count
# Use case: Analytics dashboard - show most viewed videos
# Query: .order_by("view_count", DESC).limit(100)
resource "google_firestore_index" "videos_by_views" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "view_count"
    order      = "DESCENDING"
  }
}

# Index 4: Videos by channel and publish date
# Use case: Channel history view, video timeline per channel
# Query: .where("channel_id", "==", channel_id).order_by("published_at", DESC)
resource "google_firestore_index" "videos_by_channel_published" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "published_at"
    order      = "DESCENDING"
  }
}

# Index 4b: Videos by channel and discovery time
# Use case: Channel videos sorted by when we found them
# Query: .where("channel_id", "==", channel_id).order_by("discovered_at", DESC)
resource "google_firestore_index" "videos_by_channel_discovered" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "discovered_at"
    order      = "DESCENDING"
  }
}

# Index 4c: Videos by channel and view count
# Use case: Channel's most viewed videos
# Query: .where("channel_id", "==", channel_id).order_by("view_count", DESC)
resource "google_firestore_index" "videos_by_channel_views" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "view_count"
    order      = "DESCENDING"
  }
}

# Index 4d: Videos by channel and duration
# Use case: Channel's longest videos
# Query: .where("channel_id", "==", channel_id).order_by("duration_seconds", DESC)
resource "google_firestore_index" "videos_by_channel_duration" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "duration_seconds"
    order      = "DESCENDING"
  }
}

# Index 4e: Videos by channel, status, and view count
# Use case: Filter by channel and status, sort by views
# Query: .where("channel_id", "==", X).where("status", "==", Y).order_by("view_count", DESC)
resource "google_firestore_index" "videos_by_channel_status_views" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "view_count"
    order      = "DESCENDING"
  }
}

# Index 4f: Videos by channel, status, and discovered_at
# Use case: Filter by channel and status, sort by when discovered
# Query: .where("channel_id", "==", X).where("status", "==", Y).order_by("discovered_at", DESC)
resource "google_firestore_index" "videos_by_channel_status_discovered" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "discovered_at"
    order      = "DESCENDING"
  }
}

# Index 4g: Videos by channel, status, and duration
# Use case: Filter by channel and status, sort by duration
# Query: .where("channel_id", "==", X).where("status", "==", Y).order_by("duration_seconds", DESC)
resource "google_firestore_index" "videos_by_channel_status_duration" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "duration_seconds"
    order      = "DESCENDING"
  }
}

# Index 4h: Videos by channel, status, and published_at
# Use case: Filter by channel and status, sort by publish date
# Query: .where("channel_id", "==", X).where("status", "==", Y).order_by("published_at", DESC)
resource "google_firestore_index" "videos_by_channel_status_published" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "published_at"
    order      = "DESCENDING"
  }
}

# Index 5: Videos by matched IP targets
# Use case: See all videos for specific IP (e.g., "Superman AI Content")
# Query: .where("matched_ips", "array-contains", "Superman AI Content")
#        .order_by("view_count", DESC)
resource "google_firestore_index" "videos_by_ip_and_views" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "matched_ips"
    array_config = "CONTAINS"
  }

  fields {
    field_path = "view_count"
    order      = "DESCENDING"
  }
}

# Index 6: Recent high-view videos (viral detection)
# Use case: Find videos discovered recently with high views (already viral)
# Query: .where("discovered_at", ">=", yesterday)
#        .where("view_count", ">", 100000)
#        .order_by("view_count", DESC)
resource "google_firestore_index" "videos_recent_viral" {
  database   = google_firestore_database.copycat.name
  collection = "videos"

  fields {
    field_path = "view_count"
    order      = "DESCENDING"
  }

  fields {
    field_path = "discovered_at"
    order      = "DESCENDING"
  }
}

# ==============================================================================
# CHANNELS COLLECTION INDEXES
# ==============================================================================

# Index 7: Channels due for scanning
# Use case: Get channels that need to be rescanned based on tier frequency
# Query: .where("next_scan_at", "<=", now).order_by("next_scan_at", ASC)
resource "google_firestore_index" "channels_due_for_scan" {
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "next_scan_at"
    order      = "ASCENDING"
  }
}

# Index 8: Channels by risk score
# Use case: Prioritize high-risk channels, analytics dashboard
# Query: .where("risk_score", ">=", 50).order_by("risk_score", DESC)
resource "google_firestore_index" "channels_by_risk" {
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "risk_score"
    order      = "DESCENDING"
  }
}

# Index 9: Channels by tier and risk
# Use case: Get all PLATINUM tier channels sorted by risk
# Query: .where("tier", "==", "PLATINUM").order_by("risk_score", DESC)
resource "google_firestore_index" "channels_by_tier_and_risk" {
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "tier"
    order      = "ASCENDING"
  }

  fields {
    field_path = "risk_score"
    order      = "DESCENDING"
  }
}

# Index 10: Channels by infringement rate
# Use case: Find channels with highest violation rates
# Query: .where("total_videos_found", ">", 10)
#        .order_by("infringement_rate", DESC)
resource "google_firestore_index" "channels_by_infringement_rate" {
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "total_videos_found"
    order      = "ASCENDING"
  }

  fields {
    field_path = "infringement_rate"
    order      = "DESCENDING"
  }
}

# Index 10b: Channels needing deep scan
# Use case: Find channels that haven't had deep scan yet
# Query: .where("deep_scan_completed", "==", False).limit(50)
resource "google_firestore_index" "channels_needing_deep_scan" {
  database   = google_firestore_database.copycat.name
  collection = "channels"

  fields {
    field_path = "deep_scan_completed"
    order      = "ASCENDING"
  }
}

# ==============================================================================
# KEYWORD_SCAN_STATE COLLECTION INDEXES
# ==============================================================================

# Index 11: Keywords by priority and staleness
# Use case: Keyword rotation - scan HIGH priority keywords that are stale
# Query: .where("priority", "==", "high").order_by("last_scanned_at", ASC)
resource "google_firestore_index" "keywords_by_priority" {
  database   = google_firestore_database.copycat.name
  collection = "keyword_scan_state"

  fields {
    field_path = "priority"
    order      = "ASCENDING"
  }

  fields {
    field_path = "last_scanned_at"
    order      = "ASCENDING"
  }
}

# Index 12: Keywords by effectiveness
# Use case: Identify most productive keywords for discovery
# Query: .where("total_scans", ">", 5)
#        .order_by("videos_found", DESC)
resource "google_firestore_index" "keywords_by_effectiveness" {
  database   = google_firestore_database.copycat.name
  collection = "keyword_scan_state"

  fields {
    field_path = "total_scans"
    order      = "ASCENDING"
  }

  fields {
    field_path = "videos_found"
    order      = "DESCENDING"
  }
}

# ==============================================================================
# DISCOVERY_METRICS COLLECTION INDEXES
# ==============================================================================

# Index 13: Metrics by timestamp (time-series analytics)
# Use case: Get metrics for date range, performance dashboards
# Query: .where("timestamp", ">=", start).where("timestamp", "<=", end)
#        .order_by("timestamp", DESC)
resource "google_firestore_index" "discovery_metrics_by_time" {
  database   = google_firestore_database.copycat.name
  collection = "discovery_metrics"

  fields {
    field_path = "timestamp"
    order      = "DESCENDING"
  }
}

# Index 14: Metrics by efficiency (quota usage per video)
# Use case: Track discovery efficiency over time
# Query: .where("videos_discovered", ">", 0)
#        .order_by("quota_used", ASC)
resource "google_firestore_index" "discovery_metrics_efficiency" {
  database   = google_firestore_database.copycat.name
  collection = "discovery_metrics"

  fields {
    field_path = "videos_discovered"
    order      = "ASCENDING"
  }

  fields {
    field_path = "quota_used"
    order      = "ASCENDING"
  }
}

# ==============================================================================
# VIEW_SNAPSHOTS COLLECTION INDEXES
# ==============================================================================

# Index 15: View snapshots by video and time
# Use case: Track view growth over time for trending detection
# Query: .where("video_id", "==", video_id).order_by("timestamp", DESC)
resource "google_firestore_index" "view_snapshots_by_video" {
  database   = google_firestore_database.copycat.name
  collection = "view_snapshots"

  fields {
    field_path = "video_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "timestamp"
    order      = "DESCENDING"
  }
}

# ==============================================================================
# RESULTS COLLECTION INDEXES (for vision analyzer output)
# ==============================================================================

# Index 16: Results by match status and confidence
# Use case: Get high-confidence IP matches for takedown reports
# Query: .where("match_found", "==", true)
#        .order_by("confidence", DESC)
#        .order_by("analyzed_at", DESC)
resource "google_firestore_index" "results_by_match" {
  database   = google_firestore_database.copycat.name
  collection = "results"

  fields {
    field_path = "match_found"
    order      = "ASCENDING"
  }

  fields {
    field_path = "confidence"
    order      = "DESCENDING"
  }

  fields {
    field_path = "analyzed_at"
    order      = "DESCENDING"
  }
}

# Index 17: Results by character detected
# Use case: Get all videos with specific character (e.g., "Superman")
# Query: .where("characters_detected", "array-contains", "Superman")
#        .order_by("confidence", DESC)
resource "google_firestore_index" "results_by_character" {
  database   = google_firestore_database.copycat.name
  collection = "results"

  fields {
    field_path = "characters_detected"
    array_config = "CONTAINS"
  }

  fields {
    field_path = "confidence"
    order      = "DESCENDING"
  }
}

# Index 18: Results by recommended action
# Use case: Get all videos flagged for takedown
# Query: .where("recommended_action", "==", "flag")
#        .order_by("infringement_likelihood", DESC)
resource "google_firestore_index" "results_by_action" {
  database   = google_firestore_database.copycat.name
  collection = "results"

  fields {
    field_path = "recommended_action"
    order      = "ASCENDING"
  }

  fields {
    field_path = "infringement_likelihood"
    order      = "DESCENDING"
  }
}
