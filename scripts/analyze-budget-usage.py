#!/usr/bin/env python3
"""Analyze budget usage for vision analyzer service."""

from google.cloud import firestore
from datetime import datetime, timezone, timedelta

PROJECT_ID = "copycat-429012"
DATABASE_ID = "copycat"

db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

print("💰 Budget Analysis - Vision Analyzer Service (Production)")
print("=" * 80)

# Get all analyzed videos from last 7 days
cutoff = datetime.now(timezone.utc) - timedelta(days=7)

analyzed_videos = []
for video in db.collection("videos").where("status", "==", "analyzed").stream():
    data = video.to_dict()
    analyzed_at = data.get("analyzed_at")

    if analyzed_at:
        if hasattr(analyzed_at, "timestamp"):
            analyzed_dt = datetime.fromtimestamp(analyzed_at.timestamp(), tz=timezone.utc)
        else:
            analyzed_dt = analyzed_at
        if analyzed_dt.tzinfo is None:
            analyzed_dt = analyzed_dt.replace(tzinfo=timezone.utc)

        if analyzed_dt > cutoff:
            cost = data.get("analysis_cost_usd", 0)
            duration = data.get("duration_seconds", 0)
            vision_analysis = data.get("vision_analysis", {})
            analyzed_videos.append({
                "video_id": video.id,
                "title": data.get("title", "Unknown")[:50],
                "cost": cost,
                "duration": duration,
                "analyzed_at": analyzed_dt,
                "has_infringement": vision_analysis.get("contains_infringement", False) if isinstance(vision_analysis, dict) else False,
            })

# Sort by cost descending
analyzed_videos.sort(key=lambda x: x["cost"], reverse=True)

print(f"\n📊 Last 7 Days Summary:")
print(f"   Videos analyzed: {len(analyzed_videos):,}")

total_cost = sum(v["cost"] for v in analyzed_videos)
avg_cost = total_cost / len(analyzed_videos) if analyzed_videos else 0
infringement_count = sum(1 for v in analyzed_videos if v["has_infringement"])

print(f"   Total cost: ${total_cost:.2f}")
print(f"   Average cost per video: ${avg_cost:.4f}")
print(f"   Daily average: ${total_cost / 7:.2f}")
print(f"   Videos with infringement: {infringement_count} ({infringement_count/len(analyzed_videos)*100 if analyzed_videos else 0:.1f}%)")

# Show most expensive videos
print(f"\n💸 Top 10 Most Expensive Videos:")
for i, v in enumerate(analyzed_videos[:10], 1):
    mins = int(v["duration"] // 60)
    secs = int(v["duration"] % 60)
    inf_badge = "⚠️ " if v["has_infringement"] else ""
    print(f"   {i}. ${v['cost']:.4f} - {mins}:{secs:02d} - {inf_badge}{v['title']}")

# Group by day
by_day = {}
for v in analyzed_videos:
    day = v["analyzed_at"].strftime("%Y-%m-%d")
    if day not in by_day:
        by_day[day] = {"count": 0, "cost": 0, "infringement": 0}
    by_day[day]["count"] += 1
    by_day[day]["cost"] += v["cost"]
    if v["has_infringement"]:
        by_day[day]["infringement"] += 1

print(f"\n📅 Daily Breakdown:")
for day in sorted(by_day.keys(), reverse=True):
    stats = by_day[day]
    avg = stats["cost"]/stats["count"] if stats["count"] > 0 else 0
    inf_pct = stats["infringement"]/stats["count"]*100 if stats["count"] > 0 else 0
    print(f"   {day}: {stats['count']:4,} videos = ${stats['cost']:7.2f} (avg ${avg:.4f}/video, {inf_pct:.1f}% infringement)")

# Check if we're over budget
DAILY_BUDGET = 260  # $260/day
print(f"\n💵 Budget Status:")
for day in sorted(by_day.keys(), reverse=True)[:3]:  # Last 3 days
    stats = by_day[day]
    over_budget = stats["cost"] > DAILY_BUDGET
    badge = "❌ OVER" if over_budget else "✅"
    print(f"   {day}: ${stats['cost']:7.2f} / ${DAILY_BUDGET} {badge}")

print("=" * 80)
