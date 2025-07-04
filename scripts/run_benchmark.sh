#!/bin/bash
# Convenience script to run commit analysis benchmarking with proper environment

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

echo -e "${GREEN}GolfDaddy Brain - Commit Analysis Benchmarking${NC}"
echo "================================================"

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
    echo "The benchmark tool requires a GitHub Personal Access Token"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}Warning: OPENAI_API_KEY not set${NC}"
    echo "The benchmark tool requires an OpenAI API key"
fi

# Run the benchmark tool
echo -e "\n${GREEN}Starting benchmark tool...${NC}\n"
python "$PROJECT_ROOT/scripts/benchmark_commit_analysis.py" "$@"

# Deactivate virtual environment
deactivate 2>/dev/null || true