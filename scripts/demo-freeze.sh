#!/bin/bash
# ==============================================================================
# DEMO FREEZE
# ==============================================================================
# Pins the demo site to a fixed moment and kills the ingestion pipeline to
# stop daily costs. Reverse with ./scripts/demo-unfreeze.sh.
#
# What it does:
#   1. Pauses Cloud Scheduler jobs so no new discovery/aggregation runs fire.
#   2. Detaches PubSub push subscriptions so workers never receive messages.
#      (We save the original push endpoint URLs to /tmp so unfreeze restores.)
#   3. Sets min_instances=0 on all Cloud Run services (kills always-on cost).
#   4. Sets DEMO_FROZEN_TIME on api-service so the dashboard shows the frozen
#      clock. Rebuilds frontend with VITE_DEMO_FROZEN_TIME baked in.
# ==============================================================================

set -euo pipefail

GCLOUD=/Users/isaac/google-cloud-sdk/bin/gcloud
PROJECT_ID="${PROJECT_ID:-irdeto-copycat-internal-dev}"
REGION=europe-west4
SCHEDULER_REGION=europe-west1
FROZEN_TIME="${FROZEN_TIME:-2026-04-16T14:26:00Z}"

CLOUD_RUN_SERVICES=(api-service frontend-service discovery-service risk-analyzer-service vision-analyzer-service)
SCHEDULER_JOBS=(daily-stats-aggregation discovery-service-hourly vision-analyzer-cleanup)
PUBSUB_SUBS=(risk-analyzer-video-discovered-sub risk-analyzer-vision-feedback-sub scan-ready-vision-analyzer-sub)

STATE_DIR=/tmp/copycat-demo-freeze
mkdir -p "$STATE_DIR"

echo "=== FREEZING COPYCAT DEMO ==="
echo "Project:  $PROJECT_ID"
echo "Frozen:   $FROZEN_TIME"
echo "State:    $STATE_DIR"
echo

echo "[1/4] Pausing Cloud Scheduler jobs..."
for job in "${SCHEDULER_JOBS[@]}"; do
    "$GCLOUD" scheduler jobs pause "$job" \
        --project="$PROJECT_ID" --location="$SCHEDULER_REGION" 2>/dev/null \
        && echo "  paused: $job" \
        || echo "  skipped: $job (not found or already paused)"
done

echo
echo "[2/4] Detaching PubSub push subscriptions..."
for sub in "${PUBSUB_SUBS[@]}"; do
    url=$("$GCLOUD" pubsub subscriptions describe "$sub" \
        --project="$PROJECT_ID" \
        --format='value(pushConfig.pushEndpoint)' 2>/dev/null || echo "")
    if [ -n "$url" ]; then
        echo "$url" > "$STATE_DIR/${sub}.endpoint"
        "$GCLOUD" pubsub subscriptions modify-push-config "$sub" \
            --project="$PROJECT_ID" --push-endpoint='' 2>&1 | sed 's/^/  /'
        echo "  detached: $sub (saved $url)"
    else
        echo "  skipped: $sub (no push endpoint)"
    fi
done

echo
echo "[3/4] Setting min_instances=0 on all Cloud Run services..."
for svc in "${CLOUD_RUN_SERVICES[@]}"; do
    "$GCLOUD" run services update "$svc" \
        --project="$PROJECT_ID" --region="$REGION" \
        --min-instances=0 --quiet >/dev/null 2>&1 \
        && echo "  scaled-to-zero: $svc" \
        || echo "  skipped: $svc (not found)"
done

echo
echo "[4/4] Setting DEMO_FROZEN_TIME=$FROZEN_TIME on api-service..."
"$GCLOUD" run services update api-service \
    --project="$PROJECT_ID" --region="$REGION" \
    --update-env-vars="DEMO_FROZEN_TIME=$FROZEN_TIME" --quiet >/dev/null
echo "  set: api-service"

echo
echo "NOTE: Frontend needs a rebuild with VITE_DEMO_FROZEN_TIME baked in."
echo "      Run this from repo root:"
echo
echo "        VITE_DEMO_FROZEN_TIME=$FROZEN_TIME ./scripts/deploy-frontend-frozen.sh"
echo
echo "=== FROZEN. unfreeze with: ./scripts/demo-unfreeze.sh ==="
