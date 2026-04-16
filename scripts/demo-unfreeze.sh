#!/bin/bash
# ==============================================================================
# DEMO UNFREEZE
# ==============================================================================
# Reverses demo-freeze.sh: resumes scheduler, reattaches PubSub push
# subscriptions, removes DEMO_FROZEN_TIME, restores min_instances=1 on the
# public-facing services (api + frontend), and prompts for frontend rebuild.
# ==============================================================================

set -euo pipefail

GCLOUD=/Users/isaac/google-cloud-sdk/bin/gcloud
PROJECT_ID="${PROJECT_ID:-irdeto-copycat-internal-dev}"
REGION=europe-west4
SCHEDULER_REGION=europe-west1

# Public-facing services that should be always-warm again after unfreeze.
ALWAYS_ON_SERVICES=(api-service frontend-service)
SCHEDULER_JOBS=(daily-stats-aggregation discovery-service-hourly vision-analyzer-cleanup)
PUBSUB_SUBS=(risk-analyzer-video-discovered-sub risk-analyzer-vision-feedback-sub scan-ready-vision-analyzer-sub)

STATE_DIR=/tmp/copycat-demo-freeze

echo "=== UNFREEZING COPYCAT DEMO ==="
echo "Project:  $PROJECT_ID"
echo

echo "[1/4] Removing DEMO_FROZEN_TIME from api-service..."
"$GCLOUD" run services update api-service \
    --project="$PROJECT_ID" --region="$REGION" \
    --remove-env-vars=DEMO_FROZEN_TIME --quiet >/dev/null
echo "  cleared: api-service"

echo
echo "[2/4] Restoring min_instances=1 on public-facing services..."
for svc in "${ALWAYS_ON_SERVICES[@]}"; do
    "$GCLOUD" run services update "$svc" \
        --project="$PROJECT_ID" --region="$REGION" \
        --min-instances=1 --quiet >/dev/null 2>&1 \
        && echo "  warmed: $svc" \
        || echo "  skipped: $svc"
done

echo
echo "[3/4] Reattaching PubSub push subscriptions..."
for sub in "${PUBSUB_SUBS[@]}"; do
    endpoint_file="$STATE_DIR/${sub}.endpoint"
    if [ -f "$endpoint_file" ]; then
        url=$(cat "$endpoint_file")
        "$GCLOUD" pubsub subscriptions modify-push-config "$sub" \
            --project="$PROJECT_ID" --push-endpoint="$url" 2>&1 | sed 's/^/  /'
        echo "  reattached: $sub -> $url"
    else
        echo "  WARN: no saved endpoint for $sub — reattach manually"
    fi
done

echo
echo "[4/4] Resuming Cloud Scheduler jobs..."
for job in "${SCHEDULER_JOBS[@]}"; do
    "$GCLOUD" scheduler jobs resume "$job" \
        --project="$PROJECT_ID" --location="$SCHEDULER_REGION" 2>/dev/null \
        && echo "  resumed: $job" \
        || echo "  skipped: $job"
done

echo
echo "NOTE: Frontend still has frozen clock baked in. Rebuild without it:"
echo
echo "        ./scripts/deploy-frontend-frozen.sh   # unset VITE_DEMO_FROZEN_TIME"
echo
echo "=== LIVE. ==="
