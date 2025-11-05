#!/bin/bash
set -e

echo "🧪 FULL END-TO-END FRONTEND INTEGRATION TEST"
echo "============================================="
echo ""

# Step 1: Pick a video
echo "Step 1: Selecting a video to scan..."
VIDEO_ID=$(curl -s "http://localhost:8080/api/videos?limit=1&status=discovered" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['videos'][0]['video_id'] if data['videos'] else '')" 2>/dev/null)

if [ -z "$VIDEO_ID" ]; then
    echo "❌ No discovered videos found. Using the already scanned video QfPpbhsDnWg"
    VIDEO_ID="QfPpbhsDnWg"
fi

echo "✅ Selected video: $VIDEO_ID"
echo ""

# Step 2: Check initial status
echo "Step 2: Checking initial status..."
curl -s "http://localhost:8080/api/videos/$VIDEO_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Title: {data['title']}\")
print(f\"Status: {data['status']}\")
print(f\"Has vision_analysis: {'vision_analysis' in data}\")
" 2>/dev/null
echo ""

# Step 3: Trigger scan
echo "Step 3: Triggering Gemini scan (this takes ~15-20 seconds)..."
SCAN_RESULT=$(curl -s -X POST http://localhost:8083/admin/analyze \
  -H "Content-Type: application/json" \
  -d "{\"video_id\": \"$VIDEO_ID\"}" 2>/dev/null)

echo "$SCAN_RESULT" | python3 -m json.tool 2>/dev/null || echo "$SCAN_RESULT"
echo ""

# Step 4: Verify API response
echo "Step 4: Verifying frontend API can see the results..."
curl -s "http://localhost:8080/api/videos/$VIDEO_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('📊 Frontend API Response:')
print(f'  Video ID: {data[\"video_id\"]}')
print(f'  Status: {data[\"status\"]}')
if 'vision_analysis' in data:
    va = data['vision_analysis']
    print(f'  ✅ Vision Analysis Found:')
    print(f'     Infringement: {va.get(\"contains_infringement\")}')
    print(f'     Confidence: {va.get(\"confidence_score\")}%')
    print(f'     Cost: \${va.get(\"cost_usd\")}')
    chars = va.get('characters_detected', [])
    if chars:
        print(f'     Characters: {len(chars)} detected')
        for char in chars[:2]:
            print(f'       - {char.get(\"name\")}: {char.get(\"screen_time_seconds\")}s')
else:
    print('  ❌ No vision_analysis found')
" 2>/dev/null
echo ""

# Step 5: Check filter endpoint
echo "Step 5: Checking if video appears in analyzed filter..."
curl -s "http://localhost:8080/api/videos?status=analyzed&limit=10" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'📋 Total videos with status=analyzed: {data[\"total\"]}')
print(f'Videos on this page:')
for v in data['videos'][:5]:
    title = v['title'][:60] + '...' if len(v['title']) > 60 else v['title']
    print(f'  - {v[\"video_id\"]}: {title}')
" 2>/dev/null
echo ""

echo "============================================="
echo "✅ TEST COMPLETE!"
echo ""
echo "Frontend verification:"
echo "1. Open: http://localhost:5173/videos?status=analyzed"
echo "2. You should see video: $VIDEO_ID"
echo "3. It should have a GREEN 'Analyzed' button with checkmark"
echo "============================================="
