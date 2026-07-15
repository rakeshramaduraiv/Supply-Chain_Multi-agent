#!/bin/bash
# ============================================================
# AMASCI - Deployment Management Script
# Unified interface for all deployment operations
# ============================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[AMASCI]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

usage() {
    echo ""
    echo "AMASCI Deployment Manager"
    echo "========================="
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  dev         Start development environment"
    echo "  staging     Start staging environment"
    echo "  prod        Start production environment"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  build       Build Docker images"
    echo "  logs        View service logs"
    echo "  status      Show service status"
    echo "  health      Run health checks"
    echo "  backup      Run database backups"
    echo "  migrate     Run database migrations"
    echo "  test        Run test suite"
    echo "  clean       Remove all containers and volumes"
    echo ""
    exit 0
}

cmd_dev() {
    log "Starting development environment..."
    docker compose -f docker-compose.dev.yml up -d
    success "Development environment started"
    echo ""
    echo "  Backend:  http://localhost:8000"
    echo "  Neo4j:    http://localhost:7474"
    echo "  Postgres: localhost:5432"
    echo ""
    echo "  Run frontend separately: cd frontend && npm run dev"
}

cmd_prod() {
    log "Starting production environment..."
    if [ ! -f .env.production ]; then
        error ".env.production not found. Copy from template and configure."
    fi
    docker compose -f docker-compose.prod.yml --env-file .env.production up -d
    success "Production environment started"
    echo ""
    echo "  Application: http://localhost:${NGINX_PORT:-80}"
}

cmd_staging() {
    log "Starting staging environment..."
    docker compose -f docker-compose.staging.yml --env-file .env.staging up -d
    success "Staging environment started"
    echo ""
    echo "  Application: http://localhost:8080"
}

cmd_stop() {
    log "Stopping all services..."
    docker compose -f docker-compose.dev.yml down 2>/dev/null || true
    docker compose -f docker-compose.prod.yml down 2>/dev/null || true
    success "All services stopped"
}

cmd_restart() {
    cmd_stop
    if [ "${1:-dev}" = "prod" ]; then
        cmd_prod
    else
        cmd_dev
    fi
}

cmd_build() {
    log "Building Docker images..."
    docker compose -f docker-compose.prod.yml build --no-cache
    success "Docker images built"
}

cmd_logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker compose -f docker-compose.prod.yml logs -f "$service" 2>/dev/null || \
        docker compose -f docker-compose.dev.yml logs -f "$service"
    else
        docker compose -f docker-compose.prod.yml logs -f 2>/dev/null || \
        docker compose -f docker-compose.dev.yml logs -f
    fi
}

cmd_status() {
    echo ""
    echo "=== AMASCI Service Status ==="
    echo ""
    docker ps --filter "name=amasci" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
}

cmd_health() {
    bash deployment/monitoring/health-check.sh
}

cmd_backup() {
    log "Running database backups..."
    bash deployment/backup/backup-postgres.sh
    bash deployment/backup/backup-neo4j.sh
    success "All backups completed"
}

cmd_migrate() {
    log "Running database migrations..."
    docker exec amasci-api alembic upgrade head 2>/dev/null || \
    docker exec amasci-api-dev alembic upgrade head
    success "Migrations applied"
}

cmd_test() {
    log "Running test suite..."
    echo ""
    echo "--- Backend Tests ---"
    cd backend && pytest tests/ --override-ini="addopts=" -v --tb=short -x && cd ..
    echo ""
    echo "--- Frontend Type Check ---"
    cd frontend && npx tsc --noEmit && cd ..
    echo ""
    echo "--- Frontend Build ---"
    cd frontend && npm run build && cd ..
    success "All tests passed"
}

cmd_clean() {
    warn "This will remove ALL containers, images, and volumes!"
    read -p "Continue? (y/N): " confirm
    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
    docker compose -f docker-compose.dev.yml down -v --rmi all 2>/dev/null || true
    docker compose -f docker-compose.prod.yml down -v --rmi all 2>/dev/null || true
    success "Cleanup complete"
}

case "${1:-help}" in
    dev) cmd_dev ;;
    staging) cmd_staging ;;
    prod) cmd_prod ;;
    stop) cmd_stop ;;
    restart) cmd_restart "${2:-dev}" ;;
    build) cmd_build ;;
    logs) cmd_logs "${2:-}" ;;
    status) cmd_status ;;
    health) cmd_health ;;
    backup) cmd_backup ;;
    migrate) cmd_migrate ;;
    test) cmd_test ;;
    clean) cmd_clean ;;
    *) usage ;;
esac
