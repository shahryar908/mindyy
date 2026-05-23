import asyncio
import logging
from uuid import UUID

from sqlmodel import Session

from db import engine
from photos.storage import download_object, put_object
from photos.tables import ItemStatus, MemoryItem, PhotoMetadata
from photos.processing.embeddings import build_embedding_text, embed_text
from photos.processing.exif import extract_exif
from photos.processing.faces import detect_and_cluster_faces
from photos.processing.thumbnails import make_thumbnail
from photos.processing.vision import describe_image


log = logging.getLogger(__name__)


async def run_photo_pipeline(memory_item_id: UUID) -> None:
    with Session(engine) as session:
        item = session.get(MemoryItem, memory_item_id)
        if item is None:
            log.warning("memory_item %s not found, skipping", memory_item_id)
            return

        if item.status in (ItemStatus.READY, ItemStatus.FAILED):
            return

        try:
            item.status = ItemStatus.PROCESSING
            session.add(item)
            session.commit()

            # 1. Download
            image_bytes = await asyncio.to_thread(download_object, item.source_key)

            # 2. EXIF
            exif = await asyncio.to_thread(extract_exif, image_bytes)
            item.taken_at = exif.get("taken_at")
            item.location = exif.get("location")

            # 3. Thumbnail
            thumb_bytes, thumb_ct = await asyncio.to_thread(make_thumbnail, image_bytes, 400)
            thumb_key = item.source_key.replace("photos/", "thumbs/", 1)
            await asyncio.to_thread(put_object, thumb_key, _ReadableBytes(thumb_bytes), thumb_ct)
            item.thumbnail_key = thumb_key

            # 4. Vision (async; the SDK call is awaitable)
            vision = await describe_image(image_bytes)

            # 5. Faces (CPU-bound; offload)
            await asyncio.to_thread(
                detect_and_cluster_faces,
                session,
                image_bytes,
                item.user_id,
                item.id,
            )

            # 6. Embed caption+OCR+scenes into a single vector
            embed_input = build_embedding_text(
                vision["caption"], vision["ocr_text"], vision["scenes"]
            )
            text_embedding = await embed_text(embed_input)

            # 7. Upsert photo_metadata
            meta = session.get(PhotoMetadata, item.id) or PhotoMetadata(memory_item_id=item.id)
            meta.caption = vision["caption"]
            meta.ocr_text = vision["ocr_text"]
            meta.scenes = vision["scenes"]
            meta.objects = vision["objects"]
            meta.safe = vision["safe"]
            meta.width = exif.get("width")
            meta.height = exif.get("height")
            meta.camera_make = exif.get("camera_make")
            meta.camera_model = exif.get("camera_model")
            meta.text_embedding = text_embedding
            session.add(meta)

            item.status = ItemStatus.READY
            session.add(item)
            session.commit()

        except Exception:
            log.exception("pipeline failed for %s", memory_item_id)
            session.rollback()
            failed = session.get(MemoryItem, memory_item_id)
            if failed is not None:
                failed.status = ItemStatus.FAILED
                session.add(failed)
                session.commit()
            raise


class _ReadableBytes:
    """Minimal file-like wrapper so put_object can stream raw bytes."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size == -1 or size is None:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk
