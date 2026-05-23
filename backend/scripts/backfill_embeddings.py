"""
Backfill text embeddings for photos that don't have one yet.

Usage:
    uv run python -m scripts.backfill_embeddings
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from db import engine
from photos.processing.embeddings import build_embedding_text, embed_text
from photos.tables import PhotoMetadata


async def main():
    with Session(engine) as session:
        rows = list(
            session.exec(
                select(PhotoMetadata).where(PhotoMetadata.text_embedding.is_(None))
            )
        )
        print(f"Found {len(rows)} rows missing embeddings")

        for i, meta in enumerate(rows, 1):
            text = build_embedding_text(
                meta.caption or "",
                meta.ocr_text or "",
                meta.scenes or [],
            )
            try:
                meta.text_embedding = await embed_text(text)
                session.add(meta)
                if i % 25 == 0:
                    session.commit()
                    print(f"  …{i}/{len(rows)}")
            except Exception as exc:
                print(f"  failed memory_item_id={meta.memory_item_id}: {exc}")

        session.commit()
        print("done.")


if __name__ == "__main__":
    asyncio.run(main())
