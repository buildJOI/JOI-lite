#!/usr/bin/env python3
"""
JOI wake listener. Keeps the microphone open and waits for "Joi wake up".
When heard, it starts the whole program (run.py) and says so out loud.

    python wake.py        (keep this window open)

Needs: pip install -r backend/requirements-optional.txt
"""
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Google often hears "JOI" as Joy/Joey/Choi and "wake" as weak.
WAKE = re.compile(r"\b(joi|joy|joey|choi|choy)\b[\s,.\-]*(wake|weak)[\s\-]*up\b", re.IGNORECASE)
BACKEND_PORT = int(os.getenv("JOI_PORT", "8000"))


def backend_running():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", BACKEND_PORT)) == 0


def main():
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        import pyttsx3
        from mic import listen_once
    except ImportError as e:
        sys.exit(f"Missing package ({e.name}). Run: pip install -r backend/requirements-optional.txt")

    engine = pyttsx3.init()

    def say(text):
        print(f"JOI: {text}", flush=True)
        engine.say(text)
        engine.runAndWait()

    print('Listening for "JOI wake up". Press Ctrl+C to quit.', flush=True)
    while True:
        try:
            heard = listen_once(5)
        except Exception as e:
            print(f"Microphone problem: {e}. Retrying in 5s.", flush=True)
            time.sleep(5)
            continue
        if not heard:
            continue
        print(f"heard: {heard}", flush=True)
        if not WAKE.search(heard):
            continue

        if backend_running():
            say("JOI is already awake, sir.")
            continue

        say("Waking up, sir. Starting all systems.")
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)  # own window on Windows
        subprocess.Popen([sys.executable, "run.py"], cwd=ROOT, creationflags=flags)

        for _ in range(90):
            if backend_running():
                break
            time.sleep(1)
        if backend_running():
            say("All systems online. The browser is opening.")
        else:
            say("Startup is taking longer than expected. Check the JOI window for errors.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nWake listener stopped.")