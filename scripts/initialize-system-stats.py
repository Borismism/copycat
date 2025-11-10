#!/usr/bin/env python3
"""Initialize system_stats/global document from existing data."""

import sys
from google.cloud import firestore

# Initialize Firestore
db = firestore.Client(project="copycat-429012", database="copycat")

def initialize_system_stats():
    """Count existing videos and channels and initialize system_stats."""

    print("🔍 Counting existing videos...")
    videos = list(db.collection("videos").stream())
    total_videos = len(videos)
    print(f"   Found {total_videos} videos")

    print("\n🔍 Counting existing channels...")
    channels = list(db.collection("channels").stream())
    total_channels = len(channels)
    print(f"   Found {total_channels} channels")

    print("\n💾 Writing system_stats/global document...")
    stats_ref = db.collection("system_stats").document("global")
    stats_ref.set({
        "total_videos": total_videos,
        "total_channels": total_channels,
        "updated_at": firestore.SERVER_TIMESTAMP,
    })

    print(f"✅ Initialized system_stats:")
    print(f"   - total_videos: {total_videos}")
    print(f"   - total_channels: {total_channels}")

    # Also update all channel documents with their pre-aggregated stats
    print("\n🔄 Updating channel documents with aggregated stats...")

    for channel_doc in channels:
        channel_id = channel_doc.id

        # Count videos for this channel
        channel_videos = list(db.collection("videos").where("channel_id", "==", channel_id).stream())

        total_videos_found = len(channel_videos)
        total_views = sum(v.to_dict().get("view_count", 0) for v in channel_videos)

        # Count infringements
        confirmed_infringements = 0
        videos_cleared = 0
        for v in channel_videos:
            data = v.to_dict()
            if data.get("status") == "analyzed":
                analysis = data.get("analysis", {})
                if isinstance(analysis, dict):
                    if analysis.get("contains_infringement"):
                        confirmed_infringements += 1
                    else:
                        videos_cleared += 1

        # Update channel document
        db.collection("channels").document(channel_id).update({
            "total_videos_found": total_videos_found,
            "total_views": total_views,
            "confirmed_infringements": confirmed_infringements,
            "videos_cleared": videos_cleared,
        })

        if (channels.index(channel_doc) + 1) % 10 == 0:
            print(f"   Updated {channels.index(channel_doc) + 1}/{total_channels} channels...")

    print(f"\n✅ Updated all {total_channels} channel documents with aggregated stats")

if __name__ == "__main__":
    try:
        initialize_system_stats()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
