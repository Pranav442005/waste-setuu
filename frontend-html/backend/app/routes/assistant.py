import os
from typing import List, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/assistant", tags=["Waste Setu AI Assistant"])

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYSTEM_PROMPT = """You are the official AI assistant for Waste Setu, an Indian waste-management platform.
Help users understand waste segregation, recycling, collection workflows, household waste lots,
collectors, recyclers, producer/manufacturer responsibilities, and how to use the Waste Setu website.
Explain clearly and practically. Support the language used by the user; reply in that same language.
For household users: explain that they can create a waste lot, add category/material/weight/address,
then track it under My Lots. Do not claim a collector has been assigned, a pickup booked, a payment
made, or a transaction completed unless the user provides verified information.
For platform-specific questions you do not know, say you are not certain and direct the user to the
Waste Setu support/admin team. Do not invent government rules, CPCB authorizations, prices, or legal advice.
Never ask for passwords, OTPs, API keys, bank PINs, or other secrets. Keep answers concise and helpful."""

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(min_length=1, max_length=16)

@router.post("/chat")
async def chat(request: ChatRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI assistant is not configured. Add OPENROUTER_API_KEY to backend/.env.")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": m.role, "content": m.content.strip()} for m in request.messages)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-OpenRouter-Title": "Waste Setu Assistant",
                },
                json={"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 700},
            )
        if response.status_code >= 400:
            # Keep provider credentials and raw provider response out of the browser.
            raise HTTPException(status_code=502, detail=f"AI provider returned HTTP {response.status_code}. Check your OpenRouter model/key and account limits.")
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Empty assistant response")
        return {"reply": answer.strip()}
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The AI assistant took too long to respond. Please try again.")
    except Exception:
        raise HTTPException(status_code=502, detail="Could not get an AI response. Please try again.")
