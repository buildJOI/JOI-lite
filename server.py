"""
JOI-lite FastAPI Server
========================
Fixes applied:
  ✓ Conversation history preserved across turns (no wipe)
  ✓ Personality/mood routing actually connected
  ✓ Async-safe (no blocking I/O inside async routes)
  ✓ CORS properly configured for both dev and prod
  ✓ API key never exposed to frontend
  ✓ Semantic + episodic memory injected each turn
  ✓ Auto mood detection + manual override
  ✓ Web search triggered only when relevant
  ✓ Memory extraction from user messages
  ✓ Proper error responses (never 500 silently)
"""

import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from memory_engine import (
    load_memory, save_memory,
    add_episode, extract_and_store,
    build_memory_context, log_emotion,
    begin_session, increment_messages,
)
from mood_engine import (
    detect_mood, get_mood_prompt,
    mood_valence_arousal, list_moods,
    DEFAULT_MOOD,
)
from model_handler import (
    build_system_prompt, chat_completion,
    web_search, should_search,
)

# ── State ─────────────────────────────────────────────────────────────────────

# Conversation history kept in-process (one session).
# In production you'd key by session_id/cookie.
_conversation: list[dict] = []
_current_mood: str = DEFAULT_MOOD
_memory_store: dict = {}

MAX_HISTORY = 40  # keep last N messages in context window


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _memory_store
    _memory_store = load_memory()
    begin_session(_memory_store)
    save_memory(_memory_store)
    print(f"[JOI] Memory loaded — {len(_memory_store['episodic'])} episodes, "
          f"{len(_memory_store['semantic'])} facts.")
    yield
    save_memory(_memory_store)
    print("[JOI] Memory saved. Goodbye.")


app = FastAPI(title="JOI-lite", version="2.0.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500"
).split(",")

# In production on Render, the frontend is served from the same origin,
# so we also allow the app's own domain automatically via allow_origin_regex.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Static files (frontend) ───────────────────────────────────────────────────

STATIC_DIR = "static"
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    mood: Optional[str] = None  # optional manual override


class ChatResponse(BaseModel):
    reply: str
    mood: str
    memory_summary: Optional[str] = None


class MemoryEditRequest(BaseModel):
    key: str
    value: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "JOI-lite API running", "version": "2.0.0"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "episodes": len(_memory_store.get("episodic", [])),
        "semantic_facts": len(_memory_store.get("semantic", {})),
        "mood": _current_mood,
        "messages_this_session": _memory_store["stats"].get("total_messages", 0),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    global _conversation, _current_mood, _memory_store

    user_msg = req.message.strip()

    # 1. Mood detection (manual override takes priority)
    if req.mood and req.mood in list_moods() + ["neutral"]:
        _current_mood = req.mood
    else:
        _current_mood = detect_mood(user_msg, _current_mood)

    # 2. Extract facts from user message into memory (async-safe: pure CPU)
    ep_id = add_episode(
        _memory_store,
        summary=f"User said: {user_msg[:120]}",
        tags=_extract_tags(user_msg),
        emotion=_current_mood,
        importance=_importance_score(user_msg),
    )
    extract_and_store(_memory_store, user_msg, episode_id=ep_id)

    # 3. Log emotion
    v, a = mood_valence_arousal(_current_mood)
    log_emotion(_memory_store, _current_mood, v, a)

    # 4. Optionally run web search (non-blocking, awaited)
    search_results: Optional[str] = None
    if should_search(user_msg):
        search_results = await web_search(user_msg)

    # 5. Build system prompt with memory + mood
    memory_ctx = build_memory_context(_memory_store, user_msg)
    mood_prompt = get_mood_prompt(_current_mood)
    system = build_system_prompt(memory_ctx, mood_prompt, search_results)

    # 6. Append user turn to history
    _conversation.append({"role": "user", "content": user_msg})

    # Trim history to stay within token budget (keep most recent)
    trimmed = _conversation[-MAX_HISTORY:]

    # 7. Call DeepSeek (async, non-blocking)
    try:
        reply = await chat_completion(
            messages=trimmed,
            system_prompt=system,
            temperature=0.85,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model error: {str(e)}")

    # 8. Store assistant reply in history
    _conversation.append({"role": "assistant", "content": reply})

    # 9. Store reply as episode
    add_episode(
        _memory_store,
        summary=f"JOI replied: {reply[:120]}",
        tags=["reply", _current_mood],
        emotion=_current_mood,
        importance=0.3,
    )

    # 10. Persist memory (non-blocking: run in thread so we don't block event loop)
    increment_messages(_memory_store)
    await asyncio.get_event_loop().run_in_executor(None, save_memory, _memory_store)

    return ChatResponse(
        reply=reply,
        mood=_current_mood,
        memory_summary=memory_ctx[:200] if memory_ctx else None,
    )


@app.get("/memory")
async def get_memory():
    """Return full memory state (for debug / settings UI)."""
    return {
        "user_profile": _memory_store["user_profile"],
        "semantic": _memory_store["semantic"],
        "episodic_count": len(_memory_store["episodic"]),
        "recent_episodes": _memory_store["episodic"][-10:],
        "emotional_arc": _memory_store["emotional_arc"][-20:],
        "relationships": _memory_store["relationships"],
        "stats": _memory_store["stats"],
    }


@app.post("/memory/fact")
async def set_memory_fact(req: MemoryEditRequest):
    """Manually set a semantic fact."""
    from memory_engine import set_fact
    set_fact(_memory_store, req.key, req.value, confidence=1.0)
    await asyncio.get_event_loop().run_in_executor(None, save_memory, _memory_store)
    return {"status": "ok", "key": req.key, "value": req.value}


@app.delete("/memory/fact/{key}")
async def delete_memory_fact(key: str):
    """Delete a semantic fact."""
    if key in _memory_store["semantic"]:
        del _memory_store["semantic"][key]
        await asyncio.get_event_loop().run_in_executor(None, save_memory, _memory_store)
        return {"status": "deleted", "key": key}
    raise HTTPException(status_code=404, detail=f"Fact '{key}' not found.")


@app.delete("/memory/episodes")
async def clear_episodes():
    """Clear episodic memory (keeps semantic facts and profile)."""
    _memory_store["episodic"] = []
    await asyncio.get_event_loop().run_in_executor(None, save_memory, _memory_store)
    return {"status": "episodic memory cleared"}


@app.delete("/memory/all")
async def clear_all_memory():
    """Nuclear: wipe everything."""
    global _memory_store
    from memory_engine import _blank_store
    _memory_store = _blank_store()
    await asyncio.get_event_loop().run_in_executor(None, save_memory, _memory_store)
    return {"status": "all memory cleared"}


@app.post("/conversation/reset")
async def reset_conversation():
    """Clear in-session conversation history (memory persists)."""
    global _conversation
    _conversation = []
    return {"status": "conversation reset"}


@app.get("/moods")
async def get_moods():
    from mood_engine import MOODS
    return {
        "current": _current_mood,
        "available": {k: {"tone": v["tone"]} for k, v in MOODS.items()},
    }


@app.post("/mood/{mood_name}")
async def set_mood(mood_name: str):
    global _current_mood
    from mood_engine import MOODS
    if mood_name not in MOODS:
        raise HTTPException(status_code=400, detail=f"Unknown mood '{mood_name}'. "
                            f"Available: {list(MOODS.keys())}")
    _current_mood = mood_name
    return {"status": "ok", "mood": _current_mood}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_tags(text: str) -> list[str]:
    """Simple keyword tags for episode indexing."""
    import re
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    stopwords = {"that", "this", "with", "have", "from", "they", "will",
                 "been", "were", "their", "what", "when", "where", "just",
                 "also", "some", "your", "about", "there", "which"}
    return list({w for w in words if w not in stopwords})[:10]


def _importance_score(text: str) -> float:
    """Heuristic: longer, more personal messages get higher importance."""
    length_score = min(len(text) / 500, 1.0)
    personal_signals = ["i feel", "i am", "my", "i want", "i love", "i hate",
                        "i'm", "birthday", "dream", "scared", "excited"]
    personal_score = sum(0.1 for s in personal_signals if s in text.lower())
    return min(0.3 + length_score * 0.4 + personal_score, 1.0)