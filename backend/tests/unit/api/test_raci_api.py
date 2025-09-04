def test_raci_matrices_v1_is_mounted_and_requires_auth(client):
    resp = client.get("/api/v1/raci-matrices/")
    # Previously 404; after mounting router, should now be 401 due to auth dependency
    assert resp.status_code == 401
