# STORY-006: Vision Service Configuration Integration

**Epic:** Vision Analyzer Service Enhancement
**Status:** Planning
**Priority:** HIGH
**Estimated Effort:** 4-6 hours

## Objective

Integrate the IP-specific configuration system into the vision-analyzer-service so that Gemini analysis uses the actual configured keywords, characters, visual markers, and filters for each IP instead of hardcoded values.

## Current State

The vision-analyzer-service currently uses **hardcoded Justice League configuration** in the Gemini prompt:

```python
# services/vision-analyzer-service/app/core/video_analyzer.py
TARGET_CHARACTERS = ["Superman", "Batman", "Wonder Woman", ...]  # HARDCODED
```

**Problems:**
1. ❌ Only works for Justice League
2. ❌ Cannot handle multiple IPs (Disney, Marvel, etc.)
3. ❌ No use of AI-generated configurations from config-generator
4. ❌ Cannot leverage user-customized keywords, visual markers, or false positive filters

## Desired State

Vision analyzer should:
1. ✅ Load configuration from Firestore based on video's IP
2. ✅ Use IP-specific characters, visual keywords, AI patterns
3. ✅ Apply false positive filters to avoid wasting budget
4. ✅ Support multiple IPs in the same scan queue
5. ✅ Videos tagged with multiple IPs should analyze against all relevant configs

## Architecture Changes

### 1. Add Configuration Loading

**File:** `services/vision-analyzer-service/app/core/config_loader.py` (NEW)

```python
from google.cloud import firestore
from typing import Optional
from dataclasses import dataclass

@dataclass
class IPConfig:
    """IP-specific configuration for vision analysis."""
    id: str
    name: str
    owner: str
    characters: list[str]
    visual_keywords: list[str]
    ai_tool_patterns: list[str]
    false_positive_filters: list[str]
    common_video_titles: list[str]

class ConfigLoader:
    """Loads IP configurations from Firestore."""

    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        self._cache = {}  # Simple in-memory cache

    def get_config(self, ip_id: str) -> Optional[IPConfig]:
        """Get configuration for a specific IP."""
        if ip_id in self._cache:
            return self._cache[ip_id]

        doc = self.db.collection('ip_configs').document(ip_id).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        config = IPConfig(
            id=doc.id,
            name=data.get('name'),
            owner=data.get('owner'),
            characters=data.get('characters', []),
            visual_keywords=data.get('visual_keywords', []),
            ai_tool_patterns=data.get('ai_tool_patterns', []),
            false_positive_filters=data.get('false_positive_filters', []),
            common_video_titles=data.get('common_video_titles', [])
        )

        self._cache[ip_id] = config
        return config

    def get_all_configs(self) -> list[IPConfig]:
        """Get all IP configurations (for multi-IP videos)."""
        configs = []
        docs = self.db.collection('ip_configs').stream()
        for doc in docs:
            data = doc.to_dict()
            configs.append(IPConfig(
                id=doc.id,
                name=data.get('name'),
                owner=data.get('owner'),
                characters=data.get('characters', []),
                visual_keywords=data.get('visual_keywords', []),
                ai_tool_patterns=data.get('ai_tool_patterns', []),
                false_positive_filters=data.get('false_positive_filters', []),
                common_video_titles=data.get('common_video_titles', [])
            ))
        return configs
```

### 2. Update Video Model

**File:** `services/vision-analyzer-service/app/models.py`

Add IP tracking to video metadata:

```python
class VideoMetadata:
    video_id: str
    youtube_url: str
    title: str
    description: str
    duration_seconds: int
    matched_ips: list[str]  # NEW: List of IP config IDs this video matches
    # ... existing fields
```

### 3. Update Gemini Prompt Builder

**File:** `services/vision-analyzer-service/app/core/video_analyzer.py`

Replace hardcoded characters with dynamic config:

```python
def create_analysis_prompt(video_metadata: VideoMetadata, configs: list[IPConfig]) -> str:
    """
    Create Gemini prompt using actual IP configurations.

    Args:
        video_metadata: Video to analyze
        configs: List of IP configs this video might match (can be multiple)
    """

    # If video matches multiple IPs, analyze against all
    if len(configs) > 1:
        return create_multi_ip_prompt(video_metadata, configs)

    config = configs[0]

    # Format character list
    char_bullets = '\n'.join(f"- {char}" for char in config.characters)

    # Format visual keywords
    visual_bullets = '\n'.join(f"- {kw}" for kw in config.visual_keywords)

    # Format AI patterns
    ai_pattern_bullets = '\n'.join(f"- {pattern}" for pattern in config.ai_tool_patterns)

    # Format false positive filters
    fp_filters = ', '.join(config.false_positive_filters)

    prompt = f"""Analyze this YouTube video for AI-generated copyright infringement of {config.owner}'s "{config.name}" intellectual property.

⚠️ CRITICAL: ONLY These Specific Characters Are Relevant ⚠️

TARGET CHARACTERS ({config.name} ONLY):
{char_bullets}

❌ IGNORE ALL OTHER CHARACTERS - even from the same company!

🚫 FAST REJECTION:
If video contains ONLY characters NOT in target list → Return fast rejection.

VISUAL DETECTION MARKERS (use for confirmation):
{visual_bullets}

AI TOOL PATTERNS TO DETECT:
{ai_pattern_bullets}

FALSE POSITIVE INDICATORS (if present, likely NOT infringement):
{fp_filters}

DETECTION CRITERIA:

1. **Character Verification (FIRST STEP)**:
   - Are ANY of the target characters present?
   - If NO → Fast rejection
   - If YES → Continue analysis

2. **AI-Generated Content Detection**:
   - Look for: {', '.join(config.ai_tool_patterns[:5])}
   - Check title/description for AI mentions
   - Identify AI artifacts in video

3. **False Positive Check**:
   - Does title/description contain: {fp_filters}?
   - If YES → Likely not infringement (toys, reviews, etc.)

4. **Infringement Assessment**:
   - Is this AI-generated unauthorized use of {config.name} characters?
   - Is it commercial/monetized?
   - Is it substantial use (>10 seconds)?

RESPOND IN JSON:
{{
  "contains_infringement": true/false,
  "confidence": 0-100,
  "is_ai_generated": true/false,
  "ai_tools_detected": [...],
  "characters_detected": [
    {{
      "name": "character_name",
      "screen_time_seconds": 45,
      "prominence": "high|medium|low",
      "context": "description"
    }}
  ],
  "video_type": "full_ai_movie|ai_clips|trailer|real_footage|cosplay|review|toys|other",
  "infringement_likelihood": 0-100,
  "reasoning": "Detailed explanation",
  "recommended_action": "flag|monitor|ignore"
}}

Remember: ONLY {config.name} characters matter. Use visual keywords and AI patterns for detection."""

    return prompt


def create_multi_ip_prompt(video_metadata: VideoMetadata, configs: list[IPConfig]) -> str:
    """
    Create prompt for videos that might match MULTIPLE IPs.
    Example: Video has both Superman (DC) and Spider-Man (Marvel).
    """

    all_configs_text = []
    for config in configs:
        char_list = ', '.join(config.characters)
        all_configs_text.append(f"""
IP: {config.name} ({config.owner})
Characters: {char_list}
Visual markers: {', '.join(config.visual_keywords[:5])}
""")

    prompt = f"""Analyze this YouTube video for AI-generated copyright infringement.

This video may contain characters from MULTIPLE IPs:

{chr(10).join(all_configs_text)}

For EACH IP present, analyze separately and return results.

RESPOND IN JSON:
{{
  "ip_results": [
    {{
      "ip_id": "justice-league",
      "ip_name": "Justice League",
      "contains_infringement": true/false,
      "characters_detected": [...],
      "infringement_likelihood": 0-100,
      "reasoning": "..."
    }},
    ...
  ],
  "overall_recommendation": "flag|monitor|ignore"
}}
"""
    return prompt
```

### 4. Update Worker to Load Configs

**File:** `services/vision-analyzer-service/app/worker.py`

```python
from app.core.config_loader import ConfigLoader

async def process_video_for_analysis(message_data: dict):
    """Process a single video from scan-ready queue."""

    video_id = message_data['video_id']
    matched_ips = message_data.get('matched_ips', [])  # List of IP IDs

    # Load configurations for all matched IPs
    config_loader = ConfigLoader(firestore_client)
    configs = []
    for ip_id in matched_ips:
        config = config_loader.get_config(ip_id)
        if config:
            configs.append(config)

    if not configs:
        logger.warning(f"No configs found for video {video_id}, using default")
        # Fallback to Justice League (backward compatibility)
        configs = [config_loader.get_config('justice-league')]

    # Analyze with loaded configs
    result = await video_analyzer.analyze_video(
        video_url=message_data['youtube_url'],
        video_metadata=message_data,
        configs=configs
    )

    # Save results
    await save_analysis_results(video_id, result, configs)
```

## Data Flow Changes

### Current Flow:
```
1. discovery-service finds video → publishes to discovered-videos
2. risk-analyzer-service scores video → publishes to scan-ready
3. vision-analyzer-service analyzes with HARDCODED config
```

### New Flow:
```
1. discovery-service finds video → tags with matched_ips: ['justice-league'] → publishes
2. risk-analyzer-service scores video → keeps matched_ips → publishes
3. vision-analyzer-service:
   a. Reads matched_ips from message
   b. Loads configs from Firestore for each IP
   c. Creates prompt with actual config data
   d. Analyzes video
   e. Saves results per IP
```

## Firestore Schema

**Collection:** `ip_configs`

**Document ID:** `justice-league`, `marvel-cinematic-universe`, etc.

**Document Structure:**
```json
{
  "id": "justice-league",
  "name": "Justice League",
  "owner": "Warner Bros. Entertainment Inc.",
  "type": "franchise",
  "tier": "1",
  "priority": "high",

  "characters": [
    "Superman",
    "Batman",
    "Wonder Woman",
    "Flash",
    "Aquaman",
    "Cyborg",
    "Green Lantern"
  ],

  "search_keywords": [
    "justice league ai generated",
    "superman sora ai",
    "batman runway generated",
    ...
  ],

  "visual_keywords": [
    "red cape",
    "S shield",
    "bat symbol",
    "lasso of truth",
    "trident",
    ...
  ],

  "ai_tool_patterns": [
    "sora justice league",
    "runway superman",
    "ai generated batman",
    ...
  ],

  "common_video_titles": [
    "Justice League AI Movie",
    "Superman vs Batman - AI Generated",
    ...
  ],

  "false_positive_filters": [
    "toy",
    "review",
    "unboxing",
    "cosplay",
    "gameplay",
    "official",
    "trailer",
    "licensed"
  ],

  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

## Multi-IP Video Handling

**Scenario:** Video contains both Superman (DC) AND Spider-Man (Marvel)

### Discovery Phase:
```python
# discovery-service finds video
matched_ips = []

# Check against all configs
for config in all_configs:
    if video_matches_ip(video, config):
        matched_ips.append(config.id)

# Result: matched_ips = ['justice-league', 'marvel-cinematic-universe']

publish_to_pubsub({
    'video_id': 'abc123',
    'matched_ips': matched_ips,  # MULTIPLE IPs
    ...
})
```

### Vision Analysis Phase:
```python
# vision-analyzer-service
configs = [
    config_loader.get_config('justice-league'),
    config_loader.get_config('marvel-cinematic-universe')
]

# Use multi-IP prompt
prompt = create_multi_ip_prompt(video_metadata, configs)

# Gemini returns separate analysis for EACH IP
result = {
    "ip_results": [
        {
            "ip_id": "justice-league",
            "contains_infringement": true,
            "characters_detected": ["Superman"],
            "infringement_likelihood": 85
        },
        {
            "ip_id": "marvel-cinematic-universe",
            "contains_infringement": true,
            "characters_detected": ["Spider-Man"],
            "infringement_likelihood": 90
        }
    ]
}

# Save MULTIPLE infringement records (one per IP)
```

## Implementation Steps

### Phase 1: Config Loading (1-2 hours)
- [ ] Create `config_loader.py` with ConfigLoader class
- [ ] Add IPConfig dataclass
- [ ] Implement caching mechanism
- [ ] Add tests for config loading

### Phase 2: Update Models (30 mins)
- [ ] Add `matched_ips` field to VideoMetadata
- [ ] Update PubSub message schema
- [ ] Migration plan for existing videos

### Phase 3: Update Prompt Builder (2 hours)
- [ ] Refactor `create_analysis_prompt()` to use IPConfig
- [ ] Create `create_multi_ip_prompt()` for multi-IP videos
- [ ] Remove all hardcoded values
- [ ] Test prompts with different configs

### Phase 4: Update Worker (1 hour)
- [ ] Load configs in worker
- [ ] Handle missing configs (fallback)
- [ ] Support multi-IP analysis
- [ ] Update result saving logic

### Phase 5: Testing (1-2 hours)
- [ ] Unit tests for ConfigLoader
- [ ] Integration tests with Firestore emulator
- [ ] Test single-IP videos
- [ ] Test multi-IP videos
- [ ] Test missing/invalid configs

### Phase 6: Deployment (30 mins)
- [ ] Deploy to dev environment
- [ ] Verify config loading works
- [ ] Monitor Gemini API costs
- [ ] Deploy to production

## Testing Strategy

### Unit Tests
```python
def test_config_loader_single_ip():
    """Test loading a single IP config."""
    loader = ConfigLoader(firestore_client)
    config = loader.get_config('justice-league')

    assert config.name == 'Justice League'
    assert 'Superman' in config.characters
    assert 'bat symbol' in config.visual_keywords

def test_prompt_builder_with_config():
    """Test prompt uses config values."""
    config = IPConfig(
        id='test',
        name='Test IP',
        characters=['Hero1', 'Hero2'],
        visual_keywords=['keyword1'],
        ...
    )

    prompt = create_analysis_prompt(video_metadata, [config])

    assert 'Hero1' in prompt
    assert 'Hero2' in prompt
    assert 'keyword1' in prompt

def test_multi_ip_prompt():
    """Test multi-IP video analysis."""
    configs = [
        config_loader.get_config('justice-league'),
        config_loader.get_config('marvel-cinematic-universe')
    ]

    prompt = create_multi_ip_prompt(video_metadata, configs)

    assert 'Justice League' in prompt
    assert 'Marvel' in prompt
```

### Integration Tests
```python
def test_end_to_end_with_real_config():
    """Test full flow with Firestore config."""
    # Create test config in Firestore
    firestore_client.collection('ip_configs').document('test-ip').set({
        'name': 'Test IP',
        'characters': ['TestChar1', 'TestChar2'],
        ...
    })

    # Simulate video analysis
    result = analyze_video_with_config('test-video-id', ['test-ip'])

    # Verify prompt used config values
    assert result.used_config == 'test-ip'
```

## Backward Compatibility

**Migration Strategy:**

1. **Default to Justice League** if no `matched_ips` in message
2. **Gradual rollout**: New videos get `matched_ips`, old videos use default
3. **No data loss**: Existing scan queue continues working

```python
# Fallback logic in worker
if not matched_ips:
    logger.info(f"No matched_ips for {video_id}, using default")
    matched_ips = ['justice-league']  # Backward compatible
```

## Success Metrics

- ✅ Vision analyzer can handle multiple IP configs
- ✅ No hardcoded character lists
- ✅ False positive filters reduce wasted budget by 10-15%
- ✅ Multi-IP videos analyzed correctly
- ✅ Config changes in UI immediately affect analysis
- ✅ No increase in Gemini API costs

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Config not found in Firestore | HIGH | Fallback to default config, log warning |
| Multi-IP videos cost more | MEDIUM | Limit to max 3 IPs per video |
| Cache invalidation issues | LOW | TTL-based cache (5 min) |
| Prompt too long with many IPs | MEDIUM | Truncate or split analysis |

## Future Enhancements

1. **Config versioning**: Track changes to configs over time
2. **A/B testing**: Test different prompt variations per IP
3. **Auto-tuning**: Adjust configs based on false positive rate
4. **Config templates**: Reusable templates for similar IPs

---

## ⚠️ CRITICAL - DO NOT FORGET

### 1. PubSub Message Schema Updates

**MUST UPDATE** all services that publish to `discovered-videos` and `scan-ready` topics:

#### Discovery Service Changes
**File:** `services/discovery-service/app/core/video_processor.py`

```python
# ADD matched_ips to published message
def publish_video(video_data):
    message = {
        'video_id': video_data['id'],
        'youtube_url': video_data['url'],
        'title': video_data['title'],
        'description': video_data['description'],
        'matched_ips': ['justice-league'],  # ⚠️ NEW FIELD - CRITICAL!
        # ... existing fields
    }
    publisher.publish('discovered-videos', message)
```

#### Risk Analyzer Service Changes
**File:** `services/risk-analyzer-service/app/worker.py`

```python
# MUST PRESERVE matched_ips when republishing
def republish_to_scan_ready(video_data, risk_score):
    message = {
        'video_id': video_data['video_id'],
        'youtube_url': video_data['youtube_url'],
        'matched_ips': video_data['matched_ips'],  # ⚠️ PRESERVE - CRITICAL!
        'risk_score': risk_score,
        # ... existing fields
    }
    publisher.publish('scan-ready', message)
```

**IF YOU FORGET THIS**: Vision analyzer won't know which IP configs to load!

---

### 2. Firestore Indexes

**MUST CREATE** composite index for multi-IP queries:

```bash
# Create index for querying videos by multiple IPs
gcloud firestore indexes composite create \
  --collection-group=videos \
  --field-config field-path=matched_ips,array-config=contains \
  --field-config field-path=scan_status,order=ascending
```

**OR** add to `firestore.indexes.json`:

```json
{
  "indexes": [
    {
      "collectionGroup": "videos",
      "queryScope": "COLLECTION",
      "fields": [
        {
          "fieldPath": "matched_ips",
          "arrayConfig": "CONTAINS"
        },
        {
          "fieldPath": "scan_status",
          "order": "ASCENDING"
        }
      ]
    }
  ]
}
```

**IF YOU FORGET THIS**: Queries for videos by IP will fail or be slow!

---

### 3. Environment Variables

**MUST ADD** to all service configs:

**File:** `services/vision-analyzer-service/terraform/main.tf`

```hcl
env {
  name  = "IP_CONFIG_COLLECTION"
  value = "ip_configs"
}

env {
  name  = "CONFIG_CACHE_TTL_SECONDS"
  value = "300"  # 5 minutes
}

env {
  name  = "MAX_IPS_PER_VIDEO"
  value = "3"  # Prevent prompt explosion
}
```

**IF YOU FORGET THIS**: Config loader won't know where to find configs!

---

### 4. IAM Permissions

**MUST GRANT** Firestore read access to vision-analyzer service account:

```bash
# Grant read access to ip_configs collection
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:vision-analyzer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

**OR** in Terraform:

```hcl
resource "google_project_iam_member" "vision_analyzer_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.vision_analyzer.email}"
}
```

**IF YOU FORGET THIS**: Vision analyzer can't read configs from Firestore!

---

### 5. Default Config Seed Data

**MUST SEED** at least one default config in Firestore:

**File:** `scripts/seed-default-configs.py` (NEW)

```python
#!/usr/bin/env python3
"""Seed default IP configs to Firestore."""

from google.cloud import firestore

def seed_justice_league_config():
    """Create default Justice League config."""
    db = firestore.Client()

    db.collection('ip_configs').document('justice-league').set({
        'id': 'justice-league',
        'name': 'Justice League',
        'owner': 'Warner Bros. Entertainment Inc.',
        'type': 'franchise',
        'tier': '1',
        'priority': 'high',
        'characters': [
            'Superman',
            'Batman',
            'Wonder Woman',
            'Flash',
            'Aquaman',
            'Cyborg',
            'Green Lantern'
        ],
        'search_keywords': [
            'justice league ai generated',
            'superman sora',
            'batman runway',
            # ... add more
        ],
        'visual_keywords': [
            'red cape',
            'S shield',
            'bat symbol',
            'lasso of truth',
            # ... add more
        ],
        'ai_tool_patterns': [
            'sora',
            'runway',
            'kling',
            'pika',
            'ai generated',
        ],
        'common_video_titles': [
            'Justice League AI Movie',
            'Superman AI Generated',
        ],
        'false_positive_filters': [
            'toy',
            'review',
            'unboxing',
            'cosplay',
            'gameplay',
            'official',
            'trailer',
            'licensed',
            'tutorial',
            'analysis',
            'commentary',
            'parody'
        ],
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP
    })

    print("✅ Seeded Justice League config")

if __name__ == '__main__':
    seed_justice_league_config()
```

**RUN THIS** before deploying:

```bash
# Seed configs to dev
python scripts/seed-default-configs.py

# Seed configs to prod
GCP_PROJECT=copycat-prod python scripts/seed-default-configs.py
```

**IF YOU FORGET THIS**: No configs exist, all analyses will fail!

---

### 6. Update BigQuery Schema

**MUST ADD** `matched_ips` column to results table:

**File:** `terraform/bigquery.tf`

```hcl
resource "google_bigquery_table" "vision_analysis_results" {
  # ... existing config

  schema = jsonencode([
    # ... existing fields
    {
      name = "matched_ips"
      type = "STRING"
      mode = "REPEATED"  # Array of IP IDs
      description = "List of IP configs this video was analyzed against"
    },
    {
      name = "ip_results"
      type = "RECORD"
      mode = "REPEATED"
      description = "Analysis results per IP (for multi-IP videos)"
      fields = [
        {name = "ip_id", type = "STRING"},
        {name = "ip_name", type = "STRING"},
        {name = "contains_infringement", type = "BOOLEAN"},
        {name = "infringement_likelihood", type = "INTEGER"},
        {name = "characters_detected", type = "STRING", mode = "REPEATED"}
      ]
    }
  ])
}
```

**IF YOU FORGET THIS**: Can't save multi-IP results to BigQuery!

---

### 7. Cache Invalidation Strategy

**MUST IMPLEMENT** cache invalidation when configs change:

**File:** `services/vision-analyzer-service/app/core/config_loader.py`

```python
class ConfigLoader:
    def __init__(self, firestore_client):
        self.db = firestore_client
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_ttl = int(os.getenv('CONFIG_CACHE_TTL_SECONDS', '300'))

    def get_config(self, ip_id: str) -> Optional[IPConfig]:
        """Get config with TTL-based cache invalidation."""
        now = time.time()

        # Check if cached and not expired
        if ip_id in self._cache:
            cache_time = self._cache_timestamps.get(ip_id, 0)
            if now - cache_time < self.cache_ttl:
                return self._cache[ip_id]

        # Load from Firestore
        config = self._load_from_firestore(ip_id)

        # Update cache
        self._cache[ip_id] = config
        self._cache_timestamps[ip_id] = now

        return config

    def invalidate_cache(self, ip_id: str = None):
        """Manually invalidate cache (call after config updates)."""
        if ip_id:
            self._cache.pop(ip_id, None)
            self._cache_timestamps.pop(ip_id, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
```

**IF YOU FORGET THIS**: Changes in config UI won't take effect for 5+ minutes!

---

### 8. Error Handling for Missing Configs

**MUST HANDLE** gracefully when config doesn't exist:

**File:** `services/vision-analyzer-service/app/worker.py`

```python
# Load configs with fallback
configs = []
for ip_id in matched_ips:
    config = config_loader.get_config(ip_id)
    if config:
        configs.append(config)
    else:
        logger.error(f"⚠️ Config not found for IP: {ip_id}")

if not configs:
    # CRITICAL: Don't fail - use default
    logger.warning(f"No valid configs for {video_id}, using fallback")
    default_config = config_loader.get_config('justice-league')
    if default_config:
        configs = [default_config]
    else:
        # LAST RESORT: Skip this video, republish for retry
        logger.error(f"❌ No default config available, skipping {video_id}")
        publish_to_dead_letter(message_data, "No configs available")
        return
```

**IF YOU FORGET THIS**: Service crashes when config is missing!

---

### 9. Monitoring & Alerts

**MUST ADD** monitoring for config-related issues:

**Metrics to track:**
- `config_load_failures` - Config not found in Firestore
- `config_cache_hit_rate` - Cache effectiveness
- `multi_ip_video_count` - Videos with multiple IPs
- `default_config_fallback_count` - How often we fall back

**File:** `services/vision-analyzer-service/app/core/config_loader.py`

```python
from prometheus_client import Counter, Histogram

config_load_failures = Counter('config_load_failures', 'Config not found', ['ip_id'])
config_cache_hits = Counter('config_cache_hits', 'Cache hit/miss', ['hit'])
multi_ip_videos = Counter('multi_ip_videos', 'Videos with multiple IPs')

class ConfigLoader:
    def get_config(self, ip_id: str) -> Optional[IPConfig]:
        # ... cache check
        if ip_id in self._cache:
            config_cache_hits.labels(hit='true').inc()
            return self._cache[ip_id]

        config_cache_hits.labels(hit='false').inc()

        # ... load from Firestore
        if not config:
            config_load_failures.labels(ip_id=ip_id).inc()
            logger.error(f"Config not found: {ip_id}")

        return config
```

**IF YOU FORGET THIS**: No visibility when things go wrong!

---

### 10. Update API Service Config Endpoints

**MUST ENSURE** API service has endpoints to support vision analyzer:

**File:** `services/api-service/app/routers/config.py`

```python
@router.get("/config/{ip_id}")
async def get_config(ip_id: str):
    """
    Get a specific IP configuration.
    Used by vision-analyzer-service to load configs.
    """
    doc = firestore_client.collection('ip_configs').document(ip_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Config {ip_id} not found")

    return doc.to_dict()

@router.get("/config/list")
async def list_configs():
    """
    List all IP configurations.
    Used for multi-IP matching.
    """
    configs = []
    docs = firestore_client.collection('ip_configs').stream()
    for doc in docs:
        configs.append({
            'id': doc.id,
            **doc.to_dict()
        })
    return {'configs': configs}
```

**IF YOU FORGET THIS**: Vision analyzer might load stale data!

---

### 11. Update Discovery Service IP Matching

**MUST UPDATE** discovery service to detect which IPs a video matches:

**File:** `services/discovery-service/app/core/video_processor.py`

```python
def match_video_to_ips(video_data: dict) -> list[str]:
    """
    Determine which IP configs this video matches.
    Checks title, description, and keywords.
    """
    matched_ips = []

    # Load all IP configs
    all_configs = firestore_client.collection('ip_configs').stream()

    for config_doc in all_configs:
        config = config_doc.to_dict()
        ip_id = config_doc.id

        # Check if video mentions any characters
        title_lower = video_data['title'].lower()
        desc_lower = video_data.get('description', '').lower()

        for character in config.get('characters', []):
            if character.lower() in title_lower or character.lower() in desc_lower:
                matched_ips.append(ip_id)
                break  # One match is enough

    # Default to Justice League if nothing matches (backward compatible)
    if not matched_ips:
        matched_ips = ['justice-league']

    return matched_ips
```

**IF YOU FORGET THIS**: All videos get tagged as justice-league!

---

### 12. Testing with Emulator

**MUST TEST** with Firestore emulator before deploying:

```bash
# Start Firestore emulator
gcloud beta emulators firestore start --host-port=localhost:8200

# In another terminal, set env var
export FIRESTORE_EMULATOR_HOST=localhost:8200

# Seed test data
python scripts/seed-default-configs.py

# Run tests
cd services/vision-analyzer-service
uv run pytest tests/ -v

# Test config loading
uv run python -c "
from app.core.config_loader import ConfigLoader
from google.cloud import firestore
loader = ConfigLoader(firestore.Client())
config = loader.get_config('justice-league')
print(f'✅ Loaded config: {config.name}')
print(f'✅ Characters: {config.characters}')
"
```

**IF YOU FORGET THIS**: Production bugs that could have been caught!

---

### 13. Documentation Updates

**MUST UPDATE** these docs:

1. **CLAUDE.md** - Add section on IP config system
2. **README.md** - Update architecture diagram
3. **API docs** - Document config endpoints
4. **Deployment guide** - Add config seeding step

**IF YOU FORGET THIS**: Team won't know how the system works!

---

## Pre-Deployment Checklist

Before deploying STORY-006, verify:

- [ ] PubSub message schema updated in ALL services (discovery, risk-analyzer, vision-analyzer)
- [ ] Firestore indexes created (`firestore.indexes.json` deployed)
- [ ] Environment variables added to Terraform configs
- [ ] IAM permissions granted (vision-analyzer can read Firestore)
- [ ] Default configs seeded to Firestore (dev AND prod)
- [ ] BigQuery schema updated with `matched_ips` and `ip_results`
- [ ] Cache invalidation implemented with TTL
- [ ] Error handling for missing configs
- [ ] Monitoring/metrics added
- [ ] API endpoints for config retrieval exist
- [ ] Discovery service matches videos to IPs
- [ ] Tests pass with Firestore emulator
- [ ] Documentation updated

**DO NOT DEPLOY** until all checkboxes are ✅
