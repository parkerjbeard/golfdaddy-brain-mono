#!/bin/bash
# Run parallel commit analysis benchmarking

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

echo -e "${GREEN}GolfDaddy Brain - Parallel Commit Analysis Benchmarking${NC}"
echo -e "${BLUE}======================================================${NC}"
echo -e "${YELLOW}⚡ Using asyncio for 3-5x faster execution${NC}"
echo ""

# Check if we're in the project root
if [ ! -d "$PROJECT_ROOT/backend" ] || [ ! -d "$PROJECT_ROOT/frontend" ]; then
    echo -e "${RED}Error: This script must be run from the golfdaddy-brain project${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/backend/venv" ]; then
    echo -e "${YELLOW}Backend virtual environment not found.${NC}"
    echo "Creating virtual environment..."
    cd "$PROJECT_ROOT/backend"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd "$PROJECT_ROOT"
else
    # Activate virtual environment
    source "$PROJECT_ROOT/backend/venv/bin/activate"
fi

# Check required environment variables
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${YELLOW}Warning: GITHUB_TOKEN not set${NC}"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}Warning: OPENAI_API_KEY not set${NC}"
fi

# Show comparison
echo -e "${BLUE}Benchmark Mode Comparison:${NC}"
echo "┌─────────────────┬──────────────┬──────────────┐"
echo "│ Mode            │ Execution    │ Speed        │"
echo "├─────────────────┼──────────────┼──────────────┤"
echo "│ Serial (old)    │ Sequential   │ ~30-60s      │"
echo "│ Parallel (new)  │ Concurrent   │ ~10-20s      │"
echo "└─────────────────┴──────────────┴──────────────┘"
echo ""

# Run the parallel benchmark tool
echo -e "${GREEN}Starting parallel benchmark tool...${NC}\n"
python "$PROJECT_ROOT/scripts/benchmark_commit_analysis_parallel.py" "$@"

# Deactivate virtual environment
deactivate 2>/dev/null || true