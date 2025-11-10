"""Keyword scan statistics API endpoints."""

import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel

router = APIRouter()

# Initialize Firestore
db = firestore.Client(
    project=os.getenv("GCP_PROJECT_ID", "copycat-local"),
    database="copycat"
)


class KeywordScanStat(BaseModel):
    """Single keyword scan statistic."""
    keyword: str
    priority: str
    last_scanned_at: datetime | None
    total_scans: int
    videos_found: int
    last_result_count: int
    ip_id: str | None


class KeywordStatsResponse(BaseModel):
    """Response with keyword statistics."""
    total_keywords: int
    scanned_keywords: int
    never_scanned_keywords: int
    keywords: list[KeywordScanStat]


@router.get("/stats", response_model=KeywordStatsResponse)
async def get_keyword_stats():
    """
    Get keyword scan statistics.

    Returns:
        Statistics for all keywords including scan counts and videos found
    """
    try:
        # Get all keyword scan states
        keyword_states = db.collection("keyword_scan_state").stream()

        keywords = []
        scanned_count = 0
        never_scanned_count = 0

        for doc in keyword_states:
            data = doc.to_dict()

            keyword_stat = KeywordScanStat(
                keyword=data.get("keyword", doc.id),
                priority=data.get("priority", "unknown"),
                last_scanned_at=data.get("last_scanned_at"),
                total_scans=data.get("total_scans", 0),
                videos_found=data.get("videos_found", 0),
                last_result_count=data.get("last_result_count", 0),
                ip_id=data.get("ip_name")
            )

            keywords.append(keyword_stat)

            if keyword_stat.last_scanned_at:
                scanned_count += 1
            else:
                never_scanned_count += 1

        # Sort by videos found (descending)
        keywords.sort(key=lambda x: x.videos_found, reverse=True)

        return KeywordStatsResponse(
            total_keywords=len(keywords),
            scanned_keywords=scanned_count,
            never_scanned_keywords=never_scanned_count,
            keywords=keywords
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get keyword statistics: {e!s}"
        )


@router.get("/stats/last-run")
async def get_last_run_stats():
    """
    Get statistics for the most recent keyword scan run.

    Returns:
        Keywords scanned in the last run with video counts
    """
    try:
        # Get keyword states, sorted by last_scanned_at
        keyword_states = db.collection("keyword_scan_state")\
            .order_by("last_scanned_at", direction=firestore.Query.DESCENDING)\
            .limit(50)\
            .stream()

        keywords = []
        latest_scan = None

        for doc in keyword_states:
            data = doc.to_dict()
            last_scanned = data.get("last_scanned_at")

            if not last_scanned:
                continue

            # Track latest scan time
            if not latest_scan:
                latest_scan = last_scanned

            # Only include keywords from the same scan run (within 5 minutes)
            time_diff = abs((latest_scan - last_scanned).total_seconds())
            if time_diff > 300:  # 5 minutes
                break

            keywords.append({
                "keyword": data.get("keyword", doc.id),
                "priority": data.get("priority", "unknown"),
                "videos_found": data.get("last_result_count", 0),
                "scanned_at": last_scanned.isoformat() if last_scanned else None
            })

        # Sort by videos found
        keywords.sort(key=lambda x: x["videos_found"], reverse=True)

        total_videos = sum(k["videos_found"] for k in keywords)

        return {
            "scan_time": latest_scan.isoformat() if latest_scan else None,
            "keywords_scanned": len(keywords),
            "total_videos_found": total_videos,
            "keywords": keywords
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get last run statistics: {e!s}"
        )
