#!/bin/bash
set -e

# Deployment script for backend services
# Usage: ./deploy.sh [environment] [version]

ENVIRONMENT=${1:-staging}
VERSION=${2:-latest}
REGISTRY="ghcr.io/yourusername/golfdaddy-backend"

echo "🚀 Starting deployment to $ENVIRONMENT with version $VERSION"

# Function to check command existence
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check required tools
for cmd in docker kubectl helm aws; do
    if ! command_exists $cmd; then
        echo "❌ Error: $cmd is not installed"
        exit 1
    fi
done

# Login to container registry
echo "🔐 Logging into container registry..."
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_ACTOR --password-stdin

# Pull latest image
echo "📦 Pulling image: $REGISTRY:$VERSION"
docker pull $REGISTRY:$VERSION

# Deploy based on environment
case $ENVIRONMENT in
    staging)
        echo "🌤️  Deploying to staging..."
        kubectl config use-context staging-cluster
        helm upgrade --install backend ./helm/backend \
            --namespace staging \
            --set image.tag=$VERSION \
            --set environment=staging \
            --values ./helm/backend/values.staging.yaml \
            --wait
        ;;
    
    production)
        echo "🌟 Deploying to production..."
        kubectl config use-context production-cluster
        
        # Create backup before deployment
        echo "💾 Creating database backup..."
        kubectl exec -n production deployment/backend -- python scripts/backup_database.py
        
        # Deploy with rolling update
        helm upgrade --install backend ./helm/backend \
            --namespace production \
            --set image.tag=$VERSION \
            --set environment=production \
            --values ./helm/backend/values.production.yaml \
            --wait \
            --atomic \
            --timeout 10m
        ;;
    
    *)
        echo "❌ Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

# Run post-deployment checks
echo "🔍 Running post-deployment checks..."
./scripts/deployment/health_check.sh $ENVIRONMENT

# Run migrations if needed
echo "🗄️  Checking for pending migrations..."
kubectl exec -n $ENVIRONMENT deployment/backend -- python scripts/check_migrations.py
if [ $? -eq 1 ]; then
    echo "📝 Running migrations..."
    kubectl exec -n $ENVIRONMENT deployment/backend -- python scripts/run_migrations.py
fi

# Send notification
echo "📬 Sending deployment notification..."
./scripts/deployment/notify.sh $ENVIRONMENT $VERSION "success"

echo "✅ Deployment completed successfully!"