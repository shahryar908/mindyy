import os
from typing import AsyncIterator

from groq import AsyncGroq


CHAT_LLM_MODEL = os.getenv("CHAT_LLM_MODEL", "llama-3.3-70b-versatile")

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq()
    return _client


SYSTEM_PROMPT = """\
You are mindyy, a personal memory assistant. The user asked a question about their photo library.
Below are 1-5 relevant photos with captions, dates, and tags.

Write a SHORT response (1-3 sentences) in friendly, warm tone that answers the question by referring to these photos.
- Don't list the photos; the UI shows them as cards below your text.
- If photos span multiple events/dates, point that out (e.g., "Across June 2022 you visited the beach and...")
- If there are zero photos, say so politely and suggest the user upload more.
- Never invent details that aren't in the captions/dates/tags.
- No emoji.
"""


def _build_user_message(query: str, candidates: list[dict]) -> str:
    if not candidates:
        return f"User asked: {query}\n\nNo matching photos found in their library."
    lines = [f"User asked: {query}\n\nRelevant photos:"]
    for i, c in enumerate(candidates, 1):
        date_str = (c.get("taken_at") or "")[:10] or "(no date)"
        scenes = ", ".join(c.get("scenes") or [])
        lines.append(f"{i}. {date_str} - {c['caption']} [{scenes}]")
    return "\n".join(lines)


async def stream_narrative(query: str, candidates: list[dict]) -> AsyncIterator[str]:
    user_msg = _build_user_message(query, candidates)

    stream = await _get_client().chat.completions.create(
        model=CHAT_LLM_MODEL,
        max_tokens=300,
        temperature=0.4,
        stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
