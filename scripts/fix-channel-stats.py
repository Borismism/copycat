#!/usr/bin/env python3
"""
Fix broken channel statistics by recalculating from video data.

This script:
1. Queries all videos for each channel
2. Counts confirmed_infringements, videos_cleared, videos_scanned
3. Updates channel documents with correct values

Usage:
    FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 scripts/fix-channel-stats.py

    # Production:
    GCP_PROJECT_ID=copycat-429012 FIRESTORE_DATABASE_ID=copycat uv run python3 scripts/fix-channel-stats.py
"""

import sys
from collections import defaultdict
from google.cloud import firestore

def main():
    import os

    # Initialize Firestore
    project_id = os.getenv("GCP_PROJECT_ID")
    database_id = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
    db = firestore.Client(project=project_id, database=database_id)

    print("🔧 Fixing channel statistics...")
    print()

    # Step 1: Get all channels
    channels = list(db.collection("channels").stream())
    print(f"Found {len(channels)} channels")

    # Step 2: For each channel, count videos
    for channel_doc in channels:
        channel_id = channel_doc.id
        channel_data = channel_doc.to_dict()
        channel_title = channel_data.get("channel_title", "Unknown")

        # Query all videos for this channel
        videos = db.collection("videos").where("channel_id", "==", channel_id).stream()

        # Count stats
        total_videos_found = 0
        videos_scanned = 0
        confirmed_infringements = 0
        videos_cleared = 0

        for video_doc in videos:
            video_data = video_doc.to_dict()

            # Count all videos
            total_videos_found += 1

            # Count analyzed videos
            if video_data.get("status") == "analyzed":
                videos_scanned += 1

                # Check if infringement or cleared
                analysis = video_data.get("analysis", {})
                if isinstance(analysis, dict):
                    if analysis.get("contains_infringement", False):
                        confirmed_infringements += 1
                    else:
                        videos_cleared += 1

        # Get current values
        old_scanned = channel_data.get("videos_scanned", 0)
        old_infringements = channel_data.get("confirmed_infringements", 0)
        old_cleared = channel_data.get("videos_cleared", 0)
        old_total = channel_data.get("total_videos_found", 0)

        # Check if needs update
        needs_update = (
            old_scanned != videos_scanned or
            old_infringements != confirmed_infringements or
            old_cleared != videos_cleared or
            old_total != total_videos_found
        )

        if needs_update:
            # Update channel document
            db.collection("channels").document(channel_id).update({
                "total_videos_found": total_videos_found,
                "videos_scanned": videos_scanned,
                "confirmed_infringements": confirmed_infringements,
                "videos_cleared": videos_cleared,
            })

            print(f"✅ {channel_title[:40]:40} | "
                  f"Found: {old_total:3d}→{total_videos_found:3d} | "
                  f"Scanned: {old_scanned:3d}→{videos_scanned:3d} | "
                  f"Infr: {old_infringements:4d}→{confirmed_infringements:3d} | "
                  f"Clear: {old_cleared:4d}→{videos_cleared:3d}")
        else:
            print(f"⏭️  {channel_title[:40]:40} | Already correct")

    print()
    print("✅ Channel statistics fixed!")

if __name__ == "__main__":
    main()
