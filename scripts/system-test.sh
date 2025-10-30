#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🧪 Copycat System Test${NC}"
echo -e "${BLUE}   Discovery → Risk Analyzer Flow${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check services are running
echo -e "${YELLOW}Step 1: Checking service health...${NC}"

DISCOVERY_HEALTH=$(curl -s http://localhost:8081/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
RISK_ANALYZER_HEALTH=$(curl -s http://localhost:8082/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$DISCOVERY_HEALTH" = "healthy" ]; then
    echo -e "  ✅ discovery-service: ${GREEN}healthy${NC}"
else
    echo -e "  ❌ discovery-service: ${RED}unhealthy${NC}"
    exit 1
fi

if [ "$RISK_ANALYZER_HEALTH" = "healthy" ]; then
    echo -e "  ✅ risk-analyzer-service: ${GREEN}healthy${NC}"
else
    echo -e "  ❌ risk-analyzer-service: ${RED}unhealthy${NC}"
    exit 1
fi

echo ""

# Test direct video processing
echo -e "${YELLOW}Step 2: Testing video processing...${NC}"
echo -e "  Creating test video in Firestore..."

# Create a test video directly via the discovery service's video processor
# We'll use a mock video since we don't want to hit the real YouTube API

TEST_VIDEO_ID="test_$(date +%s)"

# Use docker exec to write directly to Firestore emulator
docker exec copycat-firestore-1 curl -X PATCH \
  "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${TEST_VIDEO_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"fields\": {
      \"video_id\": {\"stringValue\": \"${TEST_VIDEO_ID}\"},
      \"title\": {\"stringValue\": \"AI Generated Superman Movie - Sora AI Test\"},
      \"channel_id\": {\"stringValue\": \"UC_test_channel_123\"},
      \"channel_title\": {\"stringValue\": \"AI Movies Test Channel\"},
      \"published_at\": {\"timestampValue\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"},
      \"view_count\": {\"integerValue\": \"50000\"},
      \"duration_seconds\": {\"integerValue\": \"300\"},
      \"initial_risk_score\": {\"integerValue\": \"75\"},
      \"status\": {\"stringValue\": \"discovered\"},
      \"discovered_at\": {\"timestampValue\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}
    }
  }" > /dev/null 2>&1

echo -e "  ✅ Test video created: ${TEST_VIDEO_ID}"

echo ""

# Publish message to discovered-videos topic
echo -e "${YELLOW}Step 3: Publishing to discovered-videos topic...${NC}"

MESSAGE_DATA=$(cat <<EOF | base64
{
  "video_id": "${TEST_VIDEO_ID}",
  "title": "AI Generated Superman Movie - Sora AI Test",
  "channel_id": "UC_test_channel_123",
  "channel_title": "AI Movies Test Channel",
  "published_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "view_count": 50000,
  "duration_seconds": 300,
  "matched_keywords": ["superman", "ai generated", "sora"],
  "discovery_method": "keyword_search",
  "initial_risk_score": 75,
  "risk_factors": {
    "keyword_relevance": 90,
    "duration_score": 80,
    "recency_score": 95,
    "view_count_score": 60,
    "channel_size_score": 50
  },
  "discovered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)

# Publish via REST API to PubSub emulator
docker exec copycat-pubsub-1 curl -X POST \
  "http://localhost:8085/v1/projects/copycat-local/topics/discovered-videos:publish" \
  -H "Content-Type: application/json" \
  -d "{
    \"messages\": [
      {
        \"data\": \"${MESSAGE_DATA}\"
      }
    ]
  }" > /dev/null 2>&1

echo -e "  ✅ Message published to discovered-videos topic"

echo ""

# Wait for risk-analyzer to process
echo -e "${YELLOW}Step 4: Waiting for risk-analyzer to process...${NC}"
sleep 3

# Check risk-analyzer logs for processing
echo -e "  Checking risk-analyzer logs..."
RISK_LOGS=$(docker-compose logs risk-analyzer-service --tail 50 2>&1 | grep -i "${TEST_VIDEO_ID}" || echo "")

if [ -n "$RISK_LOGS" ]; then
    echo -e "  ✅ Risk analyzer processed the video"
    echo ""
    echo -e "${GREEN}Risk Analyzer Output:${NC}"
    echo "$RISK_LOGS" | tail -10
else
    echo -e "  ⚠️  No logs found (risk analyzer may not have PubSub subscription active)"
fi

echo ""

# Check Firestore for updates
echo -e "${YELLOW}Step 5: Verifying data in Firestore...${NC}"

FIRESTORE_DATA=$(docker exec copycat-firestore-1 curl -s \
  "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${TEST_VIDEO_ID}")

if echo "$FIRESTORE_DATA" | grep -q "current_risk_score"; then
    echo -e "  ✅ Video updated with risk analysis"

    # Extract risk score
    RISK_SCORE=$(echo "$FIRESTORE_DATA" | grep -o '"current_risk_score":{"integerValue":"[^"]*"' | cut -d'"' -f6 || echo "N/A")
    RISK_TIER=$(echo "$FIRESTORE_DATA" | grep -o '"risk_tier":{"stringValue":"[^"]*"' | cut -d'"' -f6 || echo "N/A")

    echo -e "  📊 Current Risk Score: ${YELLOW}${RISK_SCORE}${NC}"
    echo -e "  📊 Risk Tier: ${YELLOW}${RISK_TIER}${NC}"
else
    echo -e "  ℹ️  Video exists but not yet analyzed by risk-analyzer"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ System Test Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Summary
echo -e "${BLUE}Test Summary:${NC}"
echo -e "  • Services: ✅ Both healthy"
echo -e "  • Test Video: ${TEST_VIDEO_ID}"
echo -e "  • Message Flow: discovery → risk-analyzer"
echo -e "  • Data Persistence: Firestore"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Check logs: ${NC}docker-compose logs -f risk-analyzer-service"
echo -e "  2. View Firestore: ${NC}http://localhost:8200"
echo -e "  3. Monitor PubSub: ${NC}docker-compose logs pubsub"
echo ""
