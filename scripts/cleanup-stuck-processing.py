#!/usr/bin/env python3
"""
Clean up videos stuck in 'processing' status.

Videos that have been processing for >1 hour are likely stuck and should be reset.
"""

import os
from datetime import datetime, timedelta
from google.cloud import firestore

# Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "copycat-429012")
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE_ID", "copycat")
PROCESSING_TIMEOUT_MINUTES = 10  # Videos processing >10 minutes are stuck

def main():
    # Initialize Firestore
    db = firestore.Client(project=GCP_PROJECT_ID, database=FIRESTORE_DATABASE)

    # Get all videos with status=processing
    print(f"🔍 Finding videos stuck in 'processing' status...")
    videos_ref = db.collection("videos")
    query = videos_ref.where("status", "==", "processing")

    stuck_videos = []
    from datetime import timezone
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)

    for doc in query.stream():
        data = doc.to_dict()
        video_id = doc.id

        # Check processing_started_at timestamp
        processing_started = data.get("processing_started_at")

        if processing_started:
            # Handle Firestore timestamp
            if hasattr(processing_started, 'seconds'):
                started_dt = datetime.fromtimestamp(processing_started.seconds, tz=timezone.utc)
            elif isinstance(processing_started, str):
                started_dt = datetime.fromisoformat(processing_started.replace('Z', '+00:00'))
            else:
                started_dt = processing_started

            # Ensure timezone-aware
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)

            # Check if stuck (processing > 10 minutes)
            if started_dt < cutoff_time:
                stuck_videos.append({
                    'id': video_id,
                    'title': data.get('title', 'Unknown'),
                    'started_at': started_dt,
                    'duration': (now - started_dt).total_seconds() / 60  # minutes
                })
        else:
            # No processing_started_at means it's definitely stuck
            stuck_videos.append({
                'id': video_id,
                'title': data.get('title', 'Unknown'),
                'started_at': None,
                'duration': None
            })

    if not stuck_videos:
        print("✅ No stuck videos found!")
        return

    print(f"\n⚠️  Found {len(stuck_videos)} stuck videos:\n")

    for i, video in enumerate(stuck_videos[:10], 1):
        duration_str = f"{video['duration']:.1f}m" if video['duration'] else "unknown"
        print(f"{i}. {video['id']} - {video['title'][:50]} (processing for {duration_str})")

    if len(stuck_videos) > 10:
        print(f"... and {len(stuck_videos) - 10} more")

    print(f"\n🗑️  Resetting {len(stuck_videos)} videos to 'discovered' status...")

    # Reset videos to discovered (so they can be re-scanned)
    batch = db.batch()
    count = 0
    scan_history_deleted = 0

    for video in stuck_videos:
        video_id = video['id']
        doc_ref = videos_ref.document(video_id)

        # Update video status
        batch.update(doc_ref, {
            'status': 'discovered',
            'processing_started_at': firestore.DELETE_FIELD,
            'reset_reason': f"Reset from stuck processing state (was processing for {video['duration']:.1f}m)" if video['duration'] else "Reset from stuck processing state",
            'reset_at': firestore.SERVER_TIMESTAMP,
        })
        count += 1

        # Also clean up scan_history entries for this video that are stuck in 'running'
        # Query scan_history for this video with status='running'
        scan_history_query = db.collection("scan_history").where("video_id", "==", video_id).where("status", "==", "running")

        for scan_doc in scan_history_query.stream():
            batch.delete(scan_doc.reference)
            scan_history_deleted += 1

        # Firestore batch limit is 500
        if count % 500 == 0:
            batch.commit()
            print(f"  ✓ Committed batch {count // 500} ({count} videos, {scan_history_deleted} scan history entries)")
            batch = db.batch()

    # Commit remaining
    if count % 500 != 0:
        batch.commit()

    print(f"\n✅ Successfully reset {len(stuck_videos)} videos to 'discovered' status!")
    print(f"   Also deleted {scan_history_deleted} stuck scan_history entries")
    print(f"   They will be re-queued for analysis on next discovery run.")

def cleanup_orphaned_scan_history():
    """
    Clean up scan_history entries that are stuck in 'processing' status
    even if the video itself is not processing anymore.
    """
    # Initialize Firestore
    database_id = os.getenv("FIRESTORE_DATABASE_ID", "copycat")
    db = firestore.Client(project=GCP_PROJECT_ID, database=database_id)

    print(f"\n🔍 Finding orphaned scan_history entries stuck in 'running' status...")

    from datetime import timezone
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)

    # Query all scan_history with status=running (the actual status used)
    scan_history_ref = db.collection("scan_history")
    query = scan_history_ref.where("status", "==", "running")

    orphaned = []

    for doc in query.stream():
        data = doc.to_dict()
        started_at = data.get("started_at")

        if started_at:
            # Handle Firestore timestamp
            if hasattr(started_at, 'seconds'):
                started_dt = datetime.fromtimestamp(started_at.seconds, tz=timezone.utc)
            elif isinstance(started_at, str):
                started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            else:
                started_dt = started_at

            # Ensure timezone-aware
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)

            # Check if stuck (processing > 10 minutes)
            if started_dt < cutoff_time:
                orphaned.append({
                    'id': doc.id,
                    'video_id': data.get('video_id', 'unknown'),
                    'duration': (now - started_dt).total_seconds() / 60
                })

    if not orphaned:
        print("✅ No orphaned scan_history entries found!")
        return

    print(f"\n⚠️  Found {len(orphaned)} orphaned scan_history entries")
    print(f"🗑️  Deleting {len(orphaned)} scan_history entries...")

    # Delete orphaned entries
    batch = db.batch()
    count = 0

    for entry in orphaned:
        doc_ref = scan_history_ref.document(entry['id'])
        batch.delete(doc_ref)
        count += 1

        # Firestore batch limit is 500
        if count % 500 == 0:
            batch.commit()
            print(f"  ✓ Deleted {count} entries")
            batch = db.batch()

    # Commit remaining
    if count % 500 != 0:
        batch.commit()

    print(f"\n✅ Successfully deleted {len(orphaned)} orphaned scan_history entries!")

if __name__ == "__main__":
    main()
    cleanup_orphaned_scan_history()
