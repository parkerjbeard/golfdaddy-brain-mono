# Backend Test Suite

pytest-based tests that mock Supabase so they run offline.

## Layout
- `unit/` – module-focused tests grouped by area (`api`, `services`, `repositories`, `webhooks`, etc.)
- `fixtures/` – shared payloads and sample objects
- `utils/` – helper utilities used by tests
- `conftest.py` – global fixtures, including a mocked Supabase client and `TESTING_MODE` toggle

## Running
```bash
cd backend
make test                   # full suite with coverage
pytest tests/unit/api       # scoped run
pytest -k "github_app"      # pattern match
```

Tests expect valid Supabase values in the environment (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`); they are not used for real network calls but are validated for presence.

## Conventions
- Files: `test_*.py`
- Classes: `Test*`
- Prefer fixtures over ad-hoc mocks; reuse the Supabase mock in `conftest.py`.
