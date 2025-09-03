import os
from contextlib import contextmanager


@contextmanager
def _minimal_env():
    # Ensure required settings exist before importing app
    prev = {
        "SUPABASE_URL": os.environ.get("SUPABASE_URL"),
        "SUPABASE_SERVICE_KEY": os.environ.get("SUPABASE_SERVICE_KEY"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
    }
    os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy-service-role-key")
    os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/postgres")
    os.environ.setdefault("ENVIRONMENT", "test")
    try:
        yield
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_cors_headers_not_present():
    with _minimal_env():
        # Import within context so settings load with minimal env
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
            # Assert no CORS headers are set
            headers = {k.lower(): v for k, v in resp.headers.items()}
            assert "access-control-allow-origin" not in headers
            assert "access-control-allow-credentials" not in headers
            assert resp.status_code == 200
