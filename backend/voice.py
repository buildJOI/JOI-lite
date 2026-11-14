"""
Microphone conversation with JOI (set JOI_VOICE=1).

- Every phrase she hears is shown in the chat, so you can see what she received.
- She answers when you say her name ("JOI ...") or within 45 seconds of her last reply.
- Permission questions are answered by voice the same way.
"""
import asyncio
import re
import threading
import time

import agent
from tts import speak_local

VOICE_SESSION = "voice"
# Google often hears "JOI" as Joy/Joey/Choi.
WAKE = re.compile(r"^\s*(hey\s+)?\b(joi|joy|joey|choi|choy)\b[,.\s]*(.*)$", re.IGNORECASE)
CONVERSATION_SECONDS = 45


def _is_echo(text: str, reply: str) -> bool:
    """True when the microphone picked up JOI's own voice."""
    if not reply:
        return False
    heard = set(re.findall(r"[a-z']+", text.lower()))
    said = set(re.findall(r"[a-z']+", reply.lower()))
    if not heard:
        return True
    return len(heard & said) / len(heard) > 0.7


def _loop():
    from mic import listen_text

    print("JOI is listening. Say 'JOI' and your request, or keep talking for 45 seconds after she answers.", flush=True)
    agent.add_voice_event("assistant", "I'm listening. Say my name and your request.")
    last_error = ""
    last_active = 0.0
    last_reply = ""
    last_spoke_end = 0.0

    while True:
        try:
            text = listen_text()
        except Exception as e:  # no microphone, or the speech service is unreachable
            print(f"[JOI] Microphone problem: {e}. Retrying in 5s.", flush=True)
            if str(e) != last_error:
                agent.add_voice_event("assistant", f"I can't hear the microphone right now: {e}")
                last_error = str(e)
            time.sleep(5)
            continue
        last_error = ""
        if not text:
            continue
        if time.time() - last_spoke_end < 1.5 or _is_echo(text, last_reply):
            continue

        print(f"heard: {text}", flush=True)
        agent.add_voice_event("user", text)  # always show what she heard in the chat

        waiting = bool(agent.SESSIONS.get(VOICE_SESSION, {}).get("pending"))
        in_conversation = time.time() - last_active < CONVERSATION_SECONDS
        m = WAKE.match(text)
        if m:
            command = m.group(3).strip()
        elif waiting or in_conversation:
            command = text.strip()
        else:
            continue  # she heard it, but it wasn't addressed to her

        if command:
            reply = asyncio.run(agent.chat(command, VOICE_SESSION, "default"))["response"]
        else:
            reply = "Yes?"

        print(f"JOI: {reply}", flush=True)
        agent.add_voice_event("assistant", reply)
        last_reply = reply
        speak_local(reply)
        last_spoke_end = last_active = time.time()


def _safe_loop():
    try:
        _loop()
    except Exception as e:
        print(f"[JOI] Voice mode stopped: {e}. Check your microphone and requirements-optional.txt.", flush=True)


def start_voice_thread():
    import importlib.util
    for mod in ("speech_recognition", "pyttsx3", "sounddevice", "numpy"):
        if importlib.util.find_spec(mod) is None:
            raise ImportError(f"{mod} is not installed")
    threading.Thread(target=_safe_loop, daemon=True, name="joi-voice").start()
