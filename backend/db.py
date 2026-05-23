import os

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mindyy.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    # pgvector extension must exist BEFORE create_all so Vector columns work.
    if DATABASE_URL.startswith("postgresql"):
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    import models.tables  # noqa: F401  register auth/user models
    import photos.tables  # noqa: F401  register memory_items, faces, etc.
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
