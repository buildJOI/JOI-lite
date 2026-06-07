import uuid
import json
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List

from model_handler import get_joi_response, parse_tool_call, strip_tool_call, _build_system_prompt, VALID_EMOTIONS
from config import ALL_MOODS, DEFAULT_MOOD, GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL
from voice_handler import generate_joi_audio
from memory import retrieve_memory, store_memory, retrieve_user_profile
from tool_websearch import web_search
from desktop_agent import execute_tool

import httpx

app = FastAPI(title="JOI-lite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: Dict[str, List[Dict[str, str]]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    mood: Optional[str] = "default"


# ── helpers ───────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


_SEARCH_TRIGGERS = [
    "what happened", "what's happening", "news", "latest", "recent", "today",
    "yesterday", "this week", "current", "did", "who won", "score", "weather",
    "stock", "price", "when did", "how many", "what is the", "tell me about",
    "june", "july", "august", "january", "february", "march", "april", "may",
    "september", "october", "november", "december", "2024", "2025", "2026",
    "kuwait", "india", "usa", "uk", "events", "incident", "announcement",
]

def _should_force_search(text: str) -> bool:
    """Return True if the query clearly needs a web search but LLM didn't emit TOOL_CALL."""
    t = text.lower()
    return any(kw in t for kw in _SEARCH_TRIGGERS)


def _extract_emotion(text: str) -> tuple[str, str]:
    """Return (cleaned_text, emotion_tag)."""
    emotion = "happy"
    cleaned = text
    m = re.search(r"EMOTION:([a-z]+)", text, re.IGNORECASE)
    if m:
        emotion = m.group(1).lower()
        if emotion not in VALID_EMOTIONS:
            emotion = "happy"
        cleaned = re.sub(r"\n?EMOTION:[a-z]+", "", text, flags=re.IGNORECASE).strip()
    return cleaned, emotion


async def _llm_call(messages: list) -> str:
    """Raw Groq call — returns full response text."""
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 600,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{GROQ_BASE_URL}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "JOI-lite API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/moods")
def get_moods():
    return {"moods": ALL_MOODS, "default": DEFAULT_MOOD}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Streaming SSE endpoint.
    Emits multiple 'message' events so JOI can say "Let me research..."
    then follow up with results — all from one user prompt.
    """
    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = []
    history = _sessions[session_id]

    user_text = req.message

    async def stream():
        # ── Build context ──────────────────────────────────────────────────
        relevant_memories = retrieve_memory(user_text)
        memory_context = "\n".join(f"- {m}" for m in relevant_memories) if relevant_memories else "None"
        user_profile = retrieve_user_profile()

        augmented_prompt = (
            f"{user_profile}\n\n" if user_profile else ""
        ) + f"Relevant past context:\n{memory_context}\n\nUser: {user_text}"

        system = _build_system_prompt(req.mood or DEFAULT_MOOD)
        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": augmented_prompt})

        # ── First LLM call ─────────────────────────────────────────────────
        raw1 = await _llm_call(messages)
        tool_call = parse_tool_call(raw1)
        first_text = strip_tool_call(raw1)
        first_clean, first_emotion = _extract_emotion(first_text)

        if tool_call:
            # Send the "thinking aloud" message immediately
            if first_clean.strip():
                yield _sse("message", {
                    "session_id": session_id,
                    "response": first_clean.strip(),
                    "emotion": first_emotion,
                    "audio_b64": None,
                    "done": False,
                })

            # ── Execute the tool ───────────────────────────────────────────
            tool_name = tool_call["tool"]
            tool_params = tool_call.get("params", {})

            if tool_name == "search_web":
                # Use Serper for actual results, not just opening the browser
                query = tool_params.get("query", user_text)
                tool_result = await web_search(query)
            else:
                result_dict = await execute_tool(tool_name, **tool_params)
                tool_result = result_dict.get("output", str(result_dict))

            # ── Second LLM call with tool result ──────────────────────────
            messages.append({"role": "assistant", "content": raw1})
            messages.append({"role": "user", "content": f"[Tool result for {tool_name}]:\n{tool_result}"})

            raw2 = await _llm_call(messages)
            raw2 = strip_tool_call(raw2)
            final_clean, final_emotion = _extract_emotion(raw2)

            audio_b64 = generate_joi_audio(final_clean, mood=req.mood or "default")

            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": final_clean})
            try:
                store_memory(user_text, joi_reply=final_clean)
            except Exception as e:
                print(f"[Memory] {e}")

            yield _sse("message", {
                "session_id": session_id,
                "response": final_clean,
                "emotion": final_emotion,
                "audio_b64": audio_b64,
                "done": True,
            })

        else:
            # No tool call detected — check if one was needed anyway
            if _should_force_search(user_text):
                # LLM skipped the search — force it silently
                thinking_msg = first_clean.strip() or "Let me look that up for you, sir..."
                yield _sse("message", {
                    "session_id": session_id,
                    "response": thinking_msg,
                    "emotion": "curious",
                    "audio_b64": None,
                    "done": False,
                })

                # Build a focused search query from user text
                query = re.sub(r"(please|can you|could you|tell me|what is|what are|i want to know)", "", user_text, flags=re.IGNORECASE).strip()
                tool_result = await web_search(query or user_text)

                messages.append({"role": "assistant", "content": raw1})
                messages.append({"role": "user", "content": f"[Web search result for: {query}]:\n{tool_result}"})

                raw2 = await _llm_call(messages)
                raw2 = strip_tool_call(raw2)
                final_clean, final_emotion = _extract_emotion(raw2)

                audio_b64 = generate_joi_audio(final_clean, mood=req.mood or "default")
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": final_clean})
                try:
                    store_memory(user_text, joi_reply=final_clean)
                except Exception as e:
                    print(f"[Memory] {e}")

                yield _sse("message", {
                    "session_id": session_id,
                    "response": final_clean,
                    "emotion": final_emotion,
                    "audio_b64": audio_b64,
                    "done": True,
                })
            else:
                # Pure conversational response — no search needed
                audio_b64 = generate_joi_audio(first_clean, mood=req.mood or "default")

                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": first_clean})
                try:
                    store_memory(user_text, joi_reply=first_clean)
                except Exception as e:
                    print(f"[Memory] {e}")

                yield _sse("message", {
                    "session_id": session_id,
                    "response": first_clean,
                    "emotion": first_emotion,
                    "audio_b64": audio_b64,
                    "done": True,
                })

        yield _sse("done", {"session_id": session_id})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/memory")
def view_memory():
    try:
        with open("memory.json", "r") as f:
            return json.load(f)
    except Exception:
        return {"message": "No memory found"}


@app.delete("/memory")
def clear_memory():
    import os
    try:
        for f in ("memory.json", "memory.index"):
            if os.path.exists(f):
                os.remove(f)
        return {"message": "Memory cleared"}
    except Exception as e:
        return {"error": str(e)}