#!/bin/bash
# ============================================================
# AMASCI - Database Restore Script
# Restores PostgreSQL or Neo4j from backup
# ============================================================

set -euo pipefail

usage() {
    echo "Usage: $0 <postgres|neo4j> <backup_file>"
    echo ""
    echo "Examples:"
    echo "  $0 postgres /backups/amasci_db_20240920_060000.sql.gz"
    echo "  $0 neo4j /backups/neo4j_backup_20240920_060000.dump.gz"
    exit 1
}

if [ $# -lt 2 ]; then
    usage
fi

DB_TYPE=$1
BACKUP_FILE=$2

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

restore_postgres() {
    local CONTAINER="${POSTGRES_CONTAINER:-amasci-postgres}"
    local USER="${POSTGRES_USER:-amasci_user}"
    local DB="${POSTGRES_DB:-amasci_db}"

    echo "[$(date)] Restoring PostgreSQL from: $BACKUP_FILE"
    echo "  WARNING: This will overwrite the current database!"
    read -p "  Continue? (y/N): " confirm
    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi

    echo "[$(date)] Dropping existing database..."
    docker exec "$CONTAINER" psql -U "$USER" -c "DROP DATABASE IF EXISTS ${DB};" postgres
    docker exec "$CONTAINER" psql -U "$USER" -c "CREATE DATABASE ${DB};" postgres

    echo "[$(date)] Restoring from backup..."
    gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" pg_restore -U "$USER" -d "$DB" --verbose

    echo "[$(date)] PostgreSQL restore complete."
}

restore_neo4j() {
    local CONTAINER="${NEO4J_CONTAINER:-amasci-neo4j}"

    echo "[$(date)] Restoring Neo4j from: $BACKUP_FILE"
    echo "  WARNING: This will stop Neo4j and overwrite the database!"
    read -p "  Continue? (y/N): " confirm
    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi

    local TEMP_FILE="/tmp/neo4j_restore.dump"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"

    echo "[$(date)] Stopping Neo4j..."
    docker exec "$CONTAINER" neo4j stop

    echo "[$(date)] Loading backup..."
    docker cp "$TEMP_FILE" "$CONTAINER:/backups/neo4j.dump"
    docker exec "$CONTAINER" neo4j-admin database load neo4j --from-path=/backups/ --overwrite-destination

    echo "[$(date)] Starting Neo4j..."
    docker exec "$CONTAINER" neo4j start

    rm -f "$TEMP_FILE"
    echo "[$(date)] Neo4j restore complete."
}

case "$DB_TYPE" in
    postgres) restore_postgres ;;
    neo4j) restore_neo4j ;;
    *) echo "ERROR: Unknown database type: $DB_TYPE"; usage ;;
esac
