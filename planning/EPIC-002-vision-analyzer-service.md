# EPIC 002: Vision Analyzer Service - AI-Powered Copyright Detection

**Status:** Planning
**Priority:** P0 (Critical)
**Target Completion:** Sprint 4-6 (2-3 weeks)
**Owner:** Engineering Team
**Dependencies:** Epic 001 (Risk Analyzer) ✅ COMPLETE

---

## 📋 Executive Summary

### Problem Statement
We have 186 videos discovered and risk-scored, but **0 videos analyzed** for copyright infringement. The vision-analyzer-service is the final critical piece that:
- Consumes the €240/day Gemini budget (currently unused)
- Identifies actual Justice League character usage in AI-generated content
- Provides legal evidence for takedown requests
- Learns and improves risk scoring accuracy

### Current State
- ❌ No video analysis capability
- ❌ €240/day Gemini budget unutilized (100% waste)
- ❌ No infringement detection
- ❌ Risk scores not validated against actual content
- ❌ No feedback loop to improve discovery/risk models

### Future State
- ✅ **Budget Exhaustion:** €240/day spent on highest-priority videos
- ✅ **Cost Optimization:** Smart FPS/offset adjustment per video (€0.0025-0.01/video)
- ✅ **Accurate Detection:** Gemini 2.0 Flash analyzes videos directly via YouTube URL
- ✅ **Legal Compliance:** Copyright law understanding in prompts
- ✅ **Adaptive Learning:** Results feed back to risk-analyzer for continuous improvement
- ✅ **Throughput:** 2,880 videos/day capacity (rate limit) or 24,000-96,000 videos/day (budget limit)

### Success Metrics
| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Gemini budget utilization | 0% | 95-100% | Daily spend / €240 |
| Cost per video | N/A | €0.0025-0.01 | Actual cost tracking |
| Videos analyzed/day | 0 | 2,000-3,000 | PubSub throughput |
| Infringement detection rate | N/A | 15-30% | Confirmed violations / scanned |
| False positive rate | N/A | <5% | Manual review validation |
| Average processing time | N/A | <10s/video | Gemini API latency |

---

## 🎯 Epic Objectives

### Why This Matters

**Business Impact:**
1. **Revenue Protection:** Detect infringements before they accumulate millions of views
2. **Legal Evidence:** Provide detailed analysis for DMCA takedowns
3. **Cost Efficiency:** Maximize ROI on €240/day budget (analyze 2,000-3,000 videos)
4. **Competitive Advantage:** Real-time AI-powered detection vs. manual review

**Technical Excellence:**
1. **Latest AI Technology:** Gemini 2.0 Flash with direct YouTube URL support
2. **Cost Optimization:** Variable FPS/offsets based on risk tier and video length
3. **Smart Prioritization:** HIGH risk videos get more budget allocation
4. **Continuous Learning:** Feedback loop improves upstream models

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                   RISK ANALYZER SERVICE                              │
│  - Continuously rescores videos                                      │
│  - Maintains priority queue sorted by risk                           │
│  - Publishes when scan is due (tier-based frequency)                │
│                                                                      │
│  Output: PubSub → scan-ready topic                                  │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                 VISION ANALYZER SERVICE (NEW!)                       │
│  Purpose: Analyze videos with Gemini 2.0 Flash for infringement     │
│  Budget: €240/day (~$260 USD)                                       │
│  Throughput: 2,880 videos/day (rate limited) or 24k-96k (budget)    │
│                                                                      │
│  Core Components:                                                    │
│  ├── Budget Manager                                                 │
│  │   └── Track spend, enforce daily limit, cost estimation          │
│  ├── Video Analyzer                                                 │
│  │   ├── Gemini 2.0 Flash client (google-genai SDK)                │
│  │   ├── Dynamic FPS/offset calculation by risk tier               │
│  │   ├── Copyright-aware prompt engineering                        │
│  │   └── Structured JSON output parsing                            │
│  ├── Result Processor                                               │
│  │   ├── Store analysis in Firestore                               │
│  │   ├── Export to BigQuery for analytics                          │
│  │   └── Flag high-confidence infringements                        │
│  └── Feedback Publisher                                             │
│      └── Send results to risk-analyzer for learning                │
│                                                                      │
│  Input:  PubSub ← scan-ready topic                                 │
│  Output: Firestore, BigQuery, PubSub (feedback)                    │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA OUTPUTS                                  │
│  - Firestore: Real-time analysis results                           │
│  - BigQuery: Analytics, reporting, trends                          │
│  - PubSub: Feedback to risk-analyzer (learning)                    │
│  - Alerts: High-confidence infringements for legal team            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 💰 Cost Optimization Strategy

### Gemini 2.0 Flash Pricing (as of 2025)

**Model:** `gemini-2.0-flash-exp` via Vertex AI (not API key!)

**Token Costs:**
```
Input (video):  $0.075 per 1M tokens
Output (text):  $0.30 per 1M tokens

Video Resolution Options:
- Default: 300 tokens/second (258 frames/s + 32 audio)
- Low:     100 tokens/second (66 frames/s + 32 audio)  ← RECOMMENDED

Audio: 32 tokens/second (always included)
```

**Rate Limits:**
- 30 requests/minute = 2,880 videos/day (hard limit)
- 4M tokens/minute input

### Cost Examples by Video Length

| Video Length | Resolution | Tokens | Input Cost | Output Cost | Total Cost |
|--------------|------------|--------|------------|-------------|------------|
| 30s (short)  | Low        | 3,000  | $0.0002    | $0.0002     | **$0.0004** |
| 1min         | Low        | 6,000  | $0.0005    | $0.0002     | **$0.0007** |
| 3min         | Low        | 18,000 | $0.0014    | $0.0002     | **$0.0016** |
| 5min         | Low        | 30,000 | $0.0023    | $0.0002     | **$0.0025** |
| 10min        | Low        | 60,000 | $0.0045    | $0.0002     | **$0.0047** |
| 20min        | Low        | 120,000| $0.0090    | $0.0002     | **$0.0092** |
| 30min        | Low        | 180,000| $0.0135    | $0.0002     | **$0.0137** |

### Daily Budget Allocation (€240 = $260)

**Scenario 1: Rate-Limited (Conservative)**
```
Rate limit: 2,880 videos/day
Average cost: $0.005/video (5min average)
Total cost: $14.40/day (~€13)
Budget utilization: 5.5%

❌ PROBLEM: Massive budget underutilization!
```

**Scenario 2: Budget Exhaustion (Optimal)**
```
Strategy: Scan until €240 spent, respecting rate limits

Mix of video lengths:
- 30% short (30s-2min): $0.0004-0.001  = 12,000-30,000 videos
- 50% medium (2-10min): $0.0016-0.0047 = 5,000-15,000 videos
- 20% long (10-30min):  $0.0047-0.0137 = 1,800-5,200 videos

Weighted average: $0.003/video
Total videos: ~86,000 videos/day (budget limit)

BUT rate limited to 2,880 videos/day!

Solution: Analyze longer, higher-risk videos
Average cost: $0.09/video (allocate more budget per video)
Total videos: 2,880 videos/day
Budget: $259.20 (~€240) ✅ 99.7% utilization!
```

**Optimal Strategy:**
1. Sort videos by risk score (HIGH → MEDIUM → LOW)
2. Scan highest-risk videos first
3. Allocate more budget to HIGH risk (deeper analysis)
4. Stop at rate limit OR budget exhaustion (whichever first)

---

## 🎨 Dynamic FPS & Offset Strategy

### Adaptive Sampling Based on Risk Tier

**Principle:** Higher risk = more thorough analysis = higher cost

| Risk Tier | FPS | Offsets | Budget/Video | Rationale |
|-----------|-----|---------|--------------|-----------|
| **CRITICAL (90-100)** | 1.0 | None | $0.15-0.20 | Full analysis, no skipping |
| **HIGH (70-89)** | 0.5 | 5s start/end | $0.08-0.12 | Detailed analysis |
| **MEDIUM (40-69)** | 0.33 | 10s start/end | $0.04-0.06 | Standard analysis |
| **LOW (20-39)** | 0.25 | 15s start/end | $0.02-0.03 | Light sampling |
| **VERY_LOW (0-19)** | 0.2 | 30s start/end | $0.01-0.015 | Minimal sampling |

### FPS Calculation Algorithm

```python
def calculate_video_config(video: dict) -> dict:
    """
    Calculate optimal FPS, offsets, and resolution based on:
    - Risk tier (higher risk = more frames)
    - Video duration (longer videos = lower FPS)
    - Budget remaining (less budget = lower FPS)
    """
    risk_tier = video['risk_tier']
    duration = video['duration_seconds']
    budget_remaining = get_daily_budget_remaining()

    # Base FPS by risk tier
    fps_map = {
        'CRITICAL': 1.0,
        'HIGH': 0.5,
        'MEDIUM': 0.33,
        'LOW': 0.25,
        'VERY_LOW': 0.2,
    }
    base_fps = fps_map.get(risk_tier, 0.33)

    # Adjust for video length (longer = slower FPS)
    if duration > 1800:  # 30+ minutes
        base_fps *= 0.5
    elif duration > 600:  # 10-30 minutes
        base_fps *= 0.75

    # Budget pressure adjustment
    if budget_remaining < 50:  # <$50 left
        base_fps *= 0.75  # Conserve budget

    # Offsets (skip intro/outro)
    if duration < 60:
        start_offset = 0
        end_offset = duration
    elif duration < 300:  # <5 min
        start_offset = 5
        end_offset = duration - 5
    elif duration < 600:  # 5-10 min
        start_offset = 10
        end_offset = duration - 10
    else:  # >10 min
        start_offset = 15
        end_offset = duration - 30

    # Estimate cost before scanning
    effective_duration = end_offset - start_offset
    frames_analyzed = int(effective_duration * base_fps)
    tokens = frames_analyzed * 66  # Low res = 66 tokens/frame
    tokens += effective_duration * 32  # Audio
    estimated_cost_usd = (tokens * 0.075 / 1_000_000) + (500 * 0.30 / 1_000_000)

    return {
        'fps': base_fps,
        'start_offset': f'{start_offset}s',
        'end_offset': f'{end_offset}s',
        'media_resolution': 'low',
        'estimated_cost_usd': estimated_cost_usd,
        'frames_analyzed': frames_analyzed,
    }
```

---

## 🤖 Gemini Integration - Technical Details

### SDK: `google-genai` (NOT `google-generativeai`)

**CRITICAL:** Use the NEW SDK, not the deprecated one!

```python
# ✅ CORRECT - google-genai (new SDK, supports Vertex AI)
from google import genai
from google.auth import default

credentials, project = default()
client = genai.Client(
    vertexai=True,
    project=project,
    location='us-central1'  # or europe-west4
)

# ❌ WRONG - google-generativeai (deprecated, EOL Aug 2025)
import google.generativeai as genai  # DON'T USE THIS!
```

### Video Analysis with Direct YouTube URL

**Key Feature:** Gemini 2.0 Flash accepts YouTube URLs directly (no download needed!)

```python
async def analyze_video(video_id: str, youtube_url: str, config: dict) -> dict:
    """
    Analyze YouTube video for copyright infringement.

    Args:
        video_id: Video ID
        youtube_url: Full YouTube URL
        config: FPS, offsets, resolution settings

    Returns:
        Analysis results with infringement detection
    """

    # Build Gemini request
    prompt = create_copyright_detection_prompt(video_id)

    video_config = {
        'youtube_url': youtube_url,
        'fps': config['fps'],
        'start_offset': config['start_offset'],
        'end_offset': config['end_offset'],
        'media_resolution': config['media_resolution'],
    }

    # Call Gemini 2.0 Flash
    response = await client.models.generate_content_async(
        model='gemini-2.0-flash-exp',
        contents=[
            {
                'parts': [
                    {'text': prompt},
                    {'video': video_config},
                ]
            }
        ],
        config={
            'temperature': 0.2,  # Low temp for consistency
            'max_output_tokens': 2048,
            'response_mime_type': 'application/json',  # Force JSON
        }
    )

    # Parse JSON response
    result = json.loads(response.text)

    # Calculate actual cost
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    cost_usd = (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000

    return {
        'analysis': result,
        'cost_usd': cost_usd,
        'tokens_used': input_tokens + output_tokens,
        'model': 'gemini-2.0-flash-exp',
    }
```

---

## ⚖️ Copyright Detection Prompt Engineering

### Prompt Design Principles

1. **Legal Understanding:** Embed copyright law basics
2. **Character-Specific:** Target Justice League characters only
3. **Context-Aware:** Differentiate AI-generated from fair use
4. **Structured Output:** Force JSON with specific schema
5. **Evidence-Based:** Require reasoning and timestamps

### Prompt Template

```python
def create_copyright_detection_prompt(video_metadata: dict) -> str:
    """
    Create a copyright-aware prompt for Gemini analysis.

    Includes:
    - Copyright law basics (fair use vs infringement)
    - Target characters (Justice League)
    - AI-generated content detection
    - Structured JSON output schema
    """

    characters = video_metadata.get('matched_characters', [
        'Superman', 'Batman', 'Wonder Woman',
        'Flash', 'Aquaman', 'Cyborg', 'Green Lantern'
    ])

    return f"""
# COPYRIGHT INFRINGEMENT ANALYSIS

## LEGAL CONTEXT

You are analyzing this video for potential copyright infringement under U.S. Copyright Law.

**Copyright Infringement Criteria:**
1. Unauthorized use of copyrighted characters
2. Substantial similarity to original work
3. Commercial or public distribution
4. Not protected under Fair Use doctrine

**Fair Use Exceptions (17 U.S.C. § 107):**
- Commentary, criticism, or review
- Educational purposes
- Transformative use (parody, satire)
- Limited use (brief clips with commentary)

**AI-Generated Content:**
- AI tools (Sora, Runway, Kling, etc.) do NOT grant copyright permissions
- Creating AI videos of copyrighted characters = infringement (unless fair use)
- Length matters: Full movies/episodes = higher infringement likelihood

---

## TARGET CHARACTERS

DC Comics Justice League (Warner Bros. copyright):
{', '.join(characters)}

Identify any appearances of these characters in the video.

---

## VIDEO METADATA

- **Video ID:** {video_metadata.get('video_id')}
- **Title:** {video_metadata.get('title')}
- **Duration:** {video_metadata.get('duration_seconds')}s
- **View Count:** {video_metadata.get('view_count'):,}
- **Channel:** {video_metadata.get('channel_title')}

---

## ANALYSIS INSTRUCTIONS

1. **Detect AI-Generated Content:**
   - Look for Sora, Runway, Kling, Pika, Luma watermarks/artifacts
   - Identify unnatural movements, morphing, physics inconsistencies
   - Check video title/description for AI tool mentions

2. **Identify Characters:**
   - Which Justice League characters appear?
   - Estimate screen time for each character (seconds)
   - Are they in recognizable costume/form?

3. **Assess Infringement Likelihood:**
   - Is this a full AI-generated movie/episode? (HIGH risk)
   - Is it original content vs. review/commentary? (MEDIUM/LOW risk)
   - Duration: Longer = higher risk (30min movie vs 10s clip)
   - Commercial use: Monetized? Promotional? (increases risk)

4. **Fair Use Considerations:**
   - Does video add commentary/criticism?
   - Is character use transformative (parody/satire)?
   - Is it educational or news-related?

5. **Evidence:**
   - Provide specific timestamps of character appearances
   - Note any copyright disclaimers (often invalid)
   - Identify AI tool usage evidence

---

## REQUIRED OUTPUT (JSON)

Respond ONLY with valid JSON matching this schema:

{{
  "contains_infringement": true/false,
  "confidence_score": 0-100,
  "infringement_type": "full_ai_movie" | "ai_clips" | "unauthorized_use" | "fair_use" | "none",

  "ai_generated": {{
    "is_ai": true/false,
    "confidence": 0-100,
    "tools_detected": ["Sora", "Runway", ...],
    "evidence": "Watermarks at 0:05, unnatural physics at 1:23, ..."
  }},

  "characters_detected": [
    {{
      "name": "Superman",
      "screen_time_seconds": 45,
      "prominence": "primary" | "secondary" | "background",
      "timestamps": ["0:05-0:50", "2:10-2:30"],
      "description": "Wearing classic costume, flying scenes"
    }}
  ],

  "copyright_assessment": {{
    "infringement_likelihood": 0-100,
    "reasoning": "Detailed explanation with legal basis",
    "fair_use_applies": true/false,
    "fair_use_factors": {{
      "purpose": "commercial" | "educational" | "commentary" | "transformative",
      "nature": "creative_work" | "factual",
      "amount_used": "substantial" | "minimal",
      "market_effect": "high" | "medium" | "low"
    }}
  }},

  "video_characteristics": {{
    "duration_category": "short" | "medium" | "long" | "full_length",
    "content_type": "full_movie" | "trailer" | "clips" | "review" | "other",
    "monetization_detected": true/false,
    "professional_quality": true/false
  }},

  "recommended_action": "immediate_takedown" | "monitor" | "safe_harbor" | "ignore",

  "legal_notes": "Additional context for legal team"
}}

---

## IMPORTANT GUIDELINES

- Be conservative: When uncertain, mark confidence lower
- Fair use is RARE: Most AI-generated character content is infringement
- Length matters: 30min AI movie = very high infringement risk
- Context matters: Review/commentary with clips = likely fair use
- Evidence required: Cite specific timestamps and observations
- Consider market harm: Popular videos with many views = higher priority
"""
```

---

## 📊 Stories & Implementation Plan

### Story 4.1: Service Infrastructure Setup ✨
**Priority:** P0
**Story Points:** 5
**Duration:** 1 day

**Description:**
Create the basic vision-analyzer-service structure with FastAPI, Firestore, PubSub integration.

**Tasks:**
1. Create service directory structure
   ```
   services/vision-analyzer-service/
   ├── app/
   │   ├── main.py (FastAPI app)
   │   ├── config.py (settings)
   │   ├── worker.py (PubSub subscriber)
   │   ├── core/
   │   │   ├── gemini_client.py
   │   │   ├── budget_manager.py
   │   │   └── video_analyzer.py
   │   ├── routers/
   │   │   ├── health.py
   │   │   └── admin.py (manual trigger)
   │   └── models.py (Pydantic)
   ├── tests/
   ├── terraform/
   ├── Dockerfile
   └── pyproject.toml
   ```

2. Add dependencies (UV):
   ```
   fastapi==0.120.2
   uvicorn==0.38.0
   pydantic-settings==2.11.0
   google-genai==1.46.0  # NEW SDK!
   google-cloud-firestore==2.21.0
   google-cloud-pubsub==2.32.0
   google-auth==2.42.0
   ```

3. Configure PubSub subscription to `scan-ready` topic

4. Create Terraform infrastructure (Cloud Run + IAM)

5. Add health endpoint (`/health`)

**Acceptance Criteria:**
- ✅ Service runs locally with emulators
- ✅ PubSub subscription receives messages
- ✅ Health endpoint returns 200
- ✅ Terraform deploys to Cloud Run

**Why This Matters:**
Foundation for all subsequent stories. Must be solid before adding complex logic.

---

### Story 4.2: Gemini Client Integration 🤖
**Priority:** P0
**Story Points:** 8
**Duration:** 2 days

**Description:**
Integrate Gemini 2.0 Flash with Vertex AI authentication and YouTube URL support.

**Approach Options:**

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Option A: Direct API** | Simple, fast | No abstraction | ❌ Not scalable |
| **Option B: Client Class** | Reusable, testable | More code | ✅ **RECOMMENDED** |
| **Option C: Library Wrapper** | Clean interface | Over-engineering | Maybe later |

**Selected: Option B - Client Class**

**Tasks:**
1. Create `GeminiClient` class
   ```python
   class GeminiClient:
       def __init__(self, project_id: str, location: str):
           self.project = project_id
           self.location = location
           self.client = self._init_client()

       def _init_client(self):
           """Initialize with Vertex AI auth."""
           credentials, _ = default()
           return genai.Client(
               vertexai=True,
               project=self.project,
               location=self.location,
           )

       async def analyze_video(
           self,
           youtube_url: str,
           prompt: str,
           config: dict,
       ) -> dict:
           """Analyze video and return JSON results."""
           pass
   ```

2. Implement video analysis method with:
   - YouTube URL input
   - FPS configuration
   - Start/end offsets
   - Media resolution setting
   - Error handling (rate limits, timeouts)

3. Add cost tracking:
   - Token usage logging
   - Cost calculation ($0.075 input, $0.30 output per 1M tokens)
   - Running total

4. Write unit tests with mocked responses

5. Integration test with real Gemini API (test quota)

**Acceptance Criteria:**
- ✅ Can analyze YouTube video via URL
- ✅ Returns structured JSON
- ✅ Handles rate limits gracefully
- ✅ Logs token usage and cost
- ✅ Tests pass (unit + integration)

**Technical Risks:**
- Rate limiting (30 req/min)
- Token quota (4M/min input)
- YouTube URL access (geo-restrictions?)

**Mitigation:**
- Exponential backoff for rate limits
- Queue videos when near quota
- Fallback to video download if URL fails

---

### Story 4.3: Dynamic FPS & Offset Calculator 📐
**Priority:** P0
**Story Points:** 5
**Duration:** 1 day

**Description:**
Implement intelligent FPS and offset calculation based on risk tier, video length, and budget.

**Why This Matters:**
This is the **core cost optimization**! Without this, we either:
- Overspend (analyze everything at 1 FPS = $0.15/video = €240 for 1,600 videos)
- Underspend (analyze everything at 0.2 FPS = $0.01/video = €20 for 2,880 videos = 92% waste)

**Approach:**

```python
class VideoConfigCalculator:
    """Calculate optimal analysis parameters."""

    def calculate_config(
        self,
        video: dict,
        budget_remaining: float,
        queue_size: int,
    ) -> dict:
        """
        Calculate FPS, offsets, resolution based on:
        - Risk tier (CRITICAL gets 5x budget of VERY_LOW)
        - Video duration (longer = lower FPS)
        - Budget pressure (less budget = lower FPS)
        - Queue size (many videos = lower FPS per video)

        Returns:
            {
                'fps': 0.2-1.0,
                'start_offset': '10s',
                'end_offset': '590s',
                'media_resolution': 'low',
                'estimated_cost_usd': 0.005,
            }
        """
        pass
```

**Budget Allocation by Tier:**

| Tier | Budget Multiplier | Example (5min video) |
|------|-------------------|----------------------|
| CRITICAL | 5x | $0.0125 (2.5x base) |
| HIGH | 3x | $0.0075 (1.5x base) |
| MEDIUM | 1x | $0.005 (base) |
| LOW | 0.5x | $0.0025 (0.5x base) |
| VERY_LOW | 0.3x | $0.0015 (0.3x base) |

**Tasks:**
1. Implement base FPS calculation by tier
2. Add duration adjustment (longer = slower)
3. Add budget pressure adjustment
4. Implement offset calculation (skip intro/outro)
5. Add cost estimation function
6. Write tests with various scenarios
7. Add logging/metrics for tuning

**Acceptance Criteria:**
- ✅ CRITICAL videos get 5x budget of VERY_LOW
- ✅ 30min videos use 50% FPS of 5min videos
- ✅ Accurate cost estimation (<10% error)
- ✅ All edge cases handled (0s video, 2hr video, etc.)

---

### Story 4.4: Budget Manager & Exhaustion Algorithm 💰
**Priority:** P0
**Story Points:** 8
**Duration:** 2 days

**Description:**
Implement budget tracking, daily limits, and the core "scan until exhausted" algorithm.

**Core Algorithm:**

```python
class BudgetManager:
    """
    Manage daily budget and enforce limits.

    Daily budget: €240 ($260)
    Rate limit: 30 req/min = 2,880 videos/day
    """

    DAILY_BUDGET_USD = 260.0
    RATE_LIMIT_PER_MIN = 30

    def __init__(self, firestore_client):
        self.firestore = firestore_client
        self.daily_total = self._get_daily_total()

    def can_afford(self, estimated_cost: float) -> bool:
        """Check if we can afford this video analysis."""
        return (self.daily_total + estimated_cost) <= self.DAILY_BUDGET_USD

    def record_usage(self, video_id: str, actual_cost: float):
        """Record actual cost after analysis."""
        self.daily_total += actual_cost
        # Store in Firestore for tracking

    def get_remaining_budget(self) -> float:
        """Get remaining budget for today."""
        return max(0, self.DAILY_BUDGET_USD - self.daily_total)

    async def exhaust_budget(self, priority_queue: list):
        """
        Main budget exhaustion algorithm.

        Scan videos in priority order until:
        1. Budget exhausted (€240 spent), OR
        2. Rate limit reached (2,880 videos), OR
        3. Queue empty

        Respects:
        - Rate limiting (30/min)
        - Budget allocation by tier
        - Cost estimation before scanning
        """
        scanned = 0
        start_time = time.time()

        for video in priority_queue:
            # Check budget limit
            if not self.can_afford(video['estimated_cost']):
                logger.info(f"Budget exhausted: ${self.daily_total:.2f}")
                break

            # Check rate limit
            elapsed_min = (time.time() - start_time) / 60
            if scanned >= (elapsed_min * 30):
                await asyncio.sleep(60)  # Wait 1 minute

            # SCAN VIDEO
            result = await self.analyzer.analyze(video)
            self.record_usage(video['id'], result['cost'])
            scanned += 1

            if scanned >= 2880:  # Daily rate limit
                logger.info("Rate limit reached")
                break

        logger.info(f"Scanned {scanned} videos, spent ${self.daily_total:.2f}")
```

**Tasks:**
1. Implement budget tracking in Firestore
2. Create daily reset mechanism (midnight UTC)
3. Implement rate limiting (30/min)
4. Add cost estimation before scanning
5. Build priority queue sorter (risk score DESC)
6. Implement exhaust_budget() main loop
7. Add metrics/logging for monitoring
8. Write tests for edge cases

**Acceptance Criteria:**
- ✅ Never exceeds €240/day
- ✅ Respects 30 req/min rate limit
- ✅ Scans highest-risk videos first
- ✅ Stops gracefully at limits
- ✅ Accurate daily spend tracking

**Why This Matters:**
This is the **core business logic**! Without proper budget exhaustion, we either overspend or waste capacity.

---

### Story 4.5: Copyright Detection Prompt Engineering ⚖️
**Priority:** P0
**Story Points:** 5
**Duration:** 1 day

**Description:**
Create legally-aware prompts that accurately detect copyright infringement.

**Prompt Components:**
1. **Legal Context:** Copyright law basics, fair use doctrine
2. **Character Definitions:** Justice League character descriptions
3. **AI Detection:** How to identify AI-generated content
4. **Output Schema:** Structured JSON format
5. **Evidence Requirements:** Timestamps, reasoning

**Tasks:**
1. Research copyright law (17 U.S.C. § 107)
2. Create prompt template with legal language
3. Define JSON output schema
4. Add character-specific details
5. Test with real videos (varied content types)
6. Iterate based on results (false positives/negatives)
7. Document prompt engineering decisions

**Test Cases:**
- ✅ Full AI movie (30min Superman) → HIGH infringement
- ✅ Review with clips (10min commentary) → Fair use
- ✅ AI trailer (2min Batman) → MEDIUM infringement
- ✅ Parody/satire (5min funny edits) → Fair use
- ✅ Short clip (10s action scene) → LOW infringement

**Acceptance Criteria:**
- ✅ <5% false positive rate
- ✅ >90% true positive rate (validated)
- ✅ Structured JSON output (parseable)
- ✅ Includes legal reasoning
- ✅ Provides timestamps

---

### Story 4.6: Result Processing & Feedback Loop 🔄
**Priority:** P1
**Story Points:** 5
**Duration:** 1 day

**Description:**
Store analysis results and send feedback to risk-analyzer for continuous learning.

**Data Flow:**

```
Gemini Analysis
    ↓
Firestore (videos collection)
    ├── analysis_result: {...}
    ├── gemini_cost_usd: 0.005
    ├── analyzed_at: timestamp
    ├── infringement_detected: true/false
    └── confidence_score: 0-100
    ↓
BigQuery (analytics)
    ↓
PubSub (feedback topic)
    → Risk Analyzer updates channel/video risk
```

**Tasks:**
1. Create result processor class
2. Update Firestore documents with results
3. Export to BigQuery for analytics
4. Publish feedback to PubSub
5. Add high-confidence infringement alerting
6. Create admin dashboard for results review
7. Write integration tests

**Acceptance Criteria:**
- ✅ Results stored in Firestore
- ✅ BigQuery updated for analytics
- ✅ Feedback published to risk-analyzer
- ✅ High-confidence alerts sent
- ✅ Admin can review results

---

### Story 4.7: Testing & Validation 🧪
**Priority:** P1
**Story Points:** 8
**Duration:** 2 days

**Description:**
Comprehensive testing with real videos and validation of accuracy.

**Test Levels:**

1. **Unit Tests:**
   - GeminiClient methods
   - Budget calculations
   - FPS calculator
   - Prompt generation

2. **Integration Tests:**
   - End-to-end video analysis
   - PubSub message handling
   - Firestore updates
   - Cost tracking accuracy

3. **Validation Tests:**
   - Real YouTube videos (diverse content)
   - Manual review of results
   - False positive/negative rates
   - Cost accuracy (<10% error)

**Test Dataset (20 videos):**
- 5 clear infringements (AI-generated full movies)
- 5 fair use cases (reviews, commentary)
- 5 edge cases (short clips, trailers)
- 5 non-DC content (false positive test)

**Tasks:**
1. Create test dataset (20 videos)
2. Write unit tests (80%+ coverage)
3. Write integration tests
4. Run validation tests with manual review
5. Measure accuracy metrics
6. Fix false positives/negatives
7. Document test results

**Acceptance Criteria:**
- ✅ 80%+ unit test coverage
- ✅ All integration tests pass
- ✅ <5% false positive rate
- ✅ >90% true positive rate
- ✅ Cost estimation within 10% of actual

---

### Story 4.8: Production Deployment & Monitoring 🚀
**Priority:** P1
**Story Points:** 5
**Duration:** 1 day

**Description:**
Deploy to production with monitoring, alerting, and observability.

**Monitoring Metrics:**
- Videos analyzed per day
- Budget spent vs. remaining
- Average cost per video
- Infringement detection rate
- Error rate
- Average processing time
- Queue depth

**Tasks:**
1. Deploy to Cloud Run (production)
2. Set up Cloud Monitoring dashboards
3. Configure alerting (budget exceeded, errors)
4. Add structured logging
5. Create runbook for on-call
6. Document deployment process
7. Monitor first 24 hours

**Acceptance Criteria:**
- ✅ Service deployed to production
- ✅ Monitoring dashboard live
- ✅ Alerts configured and tested
- ✅ Logs searchable in Cloud Logging
- ✅ Runbook documented

---

## 🎯 Possible Approaches & Trade-offs

### Approach A: Sync Processing (Simple)
**How:** Process videos synchronously in PubSub handler

**Pros:**
- Simple code
- Easy to reason about
- Direct error handling

**Cons:**
- PubSub ack timeout (10min max)
- Can't handle long videos (>10min)
- No parallelism

**Verdict:** ❌ Not suitable for 30min videos

---

### Approach B: Async Processing (Recommended)
**How:** PubSub triggers async job, ack immediately

**Pros:**
- No timeout issues
- Can handle any video length
- Parallelism possible

**Cons:**
- More complex
- Need job tracking
- Error handling harder

**Verdict:** ✅ **RECOMMENDED**

---

### Approach C: Batch Processing
**How:** Collect videos, process in batches

**Pros:**
- Efficient for rate limits
- Better resource utilization

**Cons:**
- Delays (wait for batch)
- Complex state management

**Verdict:** ⚠️ Maybe later for optimization

---

## 📈 Story Points Summary

| Story | Points | Duration | Priority |
|-------|--------|----------|----------|
| 4.1 Infrastructure Setup | 5 | 1 day | P0 |
| 4.2 Gemini Integration | 8 | 2 days | P0 |
| 4.3 FPS/Offset Calculator | 5 | 1 day | P0 |
| 4.4 Budget Manager | 8 | 2 days | P0 |
| 4.5 Prompt Engineering | 5 | 1 day | P0 |
| 4.6 Result Processing | 5 | 1 day | P1 |
| 4.7 Testing & Validation | 8 | 2 days | P1 |
| 4.8 Production Deployment | 5 | 1 day | P1 |
| **TOTAL** | **49 points** | **11 days** | |

**Team Velocity:** Assuming 2 points/day = ~3 weeks

---

## 🎓 Technical Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Gemini rate limits | HIGH | HIGH | Exponential backoff, queue management |
| YouTube URL access fails | HIGH | MEDIUM | Fallback to video download (yt-dlp) |
| Cost overruns | HIGH | LOW | Strict budget enforcement, estimation |
| False positives | MEDIUM | MEDIUM | Prompt iteration, manual review |
| PubSub message loss | HIGH | LOW | Dead letter queue, retries |
| Long video timeouts | MEDIUM | MEDIUM | Async processing, chunking |

---

## ✅ Definition of Done

Epic 002 is **COMPLETE** when:

1. ✅ Vision-analyzer-service deployed to production
2. ✅ Analyzing 2,000+ videos/day
3. ✅ Budget utilization >95% (€228+/€240)
4. ✅ Cost per video: $0.003-0.09 (validated)
5. ✅ Infringement detection: >15% hit rate
6. ✅ False positive rate: <5%
7. ✅ Feedback loop working (risk scores update)
8. ✅ Monitoring/alerting operational
9. ✅ Documentation complete
10. ✅ All tests passing (>80% coverage)

---

## 📚 References

- [Gemini API Video Understanding](https://ai.google.dev/gemini-api/docs/video-understanding)
- [google-genai SDK Documentation](https://github.com/googleapis/python-genai)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
- [17 U.S.C. § 107 - Fair Use](https://www.copyright.gov/title17/92chap1.html#107)
- [DMCA Takedown Process](https://www.copyright.gov/512/)

---

**Next Steps:**
1. Review this plan with team
2. Refine story estimates
3. Start with Story 4.1 (Infrastructure Setup)
4. Deploy iteratively (4.1→4.2→4.3→4.4 core path first)
