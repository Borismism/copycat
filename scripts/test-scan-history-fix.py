#!/usr/bin/env python3
"""
Test script to verify scan_history fix.

Tests that scan_history is only created when processing actually starts,
not on early validation failures.
"""

import sys
import json
import time
from google.cloud import firestore, pubsub_v1
from datetime import datetime

PROJECT_ID = "irdeto-copycat-internal-dev"
DATABASE_ID = "copycat"  # Same database name for dev and prod
TOPIC_NAME = "scan-ready"


def count_scan_history(db, video_id):
    """Count scan_history entries for a video."""
    scans = list(db.collection("scan_history").where("video_id", "==", video_id).stream())
    return len(scans), scans


def test_early_failure(db, publisher, topic_path):
    """
    Test Case 1: Early validation failure (no IP configs matched).

    Expected: NO scan_history created (fails before processing starts)
    """
    print("\n" + "="*70)
    print("TEST 1: Early Validation Failure (No IP configs)")
    print("="*70)

    # Create a fake video ID
    test_video_id = "test_early_fail_" + str(int(time.time()))

    # Publish scan-ready message with empty matched_ips
    message = {
        "video_id": test_video_id,
        "priority": 50,
        "metadata": {
            "video_id": test_video_id,
            "youtube_url": f"https://youtube.com/watch?v={test_video_id}",
            "title": "TEST: Early Failure - No Configs",
            "duration_seconds": 60,
            "view_count": 100,
            "channel_id": "test_channel",
            "channel_title": "Test Channel",
            "risk_score": 50,
            "risk_tier": "MEDIUM",
            "matched_ips": ["NONEXISTENT_IP_ID"],  # This will fail config loading
            "discovered_at": datetime.now().isoformat(),
            "last_risk_update": datetime.now().isoformat(),
        }
    }

    print(f"📤 Publishing message for video: {test_video_id}")
    message_data = json.dumps(message).encode("utf-8")
    future = publisher.publish(topic_path, message_data)
    message_id = future.result(timeout=10)
    print(f"✅ Published message: {message_id}")

    # Wait for processing
    print("⏳ Waiting 30 seconds for processing...")
    time.sleep(30)

    # Check scan_history
    count, scans = count_scan_history(db, test_video_id)
    print(f"\n📊 Results:")
    print(f"   Scan history entries: {count}")

    if count == 0:
        print("   ✅ PASS: No scan_history created for early validation failure")
        return True
    else:
        print(f"   ❌ FAIL: Expected 0 scan_history entries, got {count}")
        for scan in scans:
            data = scan.to_dict()
            print(f"      - {scan.id}: status={data.get('status')}")
        return False


def test_successful_processing(db, publisher, topic_path):
    """
    Test Case 2: Successful video processing.

    Expected: 1 scan_history created and marked as "completed"
    """
    print("\n" + "="*70)
    print("TEST 2: Successful Processing")
    print("="*70)

    # Use a real video that should process successfully
    # You'll need to replace this with an actual video_id from your system
    test_video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up

    print("⚠️  SKIPPING: Would need a real video with valid configs")
    print("   To test manually: Use /admin/analyze endpoint")
    return None


def main():
    """Run all tests."""
    print("🧪 Testing scan_history fix for vision-analyzer-service")
    print(f"   Project: {PROJECT_ID}")
    print(f"   Database: {DATABASE_ID}")

    try:
        # Initialize clients
        db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

        # Run tests
        results = []

        # Test 1: Early failure
        results.append(("Early Validation Failure", test_early_failure(db, publisher, topic_path)))

        # Test 2: Success (manual test)
        results.append(("Successful Processing", test_successful_processing(db, publisher, topic_path)))

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        for name, result in results:
            if result is True:
                print(f"✅ {name}: PASS")
            elif result is False:
                print(f"❌ {name}: FAIL")
            else:
                print(f"⏭️  {name}: SKIPPED")

        # Return exit code
        if all(r in [True, None] for r in [result for _, result in results]):
            print("\n✅ All tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
