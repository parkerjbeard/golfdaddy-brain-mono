# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GolfDaddy Brain is an AI-powered software engineering assistant that helps teams track work, manage tasks, and improve productivity through intelligent analysis of code commits and daily reports. It features a revolutionary daily batch commit analysis system that reduces AI costs by 90% while providing better contextual insights.

## Common Development Commands

### Backend (Python/FastAPI)
```bash
# Activate virtual environment (ALWAYS use this first)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install           # Production dependencies
make install-dev       # Development dependencies + pre-commit hooks

# Run backend server
make run              # Development with auto-reload
make run-prod         # Production with gunicorn
# Or from root: npm run start:backend

# Run tests
make test             # All tests with coverage
make test-unit        # Unit tests only
make test-integration # Integration tests only
pytest -k "test_name" # Run specific test
pytest -v --cov=app   # With coverage report

# Code quality
make lint             # Run all linters (Black, isort, Flake8, Pylint, Bandit)
make format           # Auto-format code
make type-check       # Type checking with mypy
make security         # Security checks (Safety + Bandit)

# Database
make migrate          # Run migrations
make migrate-create   # Create new migration
```

### Frontend (React/TypeScript)
```bash
# Install dependencies
cd frontend && npm install

# Run development server
cd frontend && npm run dev
# Or from root: npm run start:frontend

# Run tests
cd frontend
npm test              # Run tests
npm run test:ui       # Tests with UI
npm run test:coverage # With coverage

# Build & lint
npm run build         # Production build
npm run lint          # Run ESLint
npm run preview       # Preview production build
```

### Full Stack
```bash
# Start both frontend and backend
npm start  # From root directory

# Docker
make docker-build     # Build Docker images
make docker-run       # Run with Docker Compose
make docker-stop      # Stop services
```

### Docker Setup & Management
```bash
# Clean rebuild (when you want the newest version with cleared cache)
docker-compose down -v                    # Stop and remove volumes
docker system prune -f                     # Clear Docker cache
docker-compose build --no-cache           # Rebuild without cache
docker-compose up -d                      # Start services in detached mode

# Quick restart (preserves data)
docker-compose down
docker-compose up -d

# View logs
docker-compose logs -f backend            # Follow backend logs
docker-compose logs -f frontend           # Follow frontend logs
docker-compose ps                         # Check service status

# Access services
# Frontend: http://localhost:8080
# Backend API: http://localhost:8001
# API Docs: http://localhost:8001/docs

# Test credentials
# Admin: testadmin1@example.com / password123
# Manager: testmanager1@example.com / password123
# Developer: testuser1@example.com / password123
```

## Architecture Overview

### Backend Architecture (FastAPI)
**Layered Architecture:** Repository → Service → API

- **Repository Pattern**: Data access abstraction (`app/repositories/`)
  - 11 repository classes handling all database operations
  - Async SQLAlchemy with connection pooling
  
- **Service Layer**: Business logic (`app/services/`)
  - 26 service classes with dependency injection
  - Circuit breakers for external API reliability
  - Background tasks for scheduled operations
  
- **Authentication**: Hybrid approach
  - Supabase for auth (JWT tokens)
  - PostgreSQL for user profiles and roles
  - Simple role enum: `employee`, `manager`, `admin`
  
- **AI Integration**: 
  - OpenAI GPT-4/GPT-5 for analysis
  - Embeddings (text-embedding-3-large) for semantic search
  - Daily batch analysis for 90% cost reduction

### Frontend Architecture (React/TypeScript)
- **State Management**: Zustand (client) + React Query (server)
- **Component Structure**: Feature-based organization
- **API Client**: Centralized with automatic token management (`services/api/client.ts`)
- **UI Components**: Shadcn/ui with Tailwind CSS
- **Role-Based Access**: ProtectedRoute components with cached roles (5-minute TTL)

### Key Architectural Features

#### Daily Batch Commit Analysis
Revolutionary cost-saving feature that analyzes all daily commits together:
- Service: `services/daily_commit_analysis_service.py`
- Triggered by daily report submission or midnight cron
- Provides better context than individual analysis
- 90% reduction in AI API costs

#### Service Dependencies
- **Rate Limiting**: Configurable per-endpoint middleware
- **Circuit Breakers**: For external API reliability
- **Background Tasks**: EOD reminders, batch processing
- **Webhooks**: GitHub, Slack integrations

## Critical Patterns & Conventions

### API Endpoints
- RESTful with `/api/v1/` prefix
- Consistent error responses using HTTPException
- Pagination: `skip` and `limit` query parameters
- Role protection via FastAPI dependencies:
  - `get_current_user()` - Any authenticated user
  - `get_manager_or_admin_user()` - Managers/admins only
  - `get_admin_user()` - Admins only

### Frontend API Calls
- Always use centralized API client: `services/api/client.ts`
- Token management is automatic via `tokenManager.ts`
- Use `useApi` hook for data fetching
- Role checking hooks: `useIsAdmin()`, `useIsManager()`, `useIsEmployee()`

### Database Operations
- Always use repository pattern for database access
- Transactions for multi-table operations
- Migrations in `backend/migrations/` and `backend/supabase/migrations/`
- Test database for integration tests

### Testing Requirements
- Backend: pytest with fixtures, mocked Supabase
- Frontend: Vitest + React Testing Library
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Always test error cases and edge conditions

## Environment Configuration

### Required Environment Variables

#### Backend (.env)
```
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
OPENAI_API_KEY=...
SLACK_BOT_TOKEN=...
GITHUB_TOKEN=...
```

#### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## Key Services & Features

1. **RACI Matrix**: Task tracking with role assignments (`services/raci_service.py`)
2. **Documentation Generation**: AI-powered with approval workflow (`services/doc_generation_service.py`)
3. **Slack Integration**: EOD report collection (`services/slack_service.py`)
4. **Semantic Search**: Embeddings-based search (`services/semantic_search_service.py`)
5. **KPI Tracking**: Automated velocity metrics (`services/kpi_service.py`)

## Development Workflow

1. **Always activate venv first** for backend work: `source venv/bin/activate`
2. Start services: `npm start` from root (runs both frontend and backend)
3. API documentation available at: `http://localhost:8000/docs`
4. Frontend proxies `/api`, `/auth`, `/dev` to backend automatically

## Important Notes

- Virtual environment is mandatory for backend development
- Role caching in frontend uses 5-minute TTL for performance
- Daily batch analysis runs at midnight UTC or on report submission
- Circuit breakers protect against external API failures
- Sensitive data is filtered from logs automatically