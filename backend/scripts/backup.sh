#!/usr/bin/env bash
# Supabase-only backup script
# Requires: pg_dump, gzip

set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_URL="${DATABASE_URL:-}"

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump not found. Install PostgreSQL client tools and retry." >&2
  exit 1
fi

if [ -z "$DB_URL" ]; then
  echo "DATABASE_URL is not set. Export your Supabase Postgres URL and retry." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "📦 Starting Supabase backup..."
OUT_FILE="$BACKUP_DIR/golfdaddy_${TIMESTAMP}.dump"

# Use custom format (-Fc) for flexible restore
pg_dump -Fc -f "$OUT_FILE" "$DB_URL"
gzip -9 "$OUT_FILE"

echo "✅ Backup complete: ${OUT_FILE}.gz"

# Keep only last 7 days of backups (gz files)
find "$BACKUP_DIR" -type f -name "*.dump.gz" -mtime +7 -delete || true
echo "🧹 Old backups cleaned up"
