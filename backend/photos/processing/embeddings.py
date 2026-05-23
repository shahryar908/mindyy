import asyncio
import os
from typing import Any, Optional


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

_model: Any = None


def _get_model():
    global _model
    if _model is None:
        # Imported lazily so module load doesn't pay the ~100MB cost.
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def build_embedding_text(caption: str, ocr_text: str, scenes: list[str]) -> str:
    parts = []
    if caption:
        parts.append(caption.strip())
    if ocr_text and ocr_text.strip():
        parts.append(f"Text in image: {ocr_text.strip()}")
    if scenes:
        parts.append(f"Scenes: {', '.join(scenes)}")
    return "\n".join(parts).strip() or "empty photo"


def _encode(text: str) -> list[float]:
    vec = _get_model().encode(text, normalize_embeddings=True)
    return vec.astype("float32").tolist()


async def embed_text(text: str) -> Optional[list[float]]:
    if not text:
        return None
    return await asyncio.to_thread(_encode, text)


async def embed_query(text: str) -> list[float]:
    """Index-time and query-time go through the same model so distances are comparable."""
    return await asyncio.to_thread(_encode, text)
