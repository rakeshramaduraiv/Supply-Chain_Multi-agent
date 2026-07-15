# ============================================================
# AMASCI - Project Makefile
# Unified commands for development and deployment
# ============================================================

.PHONY: help dev prod stop build test lint clean backup health logs migrate

SHELL := /bin/bash

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# --- Development ---

dev: ## Start development environment
	docker compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "Backend: http://localhost:8000"
	@echo "Neo4j:   http://localhost:7474"
	@echo ""
	@echo "Start frontend: cd frontend && npm run dev"

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

dev-backend: ## Start backend with reload
	cd backend && uvicorn app.main:app --reload --port 8000

# --- Staging ---

staging: ## Start staging environment
	docker compose -f docker-compose.staging.yml --env-file .env.staging up -d

staging-build: ## Build staging images
	docker compose -f docker-compose.staging.yml build --no-cache

staging-stop: ## Stop staging environment
	docker compose -f docker-compose.staging.yml down

# --- Production ---

prod: ## Start production environment
	docker compose -f docker-compose.prod.yml --env-file .env.production up -d

prod-build: ## Build production images
	docker compose -f docker-compose.prod.yml build --no-cache

# --- Testing ---

test: ## Run all tests
	cd backend && pytest tests/ --override-ini="addopts=" -v --tb=short -x
	cd frontend && npx tsc --noEmit

test-backend: ## Run backend tests only
	cd backend && pytest tests/ --override-ini="addopts=" -v --tb=short -x

test-frontend: ## Run frontend type check and build
	cd frontend && npx tsc --noEmit && npm run build

# --- Linting ---

lint: ## Run all linters
	cd backend && ruff check app/ && black --check app/ && isort --check-only app/
	cd frontend && npx tsc --noEmit

lint-fix: ## Fix lint issues
	cd backend && ruff check --fix app/ && black app/ && isort app/

# --- Infrastructure ---

stop: ## Stop all services
	docker compose -f docker-compose.dev.yml down 2>/dev/null || true
	docker compose -f docker-compose.prod.yml down 2>/dev/null || true

restart: ## Restart development environment
	$(MAKE) stop
	$(MAKE) dev

logs: ## View all logs
	docker compose -f docker-compose.dev.yml logs -f 2>/dev/null || docker compose -f docker-compose.prod.yml logs -f

status: ## Show container status
	docker ps --filter "name=amasci" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

health: ## Run health checks
	bash deployment/monitoring/health-check.sh

# --- Database ---

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-new: ## Create new migration (usage: make migrate-new MSG="description")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

backup: ## Run database backups
	bash deployment/backup/backup-postgres.sh
	bash deployment/backup/backup-neo4j.sh

# --- Cleanup ---

clean: ## Remove containers and volumes
	docker compose -f docker-compose.dev.yml down -v 2>/dev/null || true
	docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true
	docker image prune -f

clean-all: ## Remove everything including images
	docker compose -f docker-compose.dev.yml down -v --rmi all 2>/dev/null || true
	docker compose -f docker-compose.prod.yml down -v --rmi all 2>/dev/null || true
