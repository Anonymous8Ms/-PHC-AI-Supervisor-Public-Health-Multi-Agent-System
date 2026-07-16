"""Environment and Gemini client helpers."""

import json
import os
from typing import Any, Final

from dotenv import load_dotenv
import google.generativeai as genai


load_dotenv()

GEMINI_API_KEY: Final[str] = os.getenv("GEMINI_API_KEY", "")
FLASK_PORT: Final[int] = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))
FLASK_DEBUG: Final[bool] = os.getenv("FLASK_DEBUG", "False").lower() == "true"
GEMINI_MODEL: Final[str] = "gemini-1.5-flash"
GEMINI_TIMEOUT_SECONDS: Final[int] = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "8"))

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)


def _extract_text(response: Any) -> str:
    """Extract text from Gemini responses across SDK response shapes."""
    try:
        return response.text.strip()
    except Exception:
        pass

    parts = []
    candidates = getattr(response, "candidates", []) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        response_parts = getattr(content, "parts", []) if content else []
        for part in response_parts:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _clean_json_payload(text: str) -> str:
    """Strip markdown fences when the model wraps JSON output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def get_gemini_response(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> Any:
    """Call Gemini with graceful fallback behavior."""
    fallback = {"error": "AI service temporarily unavailable"}

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return fallback if json_mode else "AI service temporarily unavailable."

    prompt = f"System instruction:\n{system_prompt}\n\nUser input:\n{user_prompt}"
    if json_mode:
        prompt += "\n\nReturn ONLY valid JSON. Do not wrap in markdown fences."

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            prompt,
            request_options={"timeout": GEMINI_TIMEOUT_SECONDS},
        )
        text = _extract_text(response)
        if json_mode:
            cleaned = _clean_json_payload(text)
            return json.loads(cleaned)
        return text
    except Exception:
        return fallback if json_mode else "AI service temporarily unavailable."
