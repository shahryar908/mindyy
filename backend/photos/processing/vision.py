import base64
import json
import logging
import os

from groq import APIError, APIStatusError, AsyncGroq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


log = logging.getLogger(__name__)

VISION_MODEL = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Groq client reads GROQ_API_KEY automatically.
_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq()
    return _client


PROMPT = """\
You analyze user photos and extract structured metadata.
The user's photos are personal memories — be respectful and descriptive but not invasive.
Do not include names of people you might recognize. Do not include political or religious commentary.

Return ONLY a JSON object (no markdown, no prose) with these keys:
{
  "caption": "one short sentence describing the scene, max 25 words",
  "scenes": ["beach", "outdoor", "sunset"],
  "objects": ["person", "umbrella", "palm tree"],
  "ocr_text": "any visible text in the image, or empty string",
  "safe": true
}
- "scenes" has 1-5 high-level scene tags.
- "objects" has 1-10 prominent objects.
- "safe" is false only for adult/violent/graphic content.
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((APIError, APIStatusError)),
    reraise=True,
)
async def describe_image(image_bytes: bytes) -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"

    completion = await _get_client().chat.completions.create(
        model=VISION_MODEL,
        max_tokens=512,
        temperature=0.2,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    text = (completion.choices[0].message.content or "").strip()

    # Strip markdown fences if the model adds them.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("vision returned non-JSON: %s", text[:500])
        return {
            "caption": "",
            "scenes": [],
            "objects": [],
            "ocr_text": "",
            "safe": True,
        }

    return {
        "caption": str(data.get("caption", ""))[:500],
        "scenes": [str(s) for s in (data.get("scenes") or [])][:5],
        "objects": [str(o) for o in (data.get("objects") or [])][:10],
        "ocr_text": str(data.get("ocr_text", ""))[:2000],
        "safe": bool(data.get("safe", True)),
    }
