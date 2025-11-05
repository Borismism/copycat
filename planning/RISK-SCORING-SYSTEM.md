# Comprehensive Risk Scoring System (0-100)

## Overview

Two-tier risk system that combines **Channel Risk** + **Video Risk** to produce a **Final Scan Priority Score (0-100)**.

Videos are scanned in descending order (100 → 0) until Gemini budget is exhausted.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCAN PRIORITY SCORE                         │
│                          (0-100)                                │
│                                                                 │
│  = (Channel Risk × 0.40) + (Video Risk × 0.60)                │
│                                                                 │
│    ↑ 40% weight           ↑ 60% weight                         │
│    Channel matters,       Video specifics matter more          │
│    but video is king                                            │
└─────────────────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
    ┌────┴────┐                    ┌────┴────┐
    │ CHANNEL │                    │  VIDEO  │
    │  RISK   │                    │  RISK   │
    │ (0-100) │                    │ (0-100) │
    └─────────┘                    └─────────┘
```

---

## Part 1: Channel Risk Score (0-100)

**Purpose:** Identify serial infringers and high-risk channels

### Factors (5 total)

#### 1. Infringement History (0-40 points) 🔴 CRITICAL
**Weight:** 40% of channel score

**Logic:** Past behavior predicts future behavior

**Calculation:**
```python
def calculate_infringement_history_score(channel: dict) -> int:
    """
    Infringement history = strongest predictor of future infringement.

    Scoring:
    - 0 infringements: 0 points (unknown/clean)
    - 1-2 infringements: 10 points (suspicious)
    - 3-5 infringements: 20 points (frequent infringer)
    - 6-10 infringements: 30 points (serial infringer)
    - 11+ infringements: 40 points (MAXIMUM RISK)

    Infringement rate also matters:
    - <10% rate: -5 points (some mistakes, not systematic)
    - 10-25% rate: +0 points (concerning)
    - 25-50% rate: +5 points (very concerning)
    - >50% rate: +10 points (systematic infringer)
    """
    infringement_count = channel.get("infringing_videos_count", 0)
    total_videos = channel.get("total_videos_found", 1)
    infringement_rate = infringement_count / total_videos if total_videos > 0 else 0

    # Base score from count
    if infringement_count == 0:
        base = 0
    elif infringement_count <= 2:
        base = 10
    elif infringement_count <= 5:
        base = 20
    elif infringement_count <= 10:
        base = 30
    else:
        base = 40

    # Rate multiplier
    if infringement_rate < 0.10:
        rate_adj = -5
    elif infringement_rate < 0.25:
        rate_adj = 0
    elif infringement_rate < 0.50:
        rate_adj = 5
    else:
        rate_adj = 10

    return min(40, max(0, base + rate_adj))
```

#### 2. Total Infringing Views (0-25 points) 🔴 IMPACT
**Weight:** 25% of channel score

**Logic:** High-view infringements = massive damage

**Calculation:**
```python
def calculate_infringing_views_score(channel: dict) -> int:
    """
    Total views on infringing content = scale of damage.

    Scoring:
    - 0 views: 0 points
    - 1k-10k views: 5 points
    - 10k-100k views: 10 points
    - 100k-1M views: 15 points
    - 1M-10M views: 20 points
    - 10M+ views: 25 points (MAXIMUM - mega viral)
    """
    total_views = channel.get("total_infringing_views", 0)

    if total_views == 0:
        return 0
    elif total_views < 10_000:
        return 5
    elif total_views < 100_000:
        return 10
    elif total_views < 1_000_000:
        return 15
    elif total_views < 10_000_000:
        return 20
    else:
        return 25
```

#### 3. Channel Activity (0-20 points) 🟡 VELOCITY
**Weight:** 20% of channel score

**Logic:** Active channels producing new content = ongoing threat

**Calculation:**
```python
def calculate_channel_activity_score(channel: dict) -> int:
    """
    How recently has this channel posted?

    Scoring:
    - Posted in last 7 days: 20 points (ACTIVE - high priority!)
    - Posted in last 30 days: 15 points (recent)
    - Posted in last 90 days: 10 points (semi-active)
    - Posted in last 180 days: 5 points (dormant)
    - No recent posts (>180 days): 0 points (inactive)

    Bonus for posting frequency:
    - >10 videos/month: +5 points (prolific)
    """
    last_upload = channel.get("last_upload_date")
    if not last_upload:
        return 0

    days_since_upload = (datetime.now(timezone.utc) - last_upload).days

    if days_since_upload <= 7:
        base = 20
    elif days_since_upload <= 30:
        base = 15
    elif days_since_upload <= 90:
        base = 10
    elif days_since_upload <= 180:
        base = 5
    else:
        base = 0

    # Bonus for prolific channels
    videos_per_month = channel.get("videos_per_month", 0)
    bonus = 5 if videos_per_month > 10 else 0

    return min(20, base + bonus)
```

#### 4. Channel Size (0-10 points) 🟢 REACH
**Weight:** 10% of channel score

**Logic:** Large channels = wider reach if infringing

**Calculation:**
```python
def calculate_channel_size_score(channel: dict) -> int:
    """
    Subscriber count = potential reach of infringements.

    Scoring:
    - <1k subs: 2 points
    - 1k-10k subs: 4 points
    - 10k-100k subs: 6 points
    - 100k-1M subs: 8 points
    - 1M+ subs: 10 points (MAXIMUM - huge reach)
    """
    subscribers = channel.get("subscriber_count", 0)

    if subscribers < 1_000:
        return 2
    elif subscribers < 10_000:
        return 4
    elif subscribers < 100_000:
        return 6
    elif subscribers < 1_000_000:
        return 8
    else:
        return 10
```

#### 5. Recency of Last Infringement (0-5 points) ⚡ URGENCY
**Weight:** 5% of channel score

**Logic:** Recent infringement = likely to do it again soon

**Calculation:**
```python
def calculate_last_infringement_recency_score(channel: dict) -> int:
    """
    How recently did we find an infringement from this channel?

    Scoring:
    - Infringement in last 7 days: 5 points (VERY HOT!)
    - Infringement in last 30 days: 3 points (recent)
    - Infringement in last 90 days: 1 point (moderately recent)
    - Older than 90 days: 0 points
    """
    last_infringement_date = channel.get("last_infringement_date")
    if not last_infringement_date:
        return 0

    days_since = (datetime.now(timezone.utc) - last_infringement_date).days

    if days_since <= 7:
        return 5
    elif days_since <= 30:
        return 3
    elif days_since <= 90:
        return 1
    else:
        return 0
```

### Channel Risk Total: MAX 100 points
```
= Infringement History (40)
+ Total Infringing Views (25)
+ Channel Activity (20)
+ Channel Size (10)
+ Last Infringement Recency (5)
```

---

## Part 2: Video Risk Score (0-100)

**Purpose:** Identify high-priority individual videos for scanning

### Factors (7 total)

#### 1. IP Character Match Quality (0-25 points) 🔴 RELEVANCE
**Weight:** 25% of video score

**Logic:** Strong keyword matches = likely infringement

**Calculation:**
```python
def calculate_ip_match_score(video: dict) -> int:
    """
    How strongly does this video match our IP targets?

    Scoring based on matched_ips list:
    - 0 matches: 0 points (shouldn't happen, but safe)
    - 1 exact character match: 15 points
    - 2+ exact character matches: 20 points
    - HIGH priority IP (Superman, Batman): +5 bonus

    Title/description contains AI terms:
    - "AI generated", "Sora", "Runway", etc: +5 points
    """
    matched_ips = video.get("matched_ips", [])
    title = video.get("title", "").lower()
    description = video.get("description", "").lower()

    if len(matched_ips) == 0:
        base = 0
    elif len(matched_ips) == 1:
        base = 15
    else:
        base = 20

    # High priority IP bonus
    high_priority_chars = ["superman", "batman", "wonder woman", "justice league"]
    has_high_priority = any(ip.lower() in str(matched_ips).lower() for ip in high_priority_chars)
    priority_bonus = 5 if has_high_priority else 0

    # AI generation keywords
    ai_keywords = ["ai generated", "sora", "runway", "kling", "pika", "ai movie", "ai video"]
    has_ai_keyword = any(kw in title or kw in description for kw in ai_keywords)
    ai_bonus = 5 if has_ai_keyword else 0

    return min(25, base + priority_bonus + ai_bonus)
```

#### 2. View Count (0-20 points) 🔴 IMPACT
**Weight:** 20% of video score

**Logic:** High views = high damage

**Calculation:**
```python
def calculate_view_count_score(video: dict) -> int:
    """
    More views = more damage if infringing.

    Scoring:
    - 0-1k views: 2 points
    - 1k-10k views: 5 points
    - 10k-100k views: 10 points
    - 100k-1M views: 15 points
    - 1M-10M views: 18 points
    - 10M+ views: 20 points (VIRAL - maximum priority!)
    """
    views = video.get("view_count", 0)

    if views < 1_000:
        return 2
    elif views < 10_000:
        return 5
    elif views < 100_000:
        return 10
    elif views < 1_000_000:
        return 15
    elif views < 10_000_000:
        return 18
    else:
        return 20
```

#### 3. View Velocity (0-20 points) 🟡 VIRAL DETECTION
**Weight:** 20% of video score

**Logic:** Going viral RIGHT NOW = scan IMMEDIATELY

**Calculation:**
```python
def calculate_view_velocity_score(video: dict) -> int:
    """
    Views per hour = viral detection.

    Scoring:
    - >10k views/hour: 20 points (MEGA VIRAL!)
    - >1k views/hour: 15 points (very viral)
    - >100 views/hour: 10 points (viral)
    - >10 views/hour: 5 points (trending)
    - <10 views/hour: 0 points (normal)
    """
    velocity = video.get("view_velocity", 0)

    if velocity > 10_000:
        return 20
    elif velocity > 1_000:
        return 15
    elif velocity > 100:
        return 10
    elif velocity > 10:
        return 5
    else:
        return 0
```

#### 4. Video Age vs Views (0-15 points) 🟢 SURVIVOR BIAS
**Weight:** 15% of video score

**Logic:** Old + high views = slipped through moderation = HIGH PRIORITY

**Calculation:**
```python
def calculate_age_vs_views_score(video: dict) -> int:
    """
    Old videos with high views = SURVIVORS = likely infringements that slipped through.

    Scoring:
    - >6 months + >100k views: 15 points (SURVIVOR!)
    - >3 months + >50k views: 10 points
    - >1 month + >10k views: 5 points
    - Recent (<1 month): based on views only
    - Old + low views: 0 points (not urgent)
    """
    published_at = video.get("published_at")
    view_count = video.get("view_count", 0)

    if not published_at:
        return 0

    age_days = (datetime.now(timezone.utc) - published_at).days

    # Recent videos: no survivor bonus (use view count only)
    if age_days <= 30:
        return 0

    # OLD + HIGH VIEWS = SURVIVOR
    if age_days > 180:  # >6 months
        if view_count > 100_000:
            return 15
        elif view_count > 10_000:
            return 5
        else:
            return 0
    elif age_days > 90:  # >3 months
        if view_count > 50_000:
            return 10
        elif view_count > 5_000:
            return 3
        else:
            return 0
    else:  # 1-3 months
        if view_count > 10_000:
            return 5
        else:
            return 0
```

#### 5. Engagement Rate (0-10 points) 🟢 INTERACTION
**Weight:** 10% of video score

**Logic:** High engagement = being watched/shared = higher impact

**Calculation:**
```python
def calculate_engagement_score(video: dict) -> int:
    """
    Likes + comments relative to views.

    Scoring:
    - >5% engagement: 10 points (highly engaging)
    - >2% engagement: 5 points (engaging)
    - <2% engagement: 0 points (normal)
    """
    views = video.get("view_count", 0)
    if views == 0:
        return 0

    likes = video.get("like_count", 0)
    comments = video.get("comment_count", 0)

    engagement_rate = (likes + comments) / views

    if engagement_rate > 0.05:
        return 10
    elif engagement_rate > 0.02:
        return 5
    else:
        return 0
```

#### 6. Video Duration (0-5 points) 🟢 CONTENT TYPE
**Weight:** 5% of video score

**Logic:** Longer videos = more substantial AI-generated content

**Calculation:**
```python
def calculate_duration_score(video: dict) -> int:
    """
    Duration = content substantiality.

    Scoring:
    - >10 min: 5 points (full movie - high priority)
    - 2-10 min: 3 points (substantial clip)
    - 1-2 min: 1 point (short clip)
    - <1 min: 0 points (very short - likely shorts)
    """
    duration_seconds = video.get("duration_seconds", 0)

    if duration_seconds > 600:  # >10 min
        return 5
    elif duration_seconds > 120:  # 2-10 min
        return 3
    elif duration_seconds > 60:  # 1-2 min
        return 1
    else:
        return 0
```

#### 7. Scan History (0-5 points) ⚡ FRESHNESS
**Weight:** 5% of video score

**Logic:** Never scanned = SUSPICIOUS, scanned clean many times = safe

**Calculation:**
```python
def calculate_scan_history_score(video: dict) -> int:
    """
    Discovery freshness - inversely related to scan count.

    Scoring:
    - Never scanned (NEW): 5 points (INVESTIGATE!)
    - Scanned 1x, clean: 3 points (still suspicious)
    - Scanned 2x, clean: 1 point (probably fine)
    - Scanned 3+x, clean: 0 points (confirmed clean)
    - Any scans with INFRINGEMENT: 5 points (confirmed bad!)
    """
    scan_count = video.get("scan_count", 0)
    has_infringement = video.get("vision_analysis", {}).get("contains_infringement", False)

    # If infringement found, always max priority
    if has_infringement:
        return 5

    # Based on clean scan count
    if scan_count == 0:
        return 5  # NEW = SUSPICIOUS
    elif scan_count == 1:
        return 3
    elif scan_count == 2:
        return 1
    else:
        return 0  # 3+ clean scans = probably safe
```

### Video Risk Total: MAX 100 points
```
= IP Match Quality (25)
+ View Count (20)
+ View Velocity (20)
+ Age vs Views (15)
+ Engagement (10)
+ Duration (5)
+ Scan History (5)
```

---

## Part 3: Final Scan Priority Score

### Formula

```python
def calculate_final_scan_priority(channel_risk: int, video_risk: int) -> int:
    """
    Combine channel and video risk into final scan priority.

    Weights:
    - Channel Risk: 40%
    - Video Risk: 60%

    Video matters more than channel, but channel provides important context.
    """
    final_score = int((channel_risk * 0.40) + (video_risk * 0.60))
    return max(0, min(100, final_score))
```

### Priority Tiers

**CRITICAL (90-100):** Scan within 6 hours
- Example: Known infringer channel + mega-viral video

**HIGH (70-89):** Scan within 24 hours
- Example: Frequent infringer channel + high-view video

**MEDIUM (50-69):** Scan within 3 days
- Example: Unknown channel + decent match quality

**LOW (30-49):** Scan within 7 days
- Example: Clean channel + weak match

**VERY_LOW (0-29):** Scan within 30 days (or skip entirely)
- Example: Clean channel + old low-view video

---

## Scanning Order

```python
# Pseudo-code for vision-analyzer scanning logic

daily_budget = 260.0  # USD
spent = 0.0

# Get ALL videos sorted by priority
videos = get_all_unscanned_videos_sorted_by_priority_desc()

for video in videos:
    if spent >= daily_budget:
        logger.info(f"Budget exhausted: ${spent:.2f}")
        break

    # Skip if priority too low (configurable threshold)
    if video.scan_priority < MINIMUM_SCAN_PRIORITY:  # e.g., 30
        logger.info(f"Skipping {video.id}: priority {video.scan_priority} < {MINIMUM_SCAN_PRIORITY}")
        continue

    # Estimate cost
    estimated_cost = estimate_scan_cost(video)

    if spent + estimated_cost > daily_budget:
        logger.info(f"Skipping {video.id}: would exceed budget")
        continue

    # SCAN
    result = analyze_with_gemini(video)
    spent += result.actual_cost

    logger.info(f"Scanned {video.id}: priority={video.scan_priority}, cost=${result.actual_cost:.4f}, total=${spent:.2f}")
```

---

## Implementation Checklist

### Phase 1: Channel Risk Calculator
- [ ] Create `channel_risk_calculator.py`
- [ ] Implement 5 factor calculations
- [ ] Add `calculate_channel_risk()` method (returns 0-100)
- [ ] Store `channel_risk` in Firestore channels collection
- [ ] Update channel risk when new infringements found

### Phase 2: Video Risk Calculator
- [ ] Update `risk_rescorer.py`
- [ ] Implement 7 factor calculations
- [ ] Replace current 6-factor model with new 7-factor model
- [ ] Store `video_risk` in Firestore videos collection

### Phase 3: Final Priority Calculator
- [ ] Create `scan_priority_calculator.py`
- [ ] Implement `calculate_final_scan_priority(channel_risk, video_risk)`
- [ ] Store `scan_priority` in Firestore videos collection
- [ ] Update priority when channel or video risk changes

### Phase 4: Vision-Analyzer Integration
- [ ] Update vision-analyzer worker to fetch videos by `scan_priority DESC`
- [ ] Add `MINIMUM_SCAN_PRIORITY` threshold (e.g., 30)
- [ ] Skip LOW/VERY_LOW videos
- [ ] Scan until budget exhausted

### Phase 5: Testing
- [ ] Test with known infringer channel (Nomika Ai)
- [ ] Verify high-priority videos scanned first
- [ ] Verify low-priority videos skipped
- [ ] Verify budget exhaustion works correctly

---

## Example Calculations

### Example 1: Serial Infringer + Viral Video

**Channel: "AI Movies Daily"**
- Infringement history: 12 videos = 40 points
- Total infringing views: 15M = 25 points
- Activity: Posted yesterday = 20 points
- Size: 50k subs = 6 points
- Last infringement: 3 days ago = 5 points
- **Channel Risk: 96/100** 🔴

**Video: "Superman AI Movie Full 2 Hours"**
- IP match: Superman (high priority) + AI keyword = 25 points
- View count: 2M views = 18 points
- Velocity: 5k views/hour = 15 points
- Age: 2 days old + high views = 0 points (recent)
- Engagement: 3% rate = 5 points
- Duration: 120 minutes = 5 points
- Scan history: Never scanned = 5 points
- **Video Risk: 73/100** 🔴

**Final Priority: (96 × 0.4) + (73 × 0.6) = 38.4 + 43.8 = 82.2 → 82/100**
**Tier: HIGH** → Scan within 24 hours

---

### Example 2: Clean Channel + Old Video

**Channel: "Movie Reviews"**
- Infringement history: 0 videos = 0 points
- Total infringing views: 0 = 0 points
- Activity: Posted last week = 20 points
- Size: 100k subs = 6 points
- Last infringement: Never = 0 points
- **Channel Risk: 26/100** 🟢

**Video: "Batman Toy Unboxing"**
- IP match: Batman match = 15 points
- View count: 500 views = 2 points
- Velocity: 0.1 views/hour = 0 points
- Age: 3 months + low views = 0 points
- Engagement: 1% rate = 0 points
- Duration: 5 minutes = 3 points
- Scan history: Never scanned = 5 points
- **Video Risk: 25/100** 🟢

**Final Priority: (26 × 0.4) + (25 × 0.6) = 10.4 + 15 = 25.4 → 25/100**
**Tier: VERY_LOW** → Skip or scan in 30 days

---

## Benefits of This System

1. **Precision:** Combines channel reputation with video specifics
2. **Efficiency:** Skips 70%+ of low-value videos
3. **Viral Detection:** Catches trending content fast (view velocity)
4. **Learning:** Adapts based on past infringements (feedback loop)
5. **Budget Optimization:** Scans highest-value targets first
6. **Transparency:** 100-point scale is intuitive and debuggable
7. **Flexibility:** Easy to tune weights and thresholds
