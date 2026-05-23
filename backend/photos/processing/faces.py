import io
import os
from typing import Any
from uuid import UUID

import numpy as np
from PIL import Image, ImageOps
import pillow_heif
from sqlmodel import Session, select

from photos.tables import Face, FaceCluster


pillow_heif.register_heif_opener()

FACE_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.6"))
INSIGHTFACE_MODEL = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
_USING_POSTGRES = os.getenv("DATABASE_URL", "sqlite://").startswith("postgresql")

_face_app: Any = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        import insightface

        _face_app = insightface.app.FaceAnalysis(name=INSIGHTFACE_MODEL)
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))
    return _face_app


def _to_stored(arr: np.ndarray):
    """Postgres pgvector accepts lists; SQLite gets bytes."""
    if _USING_POSTGRES:
        return arr.astype(np.float32).tolist()
    return arr.astype(np.float32).tobytes()


def _from_stored(value) -> np.ndarray:
    if isinstance(value, (bytes, bytearray)):
        return np.frombuffer(value, dtype=np.float32)
    return np.array(value, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def detect_and_cluster_faces(
    session: Session,
    image_bytes: bytes,
    user_id: UUID,
    memory_item_id: UUID,
) -> list[dict]:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    np_img = np.array(img)
    np_img = np_img[:, :, ::-1]  # RGB -> BGR for insightface

    faces = _get_face_app().get(np_img)
    if not faces:
        return []

    faces = faces[:20]

    clusters = list(
        session.exec(select(FaceCluster).where(FaceCluster.user_id == user_id))
    )
    cluster_embeddings: list[tuple[FaceCluster, np.ndarray]] = [
        (c, _from_stored(c.rep_embedding)) for c in clusters
    ]

    results = []
    for f in faces:
        embedding = f.normed_embedding.astype(np.float32)
        bbox = f.bbox.astype(int)

        best_cluster: FaceCluster | None = None
        best_sim = -1.0
        for cluster, emb in cluster_embeddings:
            sim = _cosine(embedding, emb)
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster

        if best_cluster is not None and best_sim >= FACE_THRESHOLD:
            existing = _from_stored(best_cluster.rep_embedding)
            new_count = best_cluster.face_count + 1
            new_centroid = (existing * best_cluster.face_count + embedding) / new_count
            new_centroid = new_centroid / (np.linalg.norm(new_centroid) + 1e-8)
            best_cluster.rep_embedding = _to_stored(new_centroid)
            best_cluster.face_count = new_count
            session.add(best_cluster)
            cluster_id = best_cluster.id
            cluster_embeddings = [
                (c, new_centroid if c.id == best_cluster.id else e)
                for c, e in cluster_embeddings
            ]
        else:
            new_cluster = FaceCluster(
                user_id=user_id,
                rep_embedding=_to_stored(embedding),
                face_count=1,
            )
            session.add(new_cluster)
            session.flush()
            cluster_id = new_cluster.id
            cluster_embeddings.append((new_cluster, embedding))

        face_row = Face(
            memory_item_id=memory_item_id,
            cluster_id=cluster_id,
            bbox={
                "x": int(bbox[0]),
                "y": int(bbox[1]),
                "width": int(bbox[2] - bbox[0]),
                "height": int(bbox[3] - bbox[1]),
            },
            embedding=_to_stored(embedding),
        )
        session.add(face_row)
        results.append({"cluster_id": str(cluster_id), "bbox": face_row.bbox})

    session.commit()
    return results
