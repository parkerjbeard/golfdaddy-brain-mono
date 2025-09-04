#!/usr/bin/env bash
# Supabase-only backup with S3 upload
# Requires: pg_dump, gzip, aws cli

set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_URL="${DATABASE_URL:-}"
S3_BUCKET="${S3_BACKUP_BUCKET:-}"
S3_PREFIX="${S3_BACKUP_PREFIX:-backups}"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

if ! command -v pg_dump >/dev/null 2>&1; then
  echo -e "${RED}pg_dump not found. Install PostgreSQL client tools and retry.${NC}" >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo -e "${RED}aws CLI not found. Install and configure AWS credentials to upload.${NC}" >&2
  exit 1
fi

if [ -z "$DB_URL" ]; then
  echo -e "${RED}DATABASE_URL is not set. Export your Supabase Postgres URL and retry.${NC}" >&2
  exit 1
fi

if [ -z "$S3_BUCKET" ]; then
  echo -e "${RED}S3_BACKUP_BUCKET is not set. Export it and retry.${NC}" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
echo "📦 Starting Supabase backup..."

OUT_FILE="$BACKUP_DIR/golfdaddy_${TIMESTAMP}.dump"
pg_dump -Fc -f "$OUT_FILE" "$DB_URL"
gzip -9 "$OUT_FILE"

echo -e "${GREEN}✅ Local backup complete: ${OUT_FILE}.gz${NC}"

S3_PATH="s3://${S3_BUCKET}/${S3_PREFIX}/golfdaddy_${TIMESTAMP}.dump.gz"
echo "☁️  Uploading to $S3_PATH ..."
aws s3 cp "${OUT_FILE}.gz" "$S3_PATH" --storage-class STANDARD_IA

echo -e "${GREEN}✅ Uploaded to S3${NC}"

# Retain only last 7 local backups
find "$BACKUP_DIR" -type f -name "*.dump.gz" -mtime +7 -delete || true
echo "🧹 Old local backups cleaned up"
