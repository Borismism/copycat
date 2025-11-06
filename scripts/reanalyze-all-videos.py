#!/usr/bin/env python3
"""
Republish all videos to trigger risk reassessment.

This script:
1. Fetches all videos from Firestore
2. Publishes each video to the video-discovered topic
3. Risk-analyzer-service will recalculate scan_priority for each
"""

import argparse
import json
import sys
from google.cloud import firestore, pubsub_v1

# Configuration
PROJECT_ID = "irdeto-copycat-internal-dev"
TOPIC_NAME = "copycat-video-discovered"


def main():
    """Republish all videos to trigger risk reassessment."""
    parser = argparse.ArgumentParser(description="Republish all videos to trigger risk reassessment")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print(f"Connecting to Firestore in project {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID, database="copycat")

    print(f"Connecting to PubSub topic {TOPIC_NAME}...")
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

    # Fetch all videos
    print("Fetching all videos from Firestore...")
    videos_ref = db.collection("videos")
    videos = list(videos_ref.stream())

    print(f"Found {len(videos)} videos")

    if not videos:
        print("No videos found. Exiting.")
        return

    # Confirm with user
    if not args.yes:
        response = input(f"Republish {len(videos)} videos to trigger risk reassessment? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    # Publish each video
    published = 0
    failed = 0

    for video_doc in videos:
        video_data = video_doc.to_dict()
        video_id = video_doc.id

        try:
            # Create message payload
            message = {
                "video_id": video_id,
                "channel_id": video_data.get("channel_id", ""),
                "title": video_data.get("title", ""),
                "view_count": video_data.get("view_count", 0),
                "duration_seconds": video_data.get("duration_seconds", 0),
            }

            # Publish to PubSub
            message_bytes = json.dumps(message).encode("utf-8")
            future = publisher.publish(topic_path, message_bytes)
            future.result()  # Wait for publish to complete

            published += 1

            if published % 10 == 0:
                print(f"Published {published}/{len(videos)} videos...")

        except Exception as e:
            print(f"Error publishing video {video_id}: {e}")
            failed += 1
            continue

    print(f"\nDone!")
    print(f"Published: {published}")
    print(f"Failed: {failed}")
    print(f"\nRisk-analyzer-service will now recalculate scan_priority for all videos.")


if __name__ == "__main__":
    main()
