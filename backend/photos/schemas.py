from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from photos.tables import ItemStatus, ItemType


class UploadResponse(BaseModel):
    id: UUID
    status: ItemStatus
    message: str = "upload accepted, processing"


class PhotoRead(BaseModel):
    id: UUID
    type: ItemType
    status: ItemStatus
    source_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    taken_at: Optional[datetime] = None
    location: Optional[str] = None
    caption: Optional[str] = None
    scenes: list[str] = []
    objects: list[str] = []
    ocr_text: Optional[str] = None
    item_metadata: dict = {}
    created_at: datetime


class PhotoListResponse(BaseModel):
    items: list[PhotoRead]
    next_cursor: Optional[str] = None


class PhotoStatus(BaseModel):
    id: UUID
    status: ItemStatus


class FaceClusterRead(BaseModel):
    id: UUID
    label: Optional[str] = None
    face_count: int
    sample_thumbnail_url: Optional[str] = None


class LabelClusterRequest(BaseModel):
    label: str = Field(min_length=1, max_length=64)
