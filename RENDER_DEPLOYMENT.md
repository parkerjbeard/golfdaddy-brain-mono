# Render.com Deployment Guide

## Quick Fix for Authentication Issues

The most common issue is frontend-backend connection. Ensure:

1. **Frontend** (`brain-frontend`) has:
   ```
   VITE_API_BASE_URL=https://brain-api.onrender.com
   VITE_API_URL=https://brain-api.onrender.com
   ```

2. **Backend** (`brain-api`) has:
   ```
   CORS_ALLOWED_ORIGINS=https://brain-frontend-wc3t.onrender.com
   ```

## Service Structure

```
Render Services:
├── brain-api (Backend - FastAPI)
│   └── URL: https://brain-api.onrender.com
├── brain-frontend (Frontend - React)
│   └── URL: https://brain-frontend-wc3t.onrender.com
└── PostgreSQL Database
    └── Internal URL: Used in DATABASE_URL
```

## Environment Variables Setup

### Backend Service (brain-api)

1. Go to your backend service on Render
2. Click "Environment" in the sidebar
3. Add variables from `backend/.env.render.example`
4. Critical variables:
   - `DATABASE_URL` - From your Render PostgreSQL
   - `SUPABASE_URL` - From Supabase project
   - `SUPABASE_SERVICE_KEY` - Service role key (keep secret!)
   - `CORS_ALLOWED_ORIGINS` - Must include your frontend URL
   - `OPENAI_API_KEY` - For AI features

### Frontend Service (brain-frontend)

1. Go to your frontend service on Render
2. Click "Environment" in the sidebar
3. Add variables from `frontend/.env.render.example`
4. Critical variables:
   - `VITE_API_BASE_URL` - Your backend URL (NOT localhost!)
   - `VITE_SUPABASE_URL` - From Supabase project
   - `VITE_SUPABASE_ANON_KEY` - Anon key (safe for frontend)

## Build & Start Commands

### Backend
- **Build Command**: `cd backend && pip install -r requirements.txt`
- **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Frontend
- **Build Command**: `cd frontend && npm install && npm run build`
- **Start Command**: `cd frontend && npm run preview -- --host 0.0.0.0 --port $PORT`
- **Publish Directory**: `frontend/dist`

## Database Setup

1. Create PostgreSQL database on Render
2. Copy the external database URL
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

### Check 2: CORS Headers
```javascript
// Should see Access-Control-Allow-Origin header
fetch('https://brain-api.onrender.com/api/v1/health', {
  headers: { 'Origin': 'https://brain-frontend-wc3t.onrender.com' }
}).then(r => console.log(...r.headers))
```

### Check 3: User Role
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
**Cause**: Backend not allowing frontend origin
**Fix**: Add frontend URL to `CORS_ALLOWED_ORIGINS`

### Issue: "Failed to fetch user profile"
**Cause**: Backend can't verify Supabase token
**Fix**: Ensure `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` match

### Issue: "Database connection failed"
**Cause**: Wrong DATABASE_URL
**Fix**: Copy external URL from Render PostgreSQL dashboard

## Deployment Checklist

- [ ] Backend service created and deployed
- [ ] Frontend service created and deployed
- [ ] PostgreSQL database created
- [ ] Backend env vars configured (especially CORS)
- [ ] Frontend env vars configured (especially API URL)
- [ ] Database migrations run
- [ ] Health check passes: `/api/v1/health`
- [ ] API docs accessible: `/docs`
- [ ] Frontend loads without console errors
- [ ] Authentication works (sign in/out)
- [ ] Role-based access works (admin dashboard)

## Support

- Render Status: https://status.render.com
- Render Docs: https://render.com/docs
- Check service logs in Render dashboard for errors