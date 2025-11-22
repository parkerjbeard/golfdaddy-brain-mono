# GolfDaddy Brain – Frontend

Vite + React + TypeScript UI that talks to the FastAPI backend via a dev proxy and uses Supabase Auth.

## Prereqs
- Node 18/20 with npm
- Backend running on `http://localhost:8000` (dev proxy targets this)

## Setup
```bash
cd frontend
npm install
npm run dev          # http://localhost:8080
```

## Env (.env in `frontend/`)
```
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=public-anon-key
# optional overrides
VITE_API_BASE_URL=/api/v1      # default; proxy handles /api,/auth,/dev,/test,/config.js
VITE_API_KEY=local-api-key     # forwarded as X-API-Key when present
```

## Scripts
- `npm run dev` – Vite dev server (port 8080, proxies to backend 8000)
- `npm run build` / `npm run preview`
- `npm run lint`
- `npm test` / `npm run test:ui` / `npm run test:coverage`

## Structure
```
src/
  components/    # UI + shadcn primitives
  pages/         # routed screens
  services/      # api client, secureStorage, token manager
  stores/        # Zustand state
  hooks/         # shared hooks
  lib/           # utilities (crypto, formatting, supabase client)
  types/         # shared DTOs/enums
```

## Notes
- Supabase session tokens are stored via the encrypted `secureStorage` helper (see `README-secure-storage.md`).
- Dev proxy in `vite.config.ts` forwards `/api`, `/auth`, `/dev`, `/test`, and `/config.js` to the backend, so no CORS config is required during development.
