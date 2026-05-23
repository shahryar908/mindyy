from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class ChatCard(BaseModel):
    id: str
    thumbnail_url: Optional[str] = None
    caption: str
    taken_at: Optional[str] = None
