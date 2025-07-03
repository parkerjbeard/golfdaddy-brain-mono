#!/bin/bash
# One-time setup script for GolfDaddy Brain

echo "🔧 GolfDaddy Brain Setup"
echo "======================="
echo ""

# Check for required tools
echo "Checking requirements..."

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed. Please install it first."
        exit 1
    else
        echo "✅ $1 found"
    fi
}

check_command docker
check_command docker-compose
check_command git

echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p data
mkdir -p backups
mkdir -p logs
echo "✅ Directories created"

echo ""

# Setup .env file
if [ ! -f .env ]; then
    echo "Setting up environment variables..."
    cp .env.example .env
    
    echo ""
    echo "📝 Please edit the .env file with your settings:"
    echo ""
    echo "Required settings:"
    echo "  - OPENAI_API_KEY: Your OpenAI API key"
    echo "  - SLACK_BOT_TOKEN: Your Slack bot token (if using Slack)"
    echo "  - SUPABASE_URL: Your Supabase URL (if using Supabase)"
    echo "  - SUPABASE_KEY: Your Supabase key (if using Supabase)"
    echo ""
    echo "Press Enter to open .env in your default editor..."
    read
    ${EDITOR:-nano} .env
else
    echo "✅ .env file already exists"
fi

echo ""

# Set up cron jobs
echo "Would you like to set up automatic backups? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    # Add cron job for daily backups at 2 AM
    (crontab -l 2>/dev/null; echo "0 2 * * * cd $(pwd) && ./scripts/backup.sh") | crontab -
    echo "✅ Daily backups scheduled for 2 AM"
fi

echo ""

# Build and start
echo "Building and starting application..."
./deploy-simple.sh

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Access the application at http://localhost:8000"
echo "2. View API documentation at http://localhost:8000/docs"
echo "3. Check logs: docker-compose -f docker-compose.simple.yml logs -f"
echo ""
echo "Daily maintenance:"
echo "- Backups will run automatically at 2 AM (if enabled)"
echo "- To manually backup: ./scripts/backup.sh"
echo "- To update: git pull && ./deploy-simple.sh"