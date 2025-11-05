#!/bin/bash
# Test viral snowball discovery with mock infringing channel

set -e

echo "=== TESTING VIRAL SNOWBALL DISCOVERY ==="

# Step 1: Create a mock channel with confirmed infringement
echo "Step 1: Creating mock infringing channel in Firestore..."
python3 << 'EOF'
import os
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8200"

from google.cloud import firestore
from datetime import datetime

db = firestore.Client(project="copycat-local")

# Create a mock channel with infringements
channel_id = "UC_test_viral_channel_123"
channel_data = {
    "channel_id": channel_id,
    "channel_title": "AI Movies Daily (TEST)",
    "has_infringements": True,
    "infringing_videos_count": 5,
    "total_infringing_views": 500000,
    "total_videos_found": 20,
    "infringement_rate": 0.25,
    "last_infringement_date": datetime.now(),
    "last_upload_date": datetime.now(),
    "last_scanned_at": datetime.now(),
}

db.collection("channels").document(channel_id).set(channel_data)
print(f"✓ Created mock channel: {channel_id}")
print(f"  - Infringements: {channel_data['infringing_videos_count']}")
print(f"  - Total views: {channel_data['total_infringing_views']:,}")
EOF

# Step 2: Trigger discovery with viral snowball
echo ""
echo "Step 2: Triggering discovery (quota=50)..."
curl -X POST "http://localhost:8081/discover/run?max_quota=50" -s | python3 -m json.tool

# Step 3: Check if viral snowball ran
echo ""
echo "Step 3: Checking discovery logs for viral snowball activity..."
docker-compose logs discovery-service --tail 50 | grep -i "viral\|snowball\|infringing"

echo ""
echo "=== TEST COMPLETE ==="
