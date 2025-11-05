#!/bin/bash
# Test Dashboard Implementation
# Tests all new analytics API endpoints

set -e

API_URL="${1:-http://localhost:8080}"

echo "=================================="
echo "Testing Dashboard Analytics APIs"
echo "Base URL: $API_URL"
echo "=================================="
echo ""

# Test 1: Hourly Stats
echo "1. Testing /api/analytics/hourly-stats..."
response=$(curl -s "$API_URL/api/analytics/hourly-stats?hours=24")
if echo "$response" | jq -e '.hours' > /dev/null 2>&1; then
    count=$(echo "$response" | jq '.hours | length')
    echo "   ✅ SUCCESS: Returned $count hourly buckets"
else
    echo "   ❌ FAILED: Invalid response"
    echo "$response" | jq '.'
fi
echo ""

# Test 2: System Health
echo "2. Testing /api/analytics/system-health..."
response=$(curl -s "$API_URL/api/analytics/system-health")
if echo "$response" | jq -e '.alerts' > /dev/null 2>&1; then
    alerts=$(echo "$response" | jq '.alerts | length')
    warnings=$(echo "$response" | jq '.warnings | length')
    info=$(echo "$response" | jq '.info | length')
    echo "   ✅ SUCCESS: $alerts alerts, $warnings warnings, $info info"
else
    echo "   ❌ FAILED: Invalid response"
    echo "$response" | jq '.'
fi
echo ""

# Test 3: Performance Metrics
echo "3. Testing /api/analytics/performance-metrics..."
response=$(curl -s "$API_URL/api/analytics/performance-metrics")
if echo "$response" | jq -e '.discovery_efficiency' > /dev/null 2>&1; then
    efficiency=$(echo "$response" | jq -r '.discovery_efficiency.value')
    throughput=$(echo "$response" | jq -r '.analysis_throughput.value')
    echo "   ✅ SUCCESS: Efficiency=$efficiency, Throughput=$throughput"
else
    echo "   ❌ FAILED: Invalid response"
    echo "$response" | jq '.'
fi
echo ""

# Test 4: Recent Events
echo "4. Testing /api/analytics/recent-events..."
response=$(curl -s "$API_URL/api/analytics/recent-events?limit=20")
if echo "$response" | jq -e '.events' > /dev/null 2>&1; then
    count=$(echo "$response" | jq '.events | length')
    echo "   ✅ SUCCESS: Returned $count events"
else
    echo "   ❌ FAILED: Invalid response"
    echo "$response" | jq '.'
fi
echo ""

# Test 5: Overview (legacy)
echo "5. Testing /api/analytics/overview..."
response=$(curl -s "$API_URL/api/analytics/overview")
if echo "$response" | jq -e '.summary' > /dev/null 2>&1; then
    echo "   ✅ SUCCESS: Overview endpoint working"
else
    echo "   ❌ FAILED: Invalid response"
    echo "$response" | jq '.'
fi
echo ""

echo "=================================="
echo "Dashboard API Tests Complete!"
echo "=================================="
