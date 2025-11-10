#!/usr/bin/env python3
"""Reset stuck videos in processing state."""

import sys
from google.cloud import firestore
from datetime import datetime, timezone


def reset_video(video_id: str, project_id: str, database_id: str):
    """Reset a stuck video to 'discovered' state for reprocessing."""
    db = firestore.Client(project=project_id, database=database_id)

    # Get video document
    video_ref = db.collection('videos').document(video_id)
    video = video_ref.get()

    if not video.exists:
        print(f"❌ Video {video_id} not found")
        return

    data = video.to_dict()
    current_status = data.get('status')

    print(f"\n📹 Video: {video_id}")
    print(f"   Title: {data.get('title', 'N/A')[:80]}")
    print(f"   Current Status: {current_status}")
    print(f"   Duration: {data.get('duration_seconds')}s")
    print(f"   Updated: {data.get('updated_at')}")

    if current_status != 'processing':
        print(f"⚠️  Video is not in 'processing' state, skipping reset")
        return

    # Reset to 'discovered' state
    video_ref.update({
        'status': 'discovered',
        'processing_started_at': None,
        'error_message': 'Reset from stuck processing state',
        'reset_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    })

    print(f"✅ Reset video {video_id} to 'discovered' state")

    # Find and update related scan history
    scan_histories = db.collection('scan_history').where('video_id', '==', video_id).where('status', '==', 'running').stream()

    for scan in scan_histories:
        scan_ref = db.collection('scan_history').document(scan.id)
        scan_ref.update({
            'status': 'failed',
            'completed_at': firestore.SERVER_TIMESTAMP,
            'error_message': 'Scan reset - video was stuck in processing',
        })
        print(f"✅ Updated scan history {scan.id} to 'failed'")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python reset-stuck-video.py <video_id>")
        sys.exit(1)

    video_id = sys.argv[1]

    # Use environment variables for project/database (default to production)
    import os
    project_id = os.getenv('GCP_PROJECT_ID', 'copycat-429012')
    database_id = os.getenv('FIRESTORE_DATABASE_ID', 'copycat')

    print(f"🔧 Resetting video in {project_id}/{database_id}...")
    reset_video(video_id, project_id, database_id)
    print("\n✅ Done!")
