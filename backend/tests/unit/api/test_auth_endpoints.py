import pytest


def test_auth_me_root_requires_bearer_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json().get("detail") in {"Invalid authentication credentials", "Not authenticated", "Authentication error: Invalid authentication credentials"}


def test_auth_me_v1_requires_bearer_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json().get("detail") in {"Invalid authentication credentials", "Not authenticated", "Authentication error: Invalid authentication credentials"}


def test_login_returns_token_with_mocked_supabase(client):
    payload = {"email": "test@example.com", "password": "password123"}
    resp = client.post("/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"
