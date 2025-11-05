#!/usr/bin/env python3
"""
NUCLEAR CLEANUP - Delete EVERYTHING from Firestore.

This deletes ALL data:
- IP configs (including deleted ones)
- Videos
- Channels
- Keyword scan states
- EVERYTHING

Use this to start completely fresh.
"""

import os
from google.cloud import firestore

def nuclear_cleanup():
    """Delete ALL collections from Firestore."""

    # Connect to Firestore emulator (same project as API)
    os.environ['FIRESTORE_EMULATOR_HOST'] = 'localhost:8200'
    db = firestore.Client(project='copycat-local')

    collections_to_delete = [
        'ip_configs',
        'deleted_ip_configs',
        'videos',
        'channels',
        'channel_profiles',
        'keyword_scan_state',
        'scan_results',
        'risk_scores',
        'view_velocity'
    ]

    total_deleted = 0

    print("=" * 60)
    print("☢️  NUCLEAR CLEANUP - DELETING ALL FIRESTORE DATA")
    print("=" * 60)

    for collection_name in collections_to_delete:
        print(f"\n🗑️  Deleting collection: {collection_name}")

        try:
            collection_ref = db.collection(collection_name)
            docs = list(collection_ref.stream())

            if not docs:
                print(f"   ✅ Empty (0 documents)")
                continue

            print(f"   Found {len(docs)} documents")

            # Delete in batches
            batch = db.batch()
            count = 0

            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                total_deleted += 1

                # Commit every 500 docs
                if count % 500 == 0:
                    batch.commit()
                    print(f"   ... deleted {count}/{len(docs)}")
                    batch = db.batch()

            # Commit remaining
            if count % 500 != 0:
                batch.commit()

            print(f"   ✅ Deleted {count} documents")

        except Exception as e:
            print(f"   ⚠️  Error: {e}")

    print("\n" + "=" * 60)
    print(f"✅ NUCLEAR CLEANUP COMPLETE")
    print(f"   Total deleted: {total_deleted} documents")
    print("=" * 60)
    print("\n🎉 Firestore is now COMPLETELY CLEAN!")
    print("\n📝 Next: Generate a new config with 3-tier keywords")


if __name__ == '__main__':
    print("\n⚠️  WARNING: This will delete EVERYTHING from Firestore!")
    print("   - All IP configs (including deleted)")
    print("   - All videos")
    print("   - All channels")
    print("   - All scan states")
    print("   - EVERYTHING\n")

    confirm = input("Type 'DELETE EVERYTHING' to proceed: ")

    if confirm != 'DELETE EVERYTHING':
        print("❌ Aborted")
        exit(0)

    nuclear_cleanup()
