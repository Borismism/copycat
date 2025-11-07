#!/usr/bin/env python3
"""Check current video status distribution in production Firestore."""

import sys
from collections import Counter
from google.cloud import firestore

# Production project
PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"


def check_video_status():
    """Check status distribution of all videos."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    print(f"🔍 Checking video status distribution...")

    # Get all videos
    videos_ref = client.collection("videos")
    videos = videos_ref.stream()

    status_counts = Counter()
    total = 0

    for video in videos:
        total += 1
        video_data = video.to_dict()
        status = video_data.get("status", "unknown")
        status_counts[status] += 1

    print(f"\n📊 Video Status Summary:")
    print(f"   Total videos: {total}")
    print(f"\n   Status breakdown:")
    for status, count in status_counts.most_common():
        percentage = (count / total * 100) if total > 0 else 0
        print(f"   - {status}: {count} ({percentage:.1f}%)")

    print(f"\n✅ Done!")


if __name__ == "__main__":
    try:
        check_video_status()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
