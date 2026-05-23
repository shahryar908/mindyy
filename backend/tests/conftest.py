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
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET", "test-bucket")

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
    import auth.tables  # noqa: F401  register auth models
    import photos.tables  # noqa: F401  register memory_items
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


@pytest.fixture
def s3_mock(monkeypatch):
    """Replaces boto3 storage calls with an in-memory dict keyed by S3 key."""
    store: dict[str, bytes] = {}

    def fake_put(key, body, content_type):
        store[key] = body.read()

    def fake_delete(key):
        store.pop(key, None)

    def fake_presigned(key, expires_in=3600):
        return f"https://test-bucket.s3.amazonaws.com/{key}?sig=fake"

    from photos import storage as storage_module
    monkeypatch.setattr(storage_module, "put_object", fake_put)
    monkeypatch.setattr(storage_module, "delete_object", fake_delete)
    monkeypatch.setattr(storage_module, "generate_presigned_get_url", fake_presigned)

    # routes.py imports these by name — patch them there too.
    from photos import routes as routes_module
    monkeypatch.setattr(routes_module, "put_object", fake_put)
    monkeypatch.setattr(routes_module, "delete_object", fake_delete)
    monkeypatch.setattr(routes_module, "generate_presigned_get_url", fake_presigned)

    # Pipeline downloads use the same in-memory store.
    def fake_download(key):
        return store.get(key, b"")

    from photos import storage as storage_module2
    monkeypatch.setattr(storage_module2, "download_object", fake_download)
    from photos.processing import pipeline as pipeline_module
    monkeypatch.setattr(pipeline_module, "download_object", fake_download)

    # Default: background processing is a no-op. Tests that want the real
    # pipeline use the `enable_pipeline` fixture below to flip this.
    async def fake_enqueue(memory_item_id):
        return None

    monkeypatch.setattr(routes_module, "enqueue_processing", fake_enqueue)

    return store


@pytest.fixture
def mock_vision(monkeypatch):
    """Replaces Groq vision call with a stub."""

    async def fake_describe(image_bytes):
        return {
            "caption": "a test photo",
            "scenes": ["test"],
            "objects": ["object"],
            "ocr_text": "",
            "safe": True,
        }

    from photos.processing import pipeline as pipeline_module
    from photos.processing import vision as vision_module
    monkeypatch.setattr(vision_module, "describe_image", fake_describe)
    monkeypatch.setattr(pipeline_module, "describe_image", fake_describe)


@pytest.fixture
def mock_faces(monkeypatch):
    """Replaces face detection with a no-op so tests don't load insightface."""

    def fake_detect(session, image_bytes, user_id, memory_item_id):
        return []

    from photos.processing import faces as faces_module
    from photos.processing import pipeline as pipeline_module
    monkeypatch.setattr(faces_module, "detect_and_cluster_faces", fake_detect)
    monkeypatch.setattr(pipeline_module, "detect_and_cluster_faces", fake_detect)


@pytest.fixture
def mock_embeddings(monkeypatch):
    """Deterministic 384-dim vector keyed by text content."""

    def _fake(text: str) -> list[float]:
        import hashlib
        import struct

        h = hashlib.sha256((text or "empty").encode()).digest()
        out: list[float] = []
        i = 0
        while len(out) < 384:
            chunk = h[i % len(h) : (i % len(h)) + 16]
            if len(chunk) < 16:
                chunk = (chunk + b"\x00" * 16)[:16]
            out.extend(struct.unpack("4f", chunk))
            i += 16
        return out[:384]

    async def fake_embed(text: str):
        return _fake(text or "")

    from photos.processing import embeddings as embeddings_module
    from chat import routes as chat_routes
    from photos.processing import pipeline as pipeline_module

    monkeypatch.setattr(embeddings_module, "embed_text", fake_embed)
    monkeypatch.setattr(embeddings_module, "embed_query", fake_embed)
    monkeypatch.setattr(pipeline_module, "embed_text", fake_embed)
    monkeypatch.setattr(chat_routes, "embed_query", fake_embed)


@pytest.fixture
def mock_intent(monkeypatch):
    """Default intent: treat query as a search with literal text as semantic_query."""

    from chat.intent import Intent, IntentFilters
    from chat import routes as chat_routes

    async def fake_parse(query: str, today=None):
        return Intent(intent="search", filters=IntentFilters(), semantic_query=query)

    monkeypatch.setattr(chat_routes, "parse_intent", fake_parse)
    return fake_parse


@pytest.fixture
def mock_rerank(monkeypatch):
    async def fake_rerank(query, candidates, top_n=5):
        return candidates[:top_n]

    from chat import routes as chat_routes
    monkeypatch.setattr(chat_routes, "rerank_candidates", fake_rerank)


@pytest.fixture
def mock_synthesis(monkeypatch):
    async def fake_stream(query, candidates):
        yield f"Found {len(candidates)} photo(s) for '{query}'."

    from chat import routes as chat_routes
    monkeypatch.setattr(chat_routes, "stream_narrative", fake_stream)


@pytest.fixture
def enable_pipeline(monkeypatch, engine):
    """Re-enable the real pipeline (still hits mock_vision / mock_faces if present)."""

    from photos import routes as routes_module
    from photos.processing import pipeline as pipeline_module

    # Force the pipeline to use the test engine instead of the prod one.
    monkeypatch.setattr(pipeline_module, "engine", engine)

    async def real_enqueue(memory_item_id):
        await pipeline_module.run_photo_pipeline(memory_item_id)

    monkeypatch.setattr(routes_module, "enqueue_processing", real_enqueue)


@pytest.fixture
def auth_headers(verified_user):
    return {"Authorization": f"Bearer {verified_user['access_token']}"}


@pytest.fixture
def make_verified_user(client, fake_redis):
    """Factory: creates additional verified users in the same test session."""

    def _make(email: str, password: str = "TestPass1!"):
        r = client.post("/auth/signup", json={"email": email, "password": password})
        assert r.status_code == 201, r.text
        user_id = r.json()["user_id"]
        code = fake_redis.get(f"otp:{user_id}")
        r = client.post("/auth/verify-otp", json={"user_id": user_id, "code": code})
        assert r.status_code == 200, r.text
        tokens = r.json()
        return {
            "user_id": user_id,
            "email": email,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        }

    return _make
