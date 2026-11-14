"""
JOI's voice output.
- speak_b64(): ElevenLabs cloud voice (returns base64 MP3 for the browser), used when ELEVENLABS_API_KEY is set.
- speak_local(): the Windows voice via pyttsx3, used for spoken replies from the desktop.
"""
import base64
import logging
import threading

import httpx

from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

log = logging.getLogger("joi.tts")
_speak_lock = threading.Lock()


async def speak_b64(text: str) -> str | None:
    if not ELEVENLABS_API_KEY or not text.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
                json={"text": text[:1500], "model_id": "eleven_turbo_v2_5"},
            )
        if r.status_code != 200:
            log.warning("ElevenLabs returned %s", r.status_code)
            return None
        return base64.b64encode(r.content).decode("utf-8")
    except httpx.HTTPError as e:
        log.warning("ElevenLabs request failed: %s", e)
        return None


def speak_local(text: str):
    """Say the text out loud with the Windows voice. Silently does nothing if pyttsx3 is missing."""
    try:
        import pyttsx3
    except ImportError:
        return
    with _speak_lock:
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            log.warning("Speech output failed: %s", e)
