import json
import logging
import os
from datetime import date
from typing import Optional

from groq import APIError, APIStatusError, AsyncGroq
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


log = logging.getLogger(__name__)
CHAT_LLM_MODEL = os.getenv("CHAT_LLM_MODEL", "llama-3.3-70b-versatile")

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq()
    return _client


class IntentFilters(BaseModel):
    date_range: Optional[tuple[date, date]] = None
    people: list[str] = Field(default_factory=list)
    location: Optional[str] = None


class Intent(BaseModel):
    intent: str = "search"  # "search" | "summarize" | "smalltalk"
    filters: IntentFilters = Field(default_factory=IntentFilters)
    semantic_query: str = ""


SYSTEM_PROMPT = """\
You convert a user's natural-language question about their personal photo library into a JSON intent object.

Output schema:
{{
  "intent": "search" | "summarize" | "smalltalk",
  "filters": {{
    "date_range": ["YYYY-MM-DD", "YYYY-MM-DD"] or null,
    "people": ["Ahmed", "Sara"],
    "location": "Karachi" or null
  }},
  "semantic_query": "free-text topic for vector search, or empty string"
}}

Rules:
- Today is {today}. If the query says "last June", convert to actual dates relative to today.
- "highlights of X" or "best of X" → intent="summarize" with date_range covering X.
- Greetings or off-topic → intent="smalltalk", everything else empty.
- Don't invent filters not in the query.
- Return ONLY the JSON, no prose, no markdown fences.
"""


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(min=1, max=4),
    retry=retry_if_exception_type((APIError, APIStatusError)),
    reraise=True,
)
async def parse_intent(query: str, today: Optional[date] = None) -> Intent:
    today = today or date.today()
    sys_prompt = SYSTEM_PROMPT.format(today=today.isoformat())

    completion = await _get_client().chat.completions.create(
        model=CHAT_LLM_MODEL,
        max_tokens=512,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": query},
        ],
    )
    text = (completion.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
        return Intent.model_validate(data)
    except Exception:
        log.exception("intent parse failed: %s", text[:300])
        return Intent(intent="smalltalk")
