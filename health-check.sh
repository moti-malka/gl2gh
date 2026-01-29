#!/bin/bash

# Health check script to verify all services are running correctly

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}gl2gh Platform Health Check${NC}"
echo ""

# Check if services are running
echo -e "${BLUE}Checking Docker services...${NC}"

services=("mongo" "redis" "backend" "worker")
all_healthy=true

for service in "${services[@]}"; do
    if docker ps --format "{{.Names}}" | grep -q "gl2gh-${service}"; then
        status=$(docker inspect --format='{{.State.Status}}' "gl2gh-${service}" 2>/dev/null || echo "not found")
        if [ "$status" == "running" ]; then
            echo -e "  ${GREEN}✓${NC} ${service} - running"
        else
            echo -e "  ${RED}✗${NC} ${service} - ${status}"
            all_healthy=false
        fi
    else
        echo -e "  ${RED}✗${NC} ${service} - not found"
        all_healthy=false
    fi
done

echo ""

# Test MongoDB connection
echo -e "${BLUE}Testing MongoDB connection...${NC}"
if docker exec gl2gh-mongo mongosh --quiet --eval "db.adminCommand('ping')" gl2gh &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} MongoDB is accessible"
else
    echo -e "  ${RED}✗${NC} MongoDB connection failed"
    all_healthy=false
fi

# Test Redis connection
echo -e "${BLUE}Testing Redis connection...${NC}"
if docker exec gl2gh-redis redis-cli ping &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Redis is accessible"
else
    echo -e "  ${RED}✗${NC} Redis connection failed"
    all_healthy=false
fi

# Test Backend API
echo -e "${BLUE}Testing Backend API...${NC}"
backend_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
if [ "$backend_response" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} Backend API responding (http://localhost:8000)"
else
    echo -e "  ${YELLOW}!${NC} Backend API not responding yet (status: ${backend_response})"
    echo -e "    ${YELLOW}Note: API may still be starting up${NC}"
fi

echo ""

# Summary
if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}✓ All critical services are healthy${NC}"
    echo ""
    echo "Access points:"
    echo "  • Backend API:     http://localhost:8000"
    echo "  • API Docs:        http://localhost:8000/docs"
    echo "  • Frontend UI:     http://localhost:3000 (if started)"
    echo "  • MongoDB:         mongodb://localhost:27017"
    echo "  • Redis:           redis://localhost:6379"
    exit 0
else
    echo -e "${RED}✗ Some services are not healthy${NC}"
    echo "Run './start.sh logs' to see detailed logs"
    exit 1
fi
