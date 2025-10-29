#!/bin/bash
set -e

# Run tests for a service
# Usage: ./scripts/test-service.sh <service-name>

SERVICE_NAME=$1

if [ -z "$SERVICE_NAME" ]; then
    echo "❌ Error: Service name required"
    echo "Usage: ./scripts/test-service.sh <service-name>"
    exit 1
fi

if [ ! -d "services/$SERVICE_NAME" ]; then
    echo "❌ Error: Service 'services/$SERVICE_NAME' not found"
    exit 1
fi

echo "🧪 Running tests for $SERVICE_NAME"
echo ""

cd services/$SERVICE_NAME

# Check if tests directory exists
if [ ! -d "tests" ] && [ ! -f "test_*.py" ]; then
    echo "⚠️  No tests found for $SERVICE_NAME"
    exit 0
fi

# Run tests with UV
echo "Running pytest..."
uv run pytest -v --cov=app --cov-report=term-missing

echo ""
echo "✅ Tests passed for $SERVICE_NAME"
