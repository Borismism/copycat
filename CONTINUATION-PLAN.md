# Continuation Plan - Pipeline Testing Flow

## Current State (2025-11-03 21:40)

### ✅ What's Complete:

1. **Story 006 Implementation - Config-Based System**
   - ✅ Created `config_loader.py` with IPConfig and ConfigLoader classes
   - ✅ Updated models to include `matched_ips` field
   - ✅ Refactored prompt_builder to use dynamic IP configs
   - ✅ Created multi-IP prompt builder for videos matching multiple IPs
   - ✅ Updated worker.py to load configs from Firestore
   - ✅ Fixed all update handlers to work in "preview mode" (before config is saved)

2. **Cleaned Up Old System**
   - ✅ Deleted `ip_targets.yaml` and all backup versions
   - ✅ Removed `ip_loader.py` completely
   - ✅ Removed `fresh_content_scanner.py` (was based on old system)
   - ✅ Removed all references to `IPTargetManager`
   - ✅ Deleted sync_keywords_from_ip_targets() method
   - ✅ Empty `keywords` collection in Firestore (0 hardcoded keywords)

3. **Fixed Config Saving**
   - ✅ Changed API service to save to `ip_configs` collection (was `ip_targets`)
   - ✅ Updated all PATCH endpoints to use `ip_configs`
   - ✅ Frontend edit interface shows immediately after generation

4. **Wired Discovery to IP Configs**
   - ✅ Updated `keyword_tracker.get_keywords_due_for_scan()` to load from `ip_configs.search_keywords`
   - ✅ Removed old rotation/tracking logic
   - ✅ Discovery now loads keywords dynamically from user-created IP configs

5. **Fixed API Issues**
   - ✅ Fixed CORS errors (API service was crashing on Gemini init)
   - ✅ Fixed Gemini client to use `GEMINI_PROJECT_ID` env var explicitly
   - ✅ Updated YouTube API key to correct value: `AIzaSyAjnn_zT-vx3nevxwF35mAZmnE4oZvOI6w`

6. **Environment Configuration**
   - ✅ Clean project ID naming:
     - `GCP_PROJECT_ID=copycat-local` (for emulators)
     - `YOUTUBE_PROJECT_ID=boris-demo-453408` (for YouTube API)
     - `GEMINI_PROJECT_ID=copycat-429012` (for Vertex AI/Gemini)
   - ✅ Firestore is persistent (docker volume)
   - ✅ All services use correct env vars

7. **User Created IP Config**
   - ✅ User created "DC Universe" config via frontend
   - ✅ Config saved to `ip_configs` collection in Firestore
   - ✅ Has 24 search keywords
   - ✅ Discovery service successfully loads keywords from this config

### 🔄 Current Status:

**Discovery Service:**
- Loads 24 keywords from 1 IP config ✅
- Has quota allocation: Tier3 gets 200 units (20% of 1000, + rollover from unused Tier1/2)
- Default max_quota for /discover/run endpoint: **500**
- YouTube API key is correct
- Ready to test

**Services Running:**
- discovery-service ✅
- risk-analyzer-service ✅
- vision-analyzer-service ✅
- api-service ✅
- frontend-service ✅
- firestore emulator ✅
- pubsub emulator ✅

## 🎯 Next Steps - Testing the Pipeline

### Step 1: Test Discovery
```bash
# Restart discovery service to pick up code changes
docker-compose restart discovery-service
sleep 5

# Trigger discovery with 500 quota
curl -X POST 'http://localhost:8081/discover/run' \
  -H 'Content-Type: application/json' \
  -d '{}' | jq .

# Check logs
docker-compose logs discovery-service --tail=30

# Expected: Should discover videos using DC Universe keywords
# Should see "Loaded 24 keywords from 1 IP configs"
# Should see quota_used > 0
# Should see videos_discovered > 0
```

### Step 2: Check PubSub Messages
```bash
# Check if videos were published to discovered-videos topic
gcloud pubsub topics list --project=copycat-local
gcloud pubsub subscriptions pull discovered-videos-sub --auto-ack --limit=5
```

### Step 3: Test Risk Analyzer
```bash
# Risk analyzer should automatically process messages from discovered-videos
docker-compose logs risk-analyzer-service --tail=30

# Check Firestore for videos
curl 'http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos' | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin), indent=2))"

# Expected: Videos should have risk scores and be published to scan-ready topic
```

### Step 4: Test Vision Analyzer
```bash
# Vision analyzer should process from scan-ready topic
docker-compose logs vision-analyzer-service --tail=50

# Expected: Should load IP config and analyze videos with Gemini
# Should see "Loaded config for dc-universe"
```

### Step 5: End-to-End Verification
```bash
# Check complete flow in Firestore
# Videos collection should have:
# - status: discovered → risk_scored → scanned
# - matched_ips: ["dc-universe"]
# - risk_score: 0-100
# - gemini_result: {...}
```

## ✅ Fixed: Keyword Generation Efficiency (2025-11-03 21:45)

**Problem:** First test showed poor efficiency - 500 quota for only 24 videos (21 units/video)
- Only 4 keywords searched out of 24 available
- Keywords were too specific: "batman ai generated", "superman runway ai"
- Each keyword returned only 6 videos instead of 30-50

**Root Cause:** Gemini prompt was explicitly telling it to generate narrow keywords like:
- "{{character}} sora"
- "{{character}} runway ai"
- "{{character}} kling"

**Fix Applied:**
Updated `app/routers/config_ai_assistant.py` prompt to:
1. ✅ Generate BROAD keywords ("batman ai" instead of "batman sora")
2. ✅ Explicitly avoid tool-specific keywords in search_keywords
3. ✅ Target 30-50 videos per keyword
4. ✅ Added cost awareness guidelines
5. ✅ Clarified: ai_tool_patterns are for DETECTION, not discovery

**Expected Results After Fix:**
- Keywords like: "batman ai", "superman ai movie", "dc universe ai"
- NOT: "batman sora", "superman runway ai", "joker kling"
- Each keyword should return 30-50 videos
- Efficiency: 2-4 units/video (vs 21 units/video before)

**Action Required:**
🔴 **Delete your current DC Universe config and regenerate it with the fixed prompt!**
The new keywords will be much more efficient.

## 🐛 Known Issues to Watch For

### Issue 1: Discovery Returns 0 Videos
**Symptoms:** quota_used=0, videos_discovered=0
**Possible Causes:**
- YouTube API quota exhausted
- Keywords too specific (no matching videos)
- YouTube API key invalid
- Tier3 quota too low (check if < 101)

**Debug:**
```bash
docker-compose logs discovery-service --tail=50 | grep -E "keyword|quota|Tier 3"
```

### Issue 2: Vision Analyzer Can't Load Config
**Symptoms:** "No valid configs for video"
**Cause:** `matched_ips` field missing or wrong collection name
**Fix:** Check video document has `matched_ips: ["dc-universe"]`

### Issue 3: PubSub Messages Not Flowing
**Symptoms:** Discovery works but risk-analyzer doesn't see messages
**Debug:**
```bash
# Check subscription exists
docker-compose exec pubsub gcloud pubsub subscriptions list

# Check messages in topic
docker-compose exec pubsub gcloud pubsub topics publish discovered-videos --message='{"test":"msg"}'
```

## 📝 Important Files Changed

### Discovery Service:
- `app/core/keyword_tracker.py` - Line 216-250: Now loads from ip_configs
- `app/core/discovery_engine.py` - Line 69: max_quota default changed
- `app/routers/discover.py` - Line 121: max_quota default = 500
- `app/core/video_processor.py` - Line 234-238: Removed IP matching (returns empty list)

### API Service:
- `app/routers/config_validate_characters.py` - Line 196: Changed to ip_configs collection
- `app/routers/config.py` - All references changed from ip_targets → ip_configs
- `app/routers/config_ai_assistant.py` - Lines 247-263, 370-384: Use GEMINI_PROJECT_ID env var

### Vision Analyzer Service:
- `app/core/config_loader.py` - NEW FILE: Loads IP configs from Firestore
- `app/core/prompt_builder.py` - Now accepts list[IPConfig], builds multi-IP prompts
- `app/core/video_analyzer.py` - Requires configs parameter
- `app/worker.py` - Loads configs and passes to analyzer
- `app/models.py` - Added matched_ips, IPSpecificResult

### Frontend:
- `app/web/src/pages/ConfigGeneratorPage.tsx` - Shows edit interface after generation

### Environment:
- `docker-compose.yml` - Updated all GOOGLE_CLOUD_PROJECT → YOUTUBE_PROJECT_ID or GEMINI_PROJECT_ID
- `.env` - Contains correct YouTube API key

## 🔑 Key Concepts

### IP Configs Flow:
1. User creates IP config via frontend (AI-assisted)
2. Config saved to Firestore `ip_configs` collection
3. Discovery loads `search_keywords` from configs
4. Videos discovered have `matched_ips: []` (discovery doesn't match, just discovers all)
5. Vision analyzer loads appropriate IPConfig when analyzing
6. Multi-IP videos get separate analysis per IP

### No Hardcoded Keywords:
- **0 keywords** in `keywords` collection
- **0 YAML files** with keywords
- **100% dynamic** - all keywords come from user-created IP configs
- If ip_configs collection is empty → 0 keywords → 0 discovery

### Budget Limits:
- Daily YouTube API: 10,000 units (default)
- Daily Gemini: €240 (~$260 USD)
- Discovery quota per run: 500 units (configurable)

## 🚀 Quick Start for New Session

```bash
# 1. Start all services
cd /Users/boris/copycat
docker-compose up -d

# 2. Verify IP config exists
curl -s 'http://localhost:8080/api/config/list' | jq '.configs[] | {id, name}'

# 3. Run discovery
curl -X POST 'http://localhost:8081/discover/run' -d '{}' | jq .

# 4. Monitor flow
docker-compose logs -f discovery-service risk-analyzer-service vision-analyzer-service
```

## 📊 Success Criteria

Discovery successful if:
- ✅ videos_discovered > 0
- ✅ quota_used > 0
- ✅ keywords_scanned > 0
- ✅ Videos published to PubSub

Risk analyzer successful if:
- ✅ Processes discovered-videos messages
- ✅ Adds risk_score to videos
- ✅ Publishes to scan-ready topic

Vision analyzer successful if:
- ✅ Loads IP config from Firestore
- ✅ Builds prompt with config data
- ✅ Calls Gemini successfully
- ✅ Saves analysis results

## 🎬 End Goal

**Complete pipeline test:**
User creates IP config → Discovery finds videos → Risk analyzer scores → Vision analyzer detects infringement → Results stored in Firestore

All with **ZERO hardcoded keywords** and **100% config-driven**.
