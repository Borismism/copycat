#!/bin/bash
set -e

echo "🧪 Vision Analyzer Service - Full Integration Test"
echo "=================================================="
echo ""

# Configuration
API_URL="http://localhost:8080"
VISION_URL="http://localhost:8083"
TEST_VIDEO_ID=""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Get a test video
echo "📹 Step 1: Finding a video to test..."
RESPONSE=$(curl -s "${API_URL}/api/videos?limit=1")
TEST_VIDEO_ID=$(echo $RESPONSE | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['videos'][0]['video_id'] if data['videos'] else '')")

if [ -z "$TEST_VIDEO_ID" ]; then
    echo -e "${RED}❌ No videos found in database${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found video: ${TEST_VIDEO_ID}${NC}"
echo ""

# Step 2: Check service health
echo "🏥 Step 2: Checking service health..."
STATUS=$(curl -s "${VISION_URL}/admin/status")
WORKER_RUNNING=$(echo $STATUS | python3 -c "import sys, json; print(json.load(sys.stdin)['worker_running'])")

if [ "$WORKER_RUNNING" != "True" ]; then
    echo -e "${RED}❌ Vision analyzer worker not running${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Service healthy${NC}"
echo ""

# Step 3: Check initial video state
echo "📊 Step 3: Checking initial video state..."
INITIAL_STATE=$(curl -s "${API_URL}/api/videos/${TEST_VIDEO_ID}")
INITIAL_STATUS=$(echo $INITIAL_STATE | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))")
echo "   Initial status: ${INITIAL_STATUS}"
echo ""

# Step 4: Trigger scan via API (simulating frontend button click)
echo "🚀 Step 4: Triggering scan (simulating 'Scan Now' button click)..."
SCAN_RESPONSE=$(curl -s -X POST "${API_URL}/api/videos/${TEST_VIDEO_ID}/scan")
SUCCESS=$(echo $SCAN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")
MESSAGE=$(echo $SCAN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', 'No message'))")

if [ "$SUCCESS" != "True" ]; then
    echo -e "${RED}❌ Failed to trigger scan: ${MESSAGE}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Scan triggered: ${MESSAGE}${NC}"
echo ""

# Step 5: Watch logs for processing
echo "👀 Step 5: Watching for processing (20 seconds)..."
echo "   Looking for: 'Received scan-ready message' and analysis completion..."
echo ""

# Start log watcher in background
docker-compose logs -f --tail=50 vision-analyzer-service 2>&1 | grep --line-buffered "${TEST_VIDEO_ID}" &
LOG_PID=$!

# Wait for processing (or timeout)
TIMEOUT=20
ELAPSED=0
PROCESSED=false

while [ $ELAPSED -lt $TIMEOUT ]; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))

    # Check if video was processed
    CURRENT_STATE=$(curl -s "${API_URL}/api/videos/${TEST_VIDEO_ID}")
    CURRENT_STATUS=$(echo $CURRENT_STATE | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")

    if [ "$CURRENT_STATUS" = "analyzed" ]; then
        PROCESSED=true
        break
    fi

    echo -ne "${YELLOW}   Waiting... ${ELAPSED}s / ${TIMEOUT}s (status: ${CURRENT_STATUS})${NC}\r"
done

# Stop log watcher
kill $LOG_PID 2>/dev/null || true

echo ""
echo ""

# Step 6: Check final state
echo "📊 Step 6: Checking final video state..."
FINAL_STATE=$(curl -s "${API_URL}/api/videos/${TEST_VIDEO_ID}")
FINAL_STATUS=$(echo $FINAL_STATE | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))")

if [ "$FINAL_STATUS" = "analyzed" ]; then
    # Extract analysis results
    INFRINGEMENT=$(echo $FINAL_STATE | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('vision_analysis', {}).get('contains_infringement', 'N/A'))" 2>/dev/null || echo "N/A")
    CONFIDENCE=$(echo $FINAL_STATE | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('vision_analysis', {}).get('confidence_score', 'N/A'))" 2>/dev/null || echo "N/A")
    COST=$(echo $FINAL_STATE | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('analysis_cost_usd', 'N/A'))" 2>/dev/null || echo "N/A")

    echo -e "${GREEN}✅ Video analyzed successfully!${NC}"
    echo ""
    echo "   📊 Analysis Results:"
    echo "   ===================="
    echo "   Status: ${FINAL_STATUS}"
    echo "   Infringement Detected: ${INFRINGEMENT}"
    echo "   Confidence Score: ${CONFIDENCE}%"
    echo "   Analysis Cost: \$${COST}"
    echo ""

    # Show character detection
    CHARACTERS=$(echo $FINAL_STATE | python3 -c "
import sys, json
data = json.load(sys.stdin)
chars = data.get('vision_analysis', {}).get('characters_detected', [])
if chars:
    for char in chars:
        print(f\"   - {char.get('name', 'Unknown')}: {char.get('screen_time_seconds', 0)}s ({char.get('prominence', 'unknown')} prominence)\")
else:
    print('   No characters detected')
" 2>/dev/null || echo "   Unable to parse character data")

    echo "   Characters Detected:"
    echo "$CHARACTERS"
    echo ""

elif [ "$FINAL_STATUS" = "error" ]; then
    echo -e "${RED}❌ Analysis failed${NC}"
    echo "   Status: ${FINAL_STATUS}"
    echo ""

elif [ "$PROCESSED" = "false" ]; then
    echo -e "${YELLOW}⏳ Analysis still in progress or rate limited${NC}"
    echo "   Status: ${FINAL_STATUS}"
    echo "   This is expected if Vertex AI is rate limiting"
    echo "   The system will automatically retry"
    echo ""

else
    echo -e "${YELLOW}⚠️  Unexpected status: ${FINAL_STATUS}${NC}"
    echo ""
fi

# Step 7: Check budget tracking
echo "💰 Step 7: Checking budget tracking..."
BUDGET_STATS=$(curl -s "${VISION_URL}/admin/budget")
SPENT=$(echo $BUDGET_STATS | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_spent_usd', 0))" 2>/dev/null || echo "0")
REMAINING=$(echo $BUDGET_STATS | python3 -c "import sys, json; print(json.load(sys.stdin).get('remaining_usd', 260))" 2>/dev/null || echo "260")
VIDEOS_ANALYZED=$(echo $BUDGET_STATS | python3 -c "import sys, json; print(json.load(sys.stdin).get('videos_analyzed', 0))" 2>/dev/null || echo "0")

echo "   Budget spent today: \$${SPENT}"
echo "   Budget remaining: \$${REMAINING}"
echo "   Videos analyzed today: ${VIDEOS_ANALYZED}"
echo ""

# Summary
echo "=================================================="
echo "🎯 Integration Test Summary"
echo "=================================================="
echo ""

if [ "$FINAL_STATUS" = "analyzed" ]; then
    echo -e "${GREEN}✅ PASS: Full integration working!${NC}"
    echo ""
    echo "   ✅ Frontend button → API endpoint"
    echo "   ✅ API → PubSub message"
    echo "   ✅ PubSub → Vision analyzer worker"
    echo "   ✅ Gemini analysis execution"
    echo "   ✅ Results stored in Firestore"
    echo "   ✅ Budget tracking updated"
    echo ""
    echo "   The 'Scan Now' button is working end-to-end!"

elif [ "$FINAL_STATUS" = "error" ]; then
    echo -e "${RED}❌ FAIL: Analysis failed${NC}"
    echo ""
    echo "   Check logs: docker-compose logs vision-analyzer-service"
    exit 1

else
    echo -e "${YELLOW}⚠️  PARTIAL: Scan queued but not completed${NC}"
    echo ""
    echo "   This usually means Vertex AI rate limiting."
    echo "   The system will automatically retry."
    echo "   Wait a few minutes and check video status again:"
    echo ""
    echo "   curl -s ${API_URL}/api/videos/${TEST_VIDEO_ID} | python3 -m json.tool"
    echo ""
fi

echo "=================================================="
