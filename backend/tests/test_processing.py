import io
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from photos.processing.pipeline import run_photo_pipeline
from photos.tables import FaceCluster, ItemStatus, MemoryItem, PhotoMetadata


def _png_bytes():
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63600100000005000164d6e2300000000049454e44"
        "ae426082"
    )


def _upload(client, headers):
    return client.post(
        "/photos/upload",
        files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=headers,
    )


async def test_pipeline_happy_path(
    client, engine, s3_mock, auth_headers, mock_vision, mock_faces
):
    r = _upload(client, auth_headers)
    photo_id = UUID(r.json()["id"])

    await run_photo_pipeline(photo_id)

    with Session(engine) as session:
        item = session.get(MemoryItem, photo_id)
        assert item.status == ItemStatus.READY
        assert item.thumbnail_key is not None
        assert item.thumbnail_key.startswith("thumbs/")

        meta = session.get(PhotoMetadata, photo_id)
        assert meta is not None
        assert meta.caption == "a test photo"
        assert "test" in meta.scenes


async def test_pipeline_marks_failed_on_error(
    client, engine, s3_mock, auth_headers, mock_faces, monkeypatch
):
    async def boom(image_bytes):
        raise RuntimeError("simulated API outage")

    from photos.processing import pipeline as pipeline_module
    monkeypatch.setattr(pipeline_module, "describe_image", boom)

    r = _upload(client, auth_headers)
    photo_id = UUID(r.json()["id"])

    with pytest.raises(RuntimeError):
        await run_photo_pipeline(photo_id)

    with Session(engine) as session:
        item = session.get(MemoryItem, photo_id)
        assert item.status == ItemStatus.FAILED


async def test_pipeline_is_idempotent(
    client, engine, s3_mock, auth_headers, mock_vision, mock_faces
):
    r = _upload(client, auth_headers)
    photo_id = UUID(r.json()["id"])

    await run_photo_pipeline(photo_id)
    # Second run should no-op because status is READY.
    await run_photo_pipeline(photo_id)

    with Session(engine) as session:
        item = session.get(MemoryItem, photo_id)
        assert item.status == ItemStatus.READY


def test_status_endpoint(client, s3_mock, auth_headers):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]

    r = client.get(f"/photos/{photo_id}/status", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == photo_id
    assert body["status"] == "uploading"


def test_status_user_isolation(client, s3_mock, auth_headers, make_verified_user):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]

    bob = make_verified_user("bob@example.com")
    r = client.get(f"/photos/{photo_id}/status", headers=bob["headers"])
    assert r.status_code == 404


def test_people_empty(client, s3_mock, auth_headers):
    r = client.get("/photos/people", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_label_unknown_cluster_returns_404(client, s3_mock, auth_headers):
    r = client.patch(
        f"/photos/people/{uuid4()}",
        json={"label": "Ahmed"},
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_label_cluster_user_isolation(
    client, engine, s3_mock, auth_headers, verified_user, make_verified_user
):
    # Insert a cluster for alice directly.
    with Session(engine) as session:
        cluster = FaceCluster(
            user_id=UUID(verified_user["user_id"]),
            rep_embedding=(b"\x00" * (512 * 4)),
            face_count=1,
        )
        session.add(cluster)
        session.commit()
        session.refresh(cluster)
        cluster_id = cluster.id

    bob = make_verified_user("bob@example.com")
    r = client.patch(
        f"/photos/people/{cluster_id}",
        json={"label": "Ahmed"},
        headers=bob["headers"],
    )
    assert r.status_code == 404

    r = client.patch(
        f"/photos/people/{cluster_id}",
        json={"label": "Ahmed"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["label"] == "Ahmed"


def test_get_photo_includes_metadata_after_processing(
    client, engine, s3_mock, auth_headers, mock_vision, mock_faces
):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]

    import asyncio
    asyncio.run(run_photo_pipeline(UUID(photo_id)))

    r = client.get(f"/photos/{photo_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["caption"] == "a test photo"
    assert body["scenes"] == ["test"]
    assert body["thumbnail_url"] is not None


# --- Unit tests for individual pipeline steps ---


def test_exif_extracts_dimensions_from_png():
    from photos.processing.exif import extract_exif

    exif = extract_exif(_png_bytes())
    assert exif["width"] == 1
    assert exif["height"] == 1


def test_thumbnail_produces_webp():
    from photos.processing.thumbnails import make_thumbnail

    # Build a slightly larger PNG for the thumbnail test.
    from PIL import Image
    img = Image.new("RGB", (800, 600), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    out, ct = make_thumbnail(buf.getvalue(), max_side=400)
    assert ct == "image/webp"
    # Result should be smaller than the input.
    assert len(out) < len(buf.getvalue())

    thumb = Image.open(io.BytesIO(out))
    assert max(thumb.size) <= 400
