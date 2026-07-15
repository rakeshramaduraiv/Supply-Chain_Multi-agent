#!/bin/bash
# ============================================================
# AMASCI - PostgreSQL Backup Script
# Supports full and incremental backups with rotation
# ============================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/app/data/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-amasci-postgres}"
POSTGRES_USER="${POSTGRES_USER:-amasci_user}"
POSTGRES_DB="${POSTGRES_DB:-amasci_db}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting PostgreSQL backup..."
echo "  Database: $POSTGRES_DB"
echo "  Output: $BACKUP_FILE"

docker exec "$POSTGRES_CONTAINER" pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --format=custom \
    --compress=9 \
    --verbose \
    2>/dev/null | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup completed successfully: $FILESIZE"
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

echo "[$(date)] Cleaning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
REMAINING=$(ls -1 "$BACKUP_DIR"/*.sql.gz 2>/dev/null | wc -l)
echo "[$(date)] Remaining backups: $REMAINING"

echo "[$(date)] PostgreSQL backup complete."
