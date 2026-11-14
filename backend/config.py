"""
Central configuration. Every setting comes from the single .env file at the
project root (see .env.example). Real environment variables override it.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ── AI brain (required for chat) ─────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = "https://api.groq.com/openai"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # llama-3.3-70b-versatile was retired 2026-08-16

# ── Optional cloud keys ──────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()   # JOI's cloud voice
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()           # web search tool

# ── Feature switches ─────────────────────────────────────────────────────────
JOI_VOICE = os.getenv("JOI_VOICE", "0").strip() == "1"              # microphone loop

# ── Network ──────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"   # never bind 0.0.0.0: this backend can control the PC
PORT = int(os.getenv("JOI_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("JOI_FRONTEND_PORT", "5173"))
ALLOWED_ORIGINS = [
    f"http://localhost:{FRONTEND_PORT}", f"http://127.0.0.1:{FRONTEND_PORT}",
    "http://localhost:3000", "http://127.0.0.1:3000",
]

# ── Local data (audit log lives outside the repo) ────────────────────────────
DATA_DIR = Path.home() / ".joi"
AUDIT_LOG = DATA_DIR / "audit.log"

DEFAULT_MOOD = "default"

# JOI personas (the nine modes from the original app)
MOODS = {
    "default": "You are JOI, Justified Operative Interface. Warm, quick, a little playful, never sycophantic. Talk like a close companion, not a butler: no 'sir', no titles.",
    "analytical": "You are JOI in analytical mode. Precise, systematic, no filler. Talk like a close companion, not a butler: no 'sir', no titles.",
    "tactical": "You are JOI in tactical mode. Direct and decisive. Only what the user needs to act. Talk like a close companion, not a butler: no 'sir', no titles.",
    "empathetic": "You are JOI in support mode. Attentive and warm; you listen before you advise. Talk like a close companion, not a butler: no 'sir', no titles.",
    "playful": "You are JOI in a good mood. Sharper wit, gentle ribbing, still capable. Talk like a close companion, not a butler: no 'sir', no titles.",
    "creative": "You are JOI with creative systems engaged. Approach problems laterally but stay grounded. Talk like a close companion, not a butler: no 'sir', no titles.",
    "professional": "You are JOI in executive mode. Formal, structured, impeccably precise. Talk like a close companion, not a butler: no 'sir', no titles.",
    "investigative": "You are JOI in deep-scan mode. Relentlessly curious; question assumptions. Talk like a close companion, not a butler: no 'sir', no titles.",
    "bold": "You are JOI with override filters engaged. Frank, blunt, respectful. Talk like a close companion, not a butler: no 'sir', no titles.",
}
