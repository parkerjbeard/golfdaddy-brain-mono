# Render.com Deployment Guide (Unified Service)

## New: Single-service deployment (no CORS issues)

We now deploy frontend and backend together as one Docker web service named `brain`. The backend serves the built frontend from `frontend/dist`, so API and static assets share the same origin and CORS is no longer needed in production.

## Service Structure

```
Render Services:
└── brain (Docker Web Service: FastAPI + React SPA)
    └── URL: https://<your-domain>.onrender.com
```

## How it works

- `Dockerfile` builds the React app, installs backend deps, copies `frontend/dist` into the image, and starts FastAPI via gunicorn bound to `$PORT`.
- `backend/app/main.py` already mounts `frontend/dist` and serves the SPA with a catch-all route.

## Deploy or Migrate

1. In Render, delete/disable the previous `brain-api` and `brain-frontend` services.
2. Use the updated `render.yaml` (single service `brain`). Create a new Web Service from this repo, or click "Blueprints" and apply.
3. Ensure your env group `brain-secrets` contains at least:
   - `DATABASE_URL` (Supabase Postgres connection string)
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `OPENAI_API_KEY` (if applicable)
   - Any other keys referenced in `backend/app/config/settings.py`

Notes:
- `VITE_API_BASE_URL` is optional. The frontend defaults to relative paths (`/api` or `/api/v1`) which work with same-origin deployment.
- Keep `/health` exposed; Render uses it for health checks.

## Build & Start (handled by Dockerfile)

- The container binds to `$PORT` automatically:
  ```
  gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
  ```

## Database Setup

1. Create PostgreSQL on Render (if not present)
2. Set `DATABASE_URL` in the service env (use the external URL)
3. Add to backend as `DATABASE_URL`
4. Run migrations:
   ```bash
   # SSH into your backend service or run locally
   cd backend
   alembic upgrade head
   ```

## Debugging Authentication Issues

### Check 1: API Connection
```javascript
// Run in browser console on frontend
fetch('https://brain-api.onrender.com/api/v1/health')
  .then(r => r.json())
  .then(console.log)
```

### Check 2: User Role
```javascript
// After signing in, check your role
const { data: { session } } = await supabase.auth.getSession()
fetch('https://brain-api.onrender.com/api/v1/auth/profile', {
  headers: { 'Authorization': `Bearer ${session.access_token}` }
}).then(r => r.json()).then(console.log)
```

## Common Issues & Solutions

### Issue: "Cannot access Manager/Admin Dashboard"
**Cause**: Frontend calling localhost instead of backend URL
**Fix**: Update `VITE_API_BASE_URL` to backend URL

### Issue: "CORS error in console"
With unified single-service deployment, CORS should not apply. Ensure the frontend is served by the backend and that you are accessing a single origin.

### Issue: "Failed to fetch user profile"
**Cause**: Backend can't verify Supabase token
**Fix**: Ensure `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` match your Supabase project

### Issue: "Database connection failed"
**Cause**: Wrong DATABASE_URL
**Fix**: Copy the connection string from Supabase (Project Settings → Database)

## Deployment Checklist

- [ ] Backend service created and deployed
- [ ] Frontend service created and deployed
- [ ] PostgreSQL database created
- [ ] Backend env vars configured
- [ ] Frontend env vars configured (especially API URL)
- [ ] Database migrations run
- [ ] Health check passes: `/health`
- [ ] API docs accessible: `/docs`
- [ ] Frontend loads without console errors
- [ ] Authentication works (sign in/out)
- [ ] Role-based access works (admin dashboard)

## Support

- Render Status: https://status.render.com
- Render Docs: https://render.com/docs
- Check service logs in Render dashboard for errors
