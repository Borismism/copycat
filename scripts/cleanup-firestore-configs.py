#!/usr/bin/env python3
"""
Clean up outdated data from Firestore.

This script deletes:
1. All IP configs (old format with search_keywords)
2. All videos (to start fresh with new keyword system)
3. All channels (optional)
4. All keyword scan states (optional)

Ready for the new 3-tier priority keyword system!
"""

import os
import sys
from google.cloud import firestore

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def cleanup_collection(db, collection_name, description):
    """Delete all documents from a collection."""
    print(f"\n📋 Cleaning up {description}...")

    collection_ref = db.collection(collection_name)
    docs = list(collection_ref.stream())

    if not docs:
        print(f"  ✅ No {description} found - already clean!")
        return 0

    print(f"  Found {len(docs)} {description}")

    # Delete in batches
    batch = db.batch()
    count = 0

    for doc in docs:
        batch.delete(doc.reference)
        count += 1

        # Commit in batches of 500 (Firestore limit)
        if count % 500 == 0:
            batch.commit()
            print(f"    Deleted {count}/{len(docs)}...")
            batch = db.batch()

    # Commit remaining
    if count % 500 != 0:
        batch.commit()

    print(f"  ✅ Deleted {count} {description}")
    return count

def cleanup_ip_configs(db):
    """Delete all IP configs from Firestore."""
    configs_ref = db.collection('ip_configs')
    configs = list(configs_ref.stream())

    if not configs:
        print("✅ No IP configs found - already clean!")
        return 0

    print(f"\n📋 Found {len(configs)} IP configs:")
    for config_doc in configs:
        config = config_doc.to_dict()
        name = config.get('name', 'Unknown')

        # Check if it's old format
        has_search_keywords = 'search_keywords' in config
        has_new_format = any(k in config for k in ['high_priority_keywords', 'medium_priority_keywords', 'low_priority_keywords'])

        format_type = "OLD FORMAT (search_keywords)" if has_search_keywords and not has_new_format else \
                      "NEW FORMAT (3-tier)" if has_new_format else \
                      "UNKNOWN FORMAT"

        print(f"  - {name} ({config_doc.id}) - {format_type}")

    # Delete all configs
    batch = db.batch()
    count = 0

    for config_doc in configs:
        batch.delete(config_doc.reference)
        count += 1

        # Commit in batches of 500 (Firestore limit)
        if count % 500 == 0:
            batch.commit()
            print(f"  Deleted {count}/{len(configs)} configs...")
            batch = db.batch()

    # Commit remaining
    if count % 500 != 0:
        batch.commit()

    print(f"✅ Deleted {count} IP configs!")
    return count

def cleanup_all():
    """Delete all data from Firestore to start fresh."""

    # Check if running against emulator or production
    emulator_host = os.getenv('FIRESTORE_EMULATOR_HOST')
    if emulator_host:
        print(f"🔧 Running against Firestore EMULATOR: {emulator_host}")
        db = firestore.Client(project="demo-project")
    else:
        print("⚠️  Running against PRODUCTION Firestore")
        confirm = input("Are you sure you want to delete production data? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Aborted")
            return
        db = firestore.Client()

    print("\n" + "=" * 60)
    print("🧹 CLEANING UP FIRESTORE DATA")
    print("=" * 60)

    total_deleted = 0

    # 1. Clean IP Configs (show details)
    print("\n1️⃣  IP CONFIGS")
    total_deleted += cleanup_ip_configs(db)

    # 2. Clean Videos
    print("\n2️⃣  VIDEOS")
    total_deleted += cleanup_collection(db, 'videos', 'videos')

    # 3. Clean Channels
    print("\n3️⃣  CHANNELS")
    total_deleted += cleanup_collection(db, 'channels', 'channel profiles')

    # 4. Clean Keyword Scan States
    print("\n4️⃣  KEYWORD SCAN STATES")
    total_deleted += cleanup_collection(db, 'keyword_scan_state', 'keyword scan states')

    print("\n" + "=" * 60)
    print(f"✅ CLEANUP COMPLETE - Deleted {total_deleted} total documents")
    print("=" * 60)
    print("\n🎉 Firestore is now CLEAN and ready for the new 3-tier keyword system!")
    print("\n📝 Next steps:")
    print("  1. Go to Config Generator: http://localhost:5173/config")
    print("  2. Click 'Generate New Configuration'")
    print("  3. Enter IP details:")
    print("     - Name: 'Justice League'")
    print("     - Company: 'Warner Bros'")
    print("     - Priority: 'High'")
    print("  4. Gemini will create keywords in 3 tiers:")
    print("     🔴 HIGH: superman ai, batman ai, wonder woman ai...")
    print("     🟡 MEDIUM: superman sora, batman runway...")
    print("     🟢 LOW: superman luma, batman veo...")
    print("  5. Save configuration and start discovering!")


if __name__ == '__main__':
    print("=" * 60)
    print("🧹 FIRESTORE CLEANUP SCRIPT")
    print("=" * 60)
    print("\nThis will delete:")
    print("  ✓ All IP configs")
    print("  ✓ All videos")
    print("  ✓ All channels")
    print("  ✓ All keyword scan states")
    print("\nReady to start fresh with the new 3-tier keyword system!")
    print("=" * 60)

    confirm = input("\nProceed with cleanup? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Aborted")
        sys.exit(0)

    cleanup_all()
