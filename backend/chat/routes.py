import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from db import get_session
from rate_limit import limiter
from auth.deps import get_current_user
from auth.tables import User

from photos.processing.embeddings import embed_query
from photos.storage import generate_presigned_get_url

from chat.intent import parse_intent
from chat.rerank import rerank_candidates
from chat.retrieval import retrieve_candidates
from chat.schemas import ChatCard, ChatRequest
from chat.synthesis import stream_narrative


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
@limiter.limit("30/hour")
async def chat(
    request: Request,
    req: ChatRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    intent = await parse_intent(req.query)

    if intent.intent == "smalltalk":
        return EventSourceResponse(_smalltalk_stream())

    query_embedding = None
    if intent.semantic_query:
        query_embedding = await embed_query(intent.semantic_query)

    candidates = retrieve_candidates(
        session, current_user.id, intent, query_embedding, top_k=20
    )

    top = await rerank_candidates(
        intent.semantic_query or req.query, candidates, top_n=5
    )

    cards = [
        ChatCard(
            id=c["id"],
            thumbnail_url=(
                generate_presigned_get_url(c["thumbnail_key"])
                if c.get("thumbnail_key")
                else None
            ),
            caption=c["caption"],
            taken_at=c.get("taken_at"),
        )
        for c in top
    ]

    async def event_generator() -> AsyncIterator[dict]:
        yield {
            "event": "cards",
            "data": json.dumps([card.model_dump() for card in cards]),
        }
        async for token in stream_narrative(req.query, top):
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


async def _smalltalk_stream() -> AsyncIterator[dict]:
    yield {"event": "cards", "data": "[]"}
    yield {
        "event": "token",
        "data": "Hi! Ask me about your photos — try 'highlights of June 2022', 'photos with Ahmed', or 'beach photos'.",
    }
    yield {"event": "done", "data": ""}
