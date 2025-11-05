#!/bin/bash
set -e

echo "🎬 Finding a new video to scan with updated prompt..."
NEW_VIDEO=$(curl -s "http://localhost:8080/api/videos?limit=1&status=discovered" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['videos'][0]['video_id'] if data['videos'] else '')" 2>/dev/null)
echo "✅ Selected: $NEW_VIDEO"

echo ""
echo "🚀 Triggering scan..."
curl -s -X POST "http://localhost:8080/api/videos/$NEW_VIDEO/scan" | python3 -m json.tool

echo ""
echo "⏳ Waiting 20 seconds for Gemini analysis..."
sleep 20

echo ""
echo "📊 Checking full analysis..."
curl -s "http://localhost:8080/api/videos/$NEW_VIDEO" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'vision_analysis' in data and data['vision_analysis']:
    print('\n✅ FULL ANALYSIS AVAILABLE!')
    print('=' * 80)
    analysis = data['vision_analysis']
    print(f'\nVideo: {data[\"title\"]}')
    print(f'ID: {data[\"video_id\"]}')
    print(f'\nInfringement: {analysis[\"contains_infringement\"]}')
    print(f'Confidence: {analysis[\"confidence_score\"]}%')
    print(f'Type: {analysis[\"infringement_type\"]}')
    print(f'\nRecommended Action: {analysis[\"recommended_action\"]}')

    if 'copyright_assessment' in analysis:
        print('\n⚖️  LEGAL REASONING:')
        print('-' * 80)
        print(analysis['copyright_assessment']['reasoning'])
    else:
        print('\n❌ No copyright_assessment found')

    print('\n\n🎯 Next: Open http://localhost:5173/videos?status=analyzed')
    print('Click \"View Analysis Details\" to see the full modal!')
else:
    print('❌ No vision_analysis yet')
"
