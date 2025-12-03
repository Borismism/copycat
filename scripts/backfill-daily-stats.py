#!/usr/bin/env python3
"""
Backfill script for daily_stats collection.

This script aggregates historical statistics into the daily_stats collection
for fast time-range queries in the dashboard.

Usage:
    # Test locally with emulator
    FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 scripts/backfill-daily-stats.py

    # Run on production
    GCP_PROJECT_ID=boris-demo-453408 uv run python3 scripts/backfill-daily-stats.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, date, UTC

# Add parent directory to path to import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api-service'))

from app.core.firestore_client import FirestoreClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_earliest_video_date(firestore_client: FirestoreClient) -> date:
    """Get the earliest video discovery date from Firestore."""
    try:
        # Query for oldest video by discovered_at
        oldest_videos = (
            firestore_client.videos_collection
            .order_by("discovered_at", direction=firestore_client.db.collection("").order_by("").ASCENDING)
            .limit(1)
            .stream()
        )

        for video in oldest_videos:
            data = video.to_dict()
            discovered_at = data.get("discovered_at")
            if discovered_at:
                logger.info(f"Earliest video found: {discovered_at.date()}")
                return discovered_at.date()

        # If no videos found, default to 30 days ago
        fallback_date = (datetime.now(UTC) - timedelta(days=30)).date()
        logger.warning(f"No videos found, using fallback date: {fallback_date}")
        return fallback_date

    except Exception as e:
        logger.error(f"Failed to get earliest video date: {e}")
        # Fallback to 30 days ago
        return (datetime.now(UTC) - timedelta(days=30)).date()


async def backfill_daily_stats(start_date: date | None = None, end_date: date | None = None):
    """
    Backfill daily statistics for historical dates.

    Args:
        start_date: Start date for backfill (default: earliest video date)
        end_date: End date for backfill (default: yesterday)
    """
    firestore_client = FirestoreClient()

    # Determine date range
    if end_date is None:
        end_date = (datetime.now(UTC) - timedelta(days=1)).date()  # Yesterday

    if start_date is None:
        start_date = await get_earliest_video_date(firestore_client)

    logger.info(f"Starting backfill from {start_date} to {end_date}")

    # Calculate total days
    total_days = (end_date - start_date).days + 1
    logger.info(f"Total days to process: {total_days}")

    # Iterate through each date and aggregate
    current_date = start_date
    processed = 0
    failed = 0

    while current_date <= end_date:
        try:
            logger.info(f"[{processed + 1}/{total_days}] Processing {current_date}...")

            # Aggregate stats for this date
            stats = await firestore_client.aggregate_daily_stats(current_date)

            logger.info(
                f"  ✓ {current_date}: "
                f"{stats['videos_discovered']} discovered, "
                f"{stats['videos_analyzed']} analyzed, "
                f"{stats['infringements_found']} infringements"
            )

            processed += 1

        except Exception as e:
            logger.error(f"  ✗ Failed to process {current_date}: {e}")
            failed += 1

        # Move to next date
        current_date += timedelta(days=1)

        # Small delay to avoid overwhelming Firestore
        if processed % 10 == 0:
            await asyncio.sleep(1)

    # Summary
    logger.info("\n" + "="*80)
    logger.info(f"Backfill complete!")
    logger.info(f"  Processed: {processed} days")
    logger.info(f"  Failed: {failed} days")
    logger.info(f"  Success rate: {(processed / total_days * 100):.1f}%")
    logger.info("="*80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill daily statistics")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Default: earliest video date"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Default: yesterday"
    )
    args = parser.parse_args()

    # Parse dates if provided
    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    # Run backfill
    asyncio.run(backfill_daily_stats(start_date=start_date, end_date=end_date))
