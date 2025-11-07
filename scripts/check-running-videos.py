#!/usr/bin/env python3
"""Check videos currently in processing status."""

import sys
from datetime import datetime, timezone
from google.cloud import firestore

PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"


def check_running_videos():
    """Check videos currently processing."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    print(f"🔍 Checking for videos currently processing...\n")

    # Query videos in processing status
    videos_ref = client.collection("videos")
    processing_videos = videos_ref.where("status", "==", "processing").stream()

    count = 0
    for video in processing_videos:
        count += 1
        video_data = video.to_dict()
        video_id = video.id

        title = video_data.get("title", "Unknown")
        channel = video_data.get("channel_title", "Unknown")
        started_at = video_data.get("processing_started_at")

        if started_at:
            if hasattr(started_at, "timestamp"):
                started_dt = datetime.fromtimestamp(started_at.timestamp(), tz=timezone.utc)
            else:
                started_dt = started_at

            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)

            elapsed = datetime.now(timezone.utc) - started_dt
            elapsed_minutes = elapsed.total_seconds() / 60

            print(f"📹 Video: {title}")
            print(f"   Channel: {channel}")
            print(f"   Video ID: {video_id}")
            print(f"   Started: {started_dt.isoformat()}")
            print(f"   Elapsed: {elapsed_minutes:.1f} minutes")

            if elapsed_minutes > 10:
                print(f"   ⚠️  WARNING: Processing for {elapsed_minutes:.1f} minutes (may be stuck!)")
            print()

    if count == 0:
        print("✅ No videos currently processing")
    else:
        print(f"\n📊 Total: {count} video(s) processing")


if __name__ == "__main__":
    try:
        check_running_videos()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
