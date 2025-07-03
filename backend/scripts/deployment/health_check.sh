#!/bin/bash
set -e

ENVIRONMENT=${1:-staging}
MAX_RETRIES=30
RETRY_INTERVAL=10

case $ENVIRONMENT in
    staging)
        API_URL="https://staging-api.golfdaddy-brain.com"
        ;;
    production)
        API_URL="https://api.golfdaddy-brain.com"
        ;;
    *)
        echo "Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

echo "🔍 Running health checks for $ENVIRONMENT..."

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local expected_status=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")
    
    if [ "$response" -eq "$expected_status" ]; then
        echo "✅ $endpoint - OK (Status: $response)"
        return 0
    else
        echo "❌ $endpoint - Failed (Expected: $expected_status, Got: $response)"
        return 1
    fi
}

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
retry_count=0
while [ $retry_count -lt $MAX_RETRIES ]; do
    if check_endpoint "/health" 200; then
        break
    fi
    
    retry_count=$((retry_count + 1))
    if [ $retry_count -eq $MAX_RETRIES ]; then
        echo "❌ Service failed to become ready after $MAX_RETRIES retries"
        exit 1
    fi
    
    echo "⏳ Retrying in $RETRY_INTERVAL seconds... ($retry_count/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

# Check all critical endpoints
echo "🔍 Checking critical endpoints..."
check_endpoint "/health" 200
check_endpoint "/api/v1/docs" 200
check_endpoint "/metrics" 200

# Check database connectivity
echo "🗄️  Checking database connectivity..."
kubectl exec -n $ENVIRONMENT deployment/backend -- python -c "
from app.core.database import get_db
import asyncio

async def check_db():
    try:
        async for db in get_db():
            await db.execute('SELECT 1')
            print('✅ Database connection - OK')
            return True
    except Exception as e:
        print(f'❌ Database connection - Failed: {e}')
        return False

asyncio.run(check_db())
"

# Check Redis connectivity
echo "📮 Checking Redis connectivity..."
kubectl exec -n $ENVIRONMENT deployment/backend -- python -c "
import redis
import os

try:
    r = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
    r.ping()
    print('✅ Redis connection - OK')
except Exception as e:
    print(f'❌ Redis connection - Failed: {e}')
"

# Check external services
echo "🌐 Checking external service connectivity..."
kubectl exec -n $ENVIRONMENT deployment/backend -- python -c "
import requests
import os

services = {
    'Supabase': os.getenv('SUPABASE_URL'),
    'OpenAI': 'https://api.openai.com/v1/models',
    'Slack': 'https://slack.com/api/api.test'
}

for name, url in services.items():
    if url:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                print(f'✅ {name} - OK')
            else:
                print(f'⚠️  {name} - Degraded (Status: {response.status_code})')
        except Exception as e:
            print(f'❌ {name} - Failed: {e}')
"

echo "✅ All health checks completed!"