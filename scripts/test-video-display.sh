#!/bin/bash
set -e

VIDEO_ID="-Pi-lzhMgZI"

echo "🎬 Testing video: $VIDEO_ID"
echo "Title: Superman in the 70s"
echo ""

echo "🚀 Triggering scan..."
curl -s -X POST "http://localhost:8080/api/videos/$VIDEO_ID/scan"

echo ""
echo "⏳ Waiting 25 seconds for Gemini analysis..."
sleep 25

echo ""
echo "📊 Checking results..."
curl -s "http://localhost:8080/api/videos/$VIDEO_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)

if 'vision_analysis' not in data or not data['vision_analysis']:
    print('❌ No analysis yet - may need more time')
    sys.exit(1)

va = data.get('vision_analysis', {})
fa = va.get('full_analysis', va)

print(f'\n✅ ANALYSIS COMPLETE')
print(f'=' * 80)
print(f'\nVideo: {data[\"title\"]}')
print(f'ID: {data[\"video_id\"]}')
print(f'\n🎯 RESULT:')
print(f'  Infringement: {fa.get(\"contains_infringement\")}')
print(f'  Confidence: {fa.get(\"confidence_score\")}%')
print(f'  Type: {fa.get(\"infringement_type\")}')

if fa.get('copyright_assessment'):
    ca = fa['copyright_assessment']
    print(f'\n⚖️  LEGAL ASSESSMENT:')
    print(f'  Likelihood: {ca.get(\"infringement_likelihood\")}%')
    print(f'  Fair Use: {ca.get(\"fair_use_applies\")}')
    print(f'\n  Reasoning (first 200 chars):')
    print(f'  {ca.get(\"reasoning\", \"N/A\")[:200]}...')

border_color = 'GREEN' if not fa.get('contains_infringement') else 'RED'
print(f'\n🎨 Now open: http://localhost:5173/videos?status=analyzed')
print(f'Look for video: {data[\"video_id\"]}')
print(f'It should have a {border_color} border!')
"
