#!/bin/bash

# gl2gh Migration Platform - Start Script
# This script starts all services needed to run the platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
cat << "EOF"
   _____ _      ___   ____ _     
  / ____| |    |__ \ / ___| |__  
 | |  __| |       ) | |  _| '_ \ 
 | |___|_|      / /| |_| | | | |
  \_____(_)    |____|\____|_| |_|
                                  
  GitLab to GitHub Migration Platform
EOF
echo -e "${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

# Determine docker compose command (v1 vs v2)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
        echo -e "${YELLOW}Please edit .env file and set your credentials${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Create artifacts directory
echo -e "${BLUE}Creating artifacts directory...${NC}"
mkdir -p artifacts
echo -e "${GREEN}✓ Artifacts directory ready${NC}"

# Parse command line arguments
MODE="${1:-up}"

case $MODE in
    up|start)
        echo -e "${BLUE}Starting gl2gh platform...${NC}"
        $DOCKER_COMPOSE up -d
        
        echo ""
        echo -e "${GREEN}✓ Services started successfully!${NC}"
        echo ""
        echo "Services available at:"
        echo -e "  ${BLUE}• Backend API:${NC}     http://localhost:8000"
        echo -e "  ${BLUE}• API Docs:${NC}        http://localhost:8000/docs"
        echo -e "  ${BLUE}• Frontend UI:${NC}     http://localhost:3000"
        echo -e "  ${BLUE}• MongoDB:${NC}         mongodb://localhost:27017"
        echo -e "  ${BLUE}• Redis:${NC}           redis://localhost:6379"
        echo ""
        echo "View logs with: $0 logs"
        echo "Stop services with: $0 stop"
        ;;
    
    logs)
        echo -e "${BLUE}Showing logs (Ctrl+C to exit)...${NC}"
        $DOCKER_COMPOSE logs -f
        ;;
    
    stop|down)
        echo -e "${BLUE}Stopping gl2gh platform...${NC}"
        $DOCKER_COMPOSE down
        echo -e "${GREEN}✓ Services stopped${NC}"
        ;;
    
    restart)
        echo -e "${BLUE}Restarting gl2gh platform...${NC}"
        $DOCKER_COMPOSE restart
        echo -e "${GREEN}✓ Services restarted${NC}"
        ;;
    
    build)
        echo -e "${BLUE}Building services...${NC}"
        $DOCKER_COMPOSE build
        echo -e "${GREEN}✓ Build complete${NC}"
        ;;
    
    clean)
        echo -e "${YELLOW}This will remove all containers, volumes, and data${NC}"
        read -p "Are you sure? (yes/no): " -r
        if [[ $REPLY == "yes" ]]; then
            echo -e "${BLUE}Cleaning up...${NC}"
            $DOCKER_COMPOSE down -v
            echo -e "${GREEN}✓ Cleanup complete${NC}"
        else
            echo "Cancelled"
        fi
        ;;
    
    status)
        echo -e "${BLUE}Service status:${NC}"
        $DOCKER_COMPOSE ps
        ;;
    
    shell-backend)
        echo -e "${BLUE}Opening shell in backend container...${NC}"
        $DOCKER_COMPOSE exec backend /bin/bash
        ;;
    
    shell-worker)
        echo -e "${BLUE}Opening shell in worker container...${NC}"
        $DOCKER_COMPOSE exec worker /bin/bash
        ;;
    
    help|--help|-h)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  up, start       Start all services (default)"
        echo "  logs            Show logs from all services"
        echo "  stop, down      Stop all services"
        echo "  restart         Restart all services"
        echo "  build           Rebuild service images"
        echo "  clean           Remove all containers and volumes"
        echo "  status          Show service status"
        echo "  shell-backend   Open shell in backend container"
        echo "  shell-worker    Open shell in worker container"
        echo "  help            Show this help message"
        ;;
    
    *)
        echo -e "${RED}Error: Unknown command '$MODE'${NC}"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac
