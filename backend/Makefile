.PHONY: help install install-dev test test-unit test-integration lint format type-check security clean run migrate docker-build docker-run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements-dev.txt
	pre-commit install

test: ## Run all tests
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-unit: ## Run unit tests only
	pytest tests/unit/ -v --cov=app --cov-report=term-missing

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

test-semantic: ## Run semantic search tests
	pytest tests/unit/services/semantic/ -v

lint: ## Run all linters
	@echo "Running Black..."
	black --check app/ tests/
	@echo "Running isort..."
	isort --check-only app/ tests/
	@echo "Running Flake8..."
	flake8 app/ tests/
	@echo "Running Pylint..."
	pylint app/ || true
	@echo "Running Bandit..."
	bandit -r app/ || true

format: ## Format code with Black and isort
	black app/ tests/
	isort app/ tests/

type-check: ## Run type checking with mypy
	mypy app/

security: ## Run security checks
	safety check
	bandit -r app/

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

run: ## Run the application locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run the application in production mode
	gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

migrate: ## Run database migrations
	python scripts/run_migrations.py

migrate-create: ## Create a new migration
	@read -p "Enter migration name: " name; \
	alembic revision -m "$$name"

docker-build: ## Build unified app image (root Dockerfile)
	docker build -f ../Dockerfile -t golfdaddy-app:latest ..

docker-run: ## Run application with Docker Compose (root compose)
	docker-compose -f ../docker-compose.yml up -d

docker-stop: ## Stop Docker Compose services
	docker compose -f ../docker-compose.yml down

docker-logs: ## View Docker logs (backend)
	docker compose -f ../docker-compose.yml logs -f backend

docker-shell: ## Open shell in backend container
	docker compose -f ../docker-compose.yml exec backend /bin/sh

db-shell: ## Connect to Supabase via psql (requires psql and $DATABASE_URL)
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "DATABASE_URL is not set. Export it (from Supabase) then rerun."; \
		exit 1; \
	fi
	psql "$$DATABASE_URL"



coverage-report: ## Generate and open coverage report
	pytest tests/ --cov=app --cov-report=html
	open htmlcov/index.html

deps-update: ## Update dependencies
	pip list --outdated
	@echo "Run 'pip install --upgrade <package>' to update specific packages"

deps-check: ## Check for dependency vulnerabilities
	safety check
	pip-audit

pre-commit: ## Run pre-commit hooks
	pre-commit run --all-files
