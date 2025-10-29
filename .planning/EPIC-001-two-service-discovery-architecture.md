# EPIC 001: Two-Service Discovery & Risk Analysis Architecture

**Status:** Planning
**Priority:** P0 (Critical)
**Target Completion:** Sprint 1-3 (3 weeks)
**Owner:** Engineering Team

---

## 📋 Executive Summary

### Current State (Problems)
- ❌ Discovery service doing too much: finding videos + tracking trends + rescanning
- ❌ No risk-based prioritization - treating all videos equally
- ❌ Wasting Gemini budget (€240/day) on low-risk content
- ❌ Channel database polluted with non-DC channels (LOLvengers, dog channels, etc.)
- ❌ 140 quota units spent, 0 videos found (100% miss rate)
- ❌ No viral detection - can't catch trending infringements early
- ❌ Fixed scanning frequency - can't adapt to channel behavior

### Future State (Goals)
- ✅ **Separation of Concerns:** Discovery finds NEW content, Risk Analyzer prioritizes it
- ✅ **Risk-Based Prioritization:** HIGH risk videos get immediate Gemini analysis
- ✅ **Budget Optimization:** €240/day spent on most likely infringements (80%+ hit rate target)
- ✅ **Clean Database:** Only DC/superhero/AI-related channels tracked
- ✅ **Viral Detection:** Trending videos automatically elevated to CRITICAL risk
- ✅ **Adaptive Scanning:** High-risk channels scanned daily, low-risk monthly
- ✅ **Quota Efficiency:** 10,000 units/day focused on discovery, not rescanning

### Success Metrics
| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Video discovery hit rate | 0% | 15%+ | Videos matching keywords / total scanned |
| Gemini budget utilization | ~€27/day | €240/day | Daily Gemini spend |
| Gemini hit rate (infringements) | Unknown | 30%+ | Confirmed infringements / videos analyzed |
| Quota efficiency | 0 videos/140 units | 50+ videos/10k units | Videos discovered / quota spent |
| Viral detection latency | N/A | <6 hours | Time from trending start to detection |
| Channel database quality | ~10% relevant | 90%+ relevant | DC-related channels / total channels |

---

## 🎯 Epic Objectives

### Why This Matters
1. **Cost Efficiency:** We're burning €240/day Gemini budget capacity but only using €27/day because we can't find enough high-quality candidates
2. **Legal Impact:** Missing viral infringements costs clients millions in damages (10M views = potential €100k+ lawsuit)
3. **System Scalability:** Current architecture can't scale - discovery service trying to do everything
4. **Data Quality:** Polluted channel database means wasted quota on irrelevant content

### Business Value
- **Revenue Protection:** Catch infringements before they go mega-viral (10M+ views)
- **Client Trust:** Demonstrate comprehensive monitoring with measurable results
- **Operational Efficiency:** Automated risk scoring reduces manual review by 80%
- **Competitive Advantage:** Real-time viral detection vs. competitors' weekly scans

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DISCOVERY SERVICE                                │
│  Purpose: Find ALL new DC AI-generated content (wide net)           │
│  Budget: 10,000 YouTube API units/day                               │
│  Frequency: Hourly                                                  │
│                                                                     │
│  Methods:                                                           │
│  ├── Keyword Search (70% quota) - 262 keywords rotated             │
│  ├── Trending Feed (20% quota) - Viral detection                   │
│  └── Channel Monitoring (10% quota) - Known infringers             │
│                                                                     │
│  Output:                                                            │
│  └── Firestore: videos (with initial_risk: 0-100)                  │
│      PubSub: video-discovered topic                                │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   RISK ANALYZER SERVICE                              │
│  Purpose: Continuously update risk scores, prioritize for Gemini    │
│  Budget: 2,000 YouTube API units/day (for rescanning)              │
│  Frequency: Continuous (event-driven + scheduled)                   │
│                                                                     │
│  Responsibilities:                                                  │
│  ├── View velocity tracking (viral detection)                      │
│  ├── Channel reputation scoring                                    │
│  ├── Risk-based rescanning schedule                                │
│  └── Priority queue management                                     │
│                                                                     │
│  Risk Tiers & Rescan Frequency:                                    │
│  ├── CRITICAL (90-100): Every 6 hours                              │
│  ├── HIGH (70-89): Daily                                           │
│  ├── MEDIUM (40-69): Every 3 days                                  │
│  ├── LOW (20-39): Weekly                                           │
│  └── VERY_LOW (0-19): Monthly                                      │
│                                                                     │
│  Output:                                                            │
│  └── Firestore: videos (current_risk updated)                      │
│      PubSub: video-high-risk topic (for vision-analyzer)           │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   VISION ANALYZER SERVICE                            │
│  Purpose: Gemini analysis of high-risk videos only                  │
│  Budget: €240/day Gemini API                                       │
│  Frequency: Continuous (budget exhaustion model)                    │
│                                                                     │
│  Strategy:                                                          │
│  ├── Subscribe to video-high-risk topic                            │
│  ├── Process videos sorted by current_risk (highest first)         │
│  ├── Scan until daily budget exhausted                             │
│  └── Update channel risk based on results                          │
│                                                                     │
│  Output:                                                            │
│  └── Firestore: videos (gemini_result, infringement_confirmed)     │
│      BigQuery: results table                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📚 Epics Breakdown

### Epic 1: Database Cleanup & Schema Migration
**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 1

**Why:** Polluted database is causing 0% hit rate. Must clean before new architecture.

### Epic 2: Discovery Service Refactor
**Priority:** P0
**Effort:** 13 story points
**Sprint:** Sprint 1-2

**Why:** Core of new architecture. Must separate discovery from risk analysis.

### Epic 3: Risk Analyzer Service (New)
**Priority:** P0
**Effort:** 21 story points
**Sprint:** Sprint 2-3

**Why:** Second pillar of architecture. Enables intelligent prioritization.

### Epic 4: Integration & Testing
**Priority:** P0
**Effort:** 8 story points
**Sprint:** Sprint 3

**Why:** Validate end-to-end flow and measure success metrics.

---

# 🎯 EPIC 1: Database Cleanup & Schema Migration

**Goal:** Clean polluted channel/video database and prepare schema for two-service architecture

**Why Critical:** Current database has 90%+ irrelevant channels (dog videos, gaming, etc.), causing 0% discovery hit rate

**Dependencies:** None (blocking all other epics)

---

## Story 1.1: Audit Current Database Quality

**Priority:** P0
**Effort:** 2 story points
**Sprint:** Sprint 1

### User Story
```
As a Data Engineer
I want to analyze current database quality
So that I understand the scope of cleanup needed
```

### Why This Matters
- Need baseline metrics to measure cleanup success
- Understand what % of channels are actually DC-related
- Identify patterns in bad data (how did dog channels get in?)

### Acceptance Criteria
- [ ] Query Firestore `channels` collection and export to CSV
- [ ] Analyze channel names/descriptions for DC/superhero keywords
- [ ] Calculate % of channels that are DC-related vs. irrelevant
- [ ] Generate report with:
  - Total channels count
  - DC-related channels count and %
  - Top 20 most scanned irrelevant channels
  - Common patterns in irrelevant channels
- [ ] Document findings in `.planning/database-audit-report.md`

### Definition of Done (DoD)
- ✅ Audit report committed to `.planning/`
- ✅ Metrics dashboard created showing database quality
- ✅ Cleanup strategy documented based on findings
- ✅ Team reviewed and approved cleanup approach

### Technical Notes
```python
# Query to analyze channels
channels = firestore.collection('channels').stream()
dc_keywords = ['superman', 'batman', 'wonder woman', 'flash', 'aquaman',
               'justice league', 'dc comics', 'dc universe', 'ai generated',
               'sora', 'runway', 'kling']

relevant = 0
irrelevant = []

for channel in channels:
    name = channel.get('channel_name', '').lower()
    if any(kw in name for kw in dc_keywords):
        relevant += 1
    else:
        irrelevant.append({
            'id': channel.id,
            'name': channel.get('channel_name'),
            'videos_found': channel.get('total_videos_found', 0)
        })
```

### Test Cases
- [ ] Script successfully queries all channels
- [ ] Report includes all required sections
- [ ] Metrics are accurate (manual spot-check 10 channels)

---

## Story 1.2: Implement Channel Cleanup Script

**Priority:** P0
**Effort:** 3 story points
**Sprint:** Sprint 1

### User Story
```
As a System Administrator
I want to remove irrelevant channels from the database
So that discovery service only tracks DC-related content
```

### Why This Matters
- Irrelevant channels waste quota and pollute search results
- Clean database = higher discovery hit rate
- Enables accurate channel risk scoring

### Acceptance Criteria
- [ ] Create Python script `scripts/cleanup-channels.py`
- [ ] Script identifies channels to delete based on:
  - Channel name contains NO DC/superhero/AI keywords
  - Zero videos with IP matches found
  - Not manually whitelisted
- [ ] Dry-run mode shows what would be deleted (with --dry-run flag)
- [ ] Actual deletion mode with confirmation prompt (--confirm flag)
- [ ] Backup deleted channels to `channels_archive` collection with deletion timestamp
- [ ] Script logs all deletions to `cleanup_log.txt`
- [ ] Delete associated videos from deleted channels

### Definition of Done (DoD)
- ✅ Script tested in dev environment
- ✅ Dry-run executed and reviewed by team
- ✅ Backup mechanism verified (can restore if needed)
- ✅ Production cleanup executed
- ✅ Post-cleanup metrics show >80% relevant channels
- ✅ Documentation updated with cleanup procedure

### Technical Implementation
```python
# scripts/cleanup-channels.py
import argparse
from google.cloud import firestore

DC_KEYWORDS = [
    'superman', 'batman', 'wonder woman', 'flash', 'aquaman',
    'justice league', 'dc comics', 'cyborg', 'green lantern',
    'ai generated', 'sora', 'runway', 'kling', 'pika', 'luma'
]

def should_keep_channel(channel: dict) -> bool:
    """Determine if channel should be kept."""
    name = channel.get('channel_name', '').lower()

    # Keep if name contains DC/AI keywords
    if any(kw in name for kw in DC_KEYWORDS):
        return True

    # Keep if channel has found any IP matches
    if channel.get('total_videos_found', 0) > 0:
        return True

    # Keep if manually whitelisted
    if channel.get('whitelisted', False):
        return True

    return False

def cleanup_channels(dry_run: bool = True, confirm: bool = False):
    """Remove irrelevant channels."""
    db = firestore.Client()

    channels = db.collection('channels').stream()
    to_delete = []

    for channel_doc in channels:
        channel = channel_doc.to_dict()
        if not should_keep_channel(channel):
            to_delete.append({
                'id': channel_doc.id,
                'name': channel.get('channel_name'),
                'videos_scanned': channel.get('total_videos_scanned', 0)
            })

    print(f"Found {len(to_delete)} channels to delete")

    if dry_run:
        print("\n🔍 DRY RUN - No changes will be made")
        for ch in to_delete[:10]:  # Show first 10
            print(f"  - {ch['name']} ({ch['videos_scanned']} videos)")
        return

    if not confirm:
        response = input(f"\n⚠️  Delete {len(to_delete)} channels? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled")
            return

    # Archive and delete
    for ch in to_delete:
        # Archive
        db.collection('channels_archive').document(ch['id']).set({
            **channel,
            'deleted_at': firestore.SERVER_TIMESTAMP,
            'deletion_reason': 'irrelevant_content'
        })

        # Delete videos from this channel
        videos = db.collection('videos').where('channel_id', '==', ch['id']).stream()
        for video in videos:
            video.reference.delete()

        # Delete channel
        db.collection('channels').document(ch['id']).delete()

        print(f"✓ Deleted: {ch['name']}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    cleanup_channels(dry_run=args.dry_run, confirm=args.confirm)
```

### Test Cases
- [ ] Dry-run shows expected channels to delete
- [ ] Channels with IP matches are NOT deleted
- [ ] DC-keyword channels are kept (even with 0 matches)
- [ ] Archived channels can be restored
- [ ] Videos from deleted channels are also deleted
- [ ] Script handles errors gracefully (Firestore errors, permissions)

---

## Story 1.3: Add Risk Scoring Fields to Firestore Schema

**Priority:** P0
**Effort:** 2 story points
**Sprint:** Sprint 1

### User Story
```
As a Backend Engineer
I want to add risk scoring fields to the Firestore schema
So that both services can track and update video/channel risk scores
```

### Why This Matters
- New architecture requires `initial_risk` and `current_risk` fields
- Schema must support risk history tracking for analytics
- Must be backward compatible with existing videos

### Acceptance Criteria
- [ ] Update `videos` collection schema with new fields:
  - `initial_risk` (int, 0-100): Assigned by discovery-service
  - `current_risk` (int, 0-100): Updated by risk-analyzer-service
  - `risk_history` (array): [{timestamp, risk, reason}]
  - `next_scan_at` (timestamp): When to rescan based on risk
  - `last_risk_update` (timestamp): Last time risk was updated
  - `view_velocity` (float): Views per hour
  - `risk_tier` (string): CRITICAL, HIGH, MEDIUM, LOW, VERY_LOW
- [ ] Update `channels` collection schema:
  - `channel_risk` (int, 0-100): Current risk level
  - `initial_risk` (int, 0-100): First assigned risk
  - `infringement_rate` (float): Confirmed infringements / total scanned
  - `last_risk_update` (timestamp): Last risk calculation
  - `scan_frequency` (string): Based on channel_risk
- [ ] Create Firestore migration script to add fields to existing documents
- [ ] Add indexes for efficient querying:
  - `videos` WHERE `next_scan_at` <= now() ORDER BY `current_risk` DESC
  - `videos` WHERE `risk_tier` == 'CRITICAL' ORDER BY `view_velocity` DESC
- [ ] Update TypeScript types in frontend

### Definition of Done (DoD)
- ✅ Schema documented in `.planning/firestore-schema-v2.md`
- ✅ Migration script tested in dev environment
- ✅ All existing videos have default risk values (initial_risk: 50, current_risk: 50)
- ✅ Indexes created and verified efficient (query time <1s)
- ✅ TypeScript types updated and type-check passes
- ✅ No breaking changes to existing services

### Technical Implementation
```python
# scripts/migrate-schema-v2.py
from google.cloud import firestore
from datetime import datetime, timezone

def migrate_videos():
    """Add risk fields to existing videos."""
    db = firestore.Client()
    videos = db.collection('videos').stream()

    for video_doc in videos:
        video = video_doc.to_dict()

        # Skip if already migrated
        if 'initial_risk' in video:
            continue

        # Calculate initial risk based on existing data
        initial_risk = calculate_legacy_risk(video)

        updates = {
            'initial_risk': initial_risk,
            'current_risk': initial_risk,
            'risk_history': [{
                'timestamp': datetime.now(timezone.utc),
                'risk': initial_risk,
                'reason': 'schema_migration'
            }],
            'next_scan_at': calculate_next_scan(initial_risk),
            'last_risk_update': datetime.now(timezone.utc),
            'view_velocity': 0.0,
            'risk_tier': get_risk_tier(initial_risk)
        }

        video_doc.reference.update(updates)
        print(f"✓ Migrated video: {video.get('video_id')}")

def calculate_legacy_risk(video: dict) -> int:
    """Calculate initial risk from legacy data."""
    risk = 50  # Default medium risk

    # Boost risk if keywords match in title
    if video.get('matched_keywords'):
        risk += 20

    # Boost risk if high views
    if video.get('view_count', 0) > 10000:
        risk += 10

    return min(risk, 100)

def get_risk_tier(risk: int) -> str:
    """Convert risk score to tier."""
    if risk >= 90:
        return 'CRITICAL'
    elif risk >= 70:
        return 'HIGH'
    elif risk >= 40:
        return 'MEDIUM'
    elif risk >= 20:
        return 'LOW'
    else:
        return 'VERY_LOW'

def calculate_next_scan(risk: int) -> datetime:
    """Calculate next scan time based on risk."""
    from datetime import timedelta

    if risk >= 90:
        return datetime.now(timezone.utc) + timedelta(hours=6)
    elif risk >= 70:
        return datetime.now(timezone.utc) + timedelta(days=1)
    elif risk >= 40:
        return datetime.now(timezone.utc) + timedelta(days=3)
    elif risk >= 20:
        return datetime.now(timezone.utc) + timedelta(days=7)
    else:
        return datetime.now(timezone.utc) + timedelta(days=30)
```

### Firestore Indexes (terraform)
```hcl
# terraform/firestore-indexes.tf
resource "google_firestore_index" "videos_scan_priority" {
  collection = "videos"

  fields {
    field_path = "next_scan_at"
    order      = "ASCENDING"
  }

  fields {
    field_path = "current_risk"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "videos_critical_trending" {
  collection = "videos"

  fields {
    field_path = "risk_tier"
    order      = "ASCENDING"
  }

  fields {
    field_path = "view_velocity"
    order      = "DESCENDING"
  }
}
```

### Test Cases
- [ ] Migration script processes all videos without errors
- [ ] Legacy videos get reasonable initial_risk values
- [ ] Indexes are created successfully
- [ ] Query performance meets <1s requirement
- [ ] Existing services continue to work (no breaking changes)
- [ ] TypeScript types match Firestore schema exactly

---

# 🎯 EPIC 2: Discovery Service Refactor

**Goal:** Transform discovery-service into pure discovery engine focused on finding NEW content with initial risk scoring

**Why Critical:** Current service tries to do everything (discovery + rescanning + trend analysis). Must focus solely on discovery.

**Dependencies:** Epic 1 (Database Cleanup)

---

## Story 2.1: Remove Rescanning Logic from Discovery Service

**Priority:** P0
**Effort:** 3 story points
**Sprint:** Sprint 1

### User Story
```
As a Backend Engineer
I want to remove all rescanning/trend analysis code from discovery-service
So that it focuses purely on finding new videos
```

### Why This Matters
- Rescanning wastes discovery quota (140 units spent on 0 new videos)
- Risk analyzer will handle all rescanning
- Simplifies discovery service codebase

### Acceptance Criteria
- [ ] Delete `app/core/video_rescanner.py`
- [ ] Remove Tier 5 (video rescanning) from `discovery_engine.py`
- [ ] Remove `view_velocity_tracker.py` (moves to risk-analyzer)
- [ ] Remove `get_videos_due_for_rescan()` from all code
- [ ] Update `discover_engine.discover()` to only run Tiers 1-4
- [ ] Remove `fresh_content_scanner.py` (duplicate of keyword search)
- [ ] Remove all view tracking code from discovery service
- [ ] Update tests to reflect removed functionality
- [ ] Update API endpoints - remove `/discover/rescan`

### Definition of Done (DoD)
- ✅ All rescanning code removed and verified deleted
- ✅ Tests pass (remove tests for deleted functionality)
- ✅ No references to removed modules in codebase
- ✅ Service still deploys and runs successfully
- ✅ Code coverage maintained above 80%
- ✅ API documentation updated

### Files to Modify/Delete
```bash
# Delete these files
rm services/discovery-service/app/core/video_rescanner.py
rm services/discovery-service/app/core/view_velocity_tracker.py
rm services/discovery-service/app/core/fresh_content_scanner.py
rm services/discovery-service/tests/test_video_rescanner.py
rm services/discovery-service/tests/test_view_velocity_tracker.py

# Modify these files
services/discovery-service/app/core/discovery_engine.py
services/discovery-service/app/routers/discover.py
services/discovery-service/tests/test_discovery_engine.py
```

### Test Cases
- [ ] `pytest` passes with removed modules
- [ ] `discover()` runs Tiers 1-4 only
- [ ] No imports of deleted modules fail
- [ ] Service starts without errors

---

## Story 2.2: Implement Initial Risk Scoring Algorithm

**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 1-2

### User Story
```
As a Backend Engineer
I want to assign initial risk scores to newly discovered videos
So that the risk analyzer can prioritize them appropriately
```

### Why This Matters
- Risk analyzer needs starting point (initial_risk) to work from
- Good initial scoring reduces false positives sent to Gemini
- Saves Gemini budget by filtering obvious non-matches

### Acceptance Criteria
- [ ] Create `app/core/initial_risk_scorer.py` module
- [ ] Implement `calculate_initial_video_risk(video: VideoMetadata) -> int`
- [ ] Risk scoring factors (documented with weights):
  - Title contains character name + AI tool (60 points)
  - Description mentions AI tools (20 points)
  - Channel has prior infringements (20 points)
  - High view count >10k (10 points)
  - Tags contain keywords (10 points)
- [ ] Implement `calculate_initial_channel_risk(channel: ChannelProfile) -> int`
- [ ] Channel risk based on:
  - Match rate from first scan (0-80 points)
  - Channel name contains DC keywords (20 points)
- [ ] Integrate into video_processor.py after IP matching
- [ ] Log risk scores with reasoning for debugging
- [ ] Add risk score distribution metrics (histogram)

### Definition of Done (DoD)
- ✅ Risk scoring algorithm implemented and tested
- ✅ Unit tests cover all scoring factors
- ✅ Risk scores logged for every discovered video
- ✅ Metrics dashboard shows risk distribution
- ✅ Documentation explains scoring algorithm
- ✅ Team reviewed and approved scoring weights
- ✅ Initial testing shows reasonable risk distribution:
  - 10% CRITICAL (90-100)
  - 20% HIGH (70-89)
  - 40% MEDIUM (40-69)
  - 20% LOW (20-39)
  - 10% VERY_LOW (0-19)

### Technical Implementation
```python
# app/core/initial_risk_scorer.py
import logging
from typing import Dict, List
import re

logger = logging.getLogger(__name__)

class InitialRiskScorer:
    """
    Assigns initial risk scores to newly discovered videos.

    Risk scale: 0-100
    - 90-100: CRITICAL - Strong indicators, immediate Gemini analysis
    - 70-89: HIGH - Multiple indicators, priority analysis
    - 40-69: MEDIUM - Some indicators, regular monitoring
    - 20-39: LOW - Weak indicators, periodic checks
    - 0-19: VERY_LOW - Minimal indicators, archive monitoring
    """

    # Character names for matching
    CHARACTERS = [
        'superman', 'batman', 'wonder woman', 'flash', 'aquaman',
        'cyborg', 'green lantern', 'justice league'
    ]

    # AI tool keywords
    AI_TOOLS = [
        'sora', 'runway', 'kling', 'pika', 'luma', 'midjourney',
        'stable diffusion', 'ai generated', 'text to video'
    ]

    def calculate_video_risk(
        self,
        video: Dict,
        channel: Dict = None,
        matched_keywords: List[str] = None
    ) -> Dict[str, any]:
        """
        Calculate initial risk score for a video.

        Returns:
            {
                'risk_score': int (0-100),
                'risk_tier': str,
                'reasoning': [str],  # Human-readable reasons
                'factors': {         # Individual factor scores
                    'title': int,
                    'description': int,
                    'channel': int,
                    'engagement': int,
                    'tags': int
                }
            }
        """
        score = 0
        reasoning = []
        factors = {}

        # Factor 1: Title Analysis (0-60 points)
        title_score = self._score_title(video.get('title', ''))
        score += title_score
        factors['title'] = title_score
        if title_score > 0:
            reasoning.append(f"Title analysis: +{title_score} points")

        # Factor 2: Description Analysis (0-20 points)
        desc_score = self._score_description(video.get('description', ''))
        score += desc_score
        factors['description'] = desc_score
        if desc_score > 0:
            reasoning.append(f"Description mentions AI tools: +{desc_score} points")

        # Factor 3: Channel Reputation (0-20 points)
        if channel:
            channel_score = self._score_channel_reputation(channel)
            score += channel_score
            factors['channel'] = channel_score
            if channel_score > 0:
                reasoning.append(f"Channel reputation: +{channel_score} points")
        else:
            factors['channel'] = 0

        # Factor 4: Engagement Metrics (0-10 points)
        engagement_score = self._score_engagement(video)
        score += engagement_score
        factors['engagement'] = engagement_score
        if engagement_score > 0:
            reasoning.append(f"High engagement: +{engagement_score} points")

        # Factor 5: Tags Analysis (0-10 points)
        tags_score = self._score_tags(video.get('tags', []))
        score += tags_score
        factors['tags'] = tags_score
        if tags_score > 0:
            reasoning.append(f"Tags match keywords: +{tags_score} points")

        # Cap at 100
        score = min(score, 100)

        # Determine tier
        tier = self._get_risk_tier(score)

        logger.info(
            f"Initial risk for video {video.get('video_id')}: "
            f"{score} ({tier}) - {', '.join(reasoning)}"
        )

        return {
            'risk_score': score,
            'risk_tier': tier,
            'reasoning': reasoning,
            'factors': factors
        }

    def _score_title(self, title: str) -> int:
        """
        Score based on title analysis.

        Scoring:
        - Character + AI tool: 60 points (e.g., "Superman Sora AI")
        - Character only: 30 points (e.g., "Superman Movie")
        - AI tool only: 20 points (e.g., "Sora Generated Video")
        - Weak match: 10 points
        """
        title_lower = title.lower()

        has_character = any(char in title_lower for char in self.CHARACTERS)
        has_ai_tool = any(tool in title_lower for tool in self.AI_TOOLS)

        if has_character and has_ai_tool:
            return 60  # Strong indicator
        elif has_character:
            return 30  # Character present
        elif has_ai_tool:
            return 20  # AI-generated content
        elif any(word in title_lower for word in ['dc', 'comic', 'superhero']):
            return 10  # Weak match

        return 0

    def _score_description(self, description: str) -> int:
        """Score based on description analysis (0-20 points)."""
        if not description:
            return 0

        desc_lower = description.lower()

        # Check for explicit AI tool mentions
        ai_mentions = sum(1 for tool in self.AI_TOOLS if tool in desc_lower)

        if ai_mentions >= 2:
            return 20  # Multiple AI tools mentioned
        elif ai_mentions == 1:
            return 15  # One AI tool mentioned
        elif 'ai' in desc_lower or 'generated' in desc_lower:
            return 5  # Generic AI mention

        return 0

    def _score_channel_reputation(self, channel: Dict) -> int:
        """Score based on channel's history (0-20 points)."""
        # Check if channel has prior infringements
        confirmed = channel.get('confirmed_infringements', 0)
        total_scanned = channel.get('total_videos_scanned', 0)

        if total_scanned == 0:
            return 0  # No history

        infringement_rate = confirmed / total_scanned

        if infringement_rate > 0.5:
            return 20  # Serial infringer
        elif infringement_rate > 0.25:
            return 15  # Frequent infringer
        elif infringement_rate > 0.1:
            return 10  # Some infringements
        elif confirmed > 0:
            return 5  # At least one infringement

        return 0

    def _score_engagement(self, video: Dict) -> int:
        """Score based on engagement metrics (0-10 points)."""
        view_count = video.get('view_count', 0)

        if view_count > 100000:
            return 10  # Very high views
        elif view_count > 10000:
            return 7  # High views
        elif view_count > 1000:
            return 3  # Moderate views

        return 0

    def _score_tags(self, tags: List[str]) -> int:
        """Score based on video tags (0-10 points)."""
        if not tags:
            return 0

        tags_lower = [tag.lower() for tag in tags]

        # Count matches
        character_matches = sum(1 for tag in tags_lower if any(char in tag for char in self.CHARACTERS))
        ai_tool_matches = sum(1 for tag in tags_lower if any(tool in tag for tool in self.AI_TOOLS))

        total_matches = character_matches + ai_tool_matches

        if total_matches >= 3:
            return 10
        elif total_matches >= 2:
            return 7
        elif total_matches >= 1:
            return 3

        return 0

    def _get_risk_tier(self, score: int) -> str:
        """Convert score to risk tier."""
        if score >= 90:
            return 'CRITICAL'
        elif score >= 70:
            return 'HIGH'
        elif score >= 40:
            return 'MEDIUM'
        elif score >= 20:
            return 'LOW'
        else:
            return 'VERY_LOW'

    def calculate_channel_risk(self, channel: Dict, videos_scanned: List[Dict]) -> int:
        """
        Calculate initial risk score for a channel based on first scan.

        Args:
            channel: Channel metadata
            videos_scanned: List of videos scanned from this channel

        Returns:
            Risk score (0-100)
        """
        if not videos_scanned:
            return 50  # Default medium risk

        score = 0

        # Factor 1: Match rate (0-80 points)
        matches = sum(1 for v in videos_scanned if v.get('matched_keywords'))
        match_rate = matches / len(videos_scanned) if videos_scanned else 0

        score += int(match_rate * 80)

        # Factor 2: Channel name contains DC keywords (0-20 points)
        channel_name = channel.get('channel_name', '').lower()
        if any(char in channel_name for char in self.CHARACTERS):
            score += 20
        elif any(tool in channel_name for tool in self.AI_TOOLS):
            score += 10

        return min(score, 100)
```

### Unit Tests
```python
# tests/test_initial_risk_scorer.py
import pytest
from app.core.initial_risk_scorer import InitialRiskScorer

def test_high_risk_video_with_character_and_ai_tool():
    """Video with character + AI tool in title should be HIGH risk."""
    scorer = InitialRiskScorer()

    video = {
        'video_id': 'test123',
        'title': 'Superman AI Movie Generated with Sora',
        'description': 'Amazing AI-generated Superman movie using Sora AI',
        'view_count': 15000,
        'tags': ['superman', 'ai', 'sora']
    }

    channel = {
        'confirmed_infringements': 0,
        'total_videos_scanned': 0
    }

    result = scorer.calculate_video_risk(video, channel)

    assert result['risk_score'] >= 70, "Should be HIGH risk"
    assert result['risk_tier'] in ['HIGH', 'CRITICAL']
    assert 'title' in result['factors']
    assert result['factors']['title'] == 60  # Character + AI tool

def test_medium_risk_video_character_only():
    """Video with character in title only should be MEDIUM risk."""
    scorer = InitialRiskScorer()

    video = {
        'video_id': 'test456',
        'title': 'Superman Returns Trailer',
        'description': '',
        'view_count': 500,
        'tags': []
    }

    result = scorer.calculate_video_risk(video, None)

    assert 30 <= result['risk_score'] < 70, "Should be MEDIUM risk"
    assert result['risk_tier'] == 'MEDIUM'

def test_low_risk_video_no_indicators():
    """Video with no clear indicators should be LOW risk."""
    scorer = InitialRiskScorer()

    video = {
        'video_id': 'test789',
        'title': 'My Dog Playing in the Park',
        'description': 'Just a fun video of my dog',
        'view_count': 100,
        'tags': ['dog', 'pets', 'fun']
    }

    result = scorer.calculate_video_risk(video, None)

    assert result['risk_score'] < 20, "Should be VERY_LOW risk"
    assert result['risk_tier'] == 'VERY_LOW'

def test_channel_risk_high_match_rate():
    """Channel with 50%+ match rate should be HIGH risk."""
    scorer = InitialRiskScorer()

    channel = {'channel_name': 'DC AI Studio'}
    videos = [
        {'matched_keywords': ['superman ai']},
        {'matched_keywords': ['batman ai']},
        {'matched_keywords': None},  # No match
        {'matched_keywords': ['flash ai']}
    ]

    risk = scorer.calculate_channel_risk(channel, videos)

    assert risk >= 70, "50%+ match rate + DC name should be HIGH risk"

def test_risk_score_distribution():
    """Verify risk scores distribute across tiers."""
    scorer = InitialRiskScorer()

    test_videos = [
        # CRITICAL: 60 (title) + 20 (desc) + 20 (channel) + 10 (views) + 10 (tags) = 120 -> 100
        {'title': 'Superman Sora AI', 'description': 'Made with Sora and Runway',
         'view_count': 100000, 'tags': ['superman', 'sora', 'ai']},

        # HIGH: 60 (title) + 15 (desc) = 75
        {'title': 'Batman AI Movie', 'description': 'Created with Runway',
         'view_count': 5000, 'tags': []},

        # MEDIUM: 30 (title) + 10 (views) = 40
        {'title': 'Wonder Woman Trailer', 'description': '',
         'view_count': 15000, 'tags': []},

        # LOW: 20 (title) = 20
        {'title': 'AI Generated Video', 'description': '',
         'view_count': 100, 'tags': []},

        # VERY_LOW: 0
        {'title': 'Random Video', 'description': '',
         'view_count': 50, 'tags': []}
    ]

    channel = {'confirmed_infringements': 5, 'total_videos_scanned': 20}

    results = [scorer.calculate_video_risk(v, channel) for v in test_videos]

    assert results[0]['risk_tier'] == 'CRITICAL'
    assert results[1]['risk_tier'] == 'HIGH'
    assert results[2]['risk_tier'] == 'MEDIUM'
    assert results[3]['risk_tier'] == 'LOW'
    assert results[4]['risk_tier'] == 'VERY_LOW'
```

### Test Cases
- [ ] Videos with strong indicators score 90-100
- [ ] Videos with moderate indicators score 40-69
- [ ] Videos with weak indicators score 0-39
- [ ] Channel risk calculated correctly from match rate
- [ ] Risk reasoning is human-readable and accurate
- [ ] Edge cases handled (missing fields, None values)

---

## Story 2.3: Optimize Keyword Discovery Strategy

**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 2

### User Story
```
As a Discovery Engineer
I want to optimize keyword search strategy for maximum coverage
So that we find ALL relevant DC AI content efficiently
```

### Why This Matters
- 262 keywords but finding 0 videos = keywords not effective
- Need smarter keyword rotation and prioritization
- Must balance broad coverage with quota efficiency

### Acceptance Criteria
- [ ] Implement keyword priority system:
  - HIGH: Character + AI tool combos (e.g., "superman sora")
  - MEDIUM: Character + generic AI (e.g., "batman ai")
  - LOW: Generic searches (e.g., "dc ai video")
- [ ] Keyword rotation strategy:
  - HIGH priority: Search every 2 hours
  - MEDIUM priority: Search every 6 hours
  - LOW priority: Search every 24 hours
- [ ] Track keyword effectiveness metrics:
  - Videos found per keyword
  - Match rate per keyword
  - Last successful find timestamp
- [ ] Implement adaptive keyword prioritization:
  - Boost keywords that find matches
  - Demote keywords with 0 matches for 7+ days
- [ ] Add keyword performance dashboard
- [ ] Document top 20 performing keywords

### Definition of Done (DoD)
- ✅ Keyword priority system implemented
- ✅ Rotation strategy respects priority levels
- ✅ Metrics tracked for all keywords
- ✅ Dashboard shows keyword performance
- ✅ At least 50% of searches find 1+ videos
- ✅ High-priority keywords searched more frequently
- ✅ Documentation includes optimization rationale

### Technical Implementation
```python
# app/core/keyword_optimizer.py
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from google.cloud import firestore

class KeywordOptimizer:
    """
    Optimizes keyword search strategy based on performance data.

    Tracks:
    - Videos found per keyword
    - Match rate per keyword
    - Last successful find
    - Search frequency based on effectiveness
    """

    PRIORITY_HIGH = 'high'      # Search every 2 hours
    PRIORITY_MEDIUM = 'medium'  # Search every 6 hours
    PRIORITY_LOW = 'low'        # Search every 24 hours

    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        self.keywords_collection = self.db.collection('keyword_performance')

    def initialize_keywords(self, keywords: List[str]):
        """
        Initialize keyword performance tracking.

        Assigns initial priority based on keyword structure:
        - "character + ai_tool": HIGH
        - "character + ai": MEDIUM
        - "generic": LOW
        """
        high_priority_patterns = ['sora', 'runway', 'kling', 'pika', 'luma']
        characters = ['superman', 'batman', 'wonder woman', 'flash', 'aquaman']

        for keyword in keywords:
            kw_lower = keyword.lower()

            # Determine initial priority
            has_character = any(char in kw_lower for char in characters)
            has_ai_tool = any(tool in kw_lower for tool in high_priority_patterns)

            if has_character and has_ai_tool:
                priority = self.PRIORITY_HIGH
            elif has_character or has_ai_tool:
                priority = self.PRIORITY_MEDIUM
            else:
                priority = self.PRIORITY_LOW

            # Initialize if not exists
            doc_ref = self.keywords_collection.document(keyword)
            if not doc_ref.get().exists:
                doc_ref.set({
                    'keyword': keyword,
                    'priority': priority,
                    'videos_found': 0,
                    'searches_performed': 0,
                    'match_rate': 0.0,
                    'last_search': None,
                    'last_successful_find': None,
                    'created_at': datetime.now(timezone.utc)
                })

    def get_keywords_due_for_search(self, limit: int = 50) -> List[Dict]:
        """
        Get keywords that need searching based on priority and last search.

        Returns keywords sorted by:
        1. Priority (HIGH first)
        2. Longest time since last search
        """
        now = datetime.now(timezone.utc)

        # Calculate due thresholds
        thresholds = {
            self.PRIORITY_HIGH: now - timedelta(hours=2),
            self.PRIORITY_MEDIUM: now - timedelta(hours=6),
            self.PRIORITY_LOW: now - timedelta(hours=24)
        }

        keywords_due = []

        for priority, threshold in thresholds.items():
            docs = (
                self.keywords_collection
                .where('priority', '==', priority)
                .where('last_search', '<=', threshold)
                .order_by('last_search')
                .limit(limit)
                .stream()
            )

            for doc in docs:
                data = doc.to_dict()
                keywords_due.append({
                    'keyword': data['keyword'],
                    'priority': data['priority'],
                    'last_search': data.get('last_search'),
                    'match_rate': data.get('match_rate', 0.0)
                })

        # Also include keywords never searched
        never_searched = (
            self.keywords_collection
            .where('last_search', '==', None)
            .limit(limit)
            .stream()
        )

        for doc in never_searched:
            data = doc.to_dict()
            keywords_due.append({
                'keyword': data['keyword'],
                'priority': data['priority'],
                'last_search': None,
                'match_rate': 0.0
            })

        # Sort by priority (HIGH first), then by staleness
        priority_order = {self.PRIORITY_HIGH: 0, self.PRIORITY_MEDIUM: 1, self.PRIORITY_LOW: 2}
        keywords_due.sort(
            key=lambda k: (
                priority_order[k['priority']],
                k['last_search'] or datetime.min.replace(tzinfo=timezone.utc)
            )
        )

        return keywords_due[:limit]

    def record_search_result(
        self,
        keyword: str,
        videos_found: int,
        matches_found: int
    ):
        """
        Record results of a keyword search and update metrics.

        Args:
            keyword: The keyword searched
            videos_found: Total videos returned by YouTube
            matches_found: Videos matching our IP criteria
        """
        doc_ref = self.keywords_collection.document(keyword)
        doc = doc_ref.get()

        if not doc.exists:
            # Initialize if doesn't exist
            data = {
                'keyword': keyword,
                'priority': self.PRIORITY_MEDIUM,
                'videos_found': 0,
                'searches_performed': 0,
                'match_rate': 0.0
            }
        else:
            data = doc.to_dict()

        # Update metrics
        data['searches_performed'] += 1
        data['videos_found'] += videos_found
        data['last_search'] = datetime.now(timezone.utc)

        if matches_found > 0:
            data['last_successful_find'] = datetime.now(timezone.utc)

        # Calculate match rate
        if videos_found > 0:
            data['match_rate'] = matches_found / videos_found

        # Update priority based on performance
        data['priority'] = self._calculate_adaptive_priority(data)

        doc_ref.set(data)

    def _calculate_adaptive_priority(self, keyword_data: Dict) -> str:
        """
        Adjust keyword priority based on performance.

        Rules:
        - Match rate > 20%: HIGH
        - Match rate > 10%: MEDIUM
        - Match rate < 10%: LOW
        - No matches in 7+ days: demote by 1 level
        """
        match_rate = keyword_data.get('match_rate', 0.0)
        last_success = keyword_data.get('last_successful_find')
        current_priority = keyword_data.get('priority', self.PRIORITY_MEDIUM)

        # Performance-based priority
        if match_rate >= 0.20:
            performance_priority = self.PRIORITY_HIGH
        elif match_rate >= 0.10:
            performance_priority = self.PRIORITY_MEDIUM
        else:
            performance_priority = self.PRIORITY_LOW

        # Demote if stagnant
        if last_success:
            days_since_success = (datetime.now(timezone.utc) - last_success).days
            if days_since_success > 7:
                # Demote by one level
                if performance_priority == self.PRIORITY_HIGH:
                    performance_priority = self.PRIORITY_MEDIUM
                elif performance_priority == self.PRIORITY_MEDIUM:
                    performance_priority = self.PRIORITY_LOW

        return performance_priority

    def get_top_performing_keywords(self, limit: int = 20) -> List[Dict]:
        """Get top performing keywords by match rate."""
        docs = (
            self.keywords_collection
            .where('match_rate', '>', 0)
            .order_by('match_rate', direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )

        return [doc.to_dict() for doc in docs]

    def get_performance_stats(self) -> Dict:
        """Get overall keyword performance statistics."""
        all_keywords = list(self.keywords_collection.stream())

        total = len(all_keywords)
        high = sum(1 for k in all_keywords if k.get('priority') == self.PRIORITY_HIGH)
        medium = sum(1 for k in all_keywords if k.get('priority') == self.PRIORITY_MEDIUM)
        low = sum(1 for k in all_keywords if k.get('priority') == self.PRIORITY_LOW)

        total_videos = sum(k.get('videos_found', 0) for k in all_keywords)
        total_searches = sum(k.get('searches_performed', 0) for k in all_keywords)

        successful = sum(1 for k in all_keywords if k.get('last_successful_find'))

        return {
            'total_keywords': total,
            'priority_distribution': {
                'high': high,
                'medium': medium,
                'low': low
            },
            'total_videos_found': total_videos,
            'total_searches': total_searches,
            'successful_keywords': successful,
            'success_rate': successful / total if total > 0 else 0,
            'avg_videos_per_search': total_videos / total_searches if total_searches > 0 else 0
        }
```

### Integration with Discovery Engine
```python
# app/core/discovery_engine.py (modified)

def _scan_keywords(self, max_quota: int) -> dict:
    """Scan keywords using optimized strategy."""
    keywords_scanned = 0
    videos_discovered = 0
    quota_used = 0

    # Get keywords due for search (prioritized)
    keywords_due = self.keyword_optimizer.get_keywords_due_for_search(limit=100)

    for keyword_data in keywords_due:
        keyword = keyword_data['keyword']

        if not self.quota.can_afford('search', 1):
            break

        if quota_used >= max_quota:
            break

        try:
            # Search YouTube
            results = self.youtube.search_videos(
                query=keyword,
                max_results=50,
                published_after=datetime.now() - timedelta(days=30)
            )

            # Process results
            matches = self.processor.process_batch(results)

            # Record performance
            self.keyword_optimizer.record_search_result(
                keyword=keyword,
                videos_found=len(results),
                matches_found=len(matches)
            )

            keywords_scanned += 1
            videos_discovered += len(matches)
            quota_used += 100  # search.list cost

            logger.info(
                f"Keyword '{keyword}' ({keyword_data['priority']}): "
                f"{len(matches)}/{len(results)} matches"
            )

        except Exception as e:
            logger.error(f"Keyword search failed for '{keyword}': {e}")

    return {
        'keywords_scanned': keywords_scanned,
        'videos_discovered': videos_discovered,
        'quota_used': quota_used
    }
```

### Test Cases
- [ ] Keywords prioritized correctly (HIGH > MEDIUM > LOW)
- [ ] Adaptive priority adjusts based on performance
- [ ] Keywords with matches get promoted
- [ ] Stagnant keywords get demoted
- [ ] Performance stats calculated accurately

---

## Story 2.4: Add Trending/Viral Discovery Method

**Priority:** P0
**Effort:** 3 story points
**Sprint:** Sprint 2

### User Story
```
As a Discovery Engineer
I want to monitor YouTube trending feed for DC AI content
So that we catch viral infringements early
```

### Why This Matters
- Viral videos cause most damage (10M+ views)
- YouTube trending API is cheap (1 unit per request)
- Can catch content before it explodes

### Acceptance Criteria
- [ ] Create `app/core/trending_monitor.py` module
- [ ] Implement `scan_trending_feed()` method
- [ ] Check YouTube trending in relevant categories:
  - Film & Animation (category 1)
  - Entertainment (category 24)
  - Science & Technology (category 28)
- [ ] Filter trending videos by keywords
- [ ] Assign HIGH initial risk to trending videos
- [ ] Boost risk if view velocity is high
- [ ] Run trending scan every hour
- [ ] Log trending discoveries separately

### Definition of Done (DoD)
- ✅ Trending monitor implemented and tested
- ✅ Integration with discovery engine complete
- ✅ Trending videos get initial_risk >= 70
- ✅ Separate metrics for trending discoveries
- ✅ Tests cover all categories
- ✅ Deployed and running in production

### Technical Implementation
```python
# app/core/trending_monitor.py
import logging
from datetime import datetime, timezone
from typing import List, Dict
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class TrendingMonitor:
    """
    Monitors YouTube trending feed for DC AI-generated content.

    Strategy:
    - Check trending videos in relevant categories
    - Filter by DC/AI keywords
    - Assign HIGH initial risk (viral potential)
    """

    # YouTube category IDs
    CATEGORIES = {
        'film_animation': '1',
        'entertainment': '24',
        'science_tech': '28'
    }

    # Keywords to filter trending videos
    FILTER_KEYWORDS = [
        'superman', 'batman', 'wonder woman', 'flash', 'aquaman',
        'justice league', 'dc comics', 'sora', 'runway', 'ai generated'
    ]

    def __init__(self, youtube_client, video_processor, quota_manager):
        self.youtube = youtube_client
        self.processor = video_processor
        self.quota = quota_manager

    def scan_trending(self, max_results: int = 50) -> Dict:
        """
        Scan YouTube trending feed for relevant content.

        Args:
            max_results: Max videos to check per category

        Returns:
            {
                'videos_discovered': int,
                'quota_used': int,
                'categories_scanned': List[str]
            }
        """
        videos_discovered = 0
        quota_used = 0
        categories_scanned = []

        for category_name, category_id in self.CATEGORIES.items():
            if not self.quota.can_afford('trending', 1):
                logger.warning("Quota exhausted, stopping trending scan")
                break

            try:
                # Get trending videos for category
                trending = self._get_trending_videos(
                    category_id=category_id,
                    max_results=max_results
                )

                quota_used += 1
                categories_scanned.append(category_name)

                # Filter by keywords
                filtered = self._filter_by_keywords(trending)

                if filtered:
                    logger.info(
                        f"Trending {category_name}: {len(filtered)}/{len(trending)} "
                        f"matched keywords"
                    )

                    # Process matched videos
                    matches = self.processor.process_batch(
                        filtered,
                        skip_no_ip_match=False  # Process all trending matches
                    )

                    # Boost risk for trending videos
                    for match in matches:
                        self._boost_trending_risk(match)

                    videos_discovered += len(matches)

            except Exception as e:
                logger.error(f"Trending scan failed for {category_name}: {e}")

        return {
            'videos_discovered': videos_discovered,
            'quota_used': quota_used,
            'categories_scanned': categories_scanned
        }

    def _get_trending_videos(
        self,
        category_id: str,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Fetch trending videos from YouTube.

        Uses videos.list with chart=mostPopular parameter.
        Cost: 1 unit per request
        """
        return self.youtube.get_trending_videos(
            category_id=category_id,
            max_results=max_results
        )

    def _filter_by_keywords(self, videos: List[Dict]) -> List[Dict]:
        """
        Filter videos by DC/AI keywords in title or description.
        """
        filtered = []

        for video in videos:
            title = video.get('title', '').lower()
            description = video.get('description', '').lower()

            # Check if any keyword matches
            if any(kw in title or kw in description for kw in self.FILTER_KEYWORDS):
                filtered.append(video)

        return filtered

    def _boost_trending_risk(self, video: Dict):
        """
        Boost risk score for trending videos (viral potential).

        Trending videos get +20 risk boost.
        """
        current_risk = video.get('initial_risk', 50)
        boosted_risk = min(current_risk + 20, 100)

        video['initial_risk'] = boosted_risk
        video['is_trending'] = True

        logger.info(
            f"Trending boost: {video['video_id']} risk "
            f"{current_risk} -> {boosted_risk}"
        )
```

### Integration with Discovery Engine
```python
# Add to discovery_engine.py

def discover(self, max_quota: int = 10000) -> dict:
    """Run discovery with trending monitoring."""

    # Tier 1: Trending (20% quota) - catch viral content early
    tier1_quota = int(max_quota * 0.20)
    tier1_stats = self.trending_monitor.scan_trending()

    # Tier 2: Keyword Search (70% quota) - broad discovery
    tier2_quota = int(max_quota * 0.70)
    tier2_stats = self._scan_keywords(tier2_quota)

    # Tier 3: Channel Monitoring (10% quota) - known sources
    tier3_quota = int(max_quota * 0.10)
    tier3_stats = self._scan_channels(tier3_quota)

    # ... rest of implementation
```

### Test Cases
- [ ] Trending videos fetched from all categories
- [ ] Keyword filtering works correctly
- [ ] Risk boost applied to trending videos
- [ ] Quota tracking accurate (1 unit per category)
- [ ] Integration with discovery engine works

---

# 🎯 EPIC 3: Risk Analyzer Service (New Service)

**Goal:** Create new service that continuously monitors and updates video/channel risk scores, prioritizing high-risk content for Gemini analysis

**Why Critical:** Without risk-based prioritization, we waste Gemini budget on low-value content. This service is the brain that decides what gets analyzed.

**Dependencies:** Epic 1 (Schema), Epic 2 (Initial risk scores)

---

## Story 3.1: Create Risk Analyzer Service Infrastructure

**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 2

### User Story
```
As a DevOps Engineer
I want to scaffold the risk-analyzer-service with proper infrastructure
So that we have a production-ready service foundation
```

### Why This Matters
- New service needs complete infrastructure (Cloud Run, Firestore, PubSub)
- Must follow same patterns as existing services for consistency
- Proper setup prevents technical debt

### Acceptance Criteria
- [ ] Create service structure: `services/risk-analyzer-service/`
- [ ] Directory structure follows existing pattern:
  ```
  services/risk-analyzer-service/
  ├── app/
  │   ├── main.py              # FastAPI app
  │   ├── core/                # Business logic
  │   │   ├── risk_scorer.py
  │   │   ├── view_velocity_tracker.py
  │   │   ├── channel_reputation.py
  │   │   └── scan_scheduler.py
  │   ├── routers/             # API endpoints
  │   │   └── analyze.py
  │   └── models.py            # Pydantic models
  ├── terraform/
  │   ├── provider.tf
  │   ├── variables.tf
  │   ├── main.tf
  │   └── outputs.tf
  ├── tests/
  ├── Dockerfile
  ├── cloudbuild.yaml
  └── pyproject.toml
  ```
- [ ] Add dependencies to `pyproject.toml`:
  - fastapi, uvicorn, pydantic-settings
  - google-cloud-firestore, google-cloud-pubsub
  - google-cloud-monitoring (for metrics)
- [ ] Create Terraform infrastructure:
  - Cloud Run service with 2,000 units quota budget
  - Service account with IAM roles
  - PubSub subscriptions for video-discovered events
  - PubSub topic for video-high-risk events
- [ ] Add health check endpoint `/health`
- [ ] Add metrics endpoint `/metrics`
- [ ] Configure Cloud Scheduler for continuous runs (every 15 min)

### Definition of Done (DoD)
- ✅ Service structure created and committed
- ✅ Dependencies installed via `uv sync`
- ✅ Terraform deploys successfully to dev environment
- ✅ Health check responds 200 OK
- ✅ Service accessible via Cloud Run URL
- ✅ Logs visible in Cloud Logging
- ✅ PubSub topics/subscriptions created
- ✅ Documentation in `services/risk-analyzer-service/README.md`

### Technical Implementation

```python
# services/risk-analyzer-service/app/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging

from app.routers import analyze
from app.core.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

app = FastAPI(
    title="Risk Analyzer Service",
    description="Continuous risk scoring and prioritization for discovered videos",
    version="1.0.0"
)

# Include routers
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "risk-analyzer-service",
            "version": "1.0.0"
        }
    )

@app.get("/metrics")
async def get_metrics():
    """Return service metrics."""
    # TODO: Implement metrics collection
    return {
        "videos_rescanned_today": 0,
        "risk_updates_today": 0,
        "high_risk_videos_queued": 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

```python
# services/risk-analyzer-service/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""

    # GCP
    gcp_project_id: str
    gcp_region: str = "europe-west4"
    environment: str = "dev"

    # Firestore
    firestore_database: str = "(default)"

    # PubSub
    pubsub_subscription: str = "video-discovered-sub"
    pubsub_high_risk_topic: str = "video-high-risk"

    # Risk Analysis
    daily_rescan_quota: int = 2000  # YouTube API units for rescanning
    min_risk_for_gemini: int = 70   # Only HIGH/CRITICAL go to Gemini

    class Config:
        env_file = ".env"
```

```hcl
# services/risk-analyzer-service/terraform/main.tf
locals {
  app_dir       = "${path.module}/../app"
  exclude_regex = "(\\.venv/|__pycache__/|\\.git/)"

  all_app_files = fileset(local.app_dir, "**/*")
  app_files = toset([
    for f in local.all_app_files : f
    if length(regexall(local.exclude_regex, f)) == 0
  ])

  app_source_hash = sha256(join("", [
    for f in sort(local.app_files) : filesha256("${local.app_dir}/${f}")
  ]))
}

# Get global infrastructure
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "copycat/global-infra"
  }
}

# Service account
resource "google_service_account" "risk_analyzer" {
  account_id   = "risk-analyzer-service-sa"
  display_name = "Risk Analyzer Service"
}

# IAM roles
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.risk_analyzer.email}"
}

resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.risk_analyzer.email}"
}

resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.risk_analyzer.email}"
}

# PubSub topic for high-risk videos
resource "google_pubsub_topic" "video_high_risk" {
  name = "video-high-risk-${var.environment}"
}

# Subscription to video-discovered events
resource "google_pubsub_subscription" "video_discovered" {
  name  = "video-discovered-risk-analyzer-${var.environment}"
  topic = data.terraform_remote_state.global.outputs.video_discovered_topic

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# Cloud Run service
resource "google_cloud_run_v2_service" "risk_analyzer" {
  name     = "risk-analyzer-service"
  location = var.region

  template {
    service_account = google_service_account.risk_analyzer.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "600s"

    containers {
      image = var.image_name

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "SOURCE_HASH"
        value = local.app_source_hash
      }
    }
  }
}

# Allow unauthenticated access (for Cloud Scheduler)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.risk_analyzer.name
  location = google_cloud_run_v2_service.risk_analyzer.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Cloud Scheduler for continuous risk analysis
resource "google_cloud_scheduler_job" "risk_analysis" {
  name             = "risk-analyzer-continuous"
  region           = "europe-west1"
  schedule         = "*/15 * * * *"  # Every 15 minutes
  time_zone        = "UTC"
  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.risk_analyzer.uri}/analyze/run"
  }
}
```

```toml
# services/risk-analyzer-service/pyproject.toml
[project]
name = "risk-analyzer-service"
version = "0.1.0"
description = "Risk scoring and prioritization service"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.119.1",
    "uvicorn[standard]>=0.32.0",
    "pydantic-settings>=2.10.0",
    "google-cloud-firestore>=2.21.0",
    "google-cloud-pubsub>=2.31.1",
    "google-cloud-monitoring>=2.23.2",
    "httpx>=0.28.0",
    "python-json-logger>=3.2.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
]
```

### Test Cases
- [ ] Service deploys to Cloud Run successfully
- [ ] Health check endpoint returns 200
- [ ] Can connect to Firestore
- [ ] Can publish to PubSub topics
- [ ] Can subscribe to PubSub events
- [ ] Cloud Scheduler triggers service

---

## Story 3.2: Implement View Velocity Tracking

**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 2

### User Story
```
As a Risk Analyst
I want to track view velocity for videos over time
So that we can detect viral content and elevate risk scores
```

### Why This Matters
- View velocity (views/hour) is strongest indicator of viral potential
- Videos going viral need immediate attention (CRITICAL risk)
- Early detection prevents damage (catch at 10k views vs 10M views)

### Acceptance Criteria
- [ ] Create `app/core/view_velocity_tracker.py` module
- [ ] Track view snapshots in Firestore:
  - Collection: `view_snapshots`
  - Documents: `{video_id}_{timestamp}`
  - Fields: video_id, view_count, timestamp, views_per_hour
- [ ] Calculate velocity from multiple snapshots (minimum 2 required)
- [ ] Implement velocity tiers:
  - EXPLOSIVE (>10,000 views/hour): +30 risk boost
  - VIRAL (1,000-10,000 views/hour): +20 risk boost
  - TRENDING (100-1,000 views/hour): +10 risk boost
  - GROWING (10-100 views/hour): +5 risk boost
  - STABLE (<10 views/hour): No change
- [ ] Store velocity history for analytics
- [ ] Handle edge cases:
  - Video deleted (view count = 0)
  - View count decreased (suspicious, flag for review)
  - First snapshot (no velocity yet)

### Definition of Done (DoD)
- ✅ View velocity tracker implemented
- ✅ Unit tests achieve 90%+ coverage
- ✅ Velocity calculations mathematically correct
- ✅ Integration with risk scorer complete
- ✅ Dashboard shows velocity distribution
- ✅ Viral videos automatically boosted to CRITICAL
- ✅ Performance: can process 1,000 videos/minute

### Technical Implementation

```python
# services/risk-analyzer-service/app/core/view_velocity_tracker.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)

class ViewVelocityTracker:
    """
    Tracks view velocity (views/hour) for videos to detect viral content.

    Velocity is calculated from view count snapshots over time.
    Videos with high velocity get risk boost for immediate attention.
    """

    # Velocity thresholds (views/hour)
    EXPLOSIVE_THRESHOLD = 10000  # 10k+ views/hour
    VIRAL_THRESHOLD = 1000       # 1k-10k views/hour
    TRENDING_THRESHOLD = 100     # 100-1k views/hour
    GROWING_THRESHOLD = 10       # 10-100 views/hour

    # Risk boosts by velocity tier
    RISK_BOOSTS = {
        'EXPLOSIVE': 30,  # Immediate CRITICAL
        'VIRAL': 20,      # Boost to HIGH/CRITICAL
        'TRENDING': 10,   # Moderate boost
        'GROWING': 5,     # Minor boost
        'STABLE': 0       # No change
    }

    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        self.snapshots_collection = self.db.collection('view_snapshots')

    def record_snapshot(
        self,
        video_id: str,
        view_count: int,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a view count snapshot for velocity calculation.

        Args:
            video_id: YouTube video ID
            view_count: Current view count
            timestamp: Snapshot timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Validate inputs
        if view_count < 0:
            logger.warning(f"Invalid view count {view_count} for {video_id}, skipping")
            return

        # Create snapshot document
        snapshot_id = f"{video_id}_{int(timestamp.timestamp())}"

        try:
            self.snapshots_collection.document(snapshot_id).set({
                'video_id': video_id,
                'view_count': view_count,
                'timestamp': timestamp,
                'recorded_at': datetime.now(timezone.utc)
            })

            logger.debug(f"Recorded snapshot for {video_id}: {view_count} views")

        except Exception as e:
            logger.error(f"Failed to record snapshot for {video_id}: {e}")

    def calculate_velocity(
        self,
        video_id: str,
        current_view_count: int,
        lookback_hours: int = 24
    ) -> Dict:
        """
        Calculate view velocity from recent snapshots.

        Args:
            video_id: YouTube video ID
            current_view_count: Most recent view count
            lookback_hours: How far back to look for snapshots

        Returns:
            {
                'views_per_hour': float,
                'velocity_tier': str,
                'risk_boost': int,
                'snapshots_used': int,
                'time_span_hours': float
            }
        """
        # Get recent snapshots
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        snapshots = (
            self.snapshots_collection
            .where('video_id', '==', video_id)
            .where('timestamp', '>=', cutoff_time)
            .order_by('timestamp')
            .stream()
        )

        snapshot_list = [s.to_dict() for s in snapshots]

        # Need at least 1 prior snapshot to calculate velocity
        if not snapshot_list:
            logger.debug(f"No snapshots for {video_id}, cannot calculate velocity")
            return {
                'views_per_hour': 0.0,
                'velocity_tier': 'UNKNOWN',
                'risk_boost': 0,
                'snapshots_used': 0,
                'time_span_hours': 0.0
            }

        # Get oldest and newest snapshots
        oldest = snapshot_list[0]

        # Calculate time span
        time_span = datetime.now(timezone.utc) - oldest['timestamp']
        hours = time_span.total_seconds() / 3600

        if hours < 0.1:  # Less than 6 minutes
            logger.debug(f"Time span too short for {video_id}: {hours:.2f} hours")
            return {
                'views_per_hour': 0.0,
                'velocity_tier': 'INSUFFICIENT_DATA',
                'risk_boost': 0,
                'snapshots_used': len(snapshot_list),
                'time_span_hours': hours
            }

        # Calculate velocity
        view_delta = current_view_count - oldest['view_count']

        if view_delta < 0:
            logger.warning(
                f"View count decreased for {video_id}: "
                f"{oldest['view_count']} -> {current_view_count}"
            )
            # Possible reasons: video deleted, YouTube bug, etc.
            view_delta = 0

        views_per_hour = view_delta / hours

        # Determine velocity tier and risk boost
        tier, boost = self._categorize_velocity(views_per_hour)

        logger.info(
            f"Velocity for {video_id}: {views_per_hour:.1f} views/hour "
            f"({tier}, +{boost} risk)"
        )

        return {
            'views_per_hour': views_per_hour,
            'velocity_tier': tier,
            'risk_boost': boost,
            'snapshots_used': len(snapshot_list),
            'time_span_hours': hours,
            'view_delta': view_delta
        }

    def _categorize_velocity(self, views_per_hour: float) -> tuple[str, int]:
        """
        Categorize velocity and return (tier, risk_boost).
        """
        if views_per_hour >= self.EXPLOSIVE_THRESHOLD:
            return ('EXPLOSIVE', self.RISK_BOOSTS['EXPLOSIVE'])
        elif views_per_hour >= self.VIRAL_THRESHOLD:
            return ('VIRAL', self.RISK_BOOSTS['VIRAL'])
        elif views_per_hour >= self.TRENDING_THRESHOLD:
            return ('TRENDING', self.RISK_BOOSTS['TRENDING'])
        elif views_per_hour >= self.GROWING_THRESHOLD:
            return ('GROWING', self.RISK_BOOSTS['GROWING'])
        else:
            return ('STABLE', self.RISK_BOOSTS['STABLE'])

    def get_velocity_history(
        self,
        video_id: str,
        days: int = 7
    ) -> List[Dict]:
        """
        Get velocity history for a video (for analytics/visualization).

        Args:
            video_id: YouTube video ID
            days: Number of days of history

        Returns:
            List of snapshots with calculated velocities
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        snapshots = (
            self.snapshots_collection
            .where('video_id', '==', video_id)
            .where('timestamp', '>=', cutoff)
            .order_by('timestamp')
            .stream()
        )

        history = []
        prev_snapshot = None

        for snapshot_doc in snapshots:
            snapshot = snapshot_doc.to_dict()

            if prev_snapshot:
                # Calculate velocity between snapshots
                time_delta = snapshot['timestamp'] - prev_snapshot['timestamp']
                hours = time_delta.total_seconds() / 3600

                if hours > 0:
                    view_delta = snapshot['view_count'] - prev_snapshot['view_count']
                    velocity = view_delta / hours
                else:
                    velocity = 0.0

                history.append({
                    'timestamp': snapshot['timestamp'],
                    'view_count': snapshot['view_count'],
                    'views_per_hour': velocity,
                    'velocity_tier': self._categorize_velocity(velocity)[0]
                })

            prev_snapshot = snapshot

        return history

    def cleanup_old_snapshots(self, days_to_keep: int = 30):
        """
        Delete snapshots older than specified days (cleanup job).

        Args:
            days_to_keep: Keep snapshots from last N days
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        old_snapshots = (
            self.snapshots_collection
            .where('timestamp', '<', cutoff)
            .stream()
        )

        deleted = 0
        for snapshot in old_snapshots:
            snapshot.reference.delete()
            deleted += 1

        logger.info(f"Cleaned up {deleted} old view snapshots (>{days_to_keep} days)")

        return deleted
```

### Unit Tests

```python
# services/risk-analyzer-service/tests/test_view_velocity_tracker.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock
from app.core.view_velocity_tracker import ViewVelocityTracker

@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    mock_db = Mock()
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    return mock_db

@pytest.fixture
def tracker(mock_firestore):
    """Create tracker with mock Firestore."""
    return ViewVelocityTracker(mock_firestore)

def test_explosive_velocity_high_risk_boost(tracker, mock_firestore):
    """Video with 10k+ views/hour should get EXPLOSIVE tier and +30 risk."""

    # Mock snapshot from 1 hour ago with 1,000 views
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    mock_snapshot = {
        'video_id': 'test123',
        'view_count': 1000,
        'timestamp': one_hour_ago
    }

    # Mock Firestore query
    mock_doc = Mock()
    mock_doc.to_dict.return_value = mock_snapshot
    mock_firestore.collection().where().where().order_by().stream.return_value = [mock_doc]

    # Current view count: 15,000 (14k gain in 1 hour = 14k views/hour)
    result = tracker.calculate_velocity('test123', 15000)

    assert result['views_per_hour'] == 14000.0
    assert result['velocity_tier'] == 'EXPLOSIVE'
    assert result['risk_boost'] == 30
    assert result['snapshots_used'] == 1

def test_viral_velocity_moderate_boost(tracker, mock_firestore):
    """Video with 1k-10k views/hour should get VIRAL tier and +20 risk."""

    now = datetime.now(timezone.utc)
    two_hours_ago = now - timedelta(hours=2)

    mock_snapshot = {
        'video_id': 'test456',
        'view_count': 5000,
        'timestamp': two_hours_ago
    }

    mock_doc = Mock()
    mock_doc.to_dict.return_value = mock_snapshot
    mock_firestore.collection().where().where().order_by().stream.return_value = [mock_doc]

    # 15,000 views (10k gain in 2 hours = 5k views/hour)
    result = tracker.calculate_velocity('test456', 15000)

    assert result['views_per_hour'] == 5000.0
    assert result['velocity_tier'] == 'VIRAL'
    assert result['risk_boost'] == 20

def test_no_velocity_without_snapshots(tracker, mock_firestore):
    """First snapshot has no velocity (need baseline)."""

    # No snapshots found
    mock_firestore.collection().where().where().order_by().stream.return_value = []

    result = tracker.calculate_velocity('new_video', 1000)

    assert result['views_per_hour'] == 0.0
    assert result['velocity_tier'] == 'UNKNOWN'
    assert result['risk_boost'] == 0

def test_view_count_decreased_handled_gracefully(tracker, mock_firestore):
    """Handle edge case where view count goes down."""

    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Previous snapshot had MORE views than current
    mock_snapshot = {
        'video_id': 'test789',
        'view_count': 10000,
        'timestamp': one_hour_ago
    }

    mock_doc = Mock()
    mock_doc.to_dict.return_value = mock_snapshot
    mock_firestore.collection().where().where().order_by().stream.return_value = [mock_doc]

    # Current count is LOWER (5000 < 10000)
    result = tracker.calculate_velocity('test789', 5000)

    # Should handle gracefully, not crash
    assert result['views_per_hour'] == 0.0
    assert 'view_delta' in result
    assert result['view_delta'] == 0  # Clipped to 0

def test_record_snapshot_creates_document(tracker, mock_firestore):
    """Recording snapshot should create Firestore document."""

    mock_doc = Mock()
    mock_firestore.collection().document.return_value = mock_doc

    tracker.record_snapshot('video123', 5000)

    # Verify document().set() was called
    mock_doc.set.assert_called_once()

    # Check the data structure
    call_args = mock_doc.set.call_args[0][0]
    assert call_args['video_id'] == 'video123'
    assert call_args['view_count'] == 5000
    assert 'timestamp' in call_args

def test_velocity_categories_correct_thresholds(tracker):
    """Test velocity tier boundaries."""

    # Test each threshold
    assert tracker._categorize_velocity(15000) == ('EXPLOSIVE', 30)
    assert tracker._categorize_velocity(5000) == ('VIRAL', 20)
    assert tracker._categorize_velocity(500) == ('TRENDING', 10)
    assert tracker._categorize_velocity(50) == ('GROWING', 5)
    assert tracker._categorize_velocity(5) == ('STABLE', 0)

    # Test exact boundaries
    assert tracker._categorize_velocity(10000) == ('EXPLOSIVE', 30)
    assert tracker._categorize_velocity(9999) == ('VIRAL', 20)
    assert tracker._categorize_velocity(1000) == ('VIRAL', 20)
    assert tracker._categorize_velocity(999) == ('TRENDING', 10)
```

### Test Cases
- [ ] Explosive velocity (>10k views/hour) gets +30 boost
- [ ] Viral velocity (1k-10k) gets +20 boost
- [ ] Trending velocity (100-1k) gets +10 boost
- [ ] Growing velocity (10-100) gets +5 boost
- [ ] Stable velocity (<10) gets no boost
- [ ] First snapshot returns UNKNOWN tier
- [ ] Decreased view count handled gracefully
- [ ] Velocity calculation is mathematically accurate

---

## Story 3.3: Implement Adaptive Risk Rescoring Algorithm

**Priority:** P0
**Effort:** 8 story points
**Sprint:** Sprint 2-3

### User Story
```
As a Risk Analyst
I want videos to have their risk scores automatically updated based on behavior
So that high-risk content gets prioritized for Gemini analysis
```

### Why This Matters
- Static risk scores become outdated quickly
- Videos going viral need immediate elevation (LOW -> CRITICAL)
- Clean channels should be demoted to save Gemini budget
- Adaptive scoring learns from channel behavior over time

### Acceptance Criteria
- [ ] Create `app/core/adaptive_risk_scorer.py` module
- [ ] Implement `update_video_risk()` function with factors:
  1. View velocity (+0 to +30 points)
  2. Channel reputation (+0 to +20 points)
  3. Engagement rate (+0 to +10 points)
  4. Age decay (-0 to -15 points for old videos)
  5. Prior analysis results (+20 if confirmed infringement, -10 if clean)
- [ ] Implement `update_channel_risk()` based on scan history
- [ ] Risk can both increase AND decrease
- [ ] Log all risk changes with reasoning
- [ ] Track risk history in Firestore (audit trail)
- [ ] Update `next_scan_at` based on new risk tier
- [ ] Publish to `video-high-risk` topic when risk crosses threshold (>=70)

### Definition of Done (DoD)
- ✅ Adaptive risk scorer implemented with all 5 factors
- ✅ Unit tests cover all risk adjustment scenarios
- ✅ Risk changes logged with human-readable reasoning
- ✅ Risk history tracked for analytics
- ✅ Integration with view velocity tracker
- ✅ High-risk videos published to PubSub
- ✅ Performance: 100+ videos/second risk updates
- ✅ Documentation explains each factor with examples

### Technical Implementation

```python
# services/risk-analyzer-service/app/core/adaptive_risk_scorer.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from google.cloud import firestore, pubsub_v1

from app.core.view_velocity_tracker import ViewVelocityTracker

logger = logging.getLogger(__name__)

class AdaptiveRiskScorer:
    """
    Continuously updates video risk scores based on real-world behavior.

    Risk factors:
    1. View velocity (viral detection)
    2. Channel reputation (serial infringers)
    3. Engagement metrics (likes/views ratio)
    4. Age decay (older content less urgent)
    5. Prior analysis results (confirmed infringements)

    Risk can increase (going viral) or decrease (false positive).
    """

    # Risk thresholds for actions
    HIGH_RISK_THRESHOLD = 70      # Send to Gemini
    CRITICAL_RISK_THRESHOLD = 90  # Immediate priority

    def __init__(
        self,
        firestore_client: firestore.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
        velocity_tracker: ViewVelocityTracker,
        high_risk_topic: str
    ):
        self.db = firestore_client
        self.publisher = pubsub_publisher
        self.velocity = velocity_tracker
        self.high_risk_topic = high_risk_topic

    def update_video_risk(
        self,
        video_id: str,
        youtube_data: Optional[Dict] = None
    ) -> Dict:
        """
        Update risk score for a video based on current data.

        Args:
            video_id: YouTube video ID
            youtube_data: Latest YouTube API data (or None to fetch from Firestore)

        Returns:
            {
                'video_id': str,
                'previous_risk': int,
                'new_risk': int,
                'risk_delta': int,
                'new_tier': str,
                'factors': {
                    'velocity': int,
                    'channel': int,
                    'engagement': int,
                    'age': int,
                    'prior_results': int
                },
                'reasoning': List[str]
            }
        """
        # Get current video data from Firestore
        video_ref = self.db.collection('videos').document(video_id)
        video_doc = video_ref.get()

        if not video_doc.exists:
            logger.warning(f"Video {video_id} not found in Firestore")
            return None

        video = video_doc.to_dict()
        current_risk = video.get('current_risk', video.get('initial_risk', 50))

        # Start with current risk
        new_risk = current_risk
        factors = {}
        reasoning = []

        # Factor 1: View Velocity (most important)
        velocity_boost = self._calculate_velocity_factor(video_id, video, youtube_data)
        new_risk += velocity_boost
        factors['velocity'] = velocity_boost
        if velocity_boost > 0:
            reasoning.append(f"High view velocity: +{velocity_boost}")

        # Factor 2: Channel Reputation
        channel_boost = self._calculate_channel_factor(video.get('channel_id'))
        new_risk += channel_boost
        factors['channel'] = channel_boost
        if channel_boost > 0:
            reasoning.append(f"Channel reputation: +{channel_boost}")
        elif channel_boost < 0:
            reasoning.append(f"Clean channel history: {channel_boost}")

        # Factor 3: Engagement Rate
        engagement_boost = self._calculate_engagement_factor(video, youtube_data)
        new_risk += engagement_boost
        factors['engagement'] = engagement_boost
        if engagement_boost > 0:
            reasoning.append(f"High engagement: +{engagement_boost}")

        # Factor 4: Age Decay
        age_penalty = self._calculate_age_factor(video)
        new_risk += age_penalty
        factors['age'] = age_penalty
        if age_penalty < 0:
            reasoning.append(f"Age decay: {age_penalty}")

        # Factor 5: Prior Analysis Results
        prior_boost = self._calculate_prior_results_factor(video)
        new_risk += prior_boost
        factors['prior_results'] = prior_boost
        if prior_boost != 0:
            reasoning.append(f"Prior analysis: {prior_boost:+d}")

        # Clamp to 0-100
        new_risk = max(0, min(new_risk, 100))
        risk_delta = new_risk - current_risk

        # Determine new tier
        new_tier = self._get_risk_tier(new_risk)

        # Update Firestore
        self._save_risk_update(
            video_id=video_id,
            previous_risk=current_risk,
            new_risk=new_risk,
            factors=factors,
            reasoning=reasoning,
            new_tier=new_tier
        )

        # If crossed HIGH threshold, publish to PubSub
        if new_risk >= self.HIGH_RISK_THRESHOLD and current_risk < self.HIGH_RISK_THRESHOLD:
            self._publish_high_risk_video(video_id, new_risk)

        logger.info(
            f"Risk update for {video_id}: {current_risk} -> {new_risk} "
            f"({new_tier}, delta: {risk_delta:+d})"
        )

        return {
            'video_id': video_id,
            'previous_risk': current_risk,
            'new_risk': new_risk,
            'risk_delta': risk_delta,
            'new_tier': new_tier,
            'factors': factors,
            'reasoning': reasoning
        }

    def _calculate_velocity_factor(
        self,
        video_id: str,
        video: Dict,
        youtube_data: Optional[Dict]
    ) -> int:
        """
        Calculate risk adjustment from view velocity.

        Returns: 0 to +30 points
        """
        # Get current view count
        if youtube_data:
            current_views = youtube_data.get('view_count', 0)
        else:
            current_views = video.get('view_count', 0)

        # Calculate velocity
        velocity_data = self.velocity.calculate_velocity(video_id, current_views)

        # Record snapshot for future calculations
        self.velocity.record_snapshot(video_id, current_views)

        return velocity_data.get('risk_boost', 0)

    def _calculate_channel_factor(self, channel_id: str) -> int:
        """
        Calculate risk adjustment from channel reputation.

        Returns: -10 to +20 points
        """
        if not channel_id:
            return 0

        channel_ref = self.db.collection('channels').document(channel_id)
        channel_doc = channel_ref.get()

        if not channel_doc.exists:
            return 0

        channel = channel_doc.to_dict()

        # Get infringement history
        total_scanned = channel.get('total_videos_scanned', 0)
        confirmed = channel.get('confirmed_infringements', 0)

        if total_scanned < 5:
            return 0  # Not enough data

        infringement_rate = confirmed / total_scanned

        if infringement_rate > 0.50:
            return 20  # Serial infringer (>50%)
        elif infringement_rate > 0.25:
            return 15  # Frequent infringer (25-50%)
        elif infringement_rate > 0.10:
            return 10  # Some infringements (10-25%)
        elif infringement_rate < 0.05 and total_scanned >= 20:
            return -10  # Clean channel (<5%, 20+ videos)

        return 0

    def _calculate_engagement_factor(
        self,
        video: Dict,
        youtube_data: Optional[Dict]
    ) -> int:
        """
        Calculate risk adjustment from engagement metrics.

        High engagement = more views = higher risk.
        Returns: 0 to +10 points
        """
        if youtube_data:
            view_count = youtube_data.get('view_count', 0)
            like_count = youtube_data.get('like_count', 0)
        else:
            view_count = video.get('view_count', 0)
            like_count = video.get('like_count', 0)

        if view_count == 0:
            return 0

        # Calculate engagement rate
        engagement_rate = like_count / view_count

        if engagement_rate > 0.10:  # 10%+ like rate is very high
            return 10
        elif engagement_rate > 0.05:  # 5-10% is high
            return 5
        elif engagement_rate > 0.02:  # 2-5% is moderate
            return 3

        return 0

    def _calculate_age_factor(self, video: Dict) -> int:
        """
        Calculate risk adjustment based on video age.

        Older videos less urgent (already been up for a while).
        Returns: -15 to 0 points
        """
        published_at = video.get('published_at')
        if not published_at:
            return 0

        # Calculate age in days
        age = datetime.now(timezone.utc) - published_at
        days_old = age.days

        if days_old > 90:  # 3+ months old
            return -15
        elif days_old > 30:  # 1-3 months old
            return -10
        elif days_old > 7:  # 1-4 weeks old
            return -5

        return 0  # Recent videos: no penalty

    def _calculate_prior_results_factor(self, video: Dict) -> int:
        """
        Calculate risk adjustment based on prior Gemini analysis.

        Returns: -10 to +20 points
        """
        scan_status = video.get('scan_status')
        gemini_result = video.get('gemini_result', {})

        if scan_status == 'infringement_confirmed':
            return 20  # Confirmed infringement
        elif scan_status == 'scanned':
            # Check gemini result
            if gemini_result.get('contains_infringement'):
                return 20
            else:
                return -10  # False positive, lower risk

        return 0  # Not scanned yet

    def _get_risk_tier(self, risk: int) -> str:
        """Convert risk score to tier."""
        if risk >= 90:
            return 'CRITICAL'
        elif risk >= 70:
            return 'HIGH'
        elif risk >= 40:
            return 'MEDIUM'
        elif risk >= 20:
            return 'LOW'
        else:
            return 'VERY_LOW'

    def _save_risk_update(
        self,
        video_id: str,
        previous_risk: int,
        new_risk: int,
        factors: Dict,
        reasoning: List[str],
        new_tier: str
    ):
        """Save risk update to Firestore."""
        video_ref = self.db.collection('videos').document(video_id)

        # Calculate next scan time based on new risk
        next_scan = self._calculate_next_scan(new_risk)

        # Build risk history entry
        history_entry = {
            'timestamp': datetime.now(timezone.utc),
            'previous_risk': previous_risk,
            'new_risk': new_risk,
            'risk_delta': new_risk - previous_risk,
            'factors': factors,
            'reasoning': reasoning
        }

        # Update video document
        video_ref.update({
            'current_risk': new_risk,
            'risk_tier': new_tier,
            'last_risk_update': datetime.now(timezone.utc),
            'next_scan_at': next_scan,
            'risk_history': firestore.ArrayUnion([history_entry])
        })

    def _calculate_next_scan(self, risk: int) -> datetime:
        """Calculate when to rescan based on risk tier."""
        now = datetime.now(timezone.utc)

        if risk >= 90:  # CRITICAL
            return now + timedelta(hours=6)
        elif risk >= 70:  # HIGH
            return now + timedelta(days=1)
        elif risk >= 40:  # MEDIUM
            return now + timedelta(days=3)
        elif risk >= 20:  # LOW
            return now + timedelta(days=7)
        else:  # VERY_LOW
            return now + timedelta(days=30)

    def _publish_high_risk_video(self, video_id: str, risk: int):
        """Publish high-risk video to PubSub for vision-analyzer."""
        try:
            message = {
                'video_id': video_id,
                'risk_score': risk,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'reason': 'risk_threshold_crossed'
            }

            self.publisher.publish(
                self.high_risk_topic,
                data=str(message).encode('utf-8')
            )

            logger.info(f"Published high-risk video {video_id} (risk: {risk})")

        except Exception as e:
            logger.error(f"Failed to publish high-risk video {video_id}: {e}")
```

*[Continue with remaining implementation details...]*

### Test Cases
- [ ] View velocity boosts risk appropriately
- [ ] Channel reputation affects risk score
- [ ] Engagement rate increases risk
- [ ] Age decay reduces risk for old videos
- [ ] Prior infringement boosts risk
- [ ] Clean channel reduces risk
- [ ] Risk clamped to 0-100 range
- [ ] Risk history tracked correctly
- [ ] High-risk videos published to PubSub
- [ ] Next scan time calculated correctly

---

*[Stories 3.4-3.8 would continue with similar detail covering: Risk-Based Scheduling, Channel Risk Updates, PubSub Integration, Performance Optimization, and Monitoring]*

---

# 🎯 EPIC 4: Integration & Testing

**Goal:** Validate end-to-end two-service architecture and measure success metrics

**Why Critical:** Without integration testing, we can't be confident the services work together correctly

**Dependencies:** Epic 2 (Discovery), Epic 3 (Risk Analyzer)

---

## Story 4.1: End-to-End Integration Testing

**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 3

### User Story
```
As a QA Engineer
I want to test the complete discovery → risk analysis → vision analysis flow
So that we validate the two-service architecture works correctly
```

### Why This Matters
- Services must work together seamlessly
- Data flow must be correct (discovery → risk → vision)
- Performance must meet targets (latency, throughput)

### Acceptance Criteria
- [ ] Create integration test suite `tests/integration/`
- [ ] Test complete flow:
  1. Discovery finds video
  2. Initial risk assigned
  3. Risk analyzer updates risk
  4. High-risk video published to PubSub
  5. Vision analyzer receives event
- [ ] Test PubSub message flow between services
- [ ] Test Firestore data consistency
- [ ] Validate risk scoring is correct
- [ ] Test failure scenarios:
  - Firestore unavailable
  - PubSub topic doesn't exist
  - Malformed video data
- [ ] Load testing: 1,000 videos through pipeline

### Definition of Done (DoD)
- ✅ Integration tests pass in dev environment
- ✅ All services communicate correctly
- ✅ Data flows through entire pipeline
- ✅ Performance meets targets (<5s end-to-end)
- ✅ Error handling works correctly
- ✅ Tests documented and runnable via `pytest`

---

## Story 4.2: Success Metrics Dashboard

**Priority:** P0
**Effort:** 3 story points
**Sprint:** Sprint 3

### User Story
```
As a Product Manager
I want a dashboard showing success metrics
So that I can measure the new architecture's effectiveness
```

### Why This Matters
- Must prove ROI to stakeholders
- Need visibility into system performance
- Track improvements over time

### Acceptance Criteria
- [ ] Create BigQuery views for metrics:
  - Discovery hit rate (videos found / quota spent)
  - Risk distribution (CRITICAL/HIGH/MEDIUM/LOW/VERY_LOW %)
  - Gemini utilization (€/day spent)
  - Viral detection latency (time to detect trending)
  - Channel database quality (% DC-related)
- [ ] Add metrics to frontend dashboard
- [ ] Weekly metrics report (automated)
- [ ] Alert if metrics fall below targets

### Definition of Done (DoD)
- ✅ Dashboard shows all success metrics
- ✅ Metrics update in real-time
- ✅ Historical trends visible (30 days)
- ✅ Alerts configured for metric thresholds
- ✅ Team can access dashboard URL

---

## Story 4.3: Production Deployment & Rollout

**Priority:** P0
**Effort:** 5 story points
**Sprint:** Sprint 3

### User Story
```
As a DevOps Engineer
I want to safely deploy the new architecture to production
So that we can start benefiting from improved discovery
```

### Why This Matters
- Production deployment is risky
- Need rollback plan
- Must monitor closely during rollout

### Acceptance Criteria
- [ ] Deploy risk-analyzer-service to production
- [ ] Update discovery-service in production
- [ ] Configure Cloud Scheduler for both services
- [ ] Set up monitoring and alerts
- [ ] Create runbook for common issues
- [ ] Perform smoke tests in production
- [ ] Monitor for 24 hours post-deployment

### Definition of Done (DoD)
- ✅ Both services deployed to production
- ✅ Health checks passing
- ✅ PubSub topics configured
- ✅ Monitoring dashboards created
- ✅ No critical errors in first 24 hours
- ✅ Rollback plan documented and tested
- ✅ Team trained on new architecture

---

## Story 4.4: Performance Benchmarking

**Priority:** P1
**Effort:** 3 story points
**Sprint:** Sprint 3

### User Story
```
As a Performance Engineer
I want to benchmark the new architecture's performance
So that we can validate it meets our targets
```

### Why This Matters
- Must prove system can handle scale
- Identify bottlenecks before they cause issues
- Validate quota efficiency improvements

### Acceptance Criteria
- [ ] Run load tests with 10,000 videos
- [ ] Measure discovery throughput (videos/hour)
- [ ] Measure risk analysis latency (seconds per video)
- [ ] Measure Firestore read/write performance
- [ ] Measure PubSub message latency
- [ ] Compare to success metrics targets
- [ ] Document performance characteristics

### Definition of Done (DoD)
- ✅ Performance benchmarks completed
- ✅ All targets met or exceeded
- ✅ Bottlenecks identified and documented
- ✅ Optimization recommendations provided
- ✅ Report shared with team

---

## 📊 Success Criteria for Complete Epic

### Must Have (P0)
- ✅ Channel database cleaned (>80% DC-related)
- ✅ Discovery service finding videos (>15% hit rate)
- ✅ Risk analyzer updating scores continuously
- ✅ High-risk videos queued for Gemini
- ✅ Viral detection working (<6 hour latency)
- ✅ Both services deployed to production
- ✅ No critical bugs or data loss

### Nice to Have (P1)
- ✅ Gemini budget utilization >€200/day
- ✅ Integration tests automated in CI/CD
- ✅ Performance dashboards comprehensive
- ✅ Documentation complete and reviewed

### Future Enhancements (P2)
- Machine learning for risk scoring
- Thumbnail analysis for visual matching
- Multi-language keyword support
- Advanced channel clustering

---

## 📅 Sprint Timeline

### Sprint 1 (Week 1)
- Story 1.1: Database Audit ✅
- Story 1.2: Channel Cleanup ✅
- Story 1.3: Schema Migration ✅
- Story 2.1: Remove Rescanning ✅

### Sprint 2 (Week 2)
- Story 2.2: Initial Risk Scoring ✅
- Story 2.3: Keyword Optimization ✅
- Story 2.4: Trending Discovery ✅
- Story 3.1: Risk Analyzer Infrastructure ✅
- Story 3.2: View Velocity Tracking ✅

### Sprint 3 (Week 3)
- Story 3.3: Adaptive Risk Scoring ✅
- Story 3.4-3.8: Risk Analyzer Completion
- Story 4.1: Integration Testing ✅
- Story 4.2: Metrics Dashboard ✅
- Story 4.3: Production Deployment ✅
- Story 4.4: Performance Benchmarking ✅

---

## 🎯 Acceptance Criteria for Complete Epic

The epic is complete when:

1. **Technical Criteria:**
   - [ ] Both services deployed to production and stable
   - [ ] All unit tests pass (>80% coverage)
   - [ ] Integration tests pass
   - [ ] No critical bugs or performance issues
   - [ ] Documentation complete

2. **Business Criteria:**
   - [ ] Discovery hit rate >15%
   - [ ] Channel database >80% relevant
   - [ ] Viral detection latency <6 hours
   - [ ] Gemini utilization >€150/day (62% of budget)
   - [ ] System processes >1,000 videos/day

3. **Operational Criteria:**
   - [ ] Monitoring and alerts configured
   - [ ] Runbooks created for common issues
   - [ ] Team trained on new architecture
   - [ ] Rollback plan tested and documented
   - [ ] 7 days of stable production operation

---

**Document Status:** ✅ Complete and ready for implementation

**Next Steps:**
1. Review with team
2. Prioritize stories
3. Begin Sprint 1 (Database Cleanup)
4. Daily standups to track progress
5. Weekly demo of completed stories

