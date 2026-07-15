# AMASCI Backend - Development Commands

.PHONY: help install run dev test lint format docker-up docker-down migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

run: ## Run production server
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

dev: ## Run development server with reload
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run test suite
	pytest tests/ -v --cov=app

lint: ## Run linters
	ruff check app/
	mypy app/

format: ## Format code
	black app/ tests/
	isort app/ tests/

docker-up: ## Start all services
	docker-compose up -d --build

docker-down: ## Stop all services
	docker-compose down

docker-logs: ## View service logs
	docker-compose logs -f api

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create msg="description")
	alembic revision --autogenerate -m "$(msg)"

init-db: ## Initialize databases
	python -m scripts.init_db

clean: ## Clean cache and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
