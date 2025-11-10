#!/usr/bin/env python3
"""Backfill hourly_stats collection from existing video data."""

import sys
from datetime import datetime, timezone
from collections import defaultdict

from google.cloud import firestore

# Initialize Firestore
db = firestore.Client(project="copycat-429012", database="copycat")

def backfill_hourly_stats():
    """Backfill hourly stats from existing videos collection."""

    print("🔍 Reading all videos from Firestore...")

    # Aggregate stats by hour
    hourly_data = defaultdict(lambda: {
        "discoveries": 0,
        "analyses": 0,
        "infringements": 0,
    })

    videos = db.collection("videos").stream()
    total_videos = 0

    for video in videos:
        total_videos += 1
        data = video.to_dict()

        # Count discovery
        discovered_at = data.get("discovered_at")
        if discovered_at:
            if isinstance(discovered_at, str):
                from dateutil import parser
                discovered_at = parser.isoparse(discovered_at)

            # Round to hour
            hour = discovered_at.replace(minute=0, second=0, microsecond=0)
            if hour.tzinfo is None:
                hour = hour.replace(tzinfo=timezone.utc)
            else:
                hour = hour.astimezone(timezone.utc)

            hour_key = hour.strftime("%Y-%m-%d_%H")
            hourly_data[hour_key]["hour"] = hour
            hourly_data[hour_key]["discoveries"] += 1

        # Count analysis
        if data.get("status") == "analyzed":
            analyzed_at = data.get("last_analyzed_at") or discovered_at
            if analyzed_at:
                if isinstance(analyzed_at, str):
                    from dateutil import parser
                    analyzed_at = parser.isoparse(analyzed_at)

                hour = analyzed_at.replace(minute=0, second=0, microsecond=0)
                if hour.tzinfo is None:
                    hour = hour.replace(tzinfo=timezone.utc)
                else:
                    hour = hour.astimezone(timezone.utc)

                hour_key = hour.strftime("%Y-%m-%d_%H")
                hourly_data[hour_key]["hour"] = hour
                hourly_data[hour_key]["analyses"] += 1

                # Count infringement
                analysis = data.get("analysis") or data.get("vision_analysis", {})
                if isinstance(analysis, dict):
                    full_analysis = analysis.get("full_analysis", analysis)
                    if full_analysis.get("contains_infringement"):
                        hourly_data[hour_key]["infringements"] += 1

        if total_videos % 100 == 0:
            print(f"  Processed {total_videos} videos...")

    print(f"✅ Processed {total_videos} total videos")
    print(f"📊 Found data for {len(hourly_data)} unique hours")

    # Write to Firestore
    print("\n💾 Writing hourly stats to Firestore...")

    batch = db.batch()
    batch_count = 0
    total_written = 0

    for hour_key, stats in sorted(hourly_data.items()):
        doc_ref = db.collection("hourly_stats").document(hour_key)

        batch.set(doc_ref, {
            "hour": stats["hour"],
            "discoveries": stats["discoveries"],
            "analyses": stats["analyses"],
            "infringements": stats["infringements"],
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        batch_count += 1
        total_written += 1

        # Commit batch every 500 documents (Firestore limit)
        if batch_count >= 500:
            batch.commit()
            print(f"  Committed batch ({total_written} hours written)")
            batch = db.batch()
            batch_count = 0

    # Commit remaining
    if batch_count > 0:
        batch.commit()
        print(f"  Committed final batch ({total_written} hours written)")

    print(f"\n✅ Backfill complete! Wrote {total_written} hourly stat documents")

    # Show sample
    print("\n📈 Sample hourly stats (most recent 5):")
    recent_stats = (
        db.collection("hourly_stats")
        .order_by("hour", direction=firestore.Query.DESCENDING)
        .limit(5)
        .stream()
    )

    for stat_doc in recent_stats:
        data = stat_doc.to_dict()
        hour = data.get("hour")
        if isinstance(hour, datetime):
            hour_str = hour.strftime("%Y-%m-%d %H:00")
        else:
            hour_str = str(hour)

        print(f"  {hour_str}: {data.get('discoveries', 0)} discoveries, "
              f"{data.get('analyses', 0)} analyses, "
              f"{data.get('infringements', 0)} infringements")

if __name__ == "__main__":
    try:
        backfill_hourly_stats()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
