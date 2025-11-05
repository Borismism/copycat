#!/bin/bash
set -e

echo "🔍 Testing Modal Display"
echo "========================"
echo ""

echo "1. Getting an analyzed video..."
VIDEO_ID=$(curl -s "http://localhost:8080/api/videos?status=analyzed&limit=1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['videos'][0]['video_id'] if data.get('videos') else 'none')" 2>/dev/null)

if [ "$VIDEO_ID" = "none" ]; then
    echo "❌ No analyzed videos found"
    exit 1
fi

echo "✅ Found video: $VIDEO_ID"
echo ""

echo "2. Checking video data structure..."
curl -s "http://localhost:8080/api/videos/$VIDEO_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Video: {data[\"title\"][:60]}...')
print(f'Status: {data[\"status\"]}')
has_va = 'vision_analysis' in data and data['vision_analysis'] is not None
print(f'Has vision_analysis: {has_va}')
if has_va:
    va = data['vision_analysis']
    print(f'  ✓ contains_infringement: {va.get(\"contains_infringement\")}')
    print(f'  ✓ confidence_score: {va.get(\"confidence_score\")}%')
    print(f'  ✓ Has ai_generated: {\"ai_generated\" in va}')
    print(f'  ✓ Has copyright_assessment: {\"copyright_assessment\" in va}')
    print(f'  ✓ Characters: {len(va.get(\"characters_detected\", []))}')
"

echo ""
echo "3. ✅ All systems ready!"
echo ""
echo "📱 TEST THE MODAL NOW:"
echo "======================"
echo "1. Open: http://localhost:5173/videos?status=analyzed"
echo "2. Find video: $VIDEO_ID"
echo "3. Click the purple 'View Analysis Details' button"
echo "4. Modal should open without errors!"
echo ""
echo "If you see errors, please paste them here."
