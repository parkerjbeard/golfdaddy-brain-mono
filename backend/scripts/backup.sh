#!/bin/bash
# Simple backup script for GolfDaddy Brain data

BACKUP_DIR="./backups"
DATA_DIR="./data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

echo "📦 Starting backup..."

# Backup SQLite database (if using SQLite)
if [ -f "$DATA_DIR/golfdaddy.db" ]; then
    cp "$DATA_DIR/golfdaddy.db" "$BACKUP_DIR/golfdaddy_${TIMESTAMP}.db"
    echo "✅ SQLite database backed up"
fi

# Backup PostgreSQL (if using PostgreSQL)
if docker-compose -f docker-compose.simple.yml ps | grep -q "db"; then
    docker-compose -f docker-compose.simple.yml exec -T db pg_dump -U postgres golfdaddy > "$BACKUP_DIR/golfdaddy_${TIMESTAMP}.sql"
    echo "✅ PostgreSQL database backed up"
fi

# Backup .env file (without sensitive data)
if [ -f ".env" ]; then
    grep -v "API_KEY\|TOKEN\|SECRET" .env > "$BACKUP_DIR/env_${TIMESTAMP}.txt"
    echo "✅ Configuration backed up (sensitive data excluded)"
fi

# Backup uploaded files or data directory
if [ -d "$DATA_DIR/uploads" ]; then
    tar -czf "$BACKUP_DIR/uploads_${TIMESTAMP}.tar.gz" -C "$DATA_DIR" uploads/
    echo "✅ Uploaded files backed up"
fi

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete
echo "🧹 Old backups cleaned up"

echo "✅ Backup complete: $BACKUP_DIR/*_${TIMESTAMP}.*"

# Optional: Copy to network drive or cloud storage
# cp $BACKUP_DIR/*_${TIMESTAMP}.* /mnt/network-backup/golfdaddy/
# aws s3 cp $BACKUP_DIR/*_${TIMESTAMP}.* s3://company-backups/golfdaddy/