# Viral Keyword Detection System - Implementation Plan

## Overview

**Goal**: Create a self-learning keyword discovery system that adapts based on what's actually getting views and being infringed.

**Strategy**: Cold start with seed keywords → Discover videos → Find viral infringements → Extract new keywords using Gemini → Validate against IP config → Add to keyword pool → Repeat

## Problem Statement

Currently, keyword discovery relies on manually curated keywords in IP configs. This misses:
- **Trending slang/terminology** (e.g., "Sora Batman movie", "AI Justice League 2025")
- **Platform-specific phrases** (e.g., "Batman Runway gen 3", "Superman Kling AI")
- **Multi-tool combinations** (e.g., "Runway + Pika Superman", "Sora Flash chase")
- **Viral phrase patterns** (e.g., what phrases get 1M+ views?)

## Solution Architecture

```
┌─────────────────┐
│  Seed Keywords  │ (from IP configs: "Superman AI", "Batman Sora")
│  in IP Configs  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Discovery Tier 3│ (keyword_tracker.py: scan YouTube with seed keywords)
│ Keyword Scanner │
└────────┬────────┘
         │ discovers videos
         v
┌─────────────────┐
│  Risk Analyzer  │ (filters to high-risk videos only)
│   + Gemini Scan │
└────────┬────────┘
         │ finds infringements
         v
┌─────────────────┐
│ Viral Filter    │ (>10k views + confirmed infringement)
│                 │
└────────┬────────┘
         │ triggers keyword extraction
         v
┌─────────────────────────────────┐
│  NEW: Viral Keyword Extractor   │
│  (Gemini analysis of metadata)  │
└────────┬────────────────────────┘
         │ extracts candidate keywords
         v
┌─────────────────────────────────┐
│  NEW: Keyword Validator         │
│  (check against IP config)      │
└────────┬────────────────────────┘
         │ validates keywords
         v
┌─────────────────────────────────┐
│  Keyword Tracker                │
│  (add to Firestore)             │
└─────────────────────────────────┘
         │
         └─> LOOP BACK to Discovery
```

## Component Breakdown

### 1. Viral Keyword Extractor (NEW)
**File**: `services/discovery-service/app/core/viral_keyword_extractor.py`

**Purpose**: Analyze viral infringing videos to extract trending keywords

**Inputs**:
- Video metadata (title, description, tags, channel_title)
- Gemini infringement result (confirmed infringement = true)
- Video stats (view_count, like_count)
- IP config (character list, AI tool patterns)

**Process**:
1. Filter for viral infringements:
   ```python
   if video.view_count < 10_000:
       return  # Not viral enough

   if not gemini_result.contains_infringement:
       return  # Not an infringement

   if gemini_result.confidence_score < 70:
       return  # Not confident enough
   ```

2. Call Gemini to extract keywords:
   ```python
   prompt = f"""
   Analyze this YouTube video metadata and extract relevant search keywords.

   VIDEO METADATA:
   - Title: {video.title}
   - Description: {video.description}
   - Tags: {video.tags}
   - Channel: {video.channel_title}
   - Views: {video.view_count:,}

   IP CONTEXT:
   - Characters: {ip_config.characters}
   - AI Tools: {ip_config.ai_tool_patterns}

   TASK:
   Extract 5-15 search keywords that YouTube users would use to find this content.

   REQUIREMENTS:
   1. Must mention at least one character: {ip_config.characters}
   2. Must mention AI generation (AI, Sora, Runway, Kling, Pika, Luma, etc.)
   3. 2-5 words per keyword
   4. Natural language (how users actually search)
   5. Remove spam/promotional terms

   OUTPUT FORMAT (JSON only):
   {{
     "keywords": [
       {{
         "phrase": "Superman Sora AI movie",
         "relevance_score": 95,
         "reasoning": "Exact match from title, high views (250k), directly describes content"
       }},
       ...
     ]
   }}
   """
   ```

3. Return extracted keywords with scores

**Output**:
```python
@dataclass
class ExtractedKeyword:
    phrase: str              # "Superman Sora movie"
    relevance_score: int     # 0-100
    reasoning: str           # Why this keyword matters
    source_video_id: str     # Where it came from
    source_views: int        # View count (proxy for popularity)
    extracted_at: datetime
```

### 2. Keyword Validator (NEW)
**File**: `services/discovery-service/app/core/keyword_validator.py`

**Purpose**: Validate extracted keywords against IP config and existing keywords

**Validation Rules**:

1. **Character Match** (REQUIRED):
   ```python
   def has_character_match(keyword: str, ip_config: IPConfig) -> bool:
       keyword_lower = keyword.lower()
       for character in ip_config.characters:
           if character.lower() in keyword_lower:
               return True
       return False
   ```

2. **AI Tool Pattern** (REQUIRED):
   ```python
   def has_ai_pattern(keyword: str, ip_config: IPConfig) -> bool:
       keyword_lower = keyword.lower()
       ai_terms = ["ai", "sora", "runway", "kling", "pika", "luma",
                   "generated", "artificial intelligence"]

       # Check explicit AI tools
       for tool in ip_config.ai_tool_patterns:
           if tool.lower() in keyword_lower:
               return True

       # Check generic AI terms
       for term in ai_terms:
           if term in keyword_lower:
               return True

       return False
   ```

3. **Quality Checks**:
   ```python
   def is_quality_keyword(keyword: str) -> bool:
       # Length check
       if len(keyword.split()) < 2 or len(keyword.split()) > 7:
           return False  # Too short or too long

       # Spam filter
       spam_terms = ["subscribe", "like", "follow", "link in bio",
                     "click here", "download", "buy"]
       if any(term in keyword.lower() for term in spam_terms):
           return False

       # Non-English check (optional - could support multi-language)
       # ...

       return True
   ```

4. **Duplicate Check**:
   ```python
   def is_duplicate(keyword: str, existing_keywords: list[str]) -> bool:
       keyword_normalized = keyword.lower().strip()

       for existing in existing_keywords:
           # Exact match
           if keyword_normalized == existing.lower().strip():
               return True

           # Substring match (90%+ overlap)
           if similar(keyword_normalized, existing.lower()) > 0.9:
               return True

       return False
   ```

5. **Priority Assignment**:
   ```python
   def calculate_priority(
       keyword: ExtractedKeyword,
       ip_config: IPConfig
   ) -> KeywordPriority:
       score = 0

       # View count (viral = high priority)
       if keyword.source_views > 500_000:
           score += 50
       elif keyword.source_views > 100_000:
           score += 30
       elif keyword.source_views > 10_000:
           score += 10

       # Relevance score from Gemini
       score += keyword.relevance_score * 0.3

       # Character match
       high_priority_chars = ["Superman", "Batman", "Wonder Woman"]
       for char in high_priority_chars:
           if char.lower() in keyword.phrase.lower():
               score += 10

       # Determine priority tier
       if score >= 70:
           return KeywordPriority.HIGH    # Scan every 3 days
       elif score >= 40:
           return KeywordPriority.MEDIUM  # Scan every 14 days
       else:
           return KeywordPriority.LOW     # Scan every 30 days
   ```

### 3. Integration with Keyword Tracker (UPDATED)
**File**: `services/discovery-service/app/core/keyword_tracker.py`

**New Methods**:

```python
class KeywordTracker:
    # ... existing methods ...

    def add_discovered_keyword(
        self,
        keyword: ExtractedKeyword,
        ip_id: str,
        priority: KeywordPriority
    ) -> bool:
        """
        Add a newly discovered keyword to tracking.

        Args:
            keyword: Extracted keyword with metadata
            ip_id: IP config ID (e.g., "dc-universe")
            priority: Assigned priority level

        Returns:
            True if added, False if duplicate/invalid
        """
        doc_ref = self.firestore.collection(self.collection).document(
            keyword.phrase
        )

        # Check if exists
        if doc_ref.get().exists:
            logger.info(f"Keyword '{keyword.phrase}' already exists, skipping")
            return False

        # Create new keyword state
        doc_ref.set({
            "keyword": keyword.phrase,
            "ip_id": ip_id,
            "priority": priority.value,
            "source": "viral_extraction",
            "source_video_id": keyword.source_video_id,
            "source_views": keyword.source_views,
            "relevance_score": keyword.relevance_score,
            "reasoning": keyword.reasoning,
            "discovered_at": keyword.extracted_at,
            "last_scanned_at": None,
            "total_scans": 0,
            "videos_found": 0,
            "status": "active",  # active | paused | retired
        })

        logger.info(
            f"Added keyword '{keyword.phrase}' "
            f"(priority={priority.value}, views={keyword.source_views:,})"
        )
        return True

    def get_keyword_performance(self, keyword: str) -> dict:
        """
        Get performance metrics for a keyword.

        Returns:
            {
                "total_scans": int,
                "videos_found": int,
                "avg_videos_per_scan": float,
                "efficiency": float,  # videos per quota unit
                "last_scan_date": datetime,
                "status": str,
            }
        """
        doc = self.firestore.collection(self.collection).document(keyword).get()
        if not doc.exists:
            return {}

        data = doc.to_dict()
        total_scans = data.get("total_scans", 0)
        videos_found = data.get("videos_found", 0)

        return {
            "total_scans": total_scans,
            "videos_found": videos_found,
            "avg_videos_per_scan": videos_found / total_scans if total_scans > 0 else 0,
            "efficiency": videos_found / (total_scans * 100) if total_scans > 0 else 0,
            "last_scan_date": data.get("last_scanned_at"),
            "status": data.get("status", "unknown"),
        }

    def retire_low_performers(self, min_scans: int = 5, min_efficiency: float = 0.01):
        """
        Retire keywords that aren't finding content.

        Args:
            min_scans: Minimum scans before retirement eligible
            min_efficiency: Minimum videos per quota unit (0.01 = 1 video per 100 quota)
        """
        query = (
            self.firestore.collection(self.collection)
            .where("status", "==", "active")
            .where("total_scans", ">=", min_scans)
        )

        retired_count = 0
        for doc in query.stream():
            data = doc.to_dict()
            perf = self.get_keyword_performance(doc.id)

            if perf["efficiency"] < min_efficiency:
                # Retire keyword
                doc.reference.update({
                    "status": "retired",
                    "retired_at": datetime.now(timezone.utc),
                    "retirement_reason": f"Low efficiency: {perf['efficiency']:.3f}"
                })
                retired_count += 1
                logger.info(
                    f"Retired keyword '{doc.id}' "
                    f"({perf['total_scans']} scans, {perf['videos_found']} videos)"
                )

        logger.info(f"Retired {retired_count} low-performing keywords")
```

### 4. Integration with Risk Analyzer (UPDATED)
**File**: `services/risk-analyzer-service/app/worker.py`

**New Callback Hook**:

```python
async def process_video_analysis(video_id: str, gemini_result: GeminiAnalysisResult):
    """
    Process completed Gemini analysis.

    This runs AFTER vision-analyzer-service completes a video scan.
    """
    # ... existing risk update logic ...

    # NEW: Trigger viral keyword extraction
    if should_extract_keywords(video_metadata, gemini_result):
        try:
            await trigger_keyword_extraction(video_id, video_metadata, gemini_result)
        except Exception as e:
            logger.error(f"Keyword extraction failed for {video_id}: {e}")

def should_extract_keywords(
    video: VideoMetadata,
    result: GeminiAnalysisResult
) -> bool:
    """
    Determine if we should extract keywords from this video.

    Criteria:
    - Confirmed infringement (high confidence)
    - Viral (>10k views)
    - Not already extracted from
    """
    if not result.contains_infringement:
        return False

    if result.confidence_score < 70:
        return False

    if video.view_count < 10_000:
        return False

    # Check if already extracted
    extraction_ref = firestore.collection("keyword_extractions").document(video.video_id)
    if extraction_ref.get().exists:
        return False

    return True

async def trigger_keyword_extraction(
    video_id: str,
    video: VideoMetadata,
    result: GeminiAnalysisResult
):
    """
    Trigger keyword extraction for a viral infringement.
    """
    from discovery_service.core.viral_keyword_extractor import ViralKeywordExtractor
    from discovery_service.core.keyword_validator import KeywordValidator

    extractor = ViralKeywordExtractor(gemini_client)
    validator = KeywordValidator()

    # Extract keywords using Gemini
    extracted = await extractor.extract_keywords(
        video_metadata=video,
        ip_configs=load_ip_configs(video.matched_ips),
        gemini_result=result
    )

    logger.info(f"Extracted {len(extracted)} candidate keywords from {video_id}")

    # Validate and add to keyword tracker
    added_count = 0
    for keyword in extracted:
        # Validate
        is_valid, priority = validator.validate(
            keyword,
            ip_config=load_ip_config(video.matched_ips[0])
        )

        if is_valid:
            # Add to keyword tracker
            success = keyword_tracker.add_discovered_keyword(
                keyword=keyword,
                ip_id=video.matched_ips[0],
                priority=priority
            )
            if success:
                added_count += 1

    # Record extraction
    firestore.collection("keyword_extractions").document(video_id).set({
        "video_id": video_id,
        "extracted_at": datetime.now(timezone.utc),
        "candidates_found": len(extracted),
        "keywords_added": added_count,
    })

    logger.info(
        f"Keyword extraction complete for {video_id}: "
        f"{added_count}/{len(extracted)} keywords added"
    )
```

## Implementation Phases

### Phase 1: Core Extraction (Week 1)
**Goal**: Build keyword extraction from viral videos

Tasks:
1. Create `viral_keyword_extractor.py`:
   - Gemini prompt for keyword extraction
   - Parse and structure results
   - Filter by character + AI patterns

2. Create `keyword_validator.py`:
   - Character match validation
   - AI pattern validation
   - Quality checks
   - Duplicate detection
   - Priority calculation

3. Add tests:
   - `test_viral_keyword_extractor.py` (mock Gemini)
   - `test_keyword_validator.py` (validation rules)

**Success Metrics**:
- Extract 5-15 keywords per viral video
- 95%+ contain character name
- 95%+ contain AI pattern
- No spam keywords pass validation

### Phase 2: Integration (Week 2)
**Goal**: Connect extraction to discovery pipeline

Tasks:
1. Update `keyword_tracker.py`:
   - `add_discovered_keyword()` method
   - `get_keyword_performance()` method
   - `retire_low_performers()` method

2. Update `risk-analyzer-service`:
   - Add callback hook after Gemini analysis
   - Trigger extraction for viral infringements
   - Record extraction attempts in Firestore

3. Add monitoring:
   - Track keyword extraction rate
   - Track keyword validation pass rate
   - Track new keyword discovery rate

**Success Metrics**:
- Extract from 100% of eligible videos
- Add 10-50 new keywords per day
- <5% duplicate rejection rate

### Phase 3: Performance Optimization (Week 3)
**Goal**: Optimize keyword performance and retirement

Tasks:
1. Implement keyword performance tracking:
   - Videos found per scan
   - Efficiency (videos per quota unit)
   - ROI vs manual keywords

2. Implement retirement system:
   - Auto-retire keywords after 5 scans with no results
   - Mark seasonal keywords (inactive but keep)
   - Archive retired keywords for analysis

3. Add keyword boosting:
   - Increase priority for high-performing keywords
   - Decrease priority for low-performing keywords
   - Dynamic scan frequency adjustment

**Success Metrics**:
- Retire 20%+ of keywords with <1% efficiency
- Boost 10%+ of keywords with >5% efficiency
- 30%+ improvement in quota efficiency

### Phase 4: Analytics & Reporting (Week 4)
**Goal**: Visibility into keyword discovery system

Tasks:
1. Build keyword analytics dashboard:
   - Top-performing keywords (by videos found)
   - Newly discovered keywords (last 7 days)
   - Retired keywords (with reasons)
   - Extraction success rate

2. Add BigQuery export:
   - `keyword_performance` table
   - `keyword_extractions` table
   - Daily aggregates

3. Create alerting:
   - Alert on keyword extraction failures
   - Alert on low keyword discovery rate
   - Alert on high retirement rate

**Success Metrics**:
- Dashboard shows 100% keyword coverage
- BigQuery has 30+ days of history
- Alerts fire correctly on anomalies

## Expected Impact

### Quota Efficiency
- **Before**: Manual keywords only, 20% discovery efficiency
- **After**: Self-learning keywords, 35-50% discovery efficiency
- **Gain**: 75-150% improvement in videos found per quota unit

### Coverage
- **Before**: 50-100 manual keywords (stale, miss trends)
- **After**: 200-500 active keywords (fresh, adapts to trends)
- **Gain**: 4-10x keyword coverage

### Viral Detection Speed
- **Before**: Find viral videos 7-30 days after upload
- **After**: Find viral videos within 24-72 hours
- **Gain**: 3-30x faster viral detection

### Example: Real-World Scenario

**Day 1**: Manual keyword "Superman Sora" finds video with 250k views
**Day 2**: Gemini confirms infringement (confidence: 95%)
**Day 3**: Extract keywords from video:
- "Superman Sora movie 2025" (relevance: 98)
- "AI Superman full film" (relevance: 92)
- "Sora Superman vs Lex Luthor" (relevance: 88)
- "OpenAI Superman AI generated" (relevance: 85)

**Day 4**: Validate and add 4 new keywords to tracker
**Day 5**: Discovery scans with new keywords
- "Superman Sora movie 2025" finds 12 new videos (800k total views)
- "AI Superman full film" finds 8 new videos (450k total views)

**Day 6**: Gemini scans new videos, 15 more infringements confirmed
**Day 7**: Extract keywords from top 3, add 8 more keywords

**Result**: 4 new keywords → 20 new videos → 15 infringements → 8 more keywords
**ROI**: 300% efficiency gain (found 5x more content per quota unit)

## Firestore Schema

### Collection: `keyword_scan_state`
```javascript
{
  // Document ID = keyword phrase
  "keyword": "Superman Sora movie",
  "ip_id": "dc-universe",
  "priority": "high",  // high | medium | low

  // Discovery metadata
  "source": "viral_extraction",  // viral_extraction | manual | ip_config
  "source_video_id": "abc123",   // Video that inspired this keyword
  "source_views": 250000,
  "relevance_score": 95,
  "reasoning": "Exact title match, 250k views...",
  "discovered_at": Timestamp,

  // Scan state
  "last_scanned_at": Timestamp,
  "last_published_date": Timestamp,
  "scan_direction": "forward",
  "total_scans": 12,
  "videos_found": 45,

  // Performance
  "status": "active",  // active | paused | retired
  "efficiency": 0.0375,  // 45 videos / (12 scans * 100 quota) = 3.75%
  "retired_at": null,
  "retirement_reason": null,
}
```

### Collection: `keyword_extractions`
```javascript
{
  // Document ID = video_id
  "video_id": "abc123",
  "extracted_at": Timestamp,
  "video_views": 250000,
  "gemini_confidence": 95,

  // Extraction results
  "candidates_found": 8,
  "keywords_added": 4,
  "keywords_rejected": 4,
  "rejection_reasons": [
    "duplicate: 'Superman AI'",
    "no character match: 'Sora AI movie'",
    "spam: 'Subscribe for more'",
    "too short: 'Superman'"
  ],

  // Added keywords
  "added_keywords": [
    "Superman Sora movie 2025",
    "AI Superman full film",
    "Sora Superman vs Lex Luthor",
    "OpenAI Superman AI generated"
  ]
}
```

## Cost Analysis

### Gemini Cost per Extraction
- **Input**: ~500 tokens (video metadata + prompt)
- **Output**: ~1,000 tokens (5-15 keywords + reasoning)
- **Total**: ~1,500 tokens
- **Cost**: $0.0005 per extraction (Gemini 2.5 Flash)

### Daily Cost Estimate
- **Viral videos per day**: 50-100
- **Extractions per day**: 50-100
- **Daily cost**: $0.025-0.05
- **Monthly cost**: $0.75-1.50

### ROI Analysis
- **Cost**: $1.50/month
- **Benefit**: 75-150% improvement in discovery efficiency
- **Quota saved**: 2,000-5,000 units/day (at $0 cost, but unlocks 20,000-50,000 more videos discovered)
- **ROI**: 10,000%+ (discovery efficiency improvement far exceeds extraction cost)

## Monitoring & Alerts

### Key Metrics to Track

1. **Extraction Rate**
   - Target: 50-100 extractions/day
   - Alert if: <10/day (system not working)

2. **Validation Pass Rate**
   - Target: 50-80% of candidates pass validation
   - Alert if: <30% (extraction quality low) or >95% (validation too loose)

3. **Keyword Addition Rate**
   - Target: 10-50 new keywords/day
   - Alert if: <5/day (not discovering enough) or >100/day (quality concern)

4. **Keyword Performance**
   - Target: 70%+ of keywords find >1 video in first 3 scans
   - Alert if: <50% (keyword quality issue)

5. **Retirement Rate**
   - Target: 10-30% of keywords retired after 5 scans
   - Alert if: >50% (extraction not working) or <5% (retirement too strict)

## Future Enhancements

### Phase 5: Multi-Language Support
- Extract keywords in Spanish, Portuguese, Japanese, Korean
- Use language-specific Gemini prompts
- Track performance by language

### Phase 6: Keyword Clustering
- Group similar keywords (e.g., "Superman Sora" + "Superman Sora AI")
- Deduplicate search efforts
- Optimize quota allocation

### Phase 7: Predictive Keyword Generation
- Use ML to predict next trending keywords
- Generate keyword variations automatically
- A/B test keyword performance

### Phase 8: Cross-IP Learning
- Learn keyword patterns from one IP, apply to others
- "If 'Batman Sora' is trending, try 'Wonder Woman Sora'"
- Share keywords across similar IPs

## Success Criteria

After 30 days of operation:

1. **Keyword Coverage**: 200-500 active keywords (vs 50-100 manual)
2. **Discovery Efficiency**: 35-50% videos found per quota (vs 20% baseline)
3. **Viral Detection Speed**: 24-72 hours (vs 7-30 days)
4. **Infringement Hit Rate**: 25-35% of discovered videos are infringements (vs 15-20%)
5. **System Cost**: <$2/month for keyword extraction
6. **Keyword Quality**: 70%+ of new keywords find videos within 3 scans

## Risks & Mitigations

### Risk 1: Keyword Quality Degradation
- **Risk**: Extracted keywords are low quality / spammy
- **Mitigation**: Strict validation rules + manual review of top 10 keywords/week

### Risk 2: Feedback Loop Collapse
- **Risk**: Keywords stop finding new content (exhausted search space)
- **Mitigation**: Retirement system removes dead keywords, makes room for new ones

### Risk 3: Cost Overrun
- **Risk**: Too many extractions drive up Gemini costs
- **Mitigation**: Limit extractions to 100/day, require >10k views

### Risk 4: Keyword Explosion
- **Risk**: Add 1000s of keywords, exhaust quota on bad keywords
- **Mitigation**: Performance tracking + automatic retirement of low performers

## Conclusion

This viral keyword detection system creates a **self-improving discovery engine** that:
- Learns from real user behavior (what gets views?)
- Adapts to trending terminology (what's popular now?)
- Optimizes quota allocation (focus on what works)
- Scales across IPs (reusable pattern)

**Implementation Time**: 4 weeks
**Monthly Cost**: <$2
**Expected ROI**: 10,000%+ (discovery efficiency improvement)
