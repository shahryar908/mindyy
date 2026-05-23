import os
import sys
from pathlib import Path

# Make backend/ importable when running pytest from project root.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Set env vars BEFORE any app modules are imported.
os.environ.setdefault("JWT_SECRET", "test-secret-must-be-at-least-32-bytes-long")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://testserver/auth/google/callback")
os.environ.setdefault("FRONTEND_REDIRECT_URL", "http://testserver/frontend/callback")

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import auth.tables  # noqa: F401  register models
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def sent_emails():
    """Captures all OTP/email sends so tests can assert + read codes."""
    return []


@pytest.fixture
def google_claims():
    """Default Google id_token claims; tests can mutate before triggering callback."""
    return {
        "sub": "google-user-12345",
        "email": "googleuser@example.com",
        "email_verified": True,
        "name": "Google User",
    }


@pytest.fixture
def client(monkeypatch, engine, fake_redis, sent_emails, google_claims):
    # Patch the engine + redis BEFORE importing app modules that bind them.
    import db
    import redis_client as rc
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(rc, "redis_client", fake_redis)

    # otp.py imports redis_client at module load — patch the name it sees.
    from auth import otp as otp_module
    monkeypatch.setattr(otp_module, "redis_client", fake_redis)

    # email.py — replace send_email so we never touch SMTP.
    from auth import email as email_module

    def fake_send_email(to, subject, body):
        sent_emails.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(email_module, "send_email", fake_send_email)

    def fake_send_otp_email(to, code):
        sent_emails.append({"to": to, "subject": "Your verification code", "body": code})

    # routes.py imports send_otp_email by name — patch there too.
    from auth import routes as routes_module
    monkeypatch.setattr(routes_module, "send_otp_email", fake_send_otp_email)

    # Mock Google OAuth helper.
    async def fake_exchange(code: str):
        return dict(google_claims)

    monkeypatch.setattr(routes_module, "exchange_code_for_id_token", fake_exchange)

    # Override get_session dependency so handlers use the test engine.
    from main import app
    from db import get_session

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    # Reset slowapi limiter state between tests.
    from rate_limit import limiter
    limiter.reset()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def signup_payload():
    return {"email": "alice@example.com", "password": "TestPass1!"}


@pytest.fixture
def signed_up_user(client, signup_payload, sent_emails, fake_redis):
    """Helper: signs up a user and returns dict with user_id + the OTP code from Redis."""
    r = client.post("/auth/signup", json=signup_payload)
    assert r.status_code == 201, r.text
    user_id = r.json()["user_id"]
    code = fake_redis.get(f"otp:{user_id}")
    return {"user_id": user_id, "email": signup_payload["email"], "code": code}


@pytest.fixture
def verified_user(client, signed_up_user):
    """Helper: signs up + verifies OTP, returns token pair + user info."""
    r = client.post(
        "/auth/verify-otp",
        json={"user_id": signed_up_user["user_id"], "code": signed_up_user["code"]},
    )
    assert r.status_code == 200, r.text
    tokens = r.json()
    return {**signed_up_user, **tokens}
