def test_me_requires_auth(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(client, verified_user):
    headers = {"Authorization": f"Bearer {verified_user['access_token']}"}
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == verified_user["email"]
    assert r.json()["is_verified"] is True


def test_me_rejects_garbage_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_me_rejects_refresh_token_used_as_access(client, verified_user):
    headers = {"Authorization": f"Bearer {verified_user['refresh_token']}"}
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 401


def test_refresh_issues_new_token_pair(client, verified_user):
    r = client.post(
        "/auth/refresh-token",
        json={"refresh_token": verified_user["refresh_token"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_refresh_rejects_access_token(client, verified_user):
    r = client.post(
        "/auth/refresh-token",
        json={"refresh_token": verified_user["access_token"]},
    )
    assert r.status_code == 401


def test_refresh_rejects_garbage(client):
    r = client.post("/auth/refresh-token", json={"refresh_token": "garbage"})
    assert r.status_code == 401


def test_logout_requires_auth(client):
    r = client.post("/auth/logout")
    assert r.status_code == 401


def test_logout_succeeds_with_valid_token(client, verified_user):
    headers = {"Authorization": f"Bearer {verified_user['access_token']}"}
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 200
