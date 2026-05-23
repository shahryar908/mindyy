def test_google_login_redirects_with_state_cookie(client):
    r = client.get("/auth/google/login", follow_redirects=False)
    assert r.status_code == 307
    assert "accounts.google.com" in r.headers["location"]
    assert "google_oauth_state" in r.cookies


def test_google_callback_creates_new_user_and_redirects(client, google_claims):
    # First hit /login to seed the state cookie.
    login = client.get("/auth/google/login", follow_redirects=False)
    state = login.cookies["google_oauth_state"]

    r = client.get(
        f"/auth/google/callback?code=test-code&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 307
    loc = r.headers["location"]
    assert "access_token=" in loc
    assert "refresh_token=" in loc


def test_google_callback_rejects_state_mismatch(client):
    client.get("/auth/google/login", follow_redirects=False)
    r = client.get(
        "/auth/google/callback?code=test-code&state=wrong-state",
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_google_callback_rejects_missing_code(client):
    login = client.get("/auth/google/login", follow_redirects=False)
    state = login.cookies["google_oauth_state"]
    r = client.get(
        f"/auth/google/callback?state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_google_callback_rejects_unverified_email(client, google_claims):
    google_claims["email_verified"] = False
    login = client.get("/auth/google/login", follow_redirects=False)
    state = login.cookies["google_oauth_state"]
    r = client.get(
        f"/auth/google/callback?code=test-code&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_google_callback_links_existing_email_account(client, google_claims, verified_user):
    # verified_user fixture made a local account at alice@example.com.
    # Pretend Google returns the same email — should link, not duplicate.
    google_claims["email"] = verified_user["email"]
    google_claims["sub"] = "google-sub-for-alice"

    login = client.get("/auth/google/login", follow_redirects=False)
    state = login.cookies["google_oauth_state"]
    r = client.get(
        f"/auth/google/callback?code=test-code&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 307
