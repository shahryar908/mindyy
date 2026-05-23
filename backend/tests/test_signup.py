def test_signup_creates_user_and_sends_otp(client, signup_payload, sent_emails, fake_redis):
    r = client.post("/auth/signup", json=signup_payload)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == signup_payload["email"]
    assert "user_id" in body

    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == signup_payload["email"]

    code = fake_redis.get(f"otp:{body['user_id']}")
    assert code is not None
    assert len(code) == 6 and code.isdigit()


def test_signup_duplicate_email_rejected(client, signup_payload):
    client.post("/auth/signup", json=signup_payload)
    r = client.post("/auth/signup", json=signup_payload)
    assert r.status_code == 409


def test_signup_weak_password_rejected(client):
    r = client.post("/auth/signup", json={"email": "bob@example.com", "password": "short"})
    assert r.status_code == 422


def test_signup_invalid_email_rejected(client):
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "TestPass1!"})
    assert r.status_code == 422


def test_signup_password_missing_uppercase_rejected(client):
    r = client.post("/auth/signup", json={"email": "c@example.com", "password": "testpass1!"})
    assert r.status_code == 422


def test_verify_otp_succeeds_with_correct_code(client, signed_up_user):
    r = client.post(
        "/auth/verify-otp",
        json={"user_id": signed_up_user["user_id"], "code": signed_up_user["code"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_verify_otp_fails_with_wrong_code(client, signed_up_user):
    r = client.post(
        "/auth/verify-otp",
        json={"user_id": signed_up_user["user_id"], "code": "000000"},
    )
    assert r.status_code == 400


def test_verify_otp_consumed_after_success(client, signed_up_user):
    client.post(
        "/auth/verify-otp",
        json={"user_id": signed_up_user["user_id"], "code": signed_up_user["code"]},
    )
    r = client.post(
        "/auth/verify-otp",
        json={"user_id": signed_up_user["user_id"], "code": signed_up_user["code"]},
    )
    assert r.status_code == 400


def test_verify_otp_locks_after_max_attempts(client, signed_up_user):
    for _ in range(5):
        client.post(
            "/auth/verify-otp",
            json={"user_id": signed_up_user["user_id"], "code": "111111"},
        )
    # 6th attempt — even with correct code, should fail because OTP was wiped.
    r = client.post(
        "/auth/verify-otp",
        json={"user_id": signed_up_user["user_id"], "code": signed_up_user["code"]},
    )
    assert r.status_code == 400


def test_verify_otp_unknown_user(client):
    r = client.post(
        "/auth/verify-otp",
        json={"user_id": "00000000-0000-0000-0000-000000000000", "code": "123456"},
    )
    assert r.status_code == 404


def test_resend_otp_rate_limited_by_cooldown(client, signed_up_user):
    r = client.post("/auth/resend-otp", json={"email": signed_up_user["email"]})
    # Still 200 (no enumeration leak), but cooldown blocks via 429.
    assert r.status_code == 429


def test_resend_otp_unknown_email_returns_200(client):
    r = client.post("/auth/resend-otp", json={"email": "nobody@example.com"})
    assert r.status_code == 200
