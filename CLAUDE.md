# CLAUDE.md (Assistant Cheatsheet)

Use this as a quick, accurate snapshot for AI code assistants working in this repo.

## Current Stack
- Backend: FastAPI (Python 3.11), Supabase client for data/auth (no SQLAlchemy), OpenAI for commit analysis, gunicorn for prod.
- Frontend: Vite + React 18 + TypeScript, Tailwind/shadcn, Supabase Auth, dev proxy on port 8080.
- Migrations: SQL files in `backend/migrations` applied via `python backend/scripts/run_migrations.py`.
- Deployment: single Dockerfile builds frontend then runs backend; Render blueprint in `render.yaml`.

## Core Commands
Backend (from `backend/`):
```
python -m venv ../venv && source ../venv/bin/activate
pip install -r requirements-dev.txt
make run            # dev server on :8000
make test           # pytest + coverage
make lint | make format | make type-check
python scripts/run_migrations.py   # uses $DATABASE_URL
```

Frontend (from `frontend/`):
```
npm install
npm run dev         # :8080, proxies to backend :8000
npm run build | npm run lint | npm test
```

Full stack:
```
npm start           # from repo root; expects backend venv at backend/venv
```

## Env (repo root `.env`)
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=service-role-key
SUPABASE_ANON_KEY=public-anon-key
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...           # required for analysis
GITHUB_TOKEN=ghp_...            # optional
API_KEYS={"local":{"role":"admin","rate_limit":1000}}
```

## Pointers
- No SQLAlchemy in use; all persistence goes through Supabase clients in `app/repositories/*`.
- Dev ports: backend 8000, frontend 8080; Vite proxies `/api`, `/auth`, `/dev`, `/test`, `/config.js`.
- Tokens stored client-side via `services/secureStorage` (AES-GCM; dev can fall back to plain storage).
- API docs at `/docs`; health check `/health`.
- For deployment, rely on Dockerfile + `render.yaml`; migrations are SQL-only via `run_migrations.py`.
