"""
server.py — Joi-lite FastAPI server

FIXES:
1. /chat route was ignoring the mood/personality system entirely — it just forwarded
   raw messages to query_model with no system prompt injected. Joi had no personality
   over the API. Fixed by accepting mood + profile in the request body and building
   the full message stack before calling query_model.

2. query_model is a synchronous (blocking) function called inside an async FastAPI
   route without run_in_executor — this blocks the entire event loop on every request.
   Fixed with asyncio.get_event_loop().run_in_executor().

3. app.py's main() CLI loop and server.py both import from model_handler — that's fine,
   but app.py was never wired to server.py at all. Removed the dead import of
   query_model from app.py's main() path (app.py is CLI-only now, server.py handles HTTP).

4. Missing /profile GET and POST routes — the frontend reads/writes profile via
   localStorage which works for the browser, but adds them here for future Flutter
   mobile / hardware integration support.

5. CORS allow_origins=["*"] with allow_credentials=True is invalid per the CORS spec —
   browsers reject credentialed requests to wildcard origins. Fixed: credentials only
   needed if cookies are used (they aren't here), so set allow_credentials=False.
"""

import asyncio
import os
import json
from typing import List, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from model_handler import query_model
from app import (
    PERSONALITY_LAYERS,
    detect_mood,
    load_user_profile,
    save_user_profile,
    update_user_profile,
    format_profile_summary,
    build_messages,
    MOOD_SWITCH_PATTERN,
)

app = FastAPI(title="JOI-lite", version="2.1")

# FIX: allow_credentials must be False when allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists before mounting
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Request / Response models ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = "deepseek"
    messages: List[ChatMessage] = Field(default_factory=list)
    # FIX: accept mood and profile so the server can inject the right system prompt
    mood: Optional[str] = "default"
    profile: Optional[Dict] = None

class ProfileUpdateRequest(BaseModel):
    message: str  # Raw user message — server extracts profile facts from it


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>JOI</h1><p>static/index.html not found.</p>", status_code=404)


@app.post("/chat")
async def chat(body: ChatRequest):
    """
    Main chat endpoint.
    Builds the full message stack (system prompt + profile + history + user turn)
    before calling query_model, so Joi always has her personality.
    """
    mood = body.mood if body.mood in PERSONALITY_LAYERS else "default"
    personality_prompt = PERSONALITY_LAYERS[mood]

    # Build profile summary if client sent profile data
    profile_summary = ""
    if body.profile:
        profile_summary = format_profile_summary(body.profile)

    # Separate the last user message from history
    raw_messages = [{"role": m.role, "content": m.content} for m in body.messages]
    if not raw_messages:
        raise HTTPException(status_code=400, detail="messages list is empty")

    # Last message must be from the user
    last_message = raw_messages[-1]
    history = raw_messages[:-1]

    if last_message["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must have role 'user'")

    full_messages = build_messages(
        personality_prompt,
        profile_summary,
        history,
        last_message["content"],
    )

    try:
        # FIX: run blocking I/O in executor so it doesn't block the event loop
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(
            None, lambda: query_model(body.model, full_messages)
        )
        return {"reply": reply, "mood": mood}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profile")
async def get_profile():
    """Return the current user profile from disk."""
    profile = load_user_profile()
    return profile


@app.post("/profile")
async def update_profile(body: ProfileUpdateRequest):
    """
    Extract profile facts from a user message and persist them.
    Useful for Flutter / hardware clients that don't manage localStorage.
    """
    profile = load_user_profile()
    updated = update_user_profile(profile, body.message)
    return updated


@app.delete("/profile/memory")
async def clear_memory():
    """Clear all stored memories."""
    profile = load_user_profile()
    profile["memory"] = []
    save_user_profile(profile)
    return {"status": "cleared"}


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
