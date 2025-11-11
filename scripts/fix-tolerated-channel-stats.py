#!/usr/bin/env python3
"""
Fix channel statistics to properly handle tolerated videos.

This script recalculates channel stats by:
1. Only counting immediate_takedown as confirmed_infringements
2. Counting tolerated/monitor/safe_harbor/ignore as videos_cleared
3. Recalculating channel risk based on corrected stats

Run with:
    GCP_PROJECT_ID=copycat-429012 FIRESTORE_DATABASE_ID=copycat uv run python3 scripts/fix-tolerated-channel-stats.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, UTC

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'risk-analyzer-service'))

from google.cloud import firestore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fix_channel_stats():
    """Recalculate all channel stats with correct tolerated video handling."""

    # Initialize Firestore
    project_id = os.getenv("GCP_PROJECT_ID", "copycat-429012")
    database_id = os.getenv("FIRESTORE_DATABASE_ID", "copycat")

    logger.info(f"Connecting to Firestore: project={project_id}, database={database_id}")

    db = firestore.Client(project=project_id, database=database_id)

    # Get all channels
    channels = db.collection("channels").stream()

    stats = {
        "channels_processed": 0,
        "channels_updated": 0,
        "videos_reclassified": 0,
        "risk_changes": [],
    }

    for channel_doc in channels:
        channel_id = channel_doc.id
        channel_data = channel_doc.to_dict()

        logger.info(f"Processing channel {channel_id}...")

        # Get all analyzed videos for this channel
        videos = db.collection("videos").where(
            "channel_id", "==", channel_id
        ).where(
            "status", "==", "analyzed"
        ).stream()

        # Count actionable vs tolerated/cleared
        confirmed_infringements = 0
        videos_cleared = 0
        total_analyzed = 0

        for video_doc in videos:
            video_data = video_doc.to_dict()
            analysis = video_data.get("analysis", {})

            if not analysis:
                continue

            total_analyzed += 1

            # Check overall_recommendation
            recommendation = analysis.get("overall_recommendation", "")

            if recommendation == "immediate_takedown":
                confirmed_infringements += 1
            else:
                # tolerated, monitor, safe_harbor, ignore -> cleared
                videos_cleared += 1

        # Update channel document with corrected stats
        old_confirmed = channel_data.get("confirmed_infringements", 0)
        old_cleared = channel_data.get("videos_cleared", 0)
        old_risk = channel_data.get("channel_risk", 0)

        if old_confirmed != confirmed_infringements or old_cleared != videos_cleared:
            logger.info(
                f"  Channel {channel_id}: "
                f"confirmed {old_confirmed}→{confirmed_infringements}, "
                f"cleared {old_cleared}→{videos_cleared}"
            )

            # Update stats
            update_data = {
                "confirmed_infringements": confirmed_infringements,
                "videos_cleared": videos_cleared,
                "total_videos_analyzed": total_analyzed,
                "updated_at": datetime.now(UTC),
            }

            # Recalculate risk using the risk calculator
            from app.core.channel_risk_calculator import ChannelRiskCalculator
            calculator = ChannelRiskCalculator()

            # Merge updated stats into channel_data for risk calculation
            channel_data.update(update_data)
            risk_result = calculator.calculate_channel_risk(channel_data)
            new_risk = risk_result["channel_risk"]

            update_data["channel_risk"] = new_risk
            update_data["channel_risk_factors"] = risk_result["factors"]

            # Save to Firestore
            db.collection("channels").document(channel_id).update(update_data)

            stats["channels_updated"] += 1
            stats["videos_reclassified"] += abs(old_confirmed - confirmed_infringements)

            if old_risk != new_risk:
                stats["risk_changes"].append({
                    "channel_id": channel_id,
                    "old_risk": old_risk,
                    "new_risk": new_risk,
                })
                logger.info(f"  Risk changed: {old_risk}→{new_risk}")

        stats["channels_processed"] += 1

    # Print summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info(f"Channels processed: {stats['channels_processed']}")
    logger.info(f"Channels updated: {stats['channels_updated']}")
    logger.info(f"Videos reclassified: {stats['videos_reclassified']}")
    logger.info(f"Risk score changes: {len(stats['risk_changes'])}")

    if stats['risk_changes']:
        logger.info("\nRisk score changes:")
        for change in sorted(stats['risk_changes'], key=lambda x: x['old_risk'] - x['new_risk'], reverse=True):
            logger.info(
                f"  {change['channel_id']}: {change['old_risk']}→{change['new_risk']} "
                f"({change['old_risk'] - change['new_risk']:+d})"
            )


if __name__ == "__main__":
    asyncio.run(fix_channel_stats())
