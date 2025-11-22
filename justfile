set shell := ["bash", "-c"]

# Show help
default:
    @just --list

# --- Setup ---

# Install all dependencies (root, backend, frontend)
setup: setup-root setup-backend setup-frontend
    @echo "🎉 Project setup complete!"

# Install root dependencies (for concurrently)
setup-root:
    npm install

# Install backend dependencies
setup-backend:
    @echo "🔧 Setting up backend..."
    cd backend && python3 -m pip install -r requirements.txt
    cd backend && python3 -m pip install -r requirements-dev.txt
    cd backend && pre-commit install

# Install frontend dependencies
setup-frontend:
    @echo "🔧 Setting up frontend..."
    cd frontend && npm install

# --- Development ---

# Run both backend and frontend
dev:
    @echo "🚀 Starting full stack development environment..."
    npx concurrently -n "BACKEND,FRONTEND" -c "blue,magenta" "just dev-backend" "just dev-frontend"

# Run backend in development mode
dev-backend:
    @echo "🐍 Starting backend..."
    cd backend && python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend in development mode
dev-frontend:
    @echo "⚛️ Starting frontend..."
    cd frontend && npm run dev

# --- Testing ---

# Run all tests
test: test-backend test-frontend

# Run backend tests
test-backend:
    @echo "🧪 Running backend tests..."
    cd backend && python3 -m pytest tests/ -v --cov=app --cov-report=term-missing

# Run frontend tests
test-frontend:
    @echo "🧪 Running frontend tests..."
    cd frontend && npm run test

# Run backend unit tests
test-backend-unit:
    @echo "🧪 Running backend unit tests..."
    cd backend && python3 -m pytest tests/unit/ -v

# --- Linting & Formatting ---

# Run all linters
lint: lint-backend lint-frontend

# Lint backend
lint-backend:
    @echo "🔍 Linting backend..."
    cd backend && python3 -m black --check app/ tests/
    cd backend && python3 -m isort --check-only app/ tests/
    cd backend && python3 -m flake8 app/ tests/

# Format backend code
format-backend:
    @echo "✨ Formatting backend..."
    cd backend && python3 -m black app/ tests/
    cd backend && python3 -m isort app/ tests/

# Lint frontend
lint-frontend:
    @echo "🔍 Linting frontend..."
    cd frontend && npm run lint

# --- Database ---

# Run migrations
migrate:
    @echo "🐘 Running database migrations..."
    cd backend && python3 scripts/run_migrations.py

# Create a new migration (interactive)
migrate-create:
    @echo "🐘 Creating new migration..."
    @read -p "Enter migration name: " name; \
    cd backend && alembic revision -m "$$name"

# --- Docker ---

# Build Docker image
docker-build:
    docker build -f Dockerfile -t golfdaddy-app:latest .

# --- Clean ---

# Clean up artifacts
clean:
    @echo "🧹 Cleaning up..."
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    rm -rf backend/.pytest_cache
    rm -rf backend/htmlcov
    rm -rf backend/.coverage
    rm -rf backend/.mypy_cache
    rm -rf frontend/dist
    rm -rf frontend/node_modules
