#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}🚀 Copycat - AI Copyright Detection${NC}"
echo -e "${BLUE}   Local Development Environment${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi

# Check .env
if [ ! -f services/discovery-service/.env ]; then
    echo -e "${YELLOW}⚠️  Creating .env file...${NC}"
    cp services/discovery-service/.env.example services/discovery-service/.env || true
fi

# Load env
export $(grep -v '^#' services/discovery-service/.env | xargs 2>/dev/null || true)

echo -e "${GREEN}✅ Pre-flight checks passed${NC}"

# Clean up
echo -e "${YELLOW}🧹 Cleaning up...${NC}"
docker-compose down -v 2>/dev/null || true

# Build
echo -e "${YELLOW}🔨 Building...${NC}"
docker-compose build

# Start
echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose up -d

# Wait
echo -e "${YELLOW}⏳ Waiting for health checks...${NC}"
sleep 10

echo ""
echo -e "${GREEN}✅ Environment ready!${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  Discovery: ${GREEN}http://localhost:8080${NC}"
echo -e "  Docs:      ${GREEN}http://localhost:8080/docs${NC}"
echo ""
echo -e "${BLUE}Commands:${NC}"
echo -e "  Logs:   ${YELLOW}docker-compose logs -f${NC}"
echo -e "  Stop:   ${YELLOW}docker-compose down${NC}"
echo ""
