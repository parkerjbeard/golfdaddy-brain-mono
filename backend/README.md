# GolfDaddy Brain – Backend

FastAPI service backed by Supabase (data + auth) with OpenAI-powered commit analysis and daily reporting.

## Layout
```
app/
  api/           # FastAPI routers (/api/v1/*, /auth, /webhooks)
  auth/          # Supabase token verification + role helpers
  config/        # Settings + Supabase client
  core/          # Common exceptions, validators, log sanitizer
  middleware/    # API key auth, rate limiting, request metrics
  models/        # Pydantic schemas for commits, reports, users, etc.
  repositories/  # Supabase data access helpers
  services/      # Business logic (analysis, RACI, reminders, zapier)
  integrations/  # OpenAI/GitHub helpers
  main.py        # App entrypoint (serves /docs and mounts built SPA when present)
scripts/         # migrations, seeding, utilities
migrations/      # SQL files applied by run_migrations.py
tests/           # pytest suite (unit-style with mocked Supabase)
```

## Environment
Set these in the repo root `.env` (loaded by `app/config/settings.py`):
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=service-role-key
SUPABASE_ANON_KEY=public-anon-key         # returned to frontend via /config.js
DATABASE_URL=postgresql://...             # used by migration runner
OPENAI_API_KEY=sk-...                     # required for analysis flows
GITHUB_TOKEN=ghp_...                      # optional, lifts GitHub rate limits
API_KEYS={"local":{"role":"admin","rate_limit":1000}}
ENABLE_RATE_LIMITING=true
ENABLE_API_AUTH=true
```

## Run locally
```
python -m venv venv && source venv/bin/activate   # from backend/
pip install -r requirements-dev.txt
make run            # http://localhost:8000, docs at /docs
```
`npm start` from the repo root also runs this app via `./venv/bin/uvicorn` if the venv lives at `backend/venv`.

## Migrations
SQL migrations live in `migrations/`. Apply them against `DATABASE_URL`:
```
python scripts/run_migrations.py
```

## Tests & quality
```
make test          # pytest with coverage
make lint          # black, isort, flake8, pylint, bandit
make format
make type-check    # mypy
```

## Helpful scripts
- `scripts/seed_historical_commits.py` – GitHub backfill (daily or per-commit modes, OpenAI-powered)
- `scripts/run_daily_analysis.py` – runs daily batch analysis (used for cron/worker scenarios)
- `scripts/diagnose_db.py` – connectivity checks for Supabase/Postgres

## API docs
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
