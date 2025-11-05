#!/usr/bin/env python3
"""
Rescore all existing videos in Firestore.

This script recalculates risk scores for all videos using the proper
channel risk calculation and comprehensive risk scoring model.

Usage:
    python scripts/rescore-all-videos.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'risk-analyzer-service'))

from google.cloud import firestore
from app.core.scan_priority_calculator import ScanPriorityCalculator


async def rescore_all_videos():
    """Rescore all videos in Firestore."""

    # Initialize Firestore
    project_id = os.getenv('GCP_PROJECT_ID', 'copycat-local')
    db = firestore.Client(project=project_id, database='(default)')

    print(f"🔍 Connected to Firestore project: {project_id}")

    # Get all videos
    videos_ref = db.collection('videos')
    videos = list(videos_ref.stream())

    total_videos = len(videos)
    print(f"📊 Found {total_videos} videos to rescore\n")

    # Initialize risk calculator
    calculator = ScanPriorityCalculator(db)

    # Track statistics
    stats = {
        'processed': 0,
        'updated': 0,
        'errors': 0,
        'skipped': 0,
    }

    # Process each video
    for i, video_doc in enumerate(videos, 1):
        video_id = video_doc.id
        video_data = video_doc.to_dict()

        try:
            # Get old scores for comparison
            old_channel_risk = video_data.get('channel_risk', 0)
            old_scan_priority = video_data.get('scan_priority', 0)
            old_priority_tier = video_data.get('priority_tier', 'UNKNOWN')

            # Calculate new risk scores
            priority_result = await calculator.calculate_priority(video_data)

            new_channel_risk = priority_result['channel_risk']
            new_video_risk = priority_result['video_risk']
            new_scan_priority = priority_result['scan_priority']
            new_priority_tier = priority_result['priority_tier']

            # Update video in Firestore
            update_data = {
                'channel_risk': new_channel_risk,
                'video_risk': new_video_risk,
                'scan_priority': new_scan_priority,
                'priority_tier': new_priority_tier,
                'last_priority_update': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
            }

            videos_ref.document(video_id).update(update_data)

            stats['processed'] += 1

            # Show if scores changed
            if old_channel_risk != new_channel_risk or old_scan_priority != new_scan_priority:
                stats['updated'] += 1
                print(f"✅ [{i}/{total_videos}] {video_id[:12]}... "
                      f"channel_risk: {old_channel_risk}→{new_channel_risk}, "
                      f"priority: {old_scan_priority}→{new_scan_priority} ({old_priority_tier}→{new_priority_tier})")
            else:
                stats['skipped'] += 1
                if i % 10 == 0:
                    print(f"⏭️  [{i}/{total_videos}] Processed {i} videos...")

        except Exception as e:
            stats['errors'] += 1
            print(f"❌ [{i}/{total_videos}] Error processing {video_id}: {e}")
            continue

    # Print summary
    print(f"\n" + "="*60)
    print(f"📈 RESCORE COMPLETE")
    print(f"="*60)
    print(f"Total videos: {total_videos}")
    print(f"Processed: {stats['processed']}")
    print(f"Updated: {stats['updated']}")
    print(f"Unchanged: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    print(f"="*60)


if __name__ == '__main__':
    # Check environment
    if not os.getenv('FIRESTORE_EMULATOR_HOST'):
        print("⚠️  FIRESTORE_EMULATOR_HOST not set. Running against production!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(1)
    else:
        print(f"✅ Using Firestore emulator: {os.getenv('FIRESTORE_EMULATOR_HOST')}\n")

    # Run async function
    asyncio.run(rescore_all_videos())
