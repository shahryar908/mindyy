from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Auth_provider(str, Enum):
    LOCAL = "local"
    GOOGLE = "google"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: Optional[str] = Field(default=None, nullable=True)
    is_verified: bool = Field(default=False)
    provider: Auth_provider = Field(default=Auth_provider.LOCAL)
    google_sub: Optional[str] = Field(default=None, unique=True, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
