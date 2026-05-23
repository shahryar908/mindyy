import os
from datetime import datetime, time, timezone
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy import and_
from sqlmodel import Session, select

from photos.tables import (
    Face,
    FaceCluster,
    ItemStatus,
    ItemType,
    MemoryItem,
    PhotoMetadata,
)
from chat.intent import Intent


_USING_POSTGRES = os.getenv("DATABASE_URL", "sqlite://").startswith("postgresql")


def _resolve_people(session: Session, user_id: UUID, names: list[str]) -> list[UUID]:
    if not names:
        return []
    rows = list(
        session.exec(
            select(FaceCluster).where(
                FaceCluster.user_id == user_id,
                FaceCluster.label.in_(names),
            )
        )
    )
    return [c.id for c in rows]


def _embedding_to_numpy(value) -> np.ndarray:
    if isinstance(value, (bytes, bytearray)):
        return np.frombuffer(value, dtype=np.float32)
    return np.array(value, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def retrieve_candidates(
    session: Session,
    user_id: UUID,
    intent: Intent,
    query_embedding: Optional[list[float]],
    top_k: int = 20,
) -> list[dict]:
    cluster_ids = _resolve_people(session, user_id, intent.filters.people)

    where_clauses = [
        MemoryItem.user_id == user_id,
        MemoryItem.type == ItemType.PHOTO,
        MemoryItem.status == ItemStatus.READY,
    ]
    if intent.filters.date_range:
        d_start, d_end = intent.filters.date_range
        start_dt = datetime.combine(d_start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(d_end, time.max, tzinfo=timezone.utc)
        where_clauses.append(
            (
                (MemoryItem.taken_at >= start_dt)
                & (MemoryItem.taken_at <= end_dt)
            )
            | (
                (MemoryItem.taken_at.is_(None))
                & (MemoryItem.created_at >= start_dt)
                & (MemoryItem.created_at <= end_dt)
            )
        )

    stmt = (
        select(MemoryItem, PhotoMetadata)
        .join(PhotoMetadata, PhotoMetadata.memory_item_id == MemoryItem.id)
        .where(and_(*where_clauses))
    )

    if cluster_ids:
        stmt = stmt.where(
            MemoryItem.id.in_(
                select(Face.memory_item_id)
                .where(Face.cluster_id.in_(cluster_ids))
                .distinct()
            )
        )

    if query_embedding is not None and intent.semantic_query and _USING_POSTGRES:
        # pgvector: order by cosine distance directly in SQL.
        stmt = stmt.order_by(
            PhotoMetadata.text_embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        rows = session.exec(stmt).all()
    elif query_embedding is not None and intent.semantic_query:
        # SQLite fallback: pull candidates then sort in Python.
        stmt = stmt.limit(500)  # cap before in-memory sort
        rows = list(session.exec(stmt))
        q = np.array(query_embedding, dtype=np.float32)
        rows.sort(
            key=lambda r: -_cosine(q, _embedding_to_numpy(r[1].text_embedding))
            if r[1].text_embedding is not None
            else 0.0
        )
        rows = rows[:top_k]
    else:
        stmt = stmt.order_by(
            MemoryItem.taken_at.desc().nullslast(),
            MemoryItem.created_at.desc(),
        ).limit(top_k)
        rows = session.exec(stmt).all()

    return [
        {
            "id": str(item.id),
            "thumbnail_key": item.thumbnail_key,
            "source_key": item.source_key,
            "taken_at": item.taken_at.isoformat() if item.taken_at else None,
            "location": item.location,
            "caption": meta.caption or "",
            "scenes": meta.scenes or [],
            "ocr_text": meta.ocr_text or "",
        }
        for item, meta in rows
    ]
