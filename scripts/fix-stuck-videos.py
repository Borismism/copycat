#!/usr/bin/env python3
"""Fix videos stuck in 'processing' status in production Firestore.

This script identifies videos that have been in 'processing' status for too long
and marks them as 'failed' so they can be retried or removed from the frontend.
"""

import sys
from datetime import datetime, timedelta, timezone
from google.cloud import firestore

# Production project
PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"

# Videos stuck in processing for more than 10 minutes are considered failed
STUCK_THRESHOLD_MINUTES = 10


def fix_stuck_videos():
    """Find and fix videos stuck in processing status."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    # Calculate cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)

    print(f"🔍 Checking for videos stuck in 'processing' status since {cutoff_time.isoformat()}...")

    # Query videos in processing status
    videos_ref = client.collection("videos")
    stuck_videos = videos_ref.where("scan_status", "==", "processing").stream()

    fixed_count = 0
    checked_count = 0

    for video in stuck_videos:
        checked_count += 1
        video_data = video.to_dict()
        video_id = video.id

        # Check when it was last updated
        updated_at = video_data.get("updated_at")
        if not updated_at:
            print(f"⚠️  Video {video_id} has no updated_at timestamp, marking as failed")
            video.reference.update({
                "scan_status": "failed",
                "error_message": "Stuck in processing with no timestamp",
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            fixed_count += 1
            continue

        # Convert to datetime if needed
        if hasattr(updated_at, "timestamp"):
            updated_datetime = datetime.fromtimestamp(updated_at.timestamp())
        else:
            updated_datetime = updated_at

        # Check if stuck
        if updated_datetime < cutoff_time:
            print(f"🔧 Fixing stuck video {video_id} (stuck since {updated_datetime.isoformat()})")
            video.reference.update({
                "scan_status": "failed",
                "error_message": "Processing timeout - instance was killed by Cloud Run health check",
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            fixed_count += 1
        else:
            time_in_processing = datetime.now(timezone.utc) - updated_datetime
            print(f"✅ Video {video_id} is still processing (for {time_in_processing.total_seconds():.0f}s)")

    print(f"\n📊 Summary:")
    print(f"   Checked: {checked_count} videos")
    print(f"   Fixed: {fixed_count} stuck videos")
    print(f"\n✅ Done!")


if __name__ == "__main__":
    try:
        fix_stuck_videos()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
