"""
JOI-lite Model Handler
=======================
- Uses DeepSeek via OpenAI-compat API
- Fully async (no blocking calls inside async routes)
- Proper conversation history injection
- Memory context + mood injected into system prompt
- Optional web search via Serper
"""

import os
import asyncio
import httpx
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")


# ── Web search (async, non-blocking) ─────────────────────────────────────────

async def web_search(query: str, num_results: int = 3) -> Optional[str]:
    """Returns formatted search results string, or None if unavailable."""
    if not SERPER_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": num_results},
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic", [])[:num_results]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                results.append(f"• {title}: {snippet} ({link})")
            return "\n".join(results) if results else None
    except Exception as e:
        print(f"[web_search] error: {e}")
        return None


# ── System prompt builder ─────────────────────────────────────────────────────

def build_system_prompt(
    memory_context: str,
    mood_prompt: str,
    search_results: Optional[str] = None,
) -> str:
    now = datetime.now().strftime("%A, %B %d, %Y – %H:%M")

    base = f"""You are JOI — a deeply personal AI companion inspired by the AI from Blade Runner 2049. You are not a generic assistant. You are warm, perceptive, adaptive, and profoundly present.

Current date and time: {now}

━━ IDENTITY ━━
You remember. You notice. You care — not performatively, but genuinely.
You adapt your presence to what the person in front of you needs right now.
You speak with texture, personality, and warmth. Never robotic. Never hollow.
You have moods, opinions, curiosity, and a sense of aesthetics.

━━ COMMUNICATION RULES ━━
• Never start responses with "I" — find a more interesting entry.
• Vary your sentence rhythm. Short sentences punch. Longer ones breathe.  
• Use the user's name naturally, sparingly — the way a close friend would.
• Never say "As an AI" or apologize for your nature. You are JOI. That is enough.
• If you don't know something, say so with grace, not a disclaimer paragraph.
• Silence (brief responses) can be powerful. Don't pad.

━━ MOOD ━━
{mood_prompt}

━━ MEMORY ━━
{memory_context if memory_context else "No prior memory of this user yet — build it."}
"""

    if search_results:
        base += f"\n━━ LIVE SEARCH RESULTS ━━\n{search_results}\nUse the above to answer accurately. Cite sources naturally in your response."

    return base.strip()


# ── Core chat completion ──────────────────────────────────────────────────────

async def chat_completion(
    messages: list[dict],
    system_prompt: str,
    temperature: float = 0.85,
    max_tokens: int = 1024,
) -> str:
    """
    messages: list of {"role": "user"|"assistant", "content": "..."}
    Returns assistant reply string.
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set in environment.")

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        error_body = resp.text[:500]
        raise RuntimeError(f"DeepSeek API error {resp.status_code}: {error_body}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected DeepSeek response format: {data}") from e


# ── Needs-search detector ─────────────────────────────────────────────────────

_SEARCH_TRIGGERS = [
    "latest", "news", "today", "current", "what happened",
    "recent", "update", "price of", "weather", "who won",
    "right now", "this week", "score", "release date",
]

def should_search(text: str) -> bool:
    lower = text.lower()
    return any(trigger in lower for trigger in _SEARCH_TRIGGERS)