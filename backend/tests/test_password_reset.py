import re


def test_forgot_password_returns_200_even_for_unknown_email(client):
    r = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r.status_code == 200


def test_forgot_password_existing_user_returns_200(client, verified_user):
    r = client.post("/auth/forgot-password", json={"email": verified_user["email"]})
    assert r.status_code == 200


def test_reset_password_with_valid_token_changes_password(client, verified_user, capsys):
    # Trigger forgot-password to generate + print a token.
    client.post("/auth/forgot-password", json={"email": verified_user["email"]})
    captured = capsys.readouterr().out
    match = re.search(r"password reset token for .+?: (\S+)", captured)
    assert match, f"reset token not printed: {captured}"
    token = match.group(1)

    r = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "NewPass1!"},
    )
    assert r.status_code == 200

    # Old password should no longer work; new one should.
    bad = client.post(
        "/auth/signin",
        json={"email": verified_user["email"], "password": "TestPass1!"},
    )
    assert bad.status_code == 401
    good = client.post(
        "/auth/signin",
        json={"email": verified_user["email"], "password": "NewPass1!"},
    )
    assert good.status_code == 200


def test_reset_password_with_garbage_token_fails(client):
    r = client.post(
        "/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "NewPass1!"},
    )
    assert r.status_code == 400
