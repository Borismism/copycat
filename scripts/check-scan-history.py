#!/usr/bin/env python3
"""Check scan history for running scans."""

import sys
from datetime import datetime, timezone
from google.cloud import firestore

PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"


def check_scan_history():
    """Check for scans in 'running' status."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    print(f"🔍 Checking for scans in 'running' status...\n")

    # Query scan_history for running scans
    scans_ref = client.collection("scan_history")
    running_scans = scans_ref.where("status", "==", "running").stream()

    count = 0
    for scan in running_scans:
        count += 1
        scan_data = scan.to_dict()
        scan_id = scan.id

        title = scan_data.get("video_title", "Unknown")
        channel = scan_data.get("channel_title", "Unknown")
        video_id = scan_data.get("video_id", "Unknown")
        started_at = scan_data.get("started_at")

        print(f"🎬 Scan: {title}")
        print(f"   Channel: {channel}")
        print(f"   Video ID: {video_id}")
        print(f"   Scan ID: {scan_id}")

        if started_at:
            if hasattr(started_at, "timestamp"):
                started_dt = datetime.fromtimestamp(started_at.timestamp(), tz=timezone.utc)
            else:
                started_dt = started_at

            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)

            elapsed = datetime.now(timezone.utc) - started_dt
            elapsed_minutes = elapsed.total_seconds() / 60

            print(f"   Started: {started_dt.isoformat()}")
            print(f"   Elapsed: {elapsed_minutes:.1f} minutes")

            if elapsed_minutes > 10:
                print(f"   ⚠️  STUCK: Running for {elapsed_minutes:.1f} minutes!")
                print(f"   🔧 Marking as failed...")

                # Mark as failed
                scan.reference.update({
                    "status": "failed",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                    "error_message": "Scan stuck in 'running' status - likely instance was killed"
                })
                print(f"   ✅ Updated to 'failed'")
        print()

    if count == 0:
        print("✅ No scans currently running")
    else:
        print(f"\n📊 Total: {count} scan(s) checked")


if __name__ == "__main__":
    try:
        check_scan_history()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
