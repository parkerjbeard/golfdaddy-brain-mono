#!/bin/bash
# Simple monitoring script for GolfDaddy Brain on AWS

# Configuration
HEALTH_URL="https://localhost/health"
MAX_MEMORY_PERCENT=80
MAX_DISK_PERCENT=85
LOG_FILE="./logs/monitor.log"

# Create log directory
mkdir -p logs

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# Check application health
check_health() {
    response=$(curl -k -s -o /dev/null -w "%{http_code}" $HEALTH_URL)
    if [ "$response" != "200" ]; then
        log_message "ERROR: Health check failed (HTTP $response)"
        # Restart container
        docker-compose -f docker-compose.aws.yml restart app
        log_message "INFO: Attempted restart of app container"
        return 1
    fi
    return 0
}

# Check memory usage
check_memory() {
    memory_usage=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
    if [ "$memory_usage" -gt "$MAX_MEMORY_PERCENT" ]; then
        log_message "WARNING: High memory usage: ${memory_usage}%"
        # Clear Docker cache if needed
        docker system prune -f >> $LOG_FILE 2>&1
    fi
}

# Check disk usage
check_disk() {
    disk_usage=$(df -h / | awk 'NR==2 {print int($5)}')
    if [ "$disk_usage" -gt "$MAX_DISK_PERCENT" ]; then
        log_message "WARNING: High disk usage: ${disk_usage}%"
        # Clean old backups
        find ./backups -name "*.gz" -mtime +3 -delete
        # Clean Docker
        docker system prune -a -f >> $LOG_FILE 2>&1
    fi
}

# Check container status
check_containers() {
    containers=$(docker-compose -f docker-compose.aws.yml ps -q | wc -l)
    if [ "$containers" -lt 2 ]; then
        log_message "ERROR: Not all containers are running"
        docker-compose -f docker-compose.aws.yml up -d
    fi
}

# Main monitoring
log_message "INFO: Starting monitoring check"

check_health || exit 1
check_memory
check_disk
check_containers

# If running from cron, only log errors
if [ -t 1 ]; then
    echo "✅ All checks passed"
    echo "Memory: $(free | grep Mem | awk '{print int($3/$2 * 100)}')%"
    echo "Disk: $(df -h / | awk 'NR==2 {print $5}')"
    echo "Containers: $(docker ps --format "table {{.Names}}\t{{.Status}}" | tail -n +2)"
fi