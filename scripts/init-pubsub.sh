#!/bin/sh
set -e

echo "🚀 Initializing PubSub emulator..."

# Wait for emulator to be ready
echo "⏳ Waiting for PubSub emulator to be ready..."
until curl -s http://pubsub:8086 > /dev/null 2>&1; do
  sleep 1
done
echo "✅ PubSub emulator is ready"

# Use REST API instead of gcloud CLI
EMULATOR_HOST="pubsub:8086"
PROJECT_ID="${PUBSUB_PROJECT_ID:-copycat-local}"

echo "📝 Creating topics..."

# Create topics using REST API
create_topic() {
  local topic=$1
  echo "  Creating topic: $topic"
  curl -s -X PUT "http://${EMULATOR_HOST}/v1/projects/${PROJECT_ID}/topics/${topic}" \
    -H "Content-Type: application/json" \
    -d '{}' > /dev/null 2>&1 && echo "    ✓ Topic $topic created" || echo "    ℹ Topic $topic already exists"
}

create_topic "discovered-videos"
create_topic "scan-ready"
create_topic "risk-scored-videos"
create_topic "frames-extracted"
create_topic "vision-analyzed"
create_topic "discovered-videos-dlq"
create_topic "risk-scored-videos-dlq"

echo ""
echo "📬 Creating subscriptions..."

# Create subscriptions using REST API
create_subscription() {
  local sub_name=$1
  local topic_name=$2
  local ack_deadline=${3:-60}

  echo "  Creating subscription: $sub_name"
  curl -s -X PUT "http://${EMULATOR_HOST}/v1/projects/${PROJECT_ID}/subscriptions/${sub_name}" \
    -H "Content-Type: application/json" \
    -d "{
      \"topic\": \"projects/${PROJECT_ID}/topics/${topic_name}\",
      \"ackDeadlineSeconds\": ${ack_deadline}
    }" > /dev/null 2>&1 && echo "    ✓ Subscription $sub_name created" || echo "    ℹ Subscription $sub_name already exists"
}

create_subscription "risk-analyzer-video-discovered-sub" "discovered-videos" 60
create_subscription "risk-scorer-sub" "discovered-videos" 60
create_subscription "vision-analyzer-scan-ready-sub" "scan-ready" 60
create_subscription "chapter-extractor-sub" "risk-scored-videos" 60
create_subscription "frame-extractor-sub" "frames-extracted" 60
create_subscription "vision-analyzer-sub" "vision-analyzed" 60

echo ""
echo "✅ PubSub initialization complete!"
echo ""
echo "📊 Topics:"
curl -s "http://${EMULATOR_HOST}/v1/projects/${PROJECT_ID}/topics" | grep -o '"name":"[^"]*"' | sed 's/"name":"projects\/.*\/topics\//  • /' | sed 's/"$//'

echo ""
echo "📬 Subscriptions:"
curl -s "http://${EMULATOR_HOST}/v1/projects/${PROJECT_ID}/subscriptions" | grep -o '"name":"[^"]*"' | sed 's/"name":"projects\/.*\/subscriptions\//  • /' | sed 's/"$//'

echo ""
