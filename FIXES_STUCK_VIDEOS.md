# Stuck Videos Fix - November 7, 2025

## Problem

Videos were getting stuck in "processing" status in production, never completing or failing. This happened when:

1. **Gemini API calls took 150-180+ seconds** (normal for video analysis)
2. **Liveness probe failed after 180 seconds** (3 checks × 60s each)
3. **Cloud Run killed the instance** with 503 error
4. **Firestore never got updated** - video stayed in "processing" forever
5. **PubSub retried endlessly** - same video tried 6+ times

## Root Causes

### 1. Blocking Sleep in Retry Logic
**File:** `services/vision-analyzer-service/app/core/gemini_client.py:192`
- Used `time.sleep(wait_time)` instead of `await asyncio.sleep(wait_time)`
- During rate limit backoff (1s, 8s, 16s, 32s, 64s), the entire event loop froze
- Health check endpoint couldn't respond → Cloud Run killed the instance

### 2. No Timeout Protection
**File:** `services/vision-analyzer-service/app/routers/analyze.py`
- No timeout wrapper around long-running Gemini analysis
- If analysis took >10 minutes, Cloud Run timeout (600s) killed the request
- Exception handler never ran → video status never updated to "failed"

### 3. Liveness Probe Configuration
**File:** `services/vision-analyzer-service/terraform/cloud_run.tf:138-147`
- `timeout_seconds = 5` - Health check must respond in 5 seconds
- `period_seconds = 60` - Checks every 60 seconds
- `failure_threshold = 3` - Fails after 180 seconds total
- During long Gemini calls, health check couldn't respond fast enough

## Fixes Applied

### Fix 1: Non-Blocking Sleep (Deployed)
**File:** `services/vision-analyzer-service/app/core/gemini_client.py`

**Before:**
```python
import time

# In retry logic:
time.sleep(wait_time)  # BLOCKS event loop!
```

**After:**
```python
import asyncio

# In retry logic:
await asyncio.sleep(wait_time)  # Non-blocking!
```

**Impact:** Health check can now respond even during rate limit backoff.

### Fix 2: Timeout Protection (Deployed)
**File:** `services/vision-analyzer-service/app/routers/analyze.py`

**Before:**
```python
result = await video_analyzer.analyze_video(
    video_metadata=scan_message.metadata,
    configs=configs,
    queue_size=1
)
```

**After:**
```python
try:
    result = await asyncio.wait_for(
        video_analyzer.analyze_video(
            video_metadata=scan_message.metadata,
            configs=configs,
            queue_size=1
        ),
        timeout=540  # 9 minutes - leaves 1 minute for cleanup
    )
except asyncio.TimeoutError:
    logger.error(f"Video analysis timed out after 540 seconds")

    # Mark video as failed
    doc_ref.update({
        "status": "failed",
        "error_message": "Analysis timed out after 9 minutes",
        "error_type": "TimeoutError",
        "failed_at": firestore.SERVER_TIMESTAMP
    })

    return {"status": "error", "video_id": video_id, "message": "Analysis timeout"}
```

**Impact:** Videos that take too long now properly fail instead of hanging forever.

### Fix 3: Cleanup Script
**File:** `scripts/fix-stuck-videos.py`

A maintenance script to find and fix videos stuck in "processing" status:

```bash
# Run to fix existing stuck videos
uv run python3 scripts/fix-stuck-videos.py
```

**What it does:**
- Finds videos in "processing" status for >10 minutes
- Marks them as "failed" with error message
- Updates Firestore so they disappear from frontend

## Deployment

Both fixes deployed to production:

```bash
./deploy.sh vision-analyzer-service prod
```

**Deployment timestamp:** November 7, 2025, 08:23 UTC

**New image:**
- `europe-west4-docker.pkg.dev/copycat-429012/copycat-docker/vision-analyzer-service:7a43a50-368a3f55`

## Verification

### Check for stuck videos:
```bash
uv run python3 scripts/fix-stuck-videos.py
```

### Monitor production logs:
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=vision-analyzer-service" \
  --limit 50 --format json --project copycat-429012
```

### Check for timeout errors:
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=vision-analyzer-service AND textPayload=~\"timed out\"" \
  --limit 20 --project copycat-429012
```

## Expected Behavior Now

1. **Health checks always respond quickly** - even during long Gemini calls
2. **Videos that timeout get marked as "failed"** - never stuck forever
3. **Proper error messages in Firestore** - frontend can show why it failed
4. **No more endless PubSub retries** - failed videos return 200 OK

## Future Improvements

1. **Reduce video analysis time:**
   - Lower FPS for very long videos (already implemented in video_config_calculator.py)
   - Skip intro/outro more aggressively
   - Analyze first 10 minutes only for 30+ minute videos

2. **Better progress tracking:**
   - Stream progress updates to Firestore during analysis
   - Show "Processing... 45% complete" in frontend

3. **Automatic retry with lower quality:**
   - If video times out at 1 FPS, retry at 0.5 FPS
   - If still times out, mark as "too_long" instead of "failed"

4. **Monitoring dashboard:**
   - Alert when >5 videos timeout in an hour
   - Track average processing time per video
   - Budget utilization vs video completion rate
