#!/usr/bin/env python3
"""
Cleanup cron job for videos stuck in 'processing' status.

Run every 10 minutes to catch videos that got stuck due to:
- Gemini API hanging
- Instance crashes
- Cloud Run scale-down
- Network issues

This is a safety net - the main fixes in gemini_client.py and main.py
should prevent most stuck videos.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from google.cloud import firestore

# Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "copycat-429012")
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE_ID", "copycat")
STUCK_THRESHOLD_MINUTES = 20  # Videos processing >20 minutes are stuck

def main():
    """Find and mark stuck videos as failed."""
    try:
        db = firestore.Client(project=GCP_PROJECT_ID, database=FIRESTORE_DATABASE)

        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)

        print(f"🔍 Checking for videos stuck in 'processing' since {cutoff_time.isoformat()}...")

        # Query videos in processing status
        videos_ref = db.collection("videos")
        stuck_videos = videos_ref.where("status", "==", "processing").stream()

        marked_count = 0
        scan_history_count = 0

        for video in stuck_videos:
            video_data = video.to_dict()
            video_id = video.id

            # Check processing_started_at timestamp
            processing_started = video_data.get("processing_started_at")

            if not processing_started:
                # No timestamp - definitely stuck
                print(f"⚠️  Video {video_id} has no processing_started_at, marking as failed")
                should_mark = True
                stuck_duration = "unknown"
            else:
                # Convert to datetime if needed
                if hasattr(processing_started, "timestamp"):
                    started_dt = datetime.fromtimestamp(processing_started.timestamp(), tz=timezone.utc)
                else:
                    started_dt = processing_started

                # Ensure timezone-aware
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)

                # Check if stuck
                if started_dt < cutoff_time:
                    stuck_duration_mins = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
                    stuck_duration = f"{stuck_duration_mins:.1f}m"
                    should_mark = True
                else:
                    should_mark = False

            if should_mark:
                print(f"🔧 Marking stuck video {video_id} as failed (processing for {stuck_duration})")

                # Mark video as failed
                video.reference.update({
                    "status": "failed",
                    "error_message": f"Video stuck in processing for >{STUCK_THRESHOLD_MINUTES} minutes - likely Gemini timeout or instance crash",
                    "error_type": "ProcessingTimeout",
                    "failed_at": firestore.SERVER_TIMESTAMP,
                    "processing_started_at": firestore.DELETE_FIELD,  # Clear stuck timestamp
                })

                marked_count += 1

                # Mark related scan history as failed
                scan_history_query = db.collection("scan_history").where("video_id", "==", video_id).where("status", "==", "running")
                for scan_doc in scan_history_query.stream():
                    scan_doc.reference.update({
                        "status": "failed",
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "error_message": f"Video stuck in processing (cleanup cron)",
                    })
                    scan_history_count += 1

        print(f"\n📊 Summary:")
        print(f"   Marked {marked_count} videos as failed")
        print(f"   Updated {scan_history_count} scan history entries")

        if marked_count == 0:
            print("✅ No stuck videos found!")
        else:
            print(f"✅ Cleanup complete - marked {marked_count} stuck video(s) as failed")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
