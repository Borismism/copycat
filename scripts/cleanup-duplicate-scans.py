#!/usr/bin/env python3
"""Clean up duplicate scan_history entries - keep only the latest per video."""

import sys
from datetime import datetime, timezone
from collections import defaultdict
from google.cloud import firestore

PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"


def cleanup_duplicate_scans():
    """Remove old/failed scan attempts, keep only the latest per video."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    print(f"🔍 Finding duplicate scan_history entries...\n")

    # Get all scans
    scans_ref = client.collection("scan_history")
    all_scans = scans_ref.stream()

    # Group by video_id
    videos = defaultdict(list)

    for scan in all_scans:
        scan_data = scan.to_dict()
        video_id = scan_data.get("video_id")
        if video_id:
            videos[video_id].append({
                "scan_id": scan.id,
                "ref": scan.reference,
                "status": scan_data.get("status"),
                "started_at": scan_data.get("started_at"),
                "completed_at": scan_data.get("completed_at"),
            })

    deleted_count = 0
    kept_count = 0

    print("📊 Processing videos with multiple scan attempts:\n")

    for video_id, scans in videos.items():
        if len(scans) <= 1:
            kept_count += len(scans)
            continue  # No duplicates

        # Sort by started_at (most recent last)
        scans_sorted = sorted(
            scans,
            key=lambda x: x.get("started_at") or datetime.min.replace(tzinfo=timezone.utc)
        )

        # Keep the last one (most recent)
        latest_scan = scans_sorted[-1]
        old_scans = scans_sorted[:-1]

        print(f"   Video {video_id[:20]}...")
        print(f"   - Total attempts: {len(scans)}")
        print(f"   - Keeping latest: {latest_scan['status']} (scan_id: {latest_scan['scan_id'][:8]}...)")
        print(f"   - Deleting {len(old_scans)} old attempts")

        # Delete old scans
        for old_scan in old_scans:
            try:
                old_scan["ref"].delete()
                deleted_count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to delete {old_scan['scan_id']}: {e}")

        kept_count += 1
        print()

    print(f"\n✅ Cleanup complete!")
    print(f"   Kept: {kept_count} scans (latest per video)")
    print(f"   Deleted: {deleted_count} old/duplicate scans")


if __name__ == "__main__":
    try:
        cleanup_duplicate_scans()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
