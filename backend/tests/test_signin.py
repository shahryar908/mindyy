def test_signin_succeeds_for_verified_user(client, verified_user, signup_payload):
    r = client.post("/auth/signin", json=signup_payload)
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_signin_wrong_password(client, verified_user, signup_payload):
    r = client.post(
        "/auth/signin",
        json={"email": signup_payload["email"], "password": "WrongPass1!"},
    )
    assert r.status_code == 401


def test_signin_unknown_email(client):
    r = client.post(
        "/auth/signin",
        json={"email": "nobody@example.com", "password": "TestPass1!"},
    )
    assert r.status_code == 401


def test_signin_blocks_unverified_user(client, signed_up_user, signup_payload):
    r = client.post("/auth/signin", json=signup_payload)
    assert r.status_code == 403
    assert "verif" in r.json()["detail"].lower()
