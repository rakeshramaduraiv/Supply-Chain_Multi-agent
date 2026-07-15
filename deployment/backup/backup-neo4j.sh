#!/bin/bash
# ============================================================
# AMASCI - Neo4j Backup Script
# Full graph database backup with rotation
# ============================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/app/data/backups/neo4j}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
NEO4J_CONTAINER="${NEO4J_CONTAINER:-amasci-neo4j}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="neo4j_backup_${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Neo4j backup..."
echo "  Container: $NEO4J_CONTAINER"
echo "  Output: $BACKUP_DIR/$BACKUP_NAME"

docker exec "$NEO4J_CONTAINER" neo4j-admin database dump neo4j --to-path=/backups/ 2>/dev/null

docker cp "$NEO4J_CONTAINER:/backups/neo4j.dump" "$BACKUP_DIR/${BACKUP_NAME}.dump"

if [ $? -eq 0 ]; then
    gzip "$BACKUP_DIR/${BACKUP_NAME}.dump"
    FILESIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.dump.gz" | cut -f1)
    echo "[$(date)] Neo4j backup completed: $FILESIZE"
else
    echo "[$(date)] ERROR: Neo4j backup failed!"
    exit 1
fi

echo "[$(date)] Cleaning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Neo4j backup complete."
