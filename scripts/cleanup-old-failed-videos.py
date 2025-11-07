#!/usr/bin/env python3
"""Clean up old failed videos from production Firestore.

This script removes videos with 'failed' status that are older than a certain threshold.
"""

import sys
from datetime import datetime, timedelta, timezone
from google.cloud import firestore

# Production project
PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"

# Delete videos that failed more than 7 days ago
FAILED_RETENTION_DAYS = 7


def cleanup_old_failed_videos():
    """Find and delete old failed videos."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    # Calculate cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=FAILED_RETENTION_DAYS)

    print(f"🔍 Finding failed videos older than {cutoff_time.isoformat()}...")

    # Query videos with failed status
    videos_ref = client.collection("videos")
    failed_videos = videos_ref.where("status", "==", "failed").stream()

    deleted_count = 0
    checked_count = 0
    kept_recent = 0

    for video in failed_videos:
        checked_count += 1
        video_data = video.to_dict()
        video_id = video.id

        # Check when it failed
        failed_at = video_data.get("failed_at")

        if not failed_at:
            # No failed_at timestamp, check updated_at
            failed_at = video_data.get("updated_at")

        if not failed_at:
            print(f"⚠️  Video {video_id} has no timestamp, deleting anyway")
            video.reference.delete()
            deleted_count += 1
            continue

        # Convert to datetime if needed
        if hasattr(failed_at, "timestamp"):
            failed_datetime = datetime.fromtimestamp(failed_at.timestamp())
        else:
            failed_datetime = failed_at

        # Make timezone aware if needed
        if failed_datetime.tzinfo is None:
            failed_datetime = failed_datetime.replace(tzinfo=timezone.utc)

        # Check if old enough to delete
        if failed_datetime < cutoff_time:
            print(f"🗑️  Deleting old failed video {video_id} (failed {failed_datetime.isoformat()})")
            video.reference.delete()
            deleted_count += 1
        else:
            age_hours = (datetime.now(timezone.utc) - failed_datetime).total_seconds() / 3600
            print(f"✅ Keeping recent failed video {video_id} (failed {age_hours:.1f}h ago)")
            kept_recent += 1

    print(f"\n📊 Summary:")
    print(f"   Checked: {checked_count} failed videos")
    print(f"   Deleted: {deleted_count} old videos")
    print(f"   Kept: {kept_recent} recent failures")
    print(f"\n✅ Done!")


if __name__ == "__main__":
    try:
        cleanup_old_failed_videos()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
