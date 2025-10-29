#!/usr/bin/env python3
"""
Update all existing channels to add deep_scan_completed field.

This is a one-time migration script to add the new deep_scan fields
to all existing channel documents in Firestore.
"""

import sys
from pathlib import Path

# Add services/discovery-service to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "discovery-service"))

from google.cloud import firestore
from app.config import settings

def update_channels():
    """Update all channels to have deep_scan_completed field."""
    db = firestore.Client(project=settings.gcp_project_id, database=f"copycat-{settings.environment}")
    channels_ref = db.collection("channels")

    # Get all channels
    channels = channels_ref.stream()

    updated = 0
    skipped = 0

    for channel_doc in channels:
        channel_id = channel_doc.id
        channel_data = channel_doc.to_dict()

        # Check if deep_scan_completed already exists
        if "deep_scan_completed" in channel_data:
            print(f"Channel {channel_id}: Already has deep_scan_completed, skipping")
            skipped += 1
            continue

        # Update with deep_scan fields
        channels_ref.document(channel_id).update({
            "deep_scan_completed": False,
            "deep_scan_at": None,
        })

        print(f"Channel {channel_id}: Added deep_scan_completed=False")
        updated += 1

    print(f"\n✅ Migration complete:")
    print(f"   Updated: {updated} channels")
    print(f"   Skipped: {skipped} channels")

if __name__ == "__main__":
    print("🔄 Starting channel migration...")
    update_channels()
