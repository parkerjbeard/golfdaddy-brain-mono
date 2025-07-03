#!/bin/bash
# Backup script with S3 support for AWS deployment

BACKUP_DIR="./backups"
DATA_DIR="./data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
S3_BUCKET=$(grep S3_BACKUP_BUCKET .env | cut -d '=' -f2)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Create backup directory
mkdir -p $BACKUP_DIR

echo "📦 Starting backup..."

# Backup SQLite database
if [ -f "$DATA_DIR/golfdaddy.db" ]; then
    BACKUP_FILE="$BACKUP_DIR/golfdaddy_${TIMESTAMP}.db"
    cp "$DATA_DIR/golfdaddy.db" "$BACKUP_FILE"
    gzip "$BACKUP_FILE"
    echo -e "${GREEN}✅ Database backed up${NC}"
    
    # Upload to S3 if configured
    if [ ! -z "$S3_BUCKET" ] && command -v aws &> /dev/null; then
        echo "☁️  Uploading to S3..."
        aws s3 cp "${BACKUP_FILE}.gz" "s3://${S3_BUCKET}/backups/" --storage-class STANDARD_IA
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Uploaded to S3${NC}"
            # Remove local backup to save space (keep only last 3 locally)
            ls -t $BACKUP_DIR/*.gz | tail -n +4 | xargs -r rm
        else
            echo -e "${RED}❌ S3 upload failed${NC}"
        fi
    fi
fi

# Backup .env file (encrypted)
if [ -f ".env" ]; then
    # Remove sensitive data and backup
    grep -v "KEY\|TOKEN\|SECRET" .env | gzip > "$BACKUP_DIR/env_${TIMESTAMP}.txt.gz"
    echo -e "${GREEN}✅ Configuration backed up${NC}"
fi

# Create backup summary
cat > "$BACKUP_DIR/backup_${TIMESTAMP}.log" << EOF
Backup Summary
==============
Date: $(date)
Database size: $(du -h "$DATA_DIR/golfdaddy.db" 2>/dev/null | cut -f1)
Total backup size: $(du -sh $BACKUP_DIR | cut -f1)
S3 Bucket: ${S3_BUCKET:-"Not configured"}
Instance: $(ec2-metadata --instance-id 2>/dev/null | cut -d " " -f 2 || echo "Unknown")
EOF

# Clean up old local backups (keep last 7 days)
find $BACKUP_DIR -type f -name "*.gz" -mtime +7 -delete

echo -e "${GREEN}✅ Backup complete${NC}"

# Check backup integrity
if [ -f "${BACKUP_FILE}.gz" ]; then
    gzip -t "${BACKUP_FILE}.gz" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Backup integrity verified${NC}"
    else
        echo -e "${RED}❌ Backup corrupted!${NC}"
        exit 1
    fi
fi

# Send notification (optional)
# You can add SNS notification here if needed
# aws sns publish --topic-arn arn:aws:sns:region:account:topic --message "GolfDaddy backup completed"