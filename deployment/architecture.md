# GolfDaddy Brain - Deployment Architecture (Render or Fly.io + Supabase)

This is the single, canonical deployment for GolfDaddy Brain using a PaaS plus managed Postgres: either Render or Fly.io for app hosting, and Supabase for database/auth. Optimized for reliability, ease-of-use, and very low operational overhead.

## Overview
- Two always-on web instances with HTTP health checks (no single point of failure)
- Managed Postgres + Auth (Supabase) with automated backups and PITR
- Platform-managed TLS, zero-downtime deploys, and simple secrets management
- Scheduled batch jobs for AI analysis using platform features
- CI/CD via GitHub Actions (deploy and nightly batch)

## Architecture
- Backend API: containerized app deployed to either Render Web Service (2 instances) or Fly.io Machines (2 machines)
- Worker (batch): background worker process for AI analysis, run on schedule
- Frontend: static site (Render Static Site) or separate Fly Machines/Cloudflare Pages
- Database/Auth/Storage: Supabase (Postgres + Auth + Storage)

## Components (choose ONE hosting platform)

### Option A: Render + Supabase (recommended simplest)
- Single Web Service using the root `Dockerfile` (builds frontend and serves API + SPA) — 2 instances (≥ 0.5 vCPU / 1 GB) with HTTP health checks to `/health`
- Optional Background Worker (if long-running jobs move out of request path)
- Cron Jobs: nightly/daily schedule to hit a secure endpoint or run worker command
- Secrets: Environment Group shared by services

### Option B: Fly.io + Supabase
- Machines App: 2 machines (shared-cpu-1x, 1 GB) with HTTP health checks to `/health`
- Worker Group: machine or process group with higher memory for AI batch
- Scheduling: start a short-lived worker on a schedule (Fly Machines or external cron)
- Static: separate Machines app or Cloudflare Pages
- Secrets: `fly secrets`

## Database & Auth (Supabase)
- Supabase Project (Starter/Pro) with automated backups and point-in-time recovery
- Supabase Auth (JWT) integrated with the app
- Restrictive RLS policies and TLS connections

## Batch AI Jobs
- Design idempotent jobs with retries and bounded runtime
- Render: Cron Job running the worker command or calling a secure endpoint
- Fly: Scheduled Machine that runs the batch and exits, or external scheduler
- Supabase: Optional Scheduled Edge Function to trigger backend job

## Health & Observability
- `/health` (fast) and `/health/detailed` (checks DB/external deps)
- Platform logs as JSON; optional Sentry for error tracking
- Uptime checks (platform or external monitor)

## Security & Secrets
- Store API keys/DB URL in platform secrets; never commit secrets
- Single-origin deployment; no CORS required
- HTTPS everywhere using platform-managed certificates

## Sizing & Cost (typical monthly)
- Web: start with 0.5 vCPU / 1 GB x2; bump to 1 vCPU / 2 GB if needed
- Worker: 1 vCPU / 2 GB (increase if memory-bound)
- Costs (rough): Render ~$50–$100, Fly ~$30–$80, Supabase ~$25–$50 → total ~$80–$150

---

## CLI Setup (Fly.io + Supabase)

### Prerequisites
- Docker installed and able to build the backend image
- `flyctl` (macOS: `brew install flyctl`)
- `supabase` CLI (macOS: `brew install supabase/tap/supabase`)
- GitHub repository (for CI/CD)

### 1) Fly.io app bootstrap
```bash
fly auth login
fly launch --no-deploy  # generates fly.toml, choose region (e.g., iad)
```

In `fly.toml`, set health checks and service. Example:

```toml
app = "golfdaddy-brain"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  UVICORN_WORKERS = "2"

[[services]]
  internal_port = 8000
  processes = ["app"]
  protocol = "tcp"
  [services.concurrency]
    hard_limit = 100
    soft_limit = 80
  [[services.http_checks]]
    interval = "10s"
    timeout = "2s"
    grace_period = "10s"
    method = "get"
    path = "/health"
  [[services.ports]]
    handlers = ["http"]
    port = 80
  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

Scale to 2 machines for redundancy:
```bash
fly scale count 2 --group app
```

### 2) Supabase project link and migrations
Create the Supabase project in the dashboard. Then:
```bash
supabase login
supabase link --project-ref <your-project-ref>
# Apply SQL migrations located in supabase/migrations or backend migrations
supabase db push
```

Get your `DATABASE_URL` from Supabase and set all app secrets in Fly:
```bash
fly secrets set \
  DATABASE_URL="postgres://..." \
  SUPABASE_URL="https://<ref>.supabase.co" \
  SUPABASE_ANON_KEY="..." \
  SUPABASE_SERVICE_KEY="..." \
  OPENAI_API_KEY="..." \
  GITHUB_TOKEN="..." \
  SLACK_BOT_TOKEN="..." \
  SLACK_SIGNING_SECRET="..."
```

### 3) Deploy backend
```bash
fly deploy --detach
```

Verify health:
```bash
fly status | cat
fly logs --region iad --app golfdaddy-brain | cat
```

### 4) Schedule AI batch job
Option A: GitHub Actions cron calling a secure endpoint (recommended simplest)
- Create endpoint `/api/v1/cron/daily-analysis` with auth guard (API key)
- Add a workflow (see CI/CD) to `curl` the endpoint nightly

Option B: Short-lived worker via Machines
```bash
fly machine run --app golfdaddy-brain \
  --env MODE=batch \
  --rm \
  registry/image:tag -- python -m backend.scripts.run_daily_analysis
```

---

## CLI Setup (Render + Supabase)

### Prerequisites
- Docker or buildpacks-compatible repo
- Render account + API key (`RENDER_API_KEY`)

### 1) Blueprint (`render.yaml`)
Add a `render.yaml` at repo root:

```yaml
services:
  - type: web
    name: brain-app
    env: docker
    plan: starter
    numInstances: 2
    healthCheckPath: /health
    dockerfilePath: Dockerfile
    envVars:
      - key: DATABASE_URL
        fromGroup: brain-secrets
      - key: SUPABASE_URL
        fromGroup: brain-secrets
      - key: SUPABASE_ANON_KEY
        fromGroup: brain-secrets
      - key: OPENAI_API_KEY
        fromGroup: brain-secrets
  # Optionally add a worker or cron if you don't call a secure endpoint
  # - type: worker
  #   name: brain-worker
  #   env: docker
  #   plan: starter
  #   dockerfilePath: Dockerfile
  #   startCommand: python -m backend.scripts.worker
  #   envVars:
  #     - key: DATABASE_URL
  #       fromGroup: brain-secrets
envVarGroups:
  - name: brain-secrets
```

### 2) Create environment group and set secrets
Use the Render dashboard or API to create `brain-secrets` and set:
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `GITHUB_TOKEN`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`.

### 3) Deploy via API (non-interactive)
```bash
export RENDER_API_KEY=xxxxxx
# Create/trigger blueprint deploy
curl -s -X POST https://api.render.com/v1/blueprints \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"repo":"https://github.com/<org>/<repo>","branch":"main"}' | jq
```

Render will build and deploy all services defined in `render.yaml`. Subsequent pushes to `main` auto-deploy.

---

## CI/CD (GitHub Actions)

### Fly.io backend deploy
Add `.github/workflows/deploy-fly.yml`:
```yaml
name: Deploy API to Fly
on:
  push:
    branches: [ main ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: docker build -t brain-app -f Dockerfile .
      - run: flyctl deploy --detach --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

### Nightly AI batch trigger (endpoint)
```yaml
name: Nightly AI Batch
on:
  schedule:
    - cron: "0 2 * * *"
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - run: |
          curl -fsSL -H "X-API-Key: ${{ secrets.CRON_API_KEY }}" \
            https://api.your-domain.com/api/v1/cron/daily-analysis
```

---

## Runbook (Day 1)
- Rotate secrets quarterly (platform secrets)
- Monitor error rates and 5xx via platform dashboard; wire Sentry if desired
- Verify nightly batch completion in logs; set alert if runtime exceeds threshold
- Scale instance sizes if p95 latency or memory pressure rises

This is the only supported deployment plan. All prior AWS-specific guidance is removed.
