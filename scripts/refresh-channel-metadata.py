#!/usr/bin/env python3
"""
Refresh channel metadata from YouTube API for all channels in Firestore.

This script:
1. Fetches all channels from Firestore
2. For each channel, calls YouTube API to get updated details
3. Updates channel document with fresh metadata:
   - thumbnail_url
   - subscriber_count
   - video_count (YouTube's total, not our discovered count)
   - last_scanned_at (set to now)

Usage:
    # Production:
    GCP_PROJECT_ID=copycat-429012 FIRESTORE_DATABASE=copycat uv run python3 scripts/refresh-channel-metadata.py

    # Dev:
    GCP_PROJECT_ID=irdeto-copycat-internal-dev FIRESTORE_DATABASE=copycat uv run python3 scripts/refresh-channel-metadata.py

    # Local emulator:
    FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 scripts/refresh-channel-metadata.py
"""

import os
import sys
import time
from datetime import datetime, UTC
from google.cloud import firestore
from google.cloud import secretmanager


def get_youtube_api_key(project_id: str) -> str:
    """Fetch YouTube API key from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{project_id}/secrets/youtube-api-key/versions/latest"

    try:
        response = client.access_secret_version(request={"name": secret_name})
        api_key = response.payload.data.decode('UTF-8')
        return api_key
    except Exception as e:
        print(f"❌ Failed to fetch YouTube API key from Secret Manager: {e}")
        print(f"   Tried: {secret_name}")
        sys.exit(1)


def main():
    # Get environment variables
    project_id = os.getenv("GCP_PROJECT_ID")
    database_id = os.getenv("FIRESTORE_DATABASE", "(default)")

    if not project_id:
        print("❌ Error: GCP_PROJECT_ID environment variable not set")
        sys.exit(1)

    # Check if using emulator
    using_emulator = os.getenv("FIRESTORE_EMULATOR_HOST") is not None

    print(f"🔄 Refreshing channel metadata...")
    print(f"   Project: {project_id}")
    print(f"   Database: {database_id}")
    print(f"   Emulator: {using_emulator}")
    print()

    # Initialize Firestore with explicit project
    db = firestore.Client(project=project_id, database=database_id)

    # Initialize YouTube client
    if using_emulator:
        print("⚠️  Using emulator - skipping YouTube API calls (no real API key)")
        youtube_client = None
    else:
        print("🔑 Fetching YouTube API key from Secret Manager...")
        api_key = get_youtube_api_key(project_id)

        # Import YouTubeClient from discovery service
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'discovery-service'))
        from app.core.youtube_client import YouTubeClient

        youtube_client = YouTubeClient(api_key)
        print("✅ YouTube client initialized")

    print()

    # Fetch all channels
    print("📺 Fetching all channels from Firestore...")
    channels = list(db.collection("channels").stream())
    print(f"   Found {len(channels)} channels")
    print()

    # Statistics
    updated_count = 0
    failed_count = 0
    skipped_count = 0
    quota_used = 0

    # Process each channel
    for idx, channel_doc in enumerate(channels, 1):
        channel_id = channel_doc.id
        channel_data = channel_doc.to_dict()
        channel_title = channel_data.get("channel_title", "Unknown")

        print(f"[{idx}/{len(channels)}] Processing: {channel_title[:50]}")
        print(f"           Channel ID: {channel_id}")

        if not youtube_client:
            print(f"           ⏭️  Skipped (emulator mode)")
            skipped_count += 1
            continue

        try:
            # Fetch channel details from YouTube
            details = youtube_client.get_channel_details(channel_id)
            quota_used += 1  # Each get_channel_details costs 1 quota unit

            if not details:
                print(f"           ⚠️  Channel not found on YouTube")
                failed_count += 1
                continue

            # Prepare update data
            update_data = {
                "last_scanned_at": datetime.now(UTC),
            }

            # Update thumbnail if available
            if details.get("thumbnail_high"):
                update_data["thumbnail_url"] = details["thumbnail_high"]

            # Update subscriber count
            if details.get("subscriber_count") is not None:
                update_data["subscriber_count"] = details["subscriber_count"]

            # Update video count (YouTube's total, not our discovered count)
            if details.get("video_count") is not None:
                # Note: We keep total_videos_found separate (our discovered count)
                # video_count is YouTube's total video count for the channel
                update_data["video_count"] = details["video_count"]

            # Update channel title if it changed
            if details.get("title"):
                update_data["channel_title"] = details["title"]

            # Update Firestore
            db.collection("channels").document(channel_id).update(update_data)

            print(f"           ✅ Updated: {details.get('subscriber_count', 0):,} subs, "
                  f"{details.get('video_count', 0):,} videos")
            updated_count += 1

            # Rate limiting - YouTube API has quota limits
            # 10,000 units per day, 1 unit per channel
            # With 100 channels, that's 100 units (1% of daily quota)
            # Sleep 0.5s between requests to be nice to the API
            time.sleep(0.5)

        except Exception as e:
            print(f"           ❌ Failed: {e}")
            failed_count += 1
            continue

    print()
    print("=" * 70)
    print("📊 Summary:")
    print(f"   Total channels:  {len(channels)}")
    print(f"   ✅ Updated:      {updated_count}")
    print(f"   ❌ Failed:       {failed_count}")
    print(f"   ⏭️  Skipped:      {skipped_count}")
    print(f"   📊 Quota used:   {quota_used} units (of 10,000 daily limit)")
    print("=" * 70)

    if failed_count > 0:
        print()
        print("⚠️  Some channels failed to update. Check logs above for details.")

    print()
    print("✅ Channel metadata refresh complete!")


if __name__ == "__main__":
    main()
