#!/bin/bash
# ============================================================
# AMASCI - Production Build Script
# Builds all components for deployment
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[BUILD]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

ENV="${1:-production}"
TAG="${2:-latest}"

echo "============================================================"
echo "  AMASCI Production Build"
echo "  Environment: $ENV"
echo "  Tag: $TAG"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# --- Validate Prerequisites ---
log "Validating prerequisites..."
command -v docker >/dev/null 2>&1 || error "Docker not found"
command -v node >/dev/null 2>&1 || error "Node.js not found"
command -v python3 >/dev/null 2>&1 || error "Python3 not found"
success "Prerequisites validated"

# --- Backend Validation ---
log "Validating backend..."
cd backend
python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/**/*.py', recursive=True)]" 2>/dev/null || error "Backend syntax errors detected"
success "Backend validation passed"
cd "$PROJECT_ROOT"

# --- Frontend Build ---
log "Building frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm ci --ignore-scripts
fi
npx tsc --noEmit || error "TypeScript errors detected"
npm run build || error "Frontend build failed"
BUILD_SIZE=$(du -sh dist/ | cut -f1)
success "Frontend built ($BUILD_SIZE)"
cd "$PROJECT_ROOT"

# --- Docker Images ---
log "Building Docker images..."

COMPOSE_FILE="docker-compose.prod.yml"
if [ "$ENV" = "staging" ]; then
    COMPOSE_FILE="docker-compose.staging.yml"
fi

docker compose -f "$COMPOSE_FILE" build \
    --build-arg VITE_API_BASE_URL="${VITE_API_BASE_URL:-}" \
    2>&1 | tail -5

success "Docker images built"

# --- Image Info ---
echo ""
echo "=== Built Images ==="
docker images --filter "reference=*amasci*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | head -10

echo ""
echo "============================================================"
success "Build complete for environment: $ENV"
echo ""
echo "Deploy with:"
echo "  docker compose -f $COMPOSE_FILE up -d"
echo "============================================================"
