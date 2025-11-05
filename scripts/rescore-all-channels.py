#!/usr/bin/env python3
"""
Calculate and update risk scores for all channels.

This script:
1. Gets all channels from Firestore
2. For each channel, calculates risk based on videos
3. Updates channel document with risk scoring fields
4. Recalculates all video risk scores with updated channel data

Usage:
    Run via docker-compose exec
"""

import asyncio
import os
from datetime import datetime, timezone
from collections import defaultdict

from google.cloud import firestore


async def rescore_all_channels():
    """Calculate risk scores for all channels."""

    project_id = os.getenv('GCP_PROJECT_ID', 'copycat-local')
    db = firestore.Client(project=project_id, database='(default)')

    print(f"🔍 Connected to Firestore project: {project_id}\n")

    # Get all channels
    channels_ref = db.collection('channels')
    channels = list(channels_ref.stream())

    print(f"📊 Found {len(channels)} channels to process\n")

    # Get all videos to calculate channel stats
    videos_ref = db.collection('videos')
    videos = list(videos_ref.stream())

    print(f"📹 Found {len(videos)} videos for analysis\n")

    # Calculate stats per channel
    channel_stats = defaultdict(lambda: {
        'total_videos_found': 0,
        'infringing_videos_count': 0,
        'videos_scanned': 0,
        'total_infringing_views': 0,
        'last_upload_date': None,
        'total_views': 0,
    })

    for video_doc in videos:
        video_data = video_doc.to_dict()
        channel_id = video_data.get('channel_id')
        if not channel_id:
            continue

        stats = channel_stats[channel_id]
        stats['total_videos_found'] += 1

        # Track views
        views = video_data.get('view_count', 0)
        stats['total_views'] += views

        # Track infringements
        vision_analysis = video_data.get('vision_analysis', {})
        if isinstance(vision_analysis, dict):
            contains_infringement = vision_analysis.get('contains_infringement', False)
            if contains_infringement:
                stats['infringing_videos_count'] += 1
                stats['total_infringing_views'] += views

        # Track scanned videos
        if vision_analysis:
            stats['videos_scanned'] += 1

        # Track last upload
        published_at = video_data.get('published_at')
        if published_at:
            if not stats['last_upload_date'] or published_at > stats['last_upload_date']:
                stats['last_upload_date'] = published_at

    print(f"📈 Calculated stats for {len(channel_stats)} channels with videos\n")

    # Update all channels
    updated = 0
    for channel_doc in channels:
        channel_id = channel_doc.id
        channel_data = channel_doc.to_dict()
        stats = channel_stats.get(channel_id, {})

        # Prepare update data
        update_data = {
            'total_videos_found': stats.get('total_videos_found', channel_data.get('video_count', 0)),
            'infringing_videos_count': stats.get('infringing_videos_count', 0),
            'videos_scanned': stats.get('videos_scanned', 0),
            'total_infringing_views': stats.get('total_infringing_views', 0),
            'last_upload_date': stats.get('last_upload_date') or channel_data.get('last_seen_at'),
            'subscriber_count': 0,  # We don't have this data yet
            'videos_per_month': 0,  # Would need to calculate from video dates
            'updated_at': datetime.now(timezone.utc),
        }

        # Update channel
        channels_ref.document(channel_id).update(update_data)
        updated += 1

        if updated % 100 == 0:
            print(f"  Updated {updated}/{len(channels)} channels...")

    print(f"\n✅ Updated {updated} channels with risk scoring fields\n")

    # Summary
    print("="*60)
    print("📊 CHANNEL UPDATE COMPLETE")
    print("="*60)
    print(f"Total channels: {len(channels)}")
    print(f"Channels updated: {updated}")
    print(f"Channels with videos: {len(channel_stats)}")
    print(f"Channels with infringements: {sum(1 for s in channel_stats.values() if s['infringing_videos_count'] > 0)}")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(rescore_all_channels())
