import io
from uuid import UUID

import pytest

from photos.processing.pipeline import run_photo_pipeline


def _png_bytes():
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63600100000005000164d6e2300000000049454e44"
        "ae426082"
    )


def test_chat_requires_auth(client):
    r = client.post("/chat", json={"query": "test"})
    assert r.status_code == 401


def test_chat_smalltalk(
    client, auth_headers, monkeypatch, mock_embeddings, mock_rerank, mock_synthesis
):
    from chat.intent import Intent
    from chat import routes as chat_routes

    async def fake_parse(query, today=None):
        return Intent(intent="smalltalk")

    monkeypatch.setattr(chat_routes, "parse_intent", fake_parse)

    r = client.post("/chat", json={"query": "hi"}, headers=auth_headers)
    assert r.status_code == 200
    assert "Ask me about your photos" in r.text


def test_chat_empty_library(
    client, auth_headers, mock_embeddings, mock_intent, mock_rerank, mock_synthesis
):
    r = client.post("/chat", json={"query": "beach"}, headers=auth_headers)
    assert r.status_code == 200
    # Cards event with empty list, then a token event from fake_stream.
    assert "cards" in r.text
    assert "Found 0 photo" in r.text


async def test_chat_with_one_photo(
    client, engine, s3_mock, auth_headers,
    mock_vision, mock_faces, mock_embeddings, mock_intent, mock_rerank, mock_synthesis,
    enable_pipeline,
):
    r = client.post(
        "/photos/upload",
        files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    photo_id = UUID(r.json()["id"])
    await run_photo_pipeline(photo_id)

    r = client.post("/chat", json={"query": "test photo"}, headers=auth_headers)
    assert r.status_code == 200
    assert "Found 1 photo" in r.text


async def test_chat_user_isolation(
    client, engine, s3_mock, auth_headers, make_verified_user,
    mock_vision, mock_faces, mock_embeddings, mock_intent, mock_rerank, mock_synthesis,
    enable_pipeline,
):
    # Alice uploads + processes.
    r = client.post(
        "/photos/upload",
        files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    photo_id = UUID(r.json()["id"])
    await run_photo_pipeline(photo_id)

    # Bob queries and should see nothing.
    bob = make_verified_user("bob@example.com")
    r = client.post("/chat", json={"query": "test photo"}, headers=bob["headers"])
    assert r.status_code == 200
    assert "Found 0 photo" in r.text
