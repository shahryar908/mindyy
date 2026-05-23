import io


def _png_bytes():
    """Minimal valid PNG (1x1 transparent pixel)."""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63600100000005000164d6e2300000000049454e44"
        "ae426082"
    )


def _upload(client, headers, name="a.png", ct="image/png"):
    return client.post(
        "/photos/upload",
        files={"file": (name, io.BytesIO(_png_bytes()), ct)},
        headers=headers,
    )


def test_upload_requires_auth(client, s3_mock):
    r = client.post(
        "/photos/upload",
        files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert r.status_code == 401


def test_upload_happy_path(client, s3_mock, auth_headers):
    r = _upload(client, auth_headers, name="vacation.png")
    assert r.status_code == 202, r.text
    data = r.json()
    assert data["status"] == "uploading"
    assert "id" in data
    assert len(s3_mock) == 1


def test_upload_rejects_bad_content_type(client, s3_mock, auth_headers):
    r = client.post(
        "/photos/upload",
        files={"file": ("a.exe", io.BytesIO(b"MZ\x00"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert len(s3_mock) == 0


def test_list_returns_only_my_photos(client, s3_mock, auth_headers):
    _upload(client, auth_headers)
    r = client.get("/photos", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"] is None


def test_list_requires_auth(client, s3_mock):
    r = client.get("/photos")
    assert r.status_code == 401


def test_list_user_isolation(client, s3_mock, auth_headers, make_verified_user):
    _upload(client, auth_headers)
    bob = make_verified_user("bob@example.com")
    r = client.get("/photos", headers=bob["headers"])
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_get_photo_returns_item(client, s3_mock, auth_headers):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]
    r = client.get(f"/photos/{photo_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == photo_id


def test_get_others_photo_returns_404(client, s3_mock, auth_headers, make_verified_user):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]
    bob = make_verified_user("bob@example.com")
    r = client.get(f"/photos/{photo_id}", headers=bob["headers"])
    assert r.status_code == 404


def test_delete_my_photo(client, s3_mock, auth_headers):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]
    assert len(s3_mock) == 1

    r = client.delete(f"/photos/{photo_id}", headers=auth_headers)
    assert r.status_code == 204
    assert len(s3_mock) == 0

    r = client.get(f"/photos/{photo_id}", headers=auth_headers)
    assert r.status_code == 404


def test_delete_others_photo_returns_404(client, s3_mock, auth_headers, make_verified_user):
    r = _upload(client, auth_headers)
    photo_id = r.json()["id"]
    assert len(s3_mock) == 1

    bob = make_verified_user("bob@example.com")
    r = client.delete(f"/photos/{photo_id}", headers=bob["headers"])
    assert r.status_code == 404
    # File still in mock S3 since delete was rejected.
    assert len(s3_mock) == 1


def test_pagination_cursor(client, s3_mock, auth_headers):
    for _ in range(5):
        _upload(client, auth_headers)

    r = client.get("/photos?limit=2", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None

    r = client.get(f"/photos?limit=2&cursor={body['next_cursor']}", headers=auth_headers)
    body2 = r.json()
    assert len(body2["items"]) == 2

    # Ensure pages don't overlap.
    seen = {i["id"] for i in body["items"]} | {i["id"] for i in body2["items"]}
    assert len(seen) == 4


def test_pagination_last_page_has_no_cursor(client, s3_mock, auth_headers):
    _upload(client, auth_headers)
    r = client.get("/photos?limit=50", headers=auth_headers)
    body = r.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"] is None
