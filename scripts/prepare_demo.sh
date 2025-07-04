#!/bin/bash
#
# GolfDaddy Brain Demo Preparation Script
# =======================================
# This script prepares your environment for running demos
#

set -e

echo "🚀 GolfDaddy Brain Demo Preparation"
echo "==================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the project root
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

echo "1️⃣  Checking Docker services..."
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Docker services are running${NC}"
else
    echo -e "${YELLOW}⚠️  Starting Docker services...${NC}"
    docker-compose up -d
    echo "   Waiting for services to be ready..."
    sleep 10
fi

echo ""
echo "2️⃣  Checking API health..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✅ API is healthy${NC}"
else
    echo -e "${RED}❌ API is not responding${NC}"
    echo "   Please check: docker-compose logs backend"
    exit 1
fi

echo ""
echo "3️⃣  Checking Frontend..."
if curl -s http://localhost:5173 > /dev/null; then
    echo -e "${GREEN}✅ Frontend is running${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend might be building, please wait...${NC}"
fi

echo ""
echo "4️⃣  Installing Python dependencies..."
pip install -q rich gitpython requests faker 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Some Python packages need to be installed manually:${NC}"
    echo "   pip install rich gitpython requests faker"
}

echo ""
echo "5️⃣  Environment variables check..."
required_vars=("OPENAI_API_KEY" "GITHUB_TOKEN" "SUPABASE_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=($var)
    fi
done

if [ ${#missing_vars[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All required environment variables are set${NC}"
else
    echo -e "${YELLOW}⚠️  Missing environment variables:${NC}"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo "   Please set these in your .env file"
fi

echo ""
echo "📋 Demo Options:"
echo "==============="
echo ""
echo "1. Quick Demo (15-20 minutes)"
echo "   ${GREEN}python scripts/demo_quick.py${NC}"
echo "   - Uses existing data"
echo "   - Shows all major features"
echo "   - Perfect for initial meetings"
echo ""
echo "2. Comprehensive Demo (45-60 minutes)"
echo "   ${GREEN}python scripts/demo_golfdaddy.py${NC}"
echo "   - Creates live GitHub repos"
echo "   - Generates real commits"
echo "   - Full end-to-end workflow"
echo ""
echo "3. Generate Demo Data"
echo "   ${GREEN}python scripts/generate_demo_data.py --days 30${NC}"
echo "   - Populates database with sample data"
echo "   - No GitHub integration needed"
echo "   - Good for offline demos"
echo ""
echo "📚 Resources:"
echo "============"
echo "- Demo Guide: ./DEMO_GUIDE.md"
echo "- API Docs: http://localhost:8000/docs"
echo "- Frontend: http://localhost:5173"
echo "- Dashboard: http://localhost:5173/dashboard"
echo ""
echo -e "${GREEN}✨ Demo environment is ready!${NC}"
echo ""
echo "Tip: Run 'python scripts/demo_quick.py' to start with a quick demo"
echo ""