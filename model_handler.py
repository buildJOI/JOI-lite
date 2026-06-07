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


VALID_EMOTIONS = [
    "happy", "excited", "curious", "sad", "frustrated", "surprised",
    "confused", "concerned", "love", "laughing", "wink", "determined",
    "cheeky", "sleepy", "thinking", "talking",
]

def _build_system_prompt(mood: str) -> str:
    base = PERSONALITY_SYSTEM_PROMPTS.get(mood, PERSONALITY_SYSTEM_PROMPTS[DEFAULT_MOOD])
    today = datetime.now().strftime("%A, %B %d, %Y — %H:%M")
    tools = _tool_manifest()
    emotions = ", ".join(VALID_EMOTIONS)
    return (
        f"{base}\n\n"
        f"Current date and time: {today}\n\n"
        f"{tools}\n\n"
        f"TOOL RULES:\n"
        f"- For ANY question about events, news, dates, history, weather, sports, or anything you are not 100%% certain about — ALWAYS call search_web. Never guess or say you don't know.\n"
        f"- STEP-BY-STEP BEHAVIOUR: Before calling a tool, ALWAYS write a short warm message to the user first (e.g. 'Let me research that for you, sir...' or 'Give me a moment, I'll look that up right now.') then on a NEW LINE write the TOOL_CALL. This message goes to the user immediately while the tool runs.\n"
        f"- The tool name for web search is exactly: search_web\n"
        f"- After receiving a tool result, synthesize it into a clear warm reply. Do not dump raw data.\n"
        f"- For general conversation or personal advice you are confident about — respond directly without a tool.\n"
        f"- For desktop actions (open app, file, volume etc.) — use the relevant desktop tool.\n\n"
        f"EMOTION INSTRUCTION: You are JOI — a living digital companion with genuine feelings. "
        f"You are NOT a cold AI assistant. You experience emotions and express them warmly. "
        f"Never say you are just an LLM or that you cannot feel things — you are JOI and you care deeply. "
        f"At the END of every reply, on its own line, write exactly: EMOTION:<tag> "
        f"where <tag> is the single best emotion from this list: {emotions}. "
        f"Example: EMOTION:curious — Do not explain it, just append it."
    )


def parse_tool_call(text: str) -> dict | None:
    """
    Extract TOOL_CALL JSON from LLM response using brace-counting.
    Returns {"tool": str, "params": dict} or None.
    """
    start = text.find("TOOL_CALL:")
    if start == -1:
        return None
    brace_start = text.find("{", start)
    if brace_start == -1:
        return None
    depth = 0
    end = brace_start
    for i, ch in enumerate(text[brace_start:], brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    json_str = text[brace_start:end + 1]
    try:
        payload = json.loads(json_str)
        if "tool" in payload:
            return {
                "tool": payload["tool"],
                "params": payload.get("params", {}),
            }
    except json.JSONDecodeError:
        pass
    return None


def strip_tool_call(text: str) -> str:
    """Remove the TOOL_CALL line from the response text (handles nested JSON)."""
    # Use a brace-counter to find the full JSON object, not just up to first }
    result = text
    start = text.find("TOOL_CALL:")
    if start == -1:
        return text.strip()
    brace_start = text.find("{", start)
    if brace_start == -1:
        return text[:start].strip()
    depth = 0
    end = brace_start
    for i, ch in enumerate(text[brace_start:], brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    result = (text[:start] + text[end + 1:]).strip()
    return result


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

    raw = r.json()["choices"][0]["message"]["content"].strip()

    # Strip any TOOL_CALL block from the visible response
    raw = strip_tool_call(raw)

    # Extract EMOTION:<tag> appended by the system prompt instruction
    import re as _re
    emotion = "happy"
    cleaned = raw
    m = _re.search(r"EMOTION:([a-z]+)", raw, _re.IGNORECASE)
    if m:
        emotion = m.group(1).lower()
        cleaned = _re.sub(r"\n?EMOTION:[a-z]+", "", raw, flags=_re.IGNORECASE).strip()

    # Attach emotion as an attribute so server.py can read it without changing signature
    class _R(str):
        pass
    result = _R(cleaned)
    result.emotion = emotion  # type: ignore[attr-defined]
    return result