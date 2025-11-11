#!/usr/bin/env python3
"""
Reset stuck videos using scan_history as source of truth.

This implements the RESILIENT approach - check scan_history for incomplete scans
and reset the corresponding videos.

Usage:
    # Prod
    GCP_PROJECT_ID=copycat-429012 FIRESTORE_DATABASE_ID=copycat uv run python3 scripts/reset-stuck-videos.py

    # Local
    FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 scripts/reset-stuck-videos.py
"""

import os
from datetime import datetime, timezone
from google.cloud import firestore

def main():
    project_id = os.getenv('GCP_PROJECT_ID', 'copycat-local')
    database_id = os.getenv('FIRESTORE_DATABASE_ID', '(default)')
    is_prod = 'copycat-429012' in project_id

    print(f"🔧 Resetting stuck videos")
    print(f"Project: {project_id}")
    print(f"Database: {database_id}")
    print(f"Environment: {'PRODUCTION' if is_prod else 'LOCAL'}")
    print()

    # Initialize Firestore
    if is_prod:
        db = firestore.Client(project=project_id, database=database_id)
    else:
        db = firestore.Client(project=project_id)

    # Find ALL scan_history entries still in 'running' state
    print("Searching for stuck scans in scan_history...")
    stuck_scans = list(db.collection('scan_history').where('status', '==', 'running').stream())

    if not stuck_scans:
        print("✅ No stuck scans found!")
        return

    print(f"⚠️  Found {len(stuck_scans)} stuck scans from terminated instance(s)\n")

    reset_count = 0
    for i, scan_doc in enumerate(stuck_scans, 1):
        scan_data = scan_doc.to_dict()
        scan_id = scan_doc.id
        video_id = scan_data.get('video_id')

        if not video_id:
            print(f"{i}. Scan {scan_id} has no video_id, skipping")
            continue

        print(f"{i}. Resetting scan {scan_id[:8]}... for video {video_id}")

        # Mark scan as failed
        try:
            scan_doc.reference.update({
                'status': 'failed',
                'completed_at': firestore.SERVER_TIMESTAMP,
                'error_message': 'Instance terminated during processing (manual reset)',
                'reset_at': firestore.SERVER_TIMESTAMP,
            })
            print(f"   ✅ Marked scan as failed")
        except Exception as e:
            print(f"   ❌ Failed to update scan_history: {e}")
            continue

        # Reset video to 'discovered'
        try:
            video_ref = db.collection('videos').document(video_id)
            video_doc = video_ref.get()

            if video_doc.exists:
                video_data = video_doc.to_dict()
                current_status = video_data.get('status')

                if current_status == 'processing':
                    video_ref.update({
                        'status': 'discovered',
                        'processing_started_at': None,
                        'error_message': 'Reset from incomplete scan (manual reset)',
                        'reset_at': firestore.SERVER_TIMESTAMP,
                        'updated_at': firestore.SERVER_TIMESTAMP,
                    })
                    print(f"   ✅ Reset video to 'discovered'")
                    reset_count += 1
                else:
                    print(f"   ℹ️  Video already in '{current_status}' state")
            else:
                print(f"   ⚠️  Video not found")

        except Exception as e:
            print(f"   ❌ Failed to reset video: {e}")

    print()
    print(f"📊 Summary:")
    print(f"   Total stuck scans: {len(stuck_scans)}")
    print(f"   Videos reset: {reset_count}")
    print(f"   Videos already processed: {len(stuck_scans) - reset_count}")

if __name__ == '__main__':
    main()
