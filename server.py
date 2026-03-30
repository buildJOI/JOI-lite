"""
server.py — Joi-lite production server

Deployment changes vs localhost version:
- Host: 0.0.0.0 (required by Render / Railway / any cloud host)
- Port: reads from PORT env variable (Render injects this automatically)
- user_profile.json: cloud servers have no persistent disk on free tier,
  so profile is accepted from the request body and returned in the response
  instead of being read/written from disk. The frontend handles persistence
  via localStorage.
- DEBUG mode off in production (reload=False)
"""

import asyncio
import os
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
    format_profile_summary,
    build_messages,
)

app = FastAPI(title="JOI-lite", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Models ───────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = "deepseek"
    messages: List[ChatMessage] = Field(default_factory=list)
    mood: Optional[str] = "default"
    profile: Optional[Dict] = None


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    path = os.path.join("static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>JOI</h1><p>static/index.html not found.</p>", status_code=404)


@app.get("/health")
async def health():
    """Render uses this to confirm the service is up."""
    return {"status": "online", "service": "joi-lite"}


@app.post("/chat")
async def chat(body: ChatRequest):
    mood = body.mood if body.mood in PERSONALITY_LAYERS else "default"
    personality_prompt = PERSONALITY_LAYERS[mood]

    profile_summary = format_profile_summary(body.profile) if body.profile else ""

    raw_messages = [{"role": m.role, "content": m.content} for m in body.messages]
    if not raw_messages:
        raise HTTPException(status_code=400, detail="messages list is empty")

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
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(
            None, lambda: query_model(body.model, full_messages)
        )
        return {"reply": reply, "mood": mood}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))   # Render sets PORT automatically
    debug = os.getenv("ENVIRONMENT", "production") == "development"
    uvicorn.run(
        "server:app",
        host="0.0.0.0",   # Required for cloud hosting — not just localhost
        port=port,
        reload=debug,
    )
