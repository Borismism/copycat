#!/usr/bin/env python3
"""Re-analyze all videos with the new 6-factor risk model."""

import requests
import json
import base64

print("🔄 Re-analyzing all videos with new 6-factor risk model...")

# Get all videos from API
print("📊 Fetching videos from API...")
response = requests.get("http://localhost:8080/api/videos?limit=200")
data = response.json()

videos = data.get("videos", [])
total = data.get("total", 0)

print(f"✅ Found {len(videos)} videos (total: {total})")

if len(videos) == 0:
    print("❌ No videos to process!")
    exit(1)

print(f"\n🔄 Republishing {len(videos)} videos to PubSub...")

processed = 0
failed = 0

for video in videos:
    # Build message
    msg = {
        "video_id": video["video_id"],
        "title": video["title"],
        "channel_id": video["channel_id"],
        "channel_title": video["channel_title"],
        "published_at": video["published_at"],
        "view_count": video["view_count"],
        "duration_seconds": video["duration_seconds"],
        "initial_risk": 50,
        "matched_keywords": video.get("matched_ips", []),
        "discovery_method": "reanalysis",
        "discovered_at": video["discovered_at"],
    }

    # Base64 encode for PubSub
    json_str = json.dumps(msg)
    encoded = base64.b64encode(json_str.encode()).decode()

    # Publish
    try:
        r = requests.post(
            "http://localhost:8086/v1/projects/copycat-local/topics/discovered-videos:publish",
            json={"messages": [{"data": encoded}]},
            timeout=5
        )
        if r.status_code == 200:
            processed += 1
            if processed % 20 == 0:
                print(f"  ✅ {processed}/{len(videos)} videos...")
        else:
            failed += 1
            print(f"  ❌ Failed {video['video_id']}: HTTP {r.status_code}")
    except Exception as e:
        failed += 1
        print(f"  ❌ Failed {video['video_id']}: {e}")

print(f"\n✅ Re-analysis complete!")
print(f"   Processed: {processed}")
print(f"   Failed: {failed}")
print(f"\n💡 Check risk-analyzer logs:")
print(f"   docker-compose logs risk-analyzer-service --tail 100 | grep 'Processing'")
