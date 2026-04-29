"""
JOI Voice Input — lightweight speech-to-text.
Uses Google's free STT API via SpeechRecognition (no local model = no RAM cost).
Supports:
  - Hotkey mode: hold Ctrl+Shift+Space to record
  - Wake word mode: background listener for "Hey JOI"
CPU/RAM cost is minimal — only active during recording.
"""

import threading
import queue
import time
import asyncio
import speech_recognition as sr

# Shared queue: voice_input.py puts transcribed text here,
# server.py reads from it to inject into chat.
voice_queue: queue.Queue = queue.Queue()

_recognizer = sr.Recognizer()
_recognizer.energy_threshold = 300       # lower = more sensitive
_recognizer.dynamic_energy_threshold = True
_recognizer.pause_threshold = 0.8        # seconds of silence = end of speech

_mic = None
_hotkey_active = False
_wake_word_active = False
_listening_lock = threading.Lock()       # prevent double-listening on slow CPU

WAKE_WORDS = {"hey joi", "hey joy", "joi", "j.o.i"}


def _get_mic():
    global _mic
    if _mic is None:
        _mic = sr.Microphone()
        # Calibrate once on first use (1 second ambient noise sample)
        with _mic as source:
            _recognizer.adjust_for_ambient_noise(source, duration=1)
    return _mic


def _transcribe(audio) -> str | None:
    """Send audio to Google STT. Returns text or None on failure."""
    try:
        text = _recognizer.recognize_google(audio)
        return text.strip().lower()
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"[JOI Voice] STT service error: {e}")
        return None


def _record_and_transcribe() -> str | None:
    """Record one phrase and return transcription."""
    if not _listening_lock.acquire(blocking=False):
        return None  # already recording on slow CPU, skip
    try:
        mic = _get_mic()
        with mic as source:
            try:
                audio = _recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                return None
        return _transcribe(audio)
    finally:
        _listening_lock.release()


# ── Hotkey mode ───────────────────────────────────────────────────────────────
# Hold Ctrl+Shift+Space → JOI listens.
# Release → transcription sent to voice_queue.

def start_hotkey_listener(callback=None):
    """
    Start hotkey listener in background thread.
    callback(text) is called with transcribed text.
    If no callback, text is pushed to voice_queue.
    """
    import keyboard

    def _on_hotkey():
        print("[JOI Voice] Hotkey pressed — listening...")
        text = _record_and_transcribe()
        if text:
            print(f"[JOI Voice] Heard: {text}")
            if callback:
                callback(text)
            else:
                voice_queue.put(text)
        else:
            print("[JOI Voice] Nothing heard.")

    keyboard.add_hotkey("ctrl+shift+space", _on_hotkey)
    print("[JOI Voice] Hotkey listener active: Ctrl+Shift+Space to speak")


# ── Wake word mode ────────────────────────────────────────────────────────────
# Continuously listens for "Hey JOI" then captures the next phrase.
# Runs in a daemon thread — very low CPU when idle (Google's VAD handles it).

def start_wake_word_listener(callback=None):
    """
    Start wake word listener in background daemon thread.
    After detecting wake word, records the command and sends to callback/queue.
    """
    def _listen_loop():
        global _wake_word_active
        _wake_word_active = True
        mic = _get_mic()
        print("[JOI Voice] Wake word listener active: say 'Hey JOI'")

        while _wake_word_active:
            try:
                with mic as source:
                    try:
                        audio = _recognizer.listen(source, timeout=2, phrase_time_limit=4)
                    except sr.WaitTimeoutError:
                        continue

                text = _transcribe(audio)
                if not text:
                    continue

                # Check if any wake word is in the transcription
                triggered = any(w in text for w in WAKE_WORDS)
                if not triggered:
                    continue

                print(f"[JOI Voice] Wake word detected in: '{text}'")

                # Strip the wake word to get the actual command
                command = text
                for w in sorted(WAKE_WORDS, key=len, reverse=True):
                    command = command.replace(w, "").strip(" ,.")

                if command:
                    # Command was in the same phrase as wake word
                    print(f"[JOI Voice] Command: {command}")
                    if callback:
                        callback(command)
                    else:
                        voice_queue.put(command)
                else:
                    # Wake word only — listen for the next phrase
                    print("[JOI Voice] Listening for command...")
                    follow = _record_and_transcribe()
                    if follow:
                        print(f"[JOI Voice] Command: {follow}")
                        if callback:
                            callback(follow)
                        else:
                            voice_queue.put(follow)

                # Small pause to avoid re-triggering immediately
                time.sleep(0.5)

            except Exception as e:
                print(f"[JOI Voice] Wake word loop error: {e}")
                time.sleep(1)

    t = threading.Thread(target=_listen_loop, daemon=True)
    t.start()
    return t


def stop_wake_word_listener():
    global _wake_word_active
    _wake_word_active = False


# ── Status ────────────────────────────────────────────────────────────────────

def is_mic_available() -> bool:
    try:
        mic = sr.Microphone()
        with mic:
            pass
        return True
    except Exception:
        return False