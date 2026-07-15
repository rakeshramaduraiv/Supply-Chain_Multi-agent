#!/bin/bash
# ============================================================
# AMASCI - Full Application Backup Script
# Backs up databases, models, uploads, and configuration
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BACKUP_BASE="${BACKUP_BASE:-$PROJECT_ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/full_${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

echo "============================================================"
echo "  AMASCI Full Backup"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Output: $BACKUP_DIR"
echo "============================================================"
echo ""

# --- PostgreSQL Backup ---
echo "[$(date +%H:%M:%S)] Backing up PostgreSQL..."
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-amasci-postgres}"
POSTGRES_USER="${POSTGRES_USER:-amasci_user}"
POSTGRES_DB="${POSTGRES_DB:-amasci_db}"

if docker ps --format '{{.Names}}' | grep -q "$POSTGRES_CONTAINER"; then
    docker exec "$POSTGRES_CONTAINER" pg_dump \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --format=custom \
        --compress=9 \
        > "$BACKUP_DIR/postgres.dump" 2>/dev/null
    echo "  PostgreSQL: $(du -h "$BACKUP_DIR/postgres.dump" | cut -f1)"
else
    echo "  PostgreSQL: SKIPPED (container not running)"
fi

# --- Neo4j Backup ---
echo "[$(date +%H:%M:%S)] Backing up Neo4j..."
NEO4J_CONTAINER="${NEO4J_CONTAINER:-amasci-neo4j}"

if docker ps --format '{{.Names}}' | grep -q "$NEO4J_CONTAINER"; then
    docker exec "$NEO4J_CONTAINER" neo4j-admin database dump neo4j --to-path=/backups/ 2>/dev/null || true
    docker cp "$NEO4J_CONTAINER:/backups/neo4j.dump" "$BACKUP_DIR/neo4j.dump" 2>/dev/null || true
    if [ -f "$BACKUP_DIR/neo4j.dump" ]; then
        echo "  Neo4j: $(du -h "$BACKUP_DIR/neo4j.dump" | cut -f1)"
    else
        echo "  Neo4j: SKIPPED (dump not available)"
    fi
else
    echo "  Neo4j: SKIPPED (container not running)"
fi

# --- ML Models Backup ---
echo "[$(date +%H:%M:%S)] Backing up ML models..."
if [ -d "$PROJECT_ROOT/backend/data/models" ] && [ "$(ls -A $PROJECT_ROOT/backend/data/models 2>/dev/null)" ]; then
    tar -czf "$BACKUP_DIR/models.tar.gz" -C "$PROJECT_ROOT/backend/data" models/
    echo "  Models: $(du -h "$BACKUP_DIR/models.tar.gz" | cut -f1)"
else
    echo "  Models: SKIPPED (no models found)"
fi

# --- Uploads Backup ---
echo "[$(date +%H:%M:%S)] Backing up uploads..."
if [ -d "$PROJECT_ROOT/backend/data/uploads" ] && [ "$(ls -A $PROJECT_ROOT/backend/data/uploads 2>/dev/null)" ]; then
    tar -czf "$BACKUP_DIR/uploads.tar.gz" -C "$PROJECT_ROOT/backend/data" uploads/
    echo "  Uploads: $(du -h "$BACKUP_DIR/uploads.tar.gz" | cut -f1)"
else
    echo "  Uploads: SKIPPED (no uploads found)"
fi

# --- Configuration Backup ---
echo "[$(date +%H:%M:%S)] Backing up configuration..."
tar -czf "$BACKUP_DIR/config.tar.gz" \
    -C "$PROJECT_ROOT" \
    --exclude='.env.production' \
    .env.development \
    .env.staging \
    deployment/nginx/ \
    deployment/monitoring/ \
    2>/dev/null || true
echo "  Config: $(du -h "$BACKUP_DIR/config.tar.gz" | cut -f1)"

# --- Create Manifest ---
cat > "$BACKUP_DIR/manifest.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "version": "1.0.0",
  "environment": "${APP_ENV:-production}",
  "components": {
    "postgres": $([ -f "$BACKUP_DIR/postgres.dump" ] && echo "true" || echo "false"),
    "neo4j": $([ -f "$BACKUP_DIR/neo4j.dump" ] && echo "true" || echo "false"),
    "models": $([ -f "$BACKUP_DIR/models.tar.gz" ] && echo "true" || echo "false"),
    "uploads": $([ -f "$BACKUP_DIR/uploads.tar.gz" ] && echo "true" || echo "false"),
    "config": true
  }
}
EOF

# --- Compress Full Backup ---
echo "[$(date +%H:%M:%S)] Compressing full backup..."
cd "$BACKUP_BASE"
tar -czf "full_${TIMESTAMP}.tar.gz" "full_${TIMESTAMP}/"
rm -rf "full_${TIMESTAMP}/"
TOTAL_SIZE=$(du -h "full_${TIMESTAMP}.tar.gz" | cut -f1)

# --- Cleanup Old Backups ---
echo "[$(date +%H:%M:%S)] Cleaning backups older than $RETENTION_DAYS days..."
find "$BACKUP_BASE" -name "full_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

echo ""
echo "============================================================"
echo "  Backup complete: full_${TIMESTAMP}.tar.gz ($TOTAL_SIZE)"
echo "============================================================"
