import pytest


def test_auth_me_v1_requires_bearer_token(client):
    """Test that /api/v1/auth/me endpoint requires authorization header."""
    # Provide API key to bypass middleware
    headers = {"X-API-Key": "test-api-key"}
    resp = client.get("/api/v1/auth/me", headers=headers)
    
    # FastAPI returns 422 when required header is missing (or 401 if logic raises it)
    # Depending on implementation of get_current_user, it might raise 401 or 422.
    # The dependency raises 422 if header is missing when API Auth is disabled, 
    # or 401 "API key required" if enabled.
    # Let's check for either 401 or 422.
    assert resp.status_code in [401, 422]
    if resp.status_code == 422:
        error = resp.json()
        assert "detail" in error or "error" in error


def test_login_returns_token_with_mocked_supabase(client):
    payload = {"email": "test@example.com", "password": "password123"}
    headers = {"X-API-Key": "test-api-key"}
    # Use v1 endpoint
    resp = client.post("/api/v1/auth/login", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"
