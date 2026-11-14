"""
JOI backend (FastAPI). Serves the /api contract used by the React frontend,
plus permission, audit and window-monitor endpoints. Binds to 127.0.0.1 only.

Run through the launcher (`python run.py` from the project root), or directly:
    cd backend && python -m uvicorn server:app --host 127.0.0.1 --port 8000
"""
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import agent
import tools
from config import ALLOWED_ORIGINS, AUDIT_LOG, DEFAULT_MOOD, ELEVENLABS_API_KEY, GROQ_API_KEY, HOST, JOI_VOICE, MOODS, PORT
from permissions import gate
from tts import speak_b64, speak_local

logging.basicConfig(level=logging.INFO, format="[JOI] %(levelname)s %(message)s")
log = logging.getLogger("joi")


WELCOME_TEXT = ""
_welcomed = False


def _greeting() -> str:
    hour = datetime.now().hour
    part = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    return f"{part}. I'm JOI, good to see you. Say my name and tell me what you need, or type below."


@asynccontextmanager
async def lifespan(_app):
    global WELCOME_TEXT
    WELCOME_TEXT = _greeting()
    agent.add_voice_event("assistant", WELCOME_TEXT)  # shown in the chat when the window opens
    if JOI_VOICE:
        try:
            import voice
            voice.start_voice_thread()
            log.info("Microphone voice mode is on.")
        except Exception as e:  # keep the backend running even if mic/TTS libs are missing
            log.error("Voice mode could not start: %s. Install: pip install -r requirements-optional.txt", e)
            agent.add_voice_event("assistant", f"My microphone could not start: {e}. "
                                  "Run: pip install -r backend\\requirements-optional.txt")
    else:
        agent.add_voice_event("assistant", "My microphone is off. Set JOI_VOICE=1 in .env and restart me.")
    yield


app = FastAPI(title="JOI Desktop", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def origin_guard(request, call_next):
    # A web page you visit could otherwise call localhost and drive your PC.
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse({"detail": "origin not allowed"}, status_code=403)
    return await call_next(request)


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None
    mood: str = DEFAULT_MOOD


class DecisionIn(BaseModel):
    session_id: str
    decision: str  # allow | allow_session | deny


@app.get("/api/health")
async def health():
    return {"ok": True, "groq_key": bool(GROQ_API_KEY),
            "voice_cloud": bool(ELEVENLABS_API_KEY), "mic_voice": JOI_VOICE}


@app.get("/api/moods")
async def moods():
    return {"moods": list(MOODS.keys()), "default": DEFAULT_MOOD}


@app.post("/api/chat")
async def chat(body: ChatIn):
    result = await agent.chat(body.message, body.session_id, body.mood)
    audio = await speak_b64(result["response"])
    emotion = "curious" if "?" in body.message else "happy"
    return {"session_id": result["session_id"], "response": result["response"],
            "emotion": emotion, "audio_b64": audio}


@app.get("/api/permissions/{session_id}")
async def pending(session_id: str):
    p = agent.SESSIONS.get(session_id, {}).get("pending")
    return {"pending": {k: p[k] for k in ("tool", "category", "description")} if p else None,
            "granted_for_session": gate.granted()}


@app.post("/api/permissions/decide")
async def decide(body: DecisionIn):
    return {"response": await agent.decide(body.session_id, body.decision)}


@app.post("/api/permissions/revoke")
async def revoke():
    gate.revoke_all()
    return {"ok": True}


@app.get("/api/voice/feed")
async def voice_feed(after: int = 0):
    global _welcomed
    if after == 0 and not _welcomed:  # the window just loaded: welcome the user out loud
        _welcomed = True
        threading.Thread(target=speak_local, args=(WELCOME_TEXT,), daemon=True).start()
    items = [e for e in agent.VOICE_FEED if e["id"] > after]
    return {"items": items, "next": items[-1]["id"] if items else after}


@app.get("/api/monitor")
async def monitor():
    return {"running": tools._monitor["running"], "events": tools.window_events()[-50:]}


@app.get("/api/audit")
async def audit(limit: int = 100):
    if not AUDIT_LOG.exists():
        return {"entries": []}
    return {"entries": AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
