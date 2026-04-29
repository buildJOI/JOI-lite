"""
JOI System Tray
Runs JOI as a background app with a tray icon.
Ctrl+Shift+J → open/hide the browser UI.
Right-click tray → menu with status and quit.
Starts the FastAPI server automatically.
"""

import sys
import threading
import subprocess
import webbrowser
import time
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem as Item
    from PIL import Image, ImageDraw
except ImportError:
    print("Install pystray and Pillow: pip install pystray pillow")
    sys.exit(1)

try:
    import keyboard
except ImportError:
    print("Install keyboard: pip install keyboard")
    sys.exit(1)

JOI_URL   = "http://127.0.0.1:8000"
ICON_SIZE = 64
SERVER_SCRIPT = str(Path(__file__).parent / "server.py")

_ui_open   = False
_server_proc = None


# ── Tray icon image (generated — no file needed) ──────────────────────────────

def _make_icon() -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Dark background circle
    draw.ellipse([2, 2, ICON_SIZE-2, ICON_SIZE-2], fill=(7, 13, 26, 255))
    # Cyan ring
    draw.ellipse([4, 4, ICON_SIZE-4, ICON_SIZE-4], outline=(0, 200, 255, 255), width=3)
    # "J" text approximation using rectangles (no font needed)
    # Vertical bar
    draw.rectangle([30, 16, 36, 44], fill=(0, 200, 255, 255))
    # Bottom curve hint
    draw.rectangle([22, 40, 34, 46], fill=(0, 200, 255, 255))
    draw.rectangle([20, 34, 26, 44], fill=(0, 200, 255, 255))
    return img


# ── Server management ─────────────────────────────────────────────────────────

def _start_server():
    global _server_proc
    if _server_proc and _server_proc.poll() is None:
        return  # already running
    _server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app",
         "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        cwd=str(Path(__file__).parent),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    print("[JOI Tray] Server started.")


def _stop_server():
    global _server_proc
    if _server_proc:
        _server_proc.terminate()
        _server_proc = None


def _wait_for_server(timeout=15) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{JOI_URL}/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# ── UI toggle ─────────────────────────────────────────────────────────────────

def toggle_ui():
    global _ui_open
    if not _ui_open:
        webbrowser.open(JOI_URL)
        _ui_open = True
    else:
        # Can't programmatically close the browser tab, just mark as closed
        # so next toggle opens it again
        _ui_open = False


# ── Hotkey ────────────────────────────────────────────────────────────────────

def _setup_hotkey():
    keyboard.add_hotkey("ctrl+shift+j", toggle_ui)
    print("[JOI Tray] Hotkey registered: Ctrl+Shift+J")


# ── Tray menu ─────────────────────────────────────────────────────────────────

def _build_menu(icon):
    def open_ui(icon, item):
        toggle_ui()

    def open_logs(icon, item):
        webbrowser.open(f"{JOI_URL}/docs")

    def quit_joi(icon, item):
        print("[JOI Tray] Shutting down...")
        _stop_server()
        keyboard.unhook_all()
        icon.stop()

    return (
        Item("Open JOI  (Ctrl+Shift+J)", open_ui, default=True),
        Item("API Docs", open_logs),
        pystray.Menu.SEPARATOR,
        Item("Quit JOI", quit_joi),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[JOI Tray] Starting...")

    # Start server in background
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    # Setup hotkey
    hotkey_thread = threading.Thread(target=_setup_hotkey, daemon=True)
    hotkey_thread.start()

    # Wait for server then open UI automatically on first launch
    def _auto_open():
        if _wait_for_server():
            print("[JOI Tray] Server ready.")
            time.sleep(0.5)
            toggle_ui()
        else:
            print("[JOI Tray] Server failed to start.")

    threading.Thread(target=_auto_open, daemon=True).start()

    # Build and run tray icon (blocks until quit)
    icon_img = _make_icon()
    icon = pystray.Icon(
        "JOI",
        icon_img,
        "JOI — Justified Operative Interface",
    )
    icon.menu = pystray.Menu(*_build_menu(icon))
    print("[JOI Tray] Running in system tray. Ctrl+Shift+J to open.")
    icon.run()


if __name__ == "__main__":
    main()