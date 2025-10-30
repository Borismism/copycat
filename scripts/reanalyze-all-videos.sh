#!/bin/bash
set -e

echo "🔄 Re-analyzing all videos with new 6-factor risk model..."

PROCESSED=0
FAILED=0
PAGE_TOKEN=""

echo "📊 Fetching all videos from Firestore (with pagination)..."

while true; do
    # Fetch page of videos
    if [ -z "$PAGE_TOKEN" ]; then
        RESPONSE=$(docker exec copycat-firestore-1 curl -s \
          "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos?pageSize=100" \
          2>/dev/null)
    else
        RESPONSE=$(docker exec copycat-firestore-1 curl -s \
          "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos?pageSize=100&pageToken=${PAGE_TOKEN}" \
          2>/dev/null)
    fi

    # Extract video IDs from this page
    VIDEO_IDS=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'documents' in data:
        for doc in data['documents']:
            # Extract video_id from document path
            video_id = doc['name'].split('/')[-1]
            print(video_id)
except:
    pass
")

    # Get next page token
    PAGE_TOKEN=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('nextPageToken', ''))
except:
    print('')
" 2>/dev/null || echo "")

    # Process videos from this page
    for VIDEO_ID in $VIDEO_IDS; do
    # Get video data from Firestore
    VIDEO_DATA=$(docker exec copycat-firestore-1 curl -s \
      "http://localhost:8200/v1/projects/copycat-local/databases/(default)/documents/videos/${VIDEO_ID}" \
      2>/dev/null)

    # Extract required fields and build JSON message
    MESSAGE=$(echo "$VIDEO_DATA" | python3 -c "
import sys, json, base64
try:
    data = json.load(sys.stdin)
    fields = data.get('fields', {})

    msg = {
        'video_id': fields.get('video_id', {}).get('stringValue', ''),
        'title': fields.get('title', {}).get('stringValue', ''),
        'channel_id': fields.get('channel_id', {}).get('stringValue', ''),
        'channel_title': fields.get('channel_title', {}).get('stringValue', ''),
        'published_at': fields.get('published_at', {}).get('timestampValue', ''),
        'view_count': int(fields.get('view_count', {}).get('integerValue', 0)),
        'duration_seconds': int(fields.get('duration_seconds', {}).get('integerValue', 0)),
        'initial_risk': float(fields.get('initial_risk', {}).get('doubleValue', 50)),
        'matched_keywords': [],
        'discovery_method': 'reanalysis',
        'discovered_at': fields.get('discovered_at', {}).get('timestampValue', ''),
    }

    # Base64 encode for PubSub
    json_str = json.dumps(msg)
    encoded = base64.b64encode(json_str.encode()).decode()
    print(encoded)
except Exception as e:
    print('ERROR', file=sys.stderr)
    sys.exit(1)
")

    if [ $? -ne 0 ] || [ -z "$MESSAGE" ]; then
        echo "  ⚠️  Skipping $VIDEO_ID (failed to extract data)"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Publish to PubSub
    docker exec copycat-pubsub-1 curl -s -X POST \
      "http://localhost:8086/v1/projects/copycat-local/topics/discovered-videos:publish" \
      -H "Content-Type: application/json" \
      -d "{\"messages\": [{\"data\": \"${MESSAGE}\"}]}" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        PROCESSED=$((PROCESSED + 1))
        if [ $((PROCESSED % 10)) -eq 0 ]; then
            echo "  ✅ Re-analyzed: $PROCESSED videos..."
        fi
    else
        echo "  ❌ Failed to publish: $VIDEO_ID"
        FAILED=$((FAILED + 1))
    fi
    done

    # Check if there's another page
    if [ -z "$PAGE_TOKEN" ]; then
        echo "  📄 Finished fetching all pages"
        break
    else
        echo "  📄 Fetching next page..."
    fi
done

echo ""
echo "✅ Re-analysis complete!"
echo "   Total processed: $PROCESSED"
echo "   Total failed: $FAILED"
echo ""
echo "The risk-analyzer-service will now reprocess all videos with:"
echo "  ✅ Discovery freshness scoring (+20 for new, -20 for clean)"
echo "  ✅ Survivor bias detection (old + high views = +15 points)"
echo ""
echo "💡 Check risk-analyzer logs:"
echo "   docker-compose logs -f risk-analyzer-service | grep 'tier='"
