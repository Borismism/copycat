#!/usr/bin/env python3
"""
Comprehensive diagnostic script for Copycat system.
Shows all issues, stuck videos, service health, and system state at a glance.

Usage:
    FIRESTORE_EMULATOR_HOST=localhost:8200 GCP_PROJECT_ID=copycat-local uv run python3 scripts/diagnose.py  # Local
    GCP_PROJECT_ID=copycat-429012 FIRESTORE_DATABASE_ID=copycat uv run python3 scripts/diagnose.py  # Prod
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from google.cloud import firestore
from collections import defaultdict

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")

def print_section(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}--- {text} ---{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.WHITE}{text}{Colors.END}")

def main():
    project_id = os.getenv('GCP_PROJECT_ID', 'copycat-local')
    database_id = os.getenv('FIRESTORE_DATABASE_ID', '(default)')
    is_prod = 'copycat-429012' in project_id

    print_header(f"🔍 COPYCAT SYSTEM DIAGNOSTICS")
    print_info(f"Project: {project_id}")
    print_info(f"Database: {database_id}")
    print_info(f"Environment: {'PRODUCTION' if is_prod else 'LOCAL'}")
    print_info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Initialize Firestore
    if is_prod:
        db = firestore.Client(project=project_id, database=database_id)
    else:
        db = firestore.Client(project=project_id)

    now = datetime.now(timezone.utc)

    # ============================================================================
    # 1. STUCK VIDEOS IN PROCESSING
    # ============================================================================
    print_section("1. Videos Stuck in Processing")
    try:
        processing_videos = list(db.collection('videos').where('status', '==', 'processing').stream())

        if not processing_videos:
            print_success(f"No videos stuck in processing")
        else:
            stuck_count = len(processing_videos)
            print_error(f"Found {stuck_count} videos stuck in 'processing' status")

            # Categorize by age
            very_old = []  # >30 min
            old = []  # 10-30 min
            recent = []  # <10 min

            for video in processing_videos:
                data = video.to_dict()
                processing_started = data.get('processing_started_at')
                updated_at = data.get('updated_at')

                if processing_started:
                    age_seconds = (now.timestamp() - processing_started.timestamp())
                elif updated_at:
                    age_seconds = (now.timestamp() - updated_at.timestamp())
                else:
                    age_seconds = 0

                age_minutes = int(age_seconds / 60)

                video_info = {
                    'id': video.id,
                    'title': data.get('title', 'N/A')[:50],
                    'age_minutes': age_minutes,
                    'channel_id': data.get('channel_id', 'N/A')
                }

                if age_minutes > 30:
                    very_old.append(video_info)
                elif age_minutes > 10:
                    old.append(video_info)
                else:
                    recent.append(video_info)

            if very_old:
                print_error(f"\n  CRITICAL: {len(very_old)} videos stuck >30 minutes:")
                for v in sorted(very_old, key=lambda x: x['age_minutes'], reverse=True)[:10]:
                    print(f"    • {v['id']}: {v['age_minutes']} min - {v['title']}")

            if old:
                print_warning(f"\n  WARNING: {len(old)} videos stuck 10-30 minutes:")
                for v in sorted(old, key=lambda x: x['age_minutes'], reverse=True)[:10]:
                    print(f"    • {v['id']}: {v['age_minutes']} min - {v['title']}")

            if recent:
                print_info(f"\n  INFO: {len(recent)} videos processing <10 minutes (may be normal)")
    except Exception as e:
        print_error(f"Failed to check stuck videos: {e}")

    # ============================================================================
    # 2. ACTIVE SCANS IN SCAN_HISTORY
    # ============================================================================
    print_section("2. Active Scans in scan_history")
    try:
        active_scans = list(db.collection('scan_history').where('status', '==', 'processing').stream())

        if not active_scans:
            print_success("No scans currently in 'processing' state")
        else:
            print_warning(f"Found {len(active_scans)} active scans")
            for scan in active_scans[:20]:
                data = scan.to_dict()
                started_at = data.get('started_at')
                age = int((now.timestamp() - started_at.timestamp()) / 60) if started_at else 0
                print(f"  • {data.get('video_id', 'N/A')}: {age} min (scan_id: {scan.id[:20]}...)")
    except Exception as e:
        print_error(f"Failed to check active scans: {e}")

    # ============================================================================
    # 3. VIDEO STATUS BREAKDOWN
    # ============================================================================
    print_section("3. Video Status Breakdown")
    try:
        # Get all videos and count by status
        all_videos = db.collection('videos').stream()
        status_counts = defaultdict(int)

        for video in all_videos:
            data = video.to_dict()
            status = data.get('status', 'unknown')
            status_counts[status] += 1

        total_videos = sum(status_counts.values())
        print_info(f"Total videos in database: {total_videos}")
        print()
        for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_videos * 100) if total_videos > 0 else 0

            if status == 'processing' and count > 50:
                print_error(f"  {status:20s}: {count:6d} ({percentage:5.1f}%)")
            elif status == 'error':
                print_warning(f"  {status:20s}: {count:6d} ({percentage:5.1f}%)")
            else:
                print_info(f"  {status:20s}: {count:6d} ({percentage:5.1f}%)")
    except Exception as e:
        print_error(f"Failed to get video status breakdown: {e}")

    # ============================================================================
    # 4. RECENT ERRORS (scan_history)
    # ============================================================================
    print_section("4. Recent Errors (Last 24h)")
    try:
        yesterday = now - timedelta(days=1)
        error_scans = list(db.collection('scan_history')
                          .where('status', '==', 'error')
                          .where('started_at', '>=', yesterday)
                          .limit(20)
                          .stream())

        if not error_scans:
            print_success("No errors in scan_history in last 24 hours")
        else:
            print_warning(f"Found {len(error_scans)} errors in last 24 hours")
            for scan in error_scans[:10]:
                data = scan.to_dict()
                error_msg = data.get('error_message', 'No error message')[:100]
                print(f"  • {data.get('video_id', 'N/A')}: {error_msg}")
    except Exception as e:
        print_warning(f"Failed to check recent errors: {e}")

    # ============================================================================
    # 5. BUDGET USAGE (if prod)
    # ============================================================================
    if is_prod:
        print_section("5. Budget Usage (Today)")
        try:
            # Get system_stats
            stats_ref = db.collection('system_stats').document('daily_stats')
            stats = stats_ref.get()

            if stats.exists:
                data = stats.to_dict()
                cost_today = data.get('cost_today', 0)
                videos_analyzed_today = data.get('videos_analyzed_today', 0)
                budget_limit = 260.0  # €260/day

                budget_pct = (cost_today / budget_limit * 100) if budget_limit > 0 else 0

                print_info(f"  Cost today: €{cost_today:.2f} / €{budget_limit:.2f} ({budget_pct:.1f}%)")
                print_info(f"  Videos analyzed today: {videos_analyzed_today}")

                if budget_pct > 90:
                    print_error(f"  WARNING: Budget at {budget_pct:.1f}%!")
                elif budget_pct > 75:
                    print_warning(f"  Budget usage is high: {budget_pct:.1f}%")
            else:
                print_warning("No system_stats found")
        except Exception as e:
            print_warning(f"Failed to check budget: {e}")

    # ============================================================================
    # 6. QUEUE BACKLOGS
    # ============================================================================
    print_section("6. Queue Status")
    try:
        # Videos pending analysis (discovered but not analyzed)
        pending = list(db.collection('videos')
                      .where('status', '==', 'discovered')
                      .limit(1000)
                      .stream())

        if len(pending) == 0:
            print_success("No videos pending analysis")
        elif len(pending) < 100:
            print_info(f"Queue size: {len(pending)} videos pending analysis (normal)")
        else:
            print_warning(f"Large queue: {len(pending)} videos pending analysis")
    except Exception as e:
        print_warning(f"Failed to check queue: {e}")

    # ============================================================================
    # 7. OLDEST UNPROCESSED VIDEOS
    # ============================================================================
    print_section("7. Oldest Unprocessed Videos")
    try:
        old_discovered = list(db.collection('videos')
                             .where('status', '==', 'discovered')
                             .order_by('discovered_at')
                             .limit(10)
                             .stream())

        if not old_discovered:
            print_success("No old unprocessed videos")
        else:
            print_info(f"Oldest {len(old_discovered)} discovered videos:")
            for video in old_discovered:
                data = video.to_dict()
                discovered = data.get('discovered_at')
                age_hours = int((now.timestamp() - discovered.timestamp()) / 3600) if discovered else 0
                print(f"  • {video.id}: {age_hours}h old - {data.get('title', 'N/A')[:50]}")
    except Exception as e:
        print_warning(f"Failed to check oldest videos: {e}")

    # ============================================================================
    # SUMMARY
    # ============================================================================
    print_header("📊 SUMMARY")

    issues = []
    if 'processing_videos' in locals() and len(processing_videos) > 50:
        issues.append(f"{len(processing_videos)} videos stuck in processing")
    if 'active_scans' in locals() and len(active_scans) > 0:
        issues.append(f"{len(active_scans)} active scans in scan_history")
    if 'error_scans' in locals() and len(error_scans) > 5:
        issues.append(f"{len(error_scans)} errors in last 24h")

    if issues:
        print_error("Issues found:")
        for issue in issues:
            print(f"  • {issue}")
        print()
        print_info("💡 To fix stuck videos, run:")
        print_info(f"   GCP_PROJECT_ID={project_id} FIRESTORE_DATABASE_ID={database_id} uv run python3 scripts/reset-stuck-videos.py")
    else:
        print_success("System looks healthy!")

    print()

if __name__ == '__main__':
    main()
