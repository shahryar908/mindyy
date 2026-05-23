import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON, LargeBinary
from sqlmodel import Field, SQLModel


_USING_POSTGRES = os.getenv("DATABASE_URL", "sqlite://").startswith("postgresql")


def _vector_column(dim: int, nullable: bool = False):
    """Use pgvector's Vector on Postgres, fall back to LargeBinary on SQLite (tests)."""
    if _USING_POSTGRES:
        from pgvector.sqlalchemy import Vector  # imported lazily so SQLite tests don't need pgvector
        return Column(Vector(dim), nullable=nullable)
    return Column(LargeBinary, nullable=nullable)


_PYTHON_VECTOR_TYPE: Any = list[float] if _USING_POSTGRES else bytes
_PYTHON_VECTOR_TYPE_OPT: Any = Optional[list[float]] if _USING_POSTGRES else Optional[bytes]


class ItemType(str, Enum):
    PHOTO = "photo"


class ItemStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MemoryItem(SQLModel, table=True):
    __tablename__ = "memory_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    user_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)

    type: ItemType = Field(default=ItemType.PHOTO, nullable=False)
    status: ItemStatus = Field(default=ItemStatus.UPLOADING, nullable=False, index=True)

    source_key: str = Field(nullable=False)
    thumbnail_key: Optional[str] = Field(default=None, nullable=True)

    taken_at: Optional[datetime] = Field(default=None, nullable=True, index=True)
    location: Optional[str] = Field(default=None, nullable=True)

    item_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PhotoMetadata(SQLModel, table=True):
    __tablename__ = "photo_metadata"

    memory_item_id: UUID = Field(
        foreign_key="memory_items.id",
        primary_key=True,
        nullable=False,
    )
    caption: Optional[str] = Field(default=None, nullable=True)
    ocr_text: Optional[str] = Field(default=None, nullable=True)
    scenes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    objects: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    safe: bool = Field(default=True, nullable=False)

    width: Optional[int] = Field(default=None, nullable=True)
    height: Optional[int] = Field(default=None, nullable=True)
    camera_make: Optional[str] = Field(default=None, nullable=True)
    camera_model: Optional[str] = Field(default=None, nullable=True)

    # 384-dim for sentence-transformers/all-MiniLM-L6-v2.
    text_embedding: _PYTHON_VECTOR_TYPE_OPT = Field(
        default=None,
        sa_column=_vector_column(384, nullable=True),
    )


class FaceCluster(SQLModel, table=True):
    __tablename__ = "face_clusters"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    user_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)
    label: Optional[str] = Field(default=None, nullable=True)
    rep_embedding: _PYTHON_VECTOR_TYPE = Field(
        sa_column=_vector_column(512, nullable=False),
    )
    face_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Face(SQLModel, table=True):
    __tablename__ = "faces"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    memory_item_id: UUID = Field(foreign_key="memory_items.id", index=True, nullable=False)
    cluster_id: UUID = Field(foreign_key="face_clusters.id", index=True, nullable=False)
    bbox: dict = Field(default_factory=dict, sa_column=Column(JSON))
    embedding: _PYTHON_VECTOR_TYPE = Field(
        sa_column=_vector_column(512, nullable=False),
    )
