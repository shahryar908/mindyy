import logging
import os
from typing import Optional

import cohere
from tenacity import retry, stop_after_attempt, wait_exponential


log = logging.getLogger(__name__)
RERANK_MODEL = os.getenv("RERANK_MODEL", "rerank-english-v3.0")

_client: Optional[cohere.AsyncClient] = None


def _get_client() -> cohere.AsyncClient:
    global _client
    if _client is None:
        _client = cohere.AsyncClient(api_key=os.environ["COHERE_API_KEY"])
    return _client


def candidate_to_document(c: dict) -> str:
    parts = [c["caption"]]
    if c["scenes"]:
        parts.append("Scenes: " + ", ".join(c["scenes"]))
    if c.get("ocr_text"):
        parts.append("Text: " + c["ocr_text"][:200])
    if c.get("taken_at"):
        parts.append("Date: " + c["taken_at"][:10])
    return " | ".join(p for p in parts if p)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), reraise=True)
async def rerank_candidates(
    query: str, candidates: list[dict], top_n: int = 5
) -> list[dict]:
    if not candidates:
        return []
    if len(candidates) <= top_n:
        return candidates

    docs = [candidate_to_document(c) for c in candidates]
    try:
        resp = await _get_client().rerank(
            model=RERANK_MODEL,
            query=query,
            documents=docs,
            top_n=top_n,
        )
    except Exception:
        log.exception("rerank failed, falling back to original order")
        return candidates[:top_n]

    return [candidates[r.index] for r in resp.results]
