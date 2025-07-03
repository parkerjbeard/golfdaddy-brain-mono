#!/bin/bash
# Simple deployment script for internal tool

echo "🚀 Deploying GolfDaddy Brain..."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull

# Ensure data directory exists
mkdir -p data

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your API keys and run again."
    exit 1
fi

# Build and start containers
echo "🐳 Building and starting Docker containers..."
docker-compose -f docker-compose.simple.yml build
docker-compose -f docker-compose.simple.yml up -d

# Wait for health check
echo "⏳ Waiting for application to be healthy..."
sleep 10

# Check if app is running
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Application is running at http://localhost:8000"
    echo "📚 API docs available at http://localhost:8000/docs"
else
    echo "❌ Application failed to start. Check logs with:"
    echo "   docker-compose -f docker-compose.simple.yml logs"
    exit 1
fi

# Show logs
echo ""
echo "📋 Recent logs:"
docker-compose -f docker-compose.simple.yml logs --tail=20

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Useful commands:"
echo "  View logs:    docker-compose -f docker-compose.simple.yml logs -f"
echo "  Restart:      docker-compose -f docker-compose.simple.yml restart"
echo "  Stop:         docker-compose -f docker-compose.simple.yml down"
echo "  Backup data:  cp -r data/ data-backup-$(date +%Y%m%d)/"