import json
import os
import re
from typing import List

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

router = APIRouter(prefix="/api/translate", tags=["Translation"])
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "gu": "Gujarati",
    "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "kn": "Kannada",
}


class TranslationRequest(BaseModel):
    texts: List[str] = Field(min_length=1, max_length=30)
    target_language: str


def extract_content(result: dict) -> str:
    """Extract assistant text while detecting OpenRouter/provider error envelopes."""
    if result.get("error"):
        error = result["error"]
        if isinstance(error, dict):
            message = error.get("message", "Unknown provider error")
            code = error.get("code", "unknown")
            raise HTTPException(status_code=502, detail=f"OpenRouter provider error ({code}): {message}")
        raise HTTPException(status_code=502, detail="OpenRouter returned an upstream error.")

    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(status_code=502, detail="OpenRouter response did not contain any completion choices. Check model availability.")

    choice = choices[0]
    if choice.get("finish_reason") == "error" or choice.get("error"):
        err = choice.get("error") or {}
        message = err.get("message", "The selected provider failed") if isinstance(err, dict) else str(err)
        raise HTTPException(status_code=502, detail=f"OpenRouter provider failed: {message}")

    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        # Some providers return content parts rather than one string.
        content = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=502, detail="OpenRouter returned an empty response. Try another model.")
    return content.strip()


def parse_translations(content: str, expected_count: int) -> List[str]:
    # Remove common Markdown code fences around JSON.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)

    candidates = [cleaned]
    # If the model added commentary, try the first JSON object/array inside it.
    obj_match = re.search(r"\{[\s\S]*\}", cleaned)
    arr_match = re.search(r"\[[\s\S]*\]", cleaned)
    if obj_match:
        candidates.append(obj_match.group(0))
    if arr_match:
        candidates.append(arr_match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            values = parsed.get("translations")
        elif isinstance(parsed, list):
            values = parsed
        else:
            values = None
        if (isinstance(values, list) and len(values) == expected_count
                and all(isinstance(item, str) for item in values)):
            return values

    # For a single string, accept a plain-text translation as a safe fallback.
    if expected_count == 1 and cleaned:
        return [cleaned]

    raise HTTPException(
        status_code=502,
        detail="The model replied, but not in the required translation-list format. Try a different OpenRouter model."
    )


@router.post("/batch")
async def translate_batch(payload: TranslationRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openrouter/free")

    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is missing from backend/.env")

    language = LANGUAGE_NAMES.get(payload.target_language)
    if not language:
        raise HTTPException(status_code=400, detail="Unsupported target language.")

    if payload.target_language == "en":
        return {"translations": payload.texts}

    clean_texts = [str(item)[:1500] for item in payload.texts]
    system_prompt = (
        "You are the translation engine for Waste Setu, an Indian waste collection, recycling and EPR platform. "
        f"Translate every string into {language}. Preserve order, meaning, numbers, names, URLs, placeholders and symbols. "
        "Do not add explanations. Return only a JSON object exactly like "
        '{"translations":["translated string 1","translated string 2"]}. '
        f"The translations array must contain exactly {len(clean_texts)} strings."
    )
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"texts": clean_texts}, ensure_ascii=False)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5500"),
        "X-Title": "Waste Setu",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=body)

        if response.status_code >= 400:
            # Keep the useful upstream message, but never expose request headers/API key.
            try:
                upstream = response.json().get("error", {}).get("message", "")
            except Exception:
                upstream = ""
            detail = f"OpenRouter HTTP {response.status_code}"
            if upstream:
                detail += f": {upstream[:300]}"
            raise HTTPException(status_code=502, detail=detail)

        try:
            result = response.json()
        except ValueError:
            raise HTTPException(status_code=502, detail="OpenRouter did not return JSON. Check the selected model/provider.")

        content = extract_content(result)
        translations = parse_translations(content, len(clean_texts))
        return {"translations": translations}

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OpenRouter request timed out. Please retry.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not connect to OpenRouter. Check your internet connection.")
