#!/usr/bin/env python3
"""
Recalculate risk scores for all channels based on current analysis data.

This script:
1. Gets all channels from Firestore
2. For each channel, counts analyzed videos (infringements vs cleared)
3. Recalculates channel_risk using the ChannelRiskCalculator
4. Updates the channel document in Firestore

Usage:
    FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local \
    uv run python3 scripts/recalculate-channel-risks.py

    # Or for production:
    GCP_PROJECT_ID=irdeto-copycat-internal-dev \
    uv run python3 scripts/recalculate-channel-risks.py
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'risk-analyzer-service'))

from google.cloud import firestore
from app.core.channel_risk_calculator import ChannelRiskCalculator


def main():
    """Recalculate risk scores for all channels."""
    # Get project from environment
    project_id = os.environ.get('GCP_PROJECT_ID')
    if not project_id:
        print("ERROR: GCP_PROJECT_ID environment variable not set")
        sys.exit(1)

    database_id = os.environ.get('FIRESTORE_DATABASE_ID', 'copycat')

    print(f"Connecting to Firestore: {project_id} / {database_id}")
    db = firestore.Client(project=project_id, database=database_id)

    # Initialize risk calculator
    risk_calculator = ChannelRiskCalculator()

    # Get all channels
    channels_ref = db.collection('channels')
    channels = list(channels_ref.stream())

    print(f"\nFound {len(channels)} channels")
    print("=" * 80)

    updated_count = 0
    error_count = 0

    for channel_doc in channels:
        channel_data = channel_doc.to_dict()
        channel_id = channel_data.get('channel_id', channel_doc.id)
        channel_title = channel_data.get('channel_title', 'Unknown')

        try:
            # Get all analyzed videos for this channel
            videos_ref = db.collection('videos').where('channel_id', '==', channel_id)
            videos = list(videos_ref.stream())

            # Count infringements and cleared
            confirmed_infringements = 0
            videos_cleared = 0
            total_videos_analyzed = 0

            for video_doc in videos:
                video_data = video_doc.to_dict()
                status = video_data.get('status')

                if status == 'analyzed':
                    total_videos_analyzed += 1
                    analysis = video_data.get('analysis')
                    if analysis and isinstance(analysis, dict):
                        contains_infringement = analysis.get('contains_infringement', False)
                        if contains_infringement:
                            confirmed_infringements += 1
                        else:
                            videos_cleared += 1

            # Update channel data with counts
            channel_data['total_videos_analyzed'] = total_videos_analyzed
            channel_data['confirmed_infringements'] = confirmed_infringements
            channel_data['videos_cleared'] = videos_cleared
            channel_data['total_videos_found'] = len(videos)

            # Calculate new risk
            old_risk = channel_data.get('channel_risk', 0)
            risk_result = risk_calculator.calculate_channel_risk(channel_data)
            new_risk = risk_result['channel_risk']

            # Update channel in Firestore
            channels_ref.document(channel_id).update({
                'channel_risk': new_risk,
                'channel_risk_factors': risk_result['factors'],
                'total_videos_analyzed': total_videos_analyzed,
                'confirmed_infringements': confirmed_infringements,
                'videos_cleared': videos_cleared,
                'total_videos_found': len(videos),
                'updated_at': datetime.now(timezone.utc),
            })

            print(f"✓ {channel_title[:50]:50} | Risk: {old_risk:3d}→{new_risk:3d} | "
                  f"Analyzed: {total_videos_analyzed:3d} | "
                  f"Infringements: {confirmed_infringements:3d} | "
                  f"Cleared: {videos_cleared:3d}")

            updated_count += 1

        except Exception as e:
            print(f"✗ {channel_title[:50]:50} | ERROR: {e}")
            error_count += 1

    print("=" * 80)
    print(f"\nSummary:")
    print(f"  Channels updated: {updated_count}")
    print(f"  Errors: {error_count}")
    print(f"\nDone! ✨")


if __name__ == '__main__':
    main()
