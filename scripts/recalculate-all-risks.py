#!/usr/bin/env python3
"""
Recalculate risks for ALL channels using NEW risk model.

Usage:
    GCP_PROJECT_ID=copycat-429012 FIRESTORE_DATABASE=copycat uv run python3 scripts/recalculate-all-risks.py [start_index]
"""

import os
import sys
import time
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions


def get_db():
    project = os.environ.get("GCP_PROJECT_ID", "copycat-local")
    database = os.environ.get("FIRESTORE_DATABASE", "(default)")
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return firestore.Client(project=project)
    return firestore.Client(project=project, database=database)


def retry_update(doc_ref, data, max_retries=3):
    """Update with retry on transient errors."""
    for attempt in range(max_retries):
        try:
            doc_ref.update(data)
            return True
        except (gcp_exceptions.DeadlineExceeded, gcp_exceptions.ServiceUnavailable) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  WARN: Failed after {max_retries} retries: {e}")
                return False
    return False


def get_recommendation(v):
    analysis = v.get("analysis") or {}
    rec = analysis.get("overall_recommendation", "")
    if v.get("status") == "infringement":
        return "immediate_takedown"
    inf_status = v.get("infringement_status", "")
    if inf_status == "immediate_takedown":
        return "immediate_takedown"
    return rec or "unknown"


def is_scanned(v):
    return v.get("status") in ["analyzed", "scanned", "infringement", "clean", "completed", "failed"]


def calc_infringement_risk(video, channel):
    f = {}
    views = video.get("view_count", 0)
    f["views"] = 25 if views >= 10_000_000 else 22 if views >= 1_000_000 else 18 if views >= 100_000 else 12 if views >= 10_000 else 6 if views >= 1_000 else 2
    
    vel = video.get("view_velocity", 0)
    f["velocity"] = 25 if vel >= 10_000 else 20 if vel >= 1_000 else 12 if vel >= 100 else 5 if vel >= 10 else 0
    
    subs = channel.get("subscriber_count", 0)
    f["reach"] = 20 if subs >= 1_000_000 else 16 if subs >= 500_000 else 12 if subs >= 100_000 else 8 if subs >= 10_000 else 4 if subs >= 1_000 else 1
    
    analysis = video.get("analysis") or {}
    likelihood = analysis.get("max_likelihood", 50)
    f["severity"] = 15 if likelihood >= 80 else 10 if likelihood >= 50 else 5
    
    dur = video.get("duration_seconds", 0)
    f["duration"] = 10 if dur >= 600 else 8 if dur >= 300 else 5 if dur >= 120 else 3 if dur >= 60 else 1
    
    f["engagement"] = 0
    if views > 0:
        eng = (video.get("like_count", 0) + video.get("comment_count", 0)) / views
        f["engagement"] = 5 if eng > 0.05 else 3 if eng > 0.02 else 0
    
    total = min(100, max(0, sum(f.values())))
    tier = "CRITICAL" if total >= 80 else "HIGH" if total >= 60 else "MEDIUM" if total >= 40 else "LOW" if total >= 20 else "MINIMAL"
    return {"infringement_risk": total, "risk_tier": tier, "risk_factors": f}


def calc_channel_risk(infringements, scanned, subs):
    if scanned == 0:
        return {"channel_risk": 0, "factors": {"rate": 0, "volume": 0, "reach": 0}}
    
    rate = infringements / scanned
    if rate <= 0: r = 0
    elif rate <= 0.10: r = int(rate * 120)
    elif rate <= 0.25: r = 12 + int((rate - 0.10) * 87)
    elif rate <= 0.50: r = 25 + int((rate - 0.25) * 52)
    elif rate <= 0.75: r = 38 + int((rate - 0.50) * 28)
    else: r = 45 + int((rate - 0.75) * 20)
    r = min(50, r)
    
    v = 0 if infringements == 0 else 4 if infringements == 1 else 8 if infringements <= 3 else 12 if infringements <= 5 else 18 if infringements <= 10 else 24 if infringements <= 20 else 30
    
    if infringements == 0: rch = 0
    else: rch = 20 if subs >= 1_000_000 else 16 if subs >= 500_000 else 12 if subs >= 100_000 else 9 if subs >= 50_000 else 6 if subs >= 10_000 else 3 if subs >= 1_000 else 0
    
    return {"channel_risk": min(100, r + v + rch), "factors": {"rate": r, "volume": v, "reach": rch}}


def process_channel(db, channel_id, ch):
    subs = ch.get("subscriber_count", 0)
    name = ch.get("channel_name", ch.get("channel_title", "?"))
    
    videos = list(db.collection("videos").where("channel_id", "==", channel_id).stream())
    if not videos:
        return None
    
    scanned = 0
    infringements = 0
    by_status = {}

    for vdoc in videos:
        v = vdoc.to_dict()

        if not is_scanned(v):
            retry_update(db.collection("videos").document(vdoc.id), {"risk_tier": "PENDING"})
            by_status["pending"] = by_status.get("pending", 0) + 1
            continue

        scanned += 1
        rec = get_recommendation(v)
        by_status[rec] = by_status.get(rec, 0) + 1

        if rec == "immediate_takedown":
            infringements += 1
            res = calc_infringement_risk(v, ch)
            retry_update(db.collection("videos").document(vdoc.id), {
                "infringement_risk": res["infringement_risk"],
                "risk_tier": res["risk_tier"],
                "risk_factors": res["risk_factors"]
            })
        else:
            tier = rec.upper() if rec in ["tolerated", "safe_harbor", "monitor"] else "CLEAR"
            retry_update(db.collection("videos").document(vdoc.id), {
                "infringement_risk": 0,
                "risk_tier": tier,
                "risk_factors": {}
            })

    # Channel risk
    ch_res = calc_channel_risk(infringements, scanned, subs)
    old = ch.get("channel_risk", 0)
    new = ch_res["channel_risk"]

    retry_update(db.collection("channels").document(channel_id), {
        "channel_risk": new,
        "channel_risk_factors": ch_res["factors"],
        "confirmed_infringements": infringements,
        "total_videos_analyzed": scanned
    })

    # Update channel_risk on videos
    for vdoc in videos:
        retry_update(db.collection("videos").document(vdoc.id), {"channel_risk": new})

    return {
        "name": name,
        "subs": subs,
        "videos": len(videos),
        "scanned": scanned,
        "infringements": infringements,
        "old_risk": old,
        "new_risk": new,
        "by_status": by_status
    }


def main():
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    db = get_db()
    
    print(f"Fetching all channels (starting from index {start_idx})...")
    channels = list(db.collection("channels").stream())
    print(f"Found {len(channels)} channels\n")
    
    total_videos = 0
    total_infringements = 0
    results = []
    
    for i, ch_doc in enumerate(channels):
        if i < start_idx:
            continue
            
        channel_id = ch_doc.id
        ch = ch_doc.to_dict()
        
        try:
            result = process_channel(db, channel_id, ch)
            if result:
                results.append(result)
                total_videos += result["videos"]
                total_infringements += result["infringements"]
                
                status_str = ", ".join(f"{k}:{v}" for k,v in result["by_status"].items())
                print(f"[{i+1}/{len(channels)}] {result['name'][:30]:<30} | {result['videos']:>4} videos | {result['infringements']:>3} inf | risk: {result['old_risk']:>3} -> {result['new_risk']:>3} | {status_str}")
        except Exception as e:
            print(f"[{i+1}/{len(channels)}] ERROR on {channel_id}: {e}")
            time.sleep(2)
            continue
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {len(results)} channels, {total_videos} videos, {total_infringements} infringements")
    
    # Show channels with highest risk
    print(f"\nTOP 10 RISKY CHANNELS:")
    for r in sorted(results, key=lambda x: x["new_risk"], reverse=True)[:10]:
        print(f"  {r['new_risk']:>3} | {r['infringements']:>3} inf / {r['scanned']:>4} scanned | {r['subs']:>12,} subs | {r['name'][:40]}")


if __name__ == "__main__":
    main()
