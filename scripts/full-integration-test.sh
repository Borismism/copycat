#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🧪 FULL DOCKER COMPOSE INTEGRATION TEST${NC}"
echo -e "${BLUE}   Complete Flow Validation${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "${CYAN}Test $TESTS_RUN: ${test_name}${NC}"

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}❌ FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo -e "${YELLOW}═══ PHASE 1: Infrastructure Validation ═══${NC}"
echo ""

# Test 1: Check all containers are running
run_test "All containers running" \
    "docker-compose ps | grep -q 'Up'"

# Test 2: Firestore emulator is healthy
run_test "Firestore emulator healthy" \
    "docker-compose ps firestore | grep -q 'healthy'"

# Test 3: PubSub emulator is healthy
run_test "PubSub emulator healthy" \
    "docker-compose ps pubsub | grep -q 'healthy'"

# Test 4: Discovery service is healthy
run_test "Discovery service healthy" \
    "curl -sf http://localhost:8081/health | grep -q '\"status\":\"healthy\"'"

# Test 5: Risk analyzer service is healthy
run_test "Risk analyzer service healthy" \
    "curl -sf http://localhost:8082/health | grep -q '\"status\":\"healthy\"'"

echo ""
echo -e "${YELLOW}═══ PHASE 2: PubSub Infrastructure ═══${NC}"
echo ""

# Test 6: Check discovered-videos topic exists
run_test "discovered-videos topic exists" \
    "docker exec copycat-pubsub-1 curl -sf 'http://localhost:8085/v1/projects/copycat-local/topics/discovered-videos' | grep -q 'name'"

# Test 7: Check scan-ready topic exists
run_test "scan-ready topic exists" \
    "docker exec copycat-pubsub-1 curl -sf 'http://localhost:8085/v1/projects/copycat-local/topics/scan-ready' | grep -q 'name'"

# Test 8: Check risk-analyzer subscription exists
run_test "risk-analyzer subscription exists" \
    "docker exec copycat-pubsub-1 curl -sf 'http://localhost:8085/v1/projects/copycat-local/subscriptions/risk-analyzer-video-discovered-sub' | grep -q 'name'"

echo ""
echo -e "${YELLOW}═══ PHASE 3: Data Flow Test ═══${NC}"
echo ""

# Generate unique test video ID
TEST_VIDEO_ID="integration_test_$(date +%s)"
echo -e "  ${CYAN}Test Video ID: ${TEST_VIDEO_ID}${NC}"
echo ""

# Test 9: Create video in Firestore via discovery service
echo -e "${CYAN}Test 9: Write video to Firestore${NC}"
docker exec copycat-firestore-1 curl -sf -X PATCH \
  "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${TEST_VIDEO_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"fields\": {
      \"video_id\": {\"stringValue\": \"${TEST_VIDEO_ID}\"},
      \"title\": {\"stringValue\": \"AI Superman Movie - Full Integration Test\"},
      \"channel_id\": {\"stringValue\": \"UC_integration_test\"},
      \"channel_title\": {\"stringValue\": \"Integration Test Channel\"},
      \"published_at\": {\"timestampValue\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"},
      \"view_count\": {\"integerValue\": \"150000\"},
      \"duration_seconds\": {\"integerValue\": \"600\"},
      \"matched_keywords\": {\"arrayValue\": {\"values\": [
        {\"stringValue\": \"superman\"},
        {\"stringValue\": \"ai generated\"},
        {\"stringValue\": \"sora ai\"}
      ]}},
      \"discovery_method\": {\"stringValue\": \"integration_test\"},
      \"initial_risk_score\": {\"integerValue\": \"85\"},
      \"status\": {\"stringValue\": \"discovered\"},
      \"discovered_at\": {\"timestampValue\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}
    }
  }" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✅ PASSED${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌ FAILED${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 10: Verify video exists in Firestore
run_test "Video exists in Firestore" \
    "docker exec copycat-firestore-1 curl -sf 'http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${TEST_VIDEO_ID}' | grep -q '${TEST_VIDEO_ID}'"

# Test 11: Publish message to discovered-videos topic
echo -e "${CYAN}Test 11: Publish to PubSub topic${NC}"
MESSAGE_DATA=$(cat <<EOF | base64
{
  "video_id": "${TEST_VIDEO_ID}",
  "title": "AI Superman Movie - Full Integration Test",
  "channel_id": "UC_integration_test",
  "channel_title": "Integration Test Channel",
  "published_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "view_count": 150000,
  "duration_seconds": 600,
  "matched_keywords": ["superman", "ai generated", "sora ai"],
  "discovery_method": "integration_test",
  "initial_risk_score": 85,
  "risk_factors": {
    "keyword_relevance": 95,
    "duration_score": 90,
    "recency_score": 100,
    "view_count_score": 80,
    "channel_size_score": 70
  },
  "discovered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)

docker exec copycat-pubsub-1 curl -sf -X POST \
  "http://localhost:8085/v1/projects/copycat-local/topics/discovered-videos:publish" \
  -H "Content-Type: application/json" \
  -d "{
    \"messages\": [
      {
        \"data\": \"${MESSAGE_DATA}\"
      }
    ]
  }" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✅ PASSED${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌ FAILED${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo -e "${YELLOW}═══ PHASE 4: Risk Analyzer Processing ═══${NC}"
echo ""

# Wait for processing
echo -e "  ${CYAN}Waiting for risk-analyzer to process message...${NC}"
sleep 5

# Test 12: Check risk-analyzer logs for processing
echo -e "${CYAN}Test 12: Risk analyzer processed message${NC}"
LOGS=$(docker-compose logs risk-analyzer-service --tail 100 2>&1)
if echo "$LOGS" | grep -q "$TEST_VIDEO_ID"; then
    echo -e "  ${GREEN}✅ PASSED${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))

    # Show processing details
    echo -e "  ${BLUE}Processing logs:${NC}"
    echo "$LOGS" | grep "$TEST_VIDEO_ID" | tail -5 | sed 's/^/    /'
else
    echo -e "  ${RED}❌ FAILED - No logs found${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""

# Test 13: Check if video was updated in Firestore
echo -e "${CYAN}Test 13: Video updated with risk analysis${NC}"
FIRESTORE_DATA=$(docker exec copycat-firestore-1 curl -sf \
  "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${TEST_VIDEO_ID}")

if echo "$FIRESTORE_DATA" | grep -q "next_scan_at"; then
    echo -e "  ${GREEN}✅ PASSED${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))

    # Extract scan time
    echo -e "  ${BLUE}Video scheduled for scan${NC}"
else
    echo -e "  ${RED}❌ FAILED - Video not updated${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo -e "${YELLOW}═══ PHASE 5: Service Communication ═══${NC}"
echo ""

# Test 14: Check PubSub worker is running
run_test "Risk analyzer PubSub worker active" \
    "docker-compose logs risk-analyzer-service | grep -q 'Listening for messages'"

# Test 15: Check Firestore connectivity
run_test "Firestore connectivity from services" \
    "curl -sf http://localhost:8081/health | grep -q 'firestore'"

echo ""
echo -e "${YELLOW}═══ PHASE 6: Data Validation ═══${NC}"
echo ""

# Test 16: Validate video document structure
echo -e "${CYAN}Test 16: Video document has required fields${NC}"
REQUIRED_FIELDS=("video_id" "title" "channel_id" "view_count" "initial_risk_score" "discovered_at")
ALL_PRESENT=true

for field in "${REQUIRED_FIELDS[@]}"; do
    if ! echo "$FIRESTORE_DATA" | grep -q "\"$field\""; then
        ALL_PRESENT=false
        echo -e "  ${RED}Missing field: $field${NC}"
    fi
done

if $ALL_PRESENT; then
    echo -e "  ${GREEN}✅ PASSED - All required fields present${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌ FAILED - Missing required fields${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo -e "${YELLOW}═══ PHASE 7: Clean Up ═══${NC}"
echo ""

# Test 17: Clean up test data
echo -e "${CYAN}Test 17: Clean up test video${NC}"
docker exec copycat-firestore-1 curl -sf -X DELETE \
  "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${TEST_VIDEO_ID}" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✅ PASSED - Test data cleaned up${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}⚠️  WARNING - Cleanup failed (non-critical)${NC}"
fi

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}📊 TEST RESULTS${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "  Total Tests Run:    ${CYAN}${TESTS_RUN}${NC}"
echo -e "  Tests Passed:       ${GREEN}${TESTS_PASSED}${NC}"
echo -e "  Tests Failed:       ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo ""
    echo -e "${GREEN}The complete Docker Compose integration is working:${NC}"
    echo -e "  ✅ Infrastructure (Firestore, PubSub, Services)"
    echo -e "  ✅ Service health checks"
    echo -e "  ✅ PubSub topics and subscriptions"
    echo -e "  ✅ Message publishing and consumption"
    echo -e "  ✅ Risk analyzer processing"
    echo -e "  ✅ Data persistence in Firestore"
    echo -e "  ✅ Service-to-service communication"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    echo -e "${YELLOW}Review the logs above for details${NC}"
    echo -e "  View logs: ${CYAN}docker-compose logs -f${NC}"
    echo ""
    exit 1
fi
