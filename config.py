import json
import os

from dotenv import load_dotenv
import google.generativeai as genai


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
GEMINI_MODEL = "gemini-1.5-flash"

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)


def _extract_text(response):
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


def _clean_json_payload(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def get_gemini_response(system_prompt, user_prompt, json_mode=False):
    fallback = {"error": "AI service temporarily unavailable"}

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return fallback if json_mode else "AI service temporarily unavailable."

    prompt = f"System instruction:\n{system_prompt}\n\nUser input:\n{user_prompt}"
    if json_mode:
        prompt += "\n\nReturn ONLY valid JSON. Do not wrap in markdown fences."

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        text = _extract_text(response)
        if json_mode:
            cleaned = _clean_json_payload(text)
            return json.loads(cleaned)
        return text
    except Exception:
        return fallback if json_mode else "AI service temporarily unavailable."
