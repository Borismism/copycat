#!/usr/bin/env python3
"""Fix channel video counts by counting actual videos in Firestore."""

import os
from google.cloud import firestore

# Set up Firestore emulator
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8200"
os.environ["GOOGLE_CLOUD_PROJECT"] = "copycat-local"

db = firestore.Client(project="copycat-local")

# Count videos per channel
print("📊 Counting videos per channel...")
videos = db.collection("videos").stream()

channel_counts = {}
for video in videos:
    data = video.to_dict()
    channel_id = data.get("channel_id")
    if channel_id:
        channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1

print(f"✅ Found {len(channel_counts)} channels with videos")

# Update channel documents
print("\n📝 Updating channel video_count fields...")
from datetime import datetime, timezone

updated = 0
created = 0
for channel_id, count in channel_counts.items():
    doc_ref = db.collection("channels").document(channel_id)
    doc = doc_ref.get()

    if doc.exists:
        # Update existing channel
        doc_ref.update({"video_count": count})
        updated += 1
    else:
        # Create missing channel (get title from first video)
        videos_query = db.collection("videos").where("channel_id", "==", channel_id).limit(1).stream()
        channel_title = "Unknown"
        for v in videos_query:
            channel_title = v.to_dict().get("channel_title", "Unknown")
            break

        # Create channel
        doc_ref.set({
            "channel_id": channel_id,
            "channel_title": channel_title,
            "discovered_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
            "video_count": count,
        })
        created += 1

    if (updated + created) % 50 == 0:
        print(f"  Processed {updated + created}/{len(channel_counts)} channels...")

print(f"\n✅ Updated {updated} channels, created {created} new channels!")
print(f"\n🔝 Top 10 channels by video count:")
top_channels = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)[:10]
for channel_id, count in top_channels:
    print(f"  {channel_id}: {count} videos")
