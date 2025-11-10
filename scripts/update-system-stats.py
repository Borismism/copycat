#!/usr/bin/env python3
"""Update system_stats/global with analyzed and infringements counts."""

import sys
from google.cloud import firestore
from google.cloud.firestore_v1.aggregation import AggregationQuery

def update_system_stats(project_id: str, database_id: str):
    """Update system_stats with current counts."""

    print(f"📊 Connecting to Firestore: {project_id}/{database_id}")
    db = firestore.Client(project=project_id, database=database_id)

    # Get current stats
    stats_ref = db.collection("system_stats").document("global")
    stats_doc = stats_ref.get()

    if not stats_doc.exists:
        print("❌ system_stats/global does not exist. Run initialize-system-stats.py first.")
        sys.exit(1)

    current_stats = stats_doc.to_dict()
    print(f"\n📈 Current stats:")
    print(f"   total_videos: {current_stats.get('total_videos', 0)}")
    print(f"   total_channels: {current_stats.get('total_channels', 0)}")
    print(f"   total_analyzed: {current_stats.get('total_analyzed', 0)}")
    print(f"   total_infringements: {current_stats.get('total_infringements', 0)}")

    # Count total analyzed videos using aggregation (fast!)
    print(f"\n🔍 Counting analyzed videos...")
    query = db.collection("videos").where(filter=firestore.FieldFilter("status", "==", "analyzed"))
    agg_query = AggregationQuery(query)
    agg_query.count(alias="total")
    result = agg_query.get()
    total_analyzed = result[0][0].value if result else 0
    print(f"   Found {total_analyzed} analyzed videos")

    # Count infringements (need to query because it's a nested field)
    print(f"\n🔍 Counting infringements...")
    analyzed_videos = db.collection("videos").where(filter=firestore.FieldFilter("status", "==", "analyzed")).stream()

    total_infringements = 0
    count = 0
    for video in analyzed_videos:
        data = video.to_dict()
        analysis = data.get("analysis", {})
        if isinstance(analysis, dict) and analysis.get("contains_infringement", False):
            total_infringements += 1

        count += 1
        if count % 100 == 0:
            print(f"   Processed {count}/{total_analyzed} videos...")

    print(f"   Found {total_infringements} infringements")

    # Update system_stats
    print(f"\n💾 Updating system_stats/global...")
    stats_ref.update({
        "total_analyzed": total_analyzed,
        "total_infringements": total_infringements,
        "updated_at": firestore.SERVER_TIMESTAMP,
    })

    print(f"\n✅ Updated system_stats:")
    print(f"   total_analyzed: {total_analyzed}")
    print(f"   total_infringements: {total_infringements}")
    print(f"   infringement_rate: {(total_infringements / total_analyzed * 100):.1f}%")


if __name__ == "__main__":
    import os

    # Get from environment or use defaults
    project_id = os.environ.get("GCP_PROJECT_ID", "copycat-429012")
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "copycat")

    try:
        update_system_stats(project_id, database_id)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
