#!/usr/bin/env python3
"""Analyze scan history to understand retry patterns."""

import sys
from datetime import datetime, timezone
from collections import defaultdict
from google.cloud import firestore

PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"


def analyze_scan_history():
    """Analyze scan attempts per video."""
    client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

    print(f"🔍 Analyzing scan history patterns...\n")

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
                "status": scan_data.get("status"),
                "started_at": scan_data.get("started_at"),
                "completed_at": scan_data.get("completed_at"),
                "video_title": scan_data.get("video_title"),
                "error_message": scan_data.get("error_message"),
            })

    # Find videos with multiple attempts
    print(f"📊 Videos with multiple scan attempts:\n")

    retried_videos = []
    for video_id, scans in videos.items():
        if len(scans) > 1:
            retried_videos.append((video_id, scans))

    # Sort by number of attempts (descending)
    retried_videos.sort(key=lambda x: len(x[1]), reverse=True)

    for video_id, scans in retried_videos[:10]:  # Top 10
        title = scans[0]["video_title"] or "Unknown"
        print(f"📹 {title}")
        print(f"   Video ID: {video_id}")
        print(f"   Total attempts: {len(scans)}")

        # Show each attempt
        for i, scan in enumerate(sorted(scans, key=lambda x: x.get("started_at") or datetime.min), 1):
            status = scan["status"]
            started = scan.get("started_at")
            error = scan.get("error_message", "")

            if started:
                if hasattr(started, "timestamp"):
                    started_dt = datetime.fromtimestamp(started.timestamp(), tz=timezone.utc)
                else:
                    started_dt = started
                time_str = started_dt.strftime("%H:%M:%S")
            else:
                time_str = "Unknown"

            error_preview = (error[:50] + "...") if (error and len(error) > 50) else (error or "")
            print(f"   {i}. {time_str} - {status} {f'({error_preview})' if error_preview else ''}")
        print()

    print(f"\n📈 Summary:")
    print(f"   Total videos scanned: {len(videos)}")
    print(f"   Videos with retries: {len(retried_videos)}")
    print(f"   Single-attempt videos: {len(videos) - len(retried_videos)}")

    # Status breakdown
    status_counts = defaultdict(int)
    for video_id, scans in videos.items():
        for scan in scans:
            status_counts[scan["status"]] += 1

    print(f"\n   Scan status breakdown:")
    for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {status}: {count}")


if __name__ == "__main__":
    try:
        analyze_scan_history()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
