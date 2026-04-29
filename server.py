import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from config import ALL_MOODS, DEFAULT_MOOD
from model_handler import get_joi_response, parse_tool_call, strip_tool_call
from tool_websearch import web_search
from voice_handler import generate_joi_audio
from desktop_agent import execute_tool
import voice_input

app = FastAPI(title="JOI — Justified Operative Interface")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
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
_sessions: dict[str, list[dict]] = {}

# ── Startup: init voice listeners ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    if voice_input.is_mic_available():
        # Hotkey: Ctrl+Shift+Space
        voice_input.start_hotkey_listener()
        # Wake word: "Hey JOI"
        voice_input.start_wake_word_listener()
        print("[JOI] Voice listeners started.")
    else:
        print("[JOI] No microphone detected — voice input disabled.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_profile() -> dict:
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"memories": [], "name": ""}


def save_profile(profile: dict):
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    mood: str = DEFAULT_MOOD
    session_id: str = "default"
    voice_enabled: bool = False


class MemoryUpdate(BaseModel):
    key: str
    value: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "JOI online"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/moods")
async def get_moods():
    return {"moods": ALL_MOODS}


@app.get("/voice/poll")
async def poll_voice():
    """
    Frontend polls this to get voice commands captured by mic.
    Returns the next queued voice text or null.
    """
    try:
        text = voice_input.voice_queue.get_nowait()
        return {"text": text}
    except Exception:
        return {"text": None}


@app.post("/chat")
async def chat(req: ChatRequest):
    if req.mood not in ALL_MOODS:
        raise HTTPException(400, f"Invalid mood. Choose: {ALL_MOODS}")

    history = _sessions.setdefault(req.session_id, [])
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(400, "Message cannot be empty.")

    # Optional web search augmentation
    search_context = ""
    if user_text.lower().startswith("search:") or "search for" in user_text.lower():
        query = user_text.removeprefix("search:").strip()
        search_context = await web_search(query)
        augmented = f"{user_text}\n\n[Web context]\n{search_context}"
    else:
        augmented = user_text

    # ── LLM call ──────────────────────────────────────────────────────────────
    try:
        llm_response = await get_joi_response(
            user_message=augmented,
            conversation_history=history,
            mood=req.mood,
        )
    except Exception as e:
        raise HTTPException(502, f"LLM error: {e}")

    # ── Tool execution loop ───────────────────────────────────────────────────
    tool_results = []
    final_reply = llm_response
    MAX_TOOL_ROUNDS = 3  # prevent runaway loops on low-spec hardware

    for _ in range(MAX_TOOL_ROUNDS):
        tool_call = parse_tool_call(final_reply)
        if not tool_call:
            break

        tool_name = tool_call["tool"]
        tool_params = tool_call["params"]
        text_before = strip_tool_call(final_reply)

        # Execute the tool
        result = await execute_tool(tool_name, **tool_params)
        tool_results.append({"tool": tool_name, "result": result})

        if not result["success"]:
            # Tool failed or was denied — tell LLM and stop
            final_reply = (
                f"{text_before}\n\n"
                f"[Tool '{tool_name}' result: {result['message']}]"
            ).strip()
            break

        # Feed result back to LLM for a natural summary
        follow_up_history = history + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": final_reply},
            {"role": "user", "content": f"[Tool result for '{tool_name}']: {result['message']}"},
        ]
        try:
            final_reply = await get_joi_response(
                user_message=f"Summarize this tool result naturally: {result['message']}",
                conversation_history=follow_up_history,
                mood=req.mood,
            )
        except Exception:
            final_reply = f"{text_before}\n\n{result['message']}".strip()
        break  # one tool per turn keeps it responsive on low-spec hardware

    # ── Persist history ───────────────────────────────────────────────────────
    history.append({"role": "user",      "content": user_text})
    history.append({"role": "assistant", "content": final_reply})
    if len(history) > 30:  # smaller window = less RAM
        _sessions[req.session_id] = history[-30:]

    # ── Voice output ──────────────────────────────────────────────────────────
    audio_b64 = None
    if req.voice_enabled:
        audio_b64 = generate_joi_audio(final_reply, mood=req.mood)

    return {
        "reply":          final_reply,
        "mood":           req.mood,
        "audio_base64":   audio_b64,
        "tool_results":   tool_results,
        "search_context": search_context or None,
    }


@app.delete("/chat/history/{session_id}")
async def clear_history(session_id: str = "default"):
    _sessions.pop(session_id, None)
    return {"status": "cleared"}


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
        raise HTTPException(404, "Index out of range")
    removed = memories.pop(index)
    profile["memories"] = memories
    save_profile(profile)
    return {"status": "deleted", "removed": removed}