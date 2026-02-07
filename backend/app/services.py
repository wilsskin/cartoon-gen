"""
Gemini native image generation (Nano Banana).

Uses google-genai SDK. Model name from:
https://ai.google.dev/gemini-api/docs/image-generation
"""
import os
import base64
import random
import time
import uuid
from typing import Any, Optional

from google import genai

# Explicit model for native image generation (Gemini 2.5 Flash Image / Nano Banana).
# Doc: https://ai.google.dev/gemini-api/docs/image-generation
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

_client: Optional[genai.Client] = None

# Retry config: only 503 and timeouts (do not retry 429 on Free Tier)
MAX_RETRIES = 2  # 3 total attempts
RETRY_STATUSES = (503,)


def _get_gemini_client() -> genai.Client:
    """
    Lazily initialize the Gemini client.

    The FastAPI app is responsible for loading environment variables once at
    process startup (see backend/app/main.py). This module relies purely on
    os.environ and must never call load_dotenv() to avoid nondeterminism.
    """
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    _client = genai.Client(api_key=api_key)
    return _client


def _is_retryable(e: Exception) -> bool:
    """True if we should retry (503 or timeout/connection only; do not retry 429)."""
    msg = (str(e) or "").lower()
    if "503" in msg or "unavailable" in msg:
        return True
    if "timeout" in msg or "timed out" in msg:
        return True
    if "connection" in msg or "network" in msg:
        return True
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    if status is not None and status in RETRY_STATUSES:
        return True
    return False


def _backoff_with_jitter(attempt: int) -> None:
    """Exponential backoff with jitter. attempt is 0-based."""
    base = 2 ** attempt
    jitter = random.uniform(0, base * 0.5)
    time.sleep(base + jitter)


def _extract_status(e: Exception) -> Optional[int]:
    """Extract HTTP status from exception if present."""
    status = getattr(e, "status_code", None)
    if status is not None:
        return int(status)
    status = getattr(e, "code", None)
    if status is not None:
        return int(status)
    return None


def generate_satire_image(prompt: str) -> dict[str, Any]:
    """
    Generate an image using Gemini native image model.

    Returns a single dict in one of two shapes:
    - Success: {"ok": True, "image_base64": str, "mime_type": str, "model": str, "request_id": str|None}
    - Failure: {"ok": False, "error": {"code": str, "message": str, "status": int|None, "details": any, "model": str, "request_id": str|None}}
    """
    request_id = str(uuid.uuid4())[:8]
    last_exception: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            client = _get_gemini_client()
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=prompt,
            )

            # Defensive parsing: try candidates[0].content.parts, then response.parts
            parts = None
            try:
                if getattr(response, "candidates", None) and len(response.candidates) > 0:
                    c0 = response.candidates[0]
                    if getattr(c0, "content", None) and getattr(c0.content, "parts", None):
                        parts = c0.content.parts
            except (IndexError, AttributeError, TypeError):
                pass
            if parts is None and hasattr(response, "parts"):
                parts = getattr(response, "parts", None)

            if not parts:
                # List top-level attribute names only (no values) for debugging
                try:
                    top_level = [k for k in dir(response) if not k.startswith("_")]
                except Exception:
                    top_level = []
                return {
                    "ok": False,
                    "error": {
                        "code": "UNEXPECTED_RESPONSE_SHAPE",
                        "message": "Image generation returned an unexpected response shape.",
                        "status": None,
                        "details": {"response_top_level_fields": top_level},
                        "model": GEMINI_IMAGE_MODEL,
                        "request_id": request_id,
                    },
                }

            image_parts = [
                (part.inline_data.data, getattr(part.inline_data, "mime_type", None) or "image/png")
                for part in parts
                if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None)
            ]

            if not image_parts:
                return {
                    "ok": False,
                    "error": {
                        "code": "NO_IMAGE_DATA",
                        "message": "Image generation succeeded but returned no image data.",
                        "status": None,
                        "details": None,
                        "model": GEMINI_IMAGE_MODEL,
                        "request_id": request_id,
                    },
                }

            image_bytes, mime_type = image_parts[0]
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            return {
                "ok": True,
                "image_base64": base64_image,
                "mime_type": mime_type or "image/png",
                "model": GEMINI_IMAGE_MODEL,
                "request_id": request_id,
            }
        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES and _is_retryable(e):
                _backoff_with_jitter(attempt)
                continue
            break

    # Failure path
    err = last_exception or RuntimeError("Unknown error")
    status = _extract_status(err)
    message = str(err)
    if not message or "GEMINI_API_KEY" in message or "api_key" in message.lower():
        message = "Image generation failed."
    if "429" in message or status == 429:
        message = "Rate limit exceeded. Please try again in a moment."
    if "503" in message or status == 503:
        message = "Service temporarily unavailable. Please try again."
    return {
        "ok": False,
        "error": {
            "code": str(getattr(err, "code", None) or type(err).__name__),
            "message": message,
            "status": status,
            "details": None,
            "model": GEMINI_IMAGE_MODEL,
            "request_id": request_id,
        },
    }
