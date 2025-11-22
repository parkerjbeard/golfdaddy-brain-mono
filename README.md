# GolfDaddy Brain

AI-assisted engineering manager with a FastAPI backend (Supabase + OpenAI) and a Vite/React frontend.

## Stack (current)
- Backend: Python 3.11, FastAPI, Supabase client (no SQLAlchemy), asyncpg migrations via `backend/scripts/run_migrations.py`
- Frontend: React 18 + TypeScript, Vite (port 8080), Tailwind/shadcn, Supabase Auth
- AI integrations: OpenAI for commit analysis and reporting
- Deployment: single Docker image (serves API + built SPA), see `render.yaml`

## Quickstart (local)
1) Prereqs: Python 3.11, Node 18/20, npm, Supabase project, OpenAI key (optional for analysis).

2) Env (`.env` at repo root is read by the backend):
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=service-role-key
SUPABASE_ANON_KEY=public-anon-key
DATABASE_URL=postgresql://...        # Supabase connection string (used by migrations)
OPENAI_API_KEY=sk-...                # required for analysis scripts
GITHUB_TOKEN=ghp_...                 # optional, lifts rate limits
API_KEYS={"local":{"role":"admin","rate_limit":1000}}
```

3) Backend
```
python -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend && make run          # http://localhost:8000, docs at /docs
```

4) Frontend
```
cd frontend
npm install
npm run dev                     # http://localhost:8080 (proxies /api, /auth, /config.js)
```

5) Run both from root (expects backend venv at backend/venv):
```
npm start
```

## Tests
- Backend: `cd backend && make test`
- Frontend: `cd frontend && npm test`

## Database migrations
Apply SQL migrations in `backend/migrations` with:
```
python backend/scripts/run_migrations.py   # uses $DATABASE_URL
```

## GitHub backfill (optional)
```
python backend/scripts/seed_historical_commits.py --repo owner/repo --days 30 --analysis-mode daily --output auto
```
Supports individual or daily modes, optional OpenAI Batch (`--use-openai-batch`), and reuse of existing analyses.

## Deployment
- Single Dockerfile builds frontend then runs FastAPI with gunicorn.
- Render blueprint: `render.yaml` (service name `brain`). Build args expect Supabase keys; see `RENDER_DEPLOYMENT.md`.

### Configuration
```bash
ENABLE_DAILY_BATCH_ANALYSIS=true
SKIP_INDIVIDUAL_COMMIT_ANALYSIS=false  # Gradual migration
EOD_REMINDER_HOUR=17  # 5 PM
EOD_REMINDER_MINUTE=30  # 5:30 PM
```

See [DAILY_BATCH_COMMIT_ANALYSIS.md](./claude_docs/DAILY_BATCH_COMMIT_ANALYSIS.md) for complete documentation.

## Daily Report Workflow

The system combines GitHub commit analysis with daily reports collected via Slack:

1. **Individual Analysis**: Each GitHub commit can be analyzed by AI to estimate work hours (optional)
2. **Daily Batch Analysis**: All commits analyzed together when daily report is submitted
3. **EOD Reports**: Slack bot prompts employees for daily reports at configurable times
4. **Intelligent Deduplication**: AI prevents double-counting between commits and reports
5. **Weekly Aggregation**: Combined view of all work performed with accurate hour tracking

See [DAILY_REPORT_WORKFLOW.md](./DAILY_REPORT_WORKFLOW.md) for detailed information.

## Deployment

Render is the canonical deployment target for this project. See `RENDER_DEPLOYMENT.md` and `render.yaml` for service configuration and environment variable management. Other deployment configs (Fly.io, Vercel/Netlify, Docker Compose) have been removed to reduce confusion.

## Automated Documentation

Note: The previous automated documentation agent and related UI have been removed to streamline the product to its core (repo scan, commit analysis, dashboard). If you need these features, refer to earlier tags or the BLOAT-REDUCTION-PLAN.md for guidance.


## License

[Your License]
