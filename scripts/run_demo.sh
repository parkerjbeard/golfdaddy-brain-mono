#!/bin/bash
# Run demo with proper environment loading

# Navigate to backend directory where .env is located
cd backend

# Activate virtual environment
source ../venv/bin/activate

# Load environment variables from .env file
set -a
source .env
set +a

# Run the demo script
echo "Starting GolfDaddy Brain Demo..."
echo "================================"
echo ""

# Check which demo to run
if [ "$1" == "full" ]; then
    echo "Running comprehensive demo..."
    python ../scripts/demo_golfdaddy.py
else
    echo "Running quick demo..."
    python ../scripts/demo_quick.py
fi