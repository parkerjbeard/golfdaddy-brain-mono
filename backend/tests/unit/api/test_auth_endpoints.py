import pytest


def test_auth_me_root_requires_bearer_token(client):
    """Test that /auth/me endpoint requires authorization header."""
    resp = client.get("/auth/me")
    # FastAPI returns 422 when required header is missing
    assert resp.status_code == 422
    error = resp.json()
    assert "error" in error
    # The validation error should indicate the authorization header is required
    assert "Field required" in error["error"]["message"] or "validation" in error["error"]["message"].lower()


def test_auth_me_v1_requires_bearer_token(client):
    """Test that /api/v1/auth/me endpoint requires authorization header."""
    resp = client.get("/api/v1/auth/me")
    # FastAPI returns 422 when required header is missing
    assert resp.status_code == 422
    error = resp.json()
    assert "error" in error
    # The validation error should indicate the authorization header is required
    assert "Field required" in error["error"]["message"] or "validation" in error["error"]["message"].lower()


def test_login_returns_token_with_mocked_supabase(client):
    payload = {"email": "test@example.com", "password": "password123"}
    resp = client.post("/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"
