#!/usr/bin/env python3
"""
JOI launcher: one command starts everything.

    python run.py                 start backend + frontend and open the browser
    python run.py --no-browser    don't open a browser window
    python run.py --skip-install  don't install dependencies (faster restarts)

It reads .env, installs missing dependencies once, starts the backend
(FastAPI on port 8000) and the frontend (Vite on port 5173), waits until both
are ready, and stops both on Ctrl+C.
"""
import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
LOGS = ROOT / "logs"
IS_WIN = os.name == "nt"


def log(msg):
    print(f"[JOI] {msg}", flush=True)


def die(msg, code=1):
    print(f"[JOI] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def load_env():
    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        log("Created .env from .env.example.")
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.split(" #", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)  # real env vars win over .env


def check_python():
    if sys.version_info < (3, 10):
        die(f"Python 3.10 or newer is required (you have {sys.version.split()[0]}).")


def has_module(name):
    return importlib.util.find_spec(name) is not None


def pip_install(req_file):
    log(f"Installing Python packages from {req_file.name} (one-time)...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)])
    if r.returncode:
        die(f"pip install failed. Try running it yourself: pip install -r {req_file}")


def ensure_backend_deps(skip):
    core = ["fastapi", "uvicorn", "httpx", "pydantic", "dotenv", "psutil", "pyautogui", "pyperclip"]
    missing = [m for m in core if not has_module(m)]
    if missing and not skip:
        pip_install(BACKEND / "requirements.txt")
    elif missing:
        die(f"Missing Python packages: {', '.join(missing)}. Run without --skip-install.")


def report_optional():
    features = {
        "microphone voice (JOI_VOICE=1)": ["speech_recognition", "pyttsx3"],
        "camera photos": ["cv2"],
        "microphone recording": ["sounddevice", "numpy"],
        "USB serial ports": ["serial"],
        "raw USB devices": ["usb"],
    }
    for feature, mods in features.items():
        if any(not has_module(m) for m in mods):
            log(f"Optional feature off: {feature}. To enable: pip install -r backend/requirements-optional.txt")


def check_keys():
    if not os.getenv("GROQ_API_KEY"):
        log("WARNING: GROQ_API_KEY is empty in .env. The app starts, but chat needs it: "
            "get a free key at https://console.groq.com")
    if os.getenv("JOI_VOICE") == "1" and not os.getenv("ELEVENLABS_API_KEY"):
        log("Note: ELEVENLABS_API_KEY is empty, so JOI will use the local Windows voice.")


def npm_path():
    npm = shutil.which("npm")
    if not npm:
        die("Node.js (npm) was not found. Install Node 18+ from https://nodejs.org and run again.")
    return npm


def ensure_frontend_deps(npm):
    if (FRONTEND / "node_modules").exists():
        return
    log("Installing frontend packages (one-time, can take a few minutes)...")
    r = subprocess.run([npm, "install"], cwd=FRONTEND, shell=IS_WIN)
    if r.returncode:
        die("npm install failed. See the output above.")


def port_in_use(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


# Bypass proxies for localhost. On Windows, urllib reads the system proxy from
# the registry, which would otherwise send the 127.0.0.1 health check through it.
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def tail(path, lines=40):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(text[-lines:]) or "(log is empty)"
    except OSError:
        return "(no log file)"


def wait_for(url, proc, name, timeout, log_path=None):
    deadline = time.time() + timeout
    last_error = "no response yet"
    while time.time() < deadline:
        if proc.poll() is not None:
            detail = f"\n--- last lines of {log_path} ---\n{tail(log_path)}" if log_path else ""
            die(f"{name} exited with code {proc.returncode}.{detail}")
        try:
            with _NO_PROXY.open(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return True
            last_error = f"HTTP {e.code}"
        except (urllib.error.URLError, OSError) as e:
            last_error = str(getattr(e, "reason", e))
        time.sleep(1)
    detail = f"\n--- last lines of {log_path} ---\n{tail(log_path)}" if log_path else ""
    die(f"{name} did not become ready at {url} within {timeout}s. Last error: {last_error}.{detail}")


def open_app_window(url):
    """Show JOI in its own window. Returns True only if the page actually loaded in it."""
    try:
        import webview
    except ImportError:
        log("pywebview is not installed, so JOI will open in your browser. "
            "For the app window: pip install pywebview")
        return False
    loaded = threading.Event()
    window = webview.create_window("JOI", url, width=1200, height=820, min_size=(900, 640),
                                   background_color="#0b0b12")
    window.events.loaded += loaded.set
    try:
        webview.start()  # blocks until the window closes; pywebview logs WebView2 errors itself
    except Exception as e:
        log(f"The app window could not open ({str(e).splitlines()[0]}).")
        return False
    if not loaded.is_set():
        log("The app window did not load (WebView2 did not start). Opening JOI in your browser instead.")
        return False
    return True


class InProcessBackend:
    """Runs the FastAPI backend in a thread of this process, so its logs print in this console."""

    def __init__(self, port):
        sys.path.insert(0, str(BACKEND))
        import uvicorn
        import server  # importing the backend shows any error here with a full traceback
        self._server = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port,
                                                     log_level="info"))
        self._thread = threading.Thread(target=self._server.run, daemon=True, name="joi-backend")
        self._thread.start()

    def poll(self):
        return None if self._thread.is_alive() else 1

    def stop(self):
        self._server.should_exit = True
        self._thread.join(timeout=5)


def stop(procs):
    for p in procs:
        if isinstance(p, InProcessBackend):
            p.stop()
        elif p.poll() is None:
            try:
                if IS_WIN:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                else:
                    p.terminate()
            except subprocess.TimeoutExpired:
                p.kill()
    for p in procs:
        if isinstance(p, InProcessBackend):
            continue
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def main():
    parser = argparse.ArgumentParser(description="Run JOI (backend + frontend).")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    check_python()
    load_env()
    backend_port = int(os.getenv("JOI_PORT", "8000"))
    frontend_port = int(os.getenv("JOI_FRONTEND_PORT", "5173"))
    for port, label in ((backend_port, "backend (JOI_PORT)"), (frontend_port, "frontend (JOI_FRONTEND_PORT)")):
        if port_in_use(port):
            die(f"Port {port} is already in use ({label}). Stop the other program or change it in .env.")

    check_keys()
    ensure_backend_deps(args.skip_install)
    report_optional()
    npm = npm_path()
    ensure_frontend_deps(npm)

    procs = []
    try:
        log(f"Starting backend on http://127.0.0.1:{backend_port} ...")
        backend = InProcessBackend(backend_port)
        procs.append(backend)
        wait_for(f"http://127.0.0.1:{backend_port}/api/health", backend, "Backend", 60)

        log(f"Starting frontend on http://127.0.0.1:{frontend_port} ...")
        env = dict(os.environ, JOI_BACKEND_URL=f"http://127.0.0.1:{backend_port}")
        frontend = subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            cwd=FRONTEND, env=env, shell=IS_WIN)
        procs.append(frontend)
        log("Waiting for the frontend. The first start on Windows can take a few minutes; Vite prints below.")
        wait_for(f"http://127.0.0.1:{frontend_port}/", frontend, "Frontend", 420)

        url = f"http://127.0.0.1:{frontend_port}"
        log("JOI is ready. Opening the JOI app window (close the window or press Ctrl+C to stop).")
        if not args.no_browser and open_app_window(url):
            return  # the user closed the window: stop everything in the finally block
        if not args.no_browser:
            webbrowser.open(url)
        log(f"JOI is running at {url}   (Ctrl+C to stop)")

        while True:
            for p in procs:
                if p.poll() is not None:
                    die(f"A process stopped unexpectedly (exit code {p.returncode}).")
            time.sleep(1)
    except KeyboardInterrupt:
        log("Stopping JOI...")
    finally:
        stop(procs)


if __name__ == "__main__":
    main()