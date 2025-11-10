#!/usr/bin/env python3
"""
Backfill hourly_stats collection from existing videos.

Reconstructs hourly discovery stats by reading all videos and grouping by discovered_at hour.
"""

import logging
import os
from collections import defaultdict
from datetime import datetime

from google.cloud import firestore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def backfill_hourly_stats():
    """Backfill hourly_stats from existing videos."""

    project_id = os.environ.get("GCP_PROJECT_ID", "copycat-429012")
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "copycat")

    logger.info(f"Connecting to Firestore: project={project_id}, database={database_id}")

    db = firestore.Client(project=project_id, database=database_id)

    # Read all videos
    logger.info("Reading all videos from Firestore...")
    videos_ref = db.collection("videos")
    videos = list(videos_ref.stream())

    logger.info(f"Found {len(videos)} videos")

    # Group by hour
    hourly_counts = defaultdict(int)

    for video in videos:
        data = video.to_dict()
        discovered_at = data.get("discovered_at")

        if not discovered_at:
            logger.warning(f"Video {video.id} has no discovered_at timestamp")
            continue

        # Round to hour
        hour = discovered_at.replace(minute=0, second=0, microsecond=0)
        hour_key = hour.strftime("%Y-%m-%d_%H")

        hourly_counts[hour_key] += 1

    logger.info(f"Grouped into {len(hourly_counts)} hourly buckets")

    # Write to hourly_stats collection
    logger.info("Writing hourly stats to Firestore...")
    stats_ref = db.collection("hourly_stats")

    batch_size = 500
    batch = db.batch()
    batch_count = 0
    total_written = 0

    for hour_key, count in sorted(hourly_counts.items()):
        # Parse hour back to datetime
        hour = datetime.strptime(hour_key, "%Y-%m-%d_%H")

        doc_ref = stats_ref.document(hour_key)
        batch.set(doc_ref, {
            "hour": hour,
            "discoveries": count,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        batch_count += 1
        total_written += 1

        # Commit batch every 500 writes
        if batch_count >= batch_size:
            logger.info(f"Committing batch ({total_written} written so far)...")
            batch.commit()
            batch = db.batch()
            batch_count = 0

    # Commit remaining
    if batch_count > 0:
        logger.info(f"Committing final batch ({total_written} total)...")
        batch.commit()

    logger.info(f"✓ Backfill complete! Wrote {total_written} hourly stats records")

    # Show sample
    logger.info("\nSample hourly stats:")
    for hour_key in sorted(hourly_counts.keys())[-5:]:
        logger.info(f"  {hour_key}: {hourly_counts[hour_key]} discoveries")


if __name__ == "__main__":
    backfill_hourly_stats()
