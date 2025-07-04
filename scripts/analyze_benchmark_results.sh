#!/bin/bash
# Convenience script to analyze benchmark results

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

echo -e "${GREEN}GolfDaddy Brain - Benchmark Results Analyzer${NC}"
echo "============================================="

# Check if benchmark results exist
if [ ! -d "$PROJECT_ROOT/benchmark_results" ]; then
    echo -e "${RED}No benchmark_results directory found${NC}"
    echo "Run ./scripts/run_benchmark.sh first to generate results"
    exit 1
fi

# Count JSON files
FILE_COUNT=$(find "$PROJECT_ROOT/benchmark_results" -name "benchmark_*.json" 2>/dev/null | wc -l)

if [ $FILE_COUNT -eq 0 ]; then
    echo -e "${YELLOW}No benchmark results found${NC}"
    echo "Run ./scripts/run_benchmark.sh first to generate results"
    exit 1
fi

echo -e "${GREEN}Found $FILE_COUNT benchmark result file(s)${NC}\n"

# Run the analyzer (doesn't need backend venv)
python "$PROJECT_ROOT/scripts/analyze_benchmarks.py" "$@"