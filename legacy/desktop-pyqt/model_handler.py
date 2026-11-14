"""
JOI Model Handler — Groq LLM with tool-call awareness.
The LLM is given a tool manifest and responds with either:
  - Plain text (conversation)
  - A tool call block: TOOL_CALL: {"tool": "...", "params": {...}}
The server parses this and routes to desktop_agent.execute_tool().
"""

import re
import json
import httpx
from datetime import datetime

from config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    PERSONALITY_SYSTEM_PROMPTS,
    DEFAULT_MOOD,
)
from desktop_agent import TOOL_SCHEMAS, RISKY_TOOLS


def _tool_manifest() -> str:
    lines = ["You have access to the following desktop tools. "
             "To use a tool, respond with EXACTLY this format on its own line:\n"
             "TOOL_CALL: {\"tool\": \"tool_name\", \"params\": {\"key\": \"value\"}}\n"
             "You may include text before or after the TOOL_CALL line.\n"
             "Tools marked [RISKY] will ask the user for permission before executing.\n\n"
             "Available tools:"]
    for t in TOOL_SCHEMAS:
        risky = " [RISKY]" if t["name"] in RISKY_TOOLS else ""
        param_str = ", ".join(f"{k}: {v}" for k, v in t["params"].items()) if t["params"] else "none"
        lines.append(f"  • {t['name']}{risky}: {t['desc']} | params: {param_str}")
    return "\n".join(lines)


def _build_system_prompt(mood: str) -> str:
    base = PERSONALITY_SYSTEM_PROMPTS.get(mood, PERSONALITY_SYSTEM_PROMPTS[DEFAULT_MOOD])
    today = datetime.now().strftime("%A, %B %d, %Y — %H:%M")
    tools = _tool_manifest()
    return (
        f"{base}\n\n"
        f"Current date and time: {today}\n\n"
        f"{tools}\n\n"
        f"Important: Only use a tool when the user's request clearly requires one. "
        f"For conversation, questions, or advice — respond normally. "
        f"After a tool executes, you will receive its result and should summarize it naturally."
    )


def parse_tool_call(text: str) -> dict | None:
    """
    Extract TOOL_CALL JSON from LLM response.
    Returns {"tool": str, "params": dict} or None.
    """
    match = re.search(r'TOOL_CALL:\s*(\{.*?\})', text, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
        if "tool" in payload:
            return {
                "tool": payload["tool"],
                "params": payload.get("params", {}),
            }
    except json.JSONDecodeError:
        pass
    return None


def strip_tool_call(text: str) -> str:
    """Remove the TOOL_CALL line from the response text."""
    return re.sub(r'TOOL_CALL:\s*\{.*?\}', '', text, flags=re.DOTALL).strip()


async def get_joi_response(
    user_message: str,
    conversation_history: list[dict],
    mood: str = DEFAULT_MOOD,
) -> str:
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY is not configured, sir. Please set it in .env"

    messages = [{"role": "system", "content": _build_system_prompt(mood)}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 512,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{GROQ_BASE_URL}/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()

    return r.json()["choices"][0]["message"]["content"].strip()