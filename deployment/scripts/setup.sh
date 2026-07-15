#!/bin/bash
# ============================================================
# AMASCI - Initial Setup Script
# Prepares a fresh environment for first deployment
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${BLUE}[SETUP]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo "============================================================"
echo "  AMASCI - Initial Environment Setup"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# --- Check Docker ---
log "Checking Docker..."
if ! command -v docker &>/dev/null; then
    echo "Docker is required. Install from https://docs.docker.com/get-docker/"
    exit 1
fi
docker_version=$(docker --version | awk '{print $3}' | tr -d ',')
success "Docker $docker_version"

if ! command -v docker compose &>/dev/null; then
    echo "Docker Compose v2 is required."
    exit 1
fi
success "Docker Compose available"

# --- Create Data Directories ---
log "Creating data directories..."
mkdir -p backend/data/uploads backend/data/models backend/data/logs backend/data/backups
touch backend/data/uploads/.gitkeep backend/data/models/.gitkeep backend/data/logs/.gitkeep
success "Data directories created"

# --- Backend Setup ---
log "Setting up backend..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
    success "Virtual environment created"
fi
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null || true
pip install -r requirements.txt -q
success "Backend dependencies installed"
cd "$PROJECT_ROOT"

# --- Frontend Setup ---
log "Setting up frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm ci
    success "Frontend dependencies installed"
else
    success "Frontend dependencies already installed"
fi
npx tsc --noEmit
success "TypeScript validation passed"
cd "$PROJECT_ROOT"

# --- Environment Files ---
log "Checking environment files..."
if [ ! -f ".env.development" ]; then
    warn ".env.development not found - using defaults"
fi
if [ ! -f ".env.staging" ]; then
    warn ".env.staging not found - using defaults"
fi
success "Environment files checked"

# --- Docker Network ---
log "Preparing Docker networks..."
docker network create amasci-net 2>/dev/null || true
success "Docker networks ready"

# --- Summary ---
echo ""
echo "============================================================"
success "Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Start development:  make dev"
echo "    2. Start frontend:     cd frontend && npm run dev"
echo "    3. Run tests:          make test"
echo "    4. Build production:   make prod-build"
echo ""
echo "  Documentation:"
echo "    - Deployment:  deployment/docs/DEPLOYMENT.md"
echo "    - Developer:   deployment/docs/DEVELOPER.md"
echo "    - API:         deployment/docs/API.md"
echo "============================================================"
