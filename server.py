import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from config import ALL_MOODS, DEFAULT_MOOD
from model_handler import get_joi_response
from tool_websearch import web_search
from voice_handler import generate_joi_audio

app = FastAPI(title="JOI-lite API")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

PROFILE_PATH = Path(__file__).parent / "user_profile.json"


def load_profile() -> dict:
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"memories": [], "name": ""}


def save_profile(profile: dict) -> None:
    PROFILE_PATH.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
    )


_sessions: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    mood: str = DEFAULT_MOOD
    session_id: str = "default"
    voice_enabled: bool = False


class MemoryUpdate(BaseModel):
    key: str
    value: str


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "JOI-lite API running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/moods")
async def get_moods():
    return {"moods": ALL_MOODS}


@app.post("/chat")
async def chat(req: ChatRequest):
    if req.mood not in ALL_MOODS:
        raise HTTPException(status_code=400, detail=f"Invalid mood. Choose from: {ALL_MOODS}")

    history = _sessions.setdefault(req.session_id, [])

    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    search_context = ""
    trigger = user_text.lower()
    if trigger.startswith("search:") or "search for" in trigger:
        query = user_text.removeprefix("search:").strip()
        search_context = await web_search(query)
        augmented_message = f"{user_text}\n\n[Web context]\n{search_context}"
    else:
        augmented_message = user_text

    try:
        reply = await get_joi_response(
            user_message=augmented_message,
            conversation_history=history,
            mood=req.mood,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model error: {e}")

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})

    if len(history) > 40:
        _sessions[req.session_id] = history[-40:]

    audio_b64 = None
    if req.voice_enabled:
        audio_b64 = generate_joi_audio(reply, mood=req.mood)

    return {
        "reply": reply,
        "mood": req.mood,
        "audio_base64": audio_b64,
        "search_context": search_context or None,
    }


@app.delete("/chat/history/{session_id}")
async def clear_history(session_id: str = "default"):
    _sessions.pop(session_id, None)
    return {"status": "history cleared", "session_id": session_id}


@app.get("/memory")
async def get_memory():
    return load_profile()


@app.post("/memory")
async def add_memory(update: MemoryUpdate):
    profile = load_profile()
    profile.setdefault("memories", [])
    profile["memories"].append({update.key: update.value})
    save_profile(profile)
    return {"status": "saved", "profile": profile}


@app.delete("/memory/{index}")
async def delete_memory(index: int):
    profile = load_profile()
    memories = profile.get("memories", [])
    if index < 0 or index >= len(memories):
        raise HTTPException(status_code=404, detail="Memory index out of range")
    removed = memories.pop(index)
    profile["memories"] = memories
    save_profile(profile)
    return {"status": "deleted", "removed": removed}