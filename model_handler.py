import httpx
from datetime import datetime
from config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    PERSONALITY_SYSTEM_PROMPTS,
    DEFAULT_MOOD,
)


def _build_system_prompt(mood: str) -> str:
    base = PERSONALITY_SYSTEM_PROMPTS.get(mood, PERSONALITY_SYSTEM_PROMPTS[DEFAULT_MOOD])
    today = datetime.now().strftime("%A, %B %d, %Y")
    return f"{base}\n\nToday's date is {today}."


async def get_joi_response(
    user_message: str,
    conversation_history: list[dict],
    mood: str = DEFAULT_MOOD,
) -> str:
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY is not configured. Please set it in your .env file."

    system_prompt = _build_system_prompt(mood)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": 512,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"].strip()