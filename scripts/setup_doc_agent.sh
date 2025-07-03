#!/bin/bash
#
# Setup script for GolfDaddy Brain Documentation Agent
# This script helps configure the documentation agent for your repository
#

set -e

echo "🚀 GolfDaddy Brain Documentation Agent Setup"
echo "==========================================="
echo ""

# Check if running in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: This script must be run from within a Git repository"
    exit 1
fi

# Function to prompt for input with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " value
        value="${value:-$default}"
    else
        read -p "$prompt: " value
    fi
    
    eval "$var_name='$value'"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "📋 Prerequisites Check"
echo "--------------------"

# Check Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✅ Python: $PYTHON_VERSION"
else
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Check pip
if command_exists pip3; then
    echo "✅ pip is installed"
else
    echo "❌ pip3 is required but not found"
    exit 1
fi

echo ""
echo "🔧 Configuration"
echo "---------------"
echo "Please provide the following information:"
echo ""

# Get repository information
CURRENT_REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*github.com[:/]\(.*\)\.git/\1/' || echo "")
prompt_with_default "GitHub repository for documentation (owner/repo)" "$CURRENT_REPO" "DOCS_REPO"

# API Keys
echo ""
echo "🔑 API Keys Required:"
echo "-------------------"
echo "1. OpenAI API Key - for AI-powered documentation analysis"
echo "2. GitHub Personal Access Token - for creating PRs (needs 'repo' scope)"
echo "3. Slack Bot Token (optional) - for approval workflows"
echo ""

prompt_with_default "OpenAI API Key" "" "OPENAI_KEY"
prompt_with_default "GitHub Personal Access Token" "" "GITHUB_TOKEN"
prompt_with_default "Slack Bot Token (optional, press Enter to skip)" "" "SLACK_TOKEN"

if [ -n "$SLACK_TOKEN" ]; then
    prompt_with_default "Slack Channel for approvals (e.g., #dev-docs)" "#documentation" "SLACK_CHANNEL"
fi

echo ""
echo "📦 Installing Dependencies"
echo "------------------------"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages
echo "Installing required packages..."
pip install -q --upgrade pip
pip install -q openai github slack-sdk sqlalchemy

echo "✅ Dependencies installed"

echo ""
echo "🔧 Creating Configuration"
echo "-----------------------"

# Create .env file
cat > .env.doc-agent << EOF
# GolfDaddy Brain Documentation Agent Configuration
# Generated on $(date)

# Repository Settings
DOCS_REPOSITORY=$DOCS_REPO

# API Keys
OPENAI_API_KEY=$OPENAI_KEY
GITHUB_TOKEN=$GITHUB_TOKEN

# Slack Configuration (Optional)
EOF

if [ -n "$SLACK_TOKEN" ]; then
    cat >> .env.doc-agent << EOF
SLACK_BOT_TOKEN=$SLACK_TOKEN
SLACK_CHANNEL=$SLACK_CHANNEL
EOF
fi

# Add .env.doc-agent to .gitignore if not already there
if ! grep -q ".env.doc-agent" .gitignore 2>/dev/null; then
    echo "" >> .gitignore
    echo "# Documentation agent configuration" >> .gitignore
    echo ".env.doc-agent" >> .gitignore
    echo "✅ Added .env.doc-agent to .gitignore"
fi

echo ""
echo "🎯 GitHub Actions Setup"
echo "---------------------"
echo "To enable automatic documentation updates on commits:"
echo ""
echo "1. Go to your repository settings on GitHub"
echo "2. Navigate to Settings > Secrets and variables > Actions"
echo "3. Add the following secrets:"
echo "   - OPENAI_API_KEY: $OPENAI_KEY"
echo "   - DOC_AGENT_GITHUB_TOKEN: $GITHUB_TOKEN"
if [ -n "$SLACK_TOKEN" ]; then
    echo "   - SLACK_BOT_TOKEN: $SLACK_TOKEN"
fi
echo ""
echo "4. Add the following variables:"
echo "   - DOCS_REPOSITORY: $DOCS_REPO"
if [ -n "$SLACK_CHANNEL" ]; then
    echo "   - SLACK_DOC_CHANNEL: $SLACK_CHANNEL"
fi

echo ""
echo "📝 Pre-commit Hook Setup (Optional)"
echo "----------------------------------"
read -p "Would you like to install the pre-commit hook? (y/N): " install_hook

if [[ "$install_hook" =~ ^[Yy]$ ]]; then
    # Create pre-commit hook
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# GolfDaddy Brain Documentation Agent Pre-commit Hook

# Load configuration
if [ -f .env.doc-agent ]; then
    export $(cat .env.doc-agent | grep -v '^#' | xargs)
fi

# Run documentation analysis on staged changes
echo "🔍 Analyzing changes for documentation updates..."
python scripts/pre_commit_auto_docs.py

# The script will exit with 0 if no docs needed or if approved
exit $?
EOF
    chmod +x .git/hooks/pre-commit
    echo "✅ Pre-commit hook installed"
fi

echo ""
echo "🧪 Testing Configuration"
echo "----------------------"

# Test script to verify setup
cat > test_doc_agent.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Load environment variables
env_file = Path('.env.doc-agent')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Test imports
try:
    from doc_agent.client import AutoDocClient
    print("✅ Doc agent module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import doc agent: {e}")
    sys.exit(1)

# Test configuration
required_vars = ['OPENAI_API_KEY', 'GITHUB_TOKEN', 'DOCS_REPOSITORY']
missing = [var for var in required_vars if not os.environ.get(var)]

if missing:
    print(f"❌ Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)
else:
    print("✅ All required environment variables are set")

# Test client initialization
try:
    client = AutoDocClient(
        openai_api_key=os.environ['OPENAI_API_KEY'],
        github_token=os.environ['GITHUB_TOKEN'],
        docs_repo=os.environ['DOCS_REPOSITORY'],
        slack_channel=os.environ.get('SLACK_CHANNEL')
    )
    print("✅ Doc agent client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize client: {e}")
    sys.exit(1)

print("\n🎉 Documentation agent is configured and ready!")
EOF

python test_doc_agent.py
rm test_doc_agent.py

echo ""
echo "✨ Setup Complete!"
echo "=================="
echo ""
echo "The documentation agent is now configured for your repository."
echo ""
echo "📚 Quick Start:"
echo "--------------"
echo "1. Manual run: source .env.doc-agent && python scripts/auto_docs.py"
echo "2. The GitHub Action will run automatically on pushes to main/develop"
echo "3. Pre-commit hook will analyze changes before commits (if installed)"
echo ""
echo "For more information, see: docs/doc_agent_documentation.md"
echo ""