"""
JOI tool registry.

Each tool is a normal function decorated with @tool. Tools that declare a
`category` need the user's permission first (see permissions.py); the agent
asks by voice/chat before they run. Tools without a category run directly.

Windows is the primary target; cross-platform fallbacks are noted inline.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import wave
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, quote_plus

import httpx
import psutil

from permissions import gate, CATEGORY_TEXT

IS_WIN = platform.system() == "Windows"
MEDIA_DIR = Path.home() / "Pictures" / "JOI"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

REGISTRY: dict[str, dict] = {}


def tool(name, description, params=None, required=None, category=None):
    def wrap(fn):
        REGISTRY[name] = {
            "fn": fn,
            "description": description,
            "params": params or {},
            "required": required or [],
            "category": category,
        }
        return fn
    return wrap


def ok(message, data=None):
    return {"success": True, "message": message, "data": data}


def fail(message):
    return {"success": False, "message": message, "data": None}


def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def openai_schemas() -> list[dict]:
    out = []
    for name, spec in REGISTRY.items():
        desc = spec["description"]
        if spec["category"]:
            desc += " (needs the user's permission first)"
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": spec["params"],
                    "required": spec["required"],
                },
            },
        })
    return out


# ── Browser ───────────────────────────────────────────────────────────────────

def _find_chrome() -> str | None:
    candidates = [shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium")]
    if IS_WIN:
        candidates += [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    return next((c for c in candidates if c and Path(c).exists()), None)


def _open(url: str, browser: str = "chrome") -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if browser.lower() in ("chrome", "google chrome"):
        chrome = _find_chrome()
        if chrome:
            subprocess.Popen([chrome, url])
            return "Chrome"
    webbrowser.open_new_tab(url)
    return "your default browser"


@tool("open_url", "Open a web address in Chrome",
      {"url": {"type": "string"}, "browser": {"type": "string", "description": "chrome or default"}},
      ["url"])
def open_url(url, browser="chrome"):
    where = _open(url, browser)
    return ok(f"Opened {url} in {where}.", data=url)


@tool("open_youtube", "Search YouTube for a query and open the results in Chrome",
      {"query": {"type": "string"}, "browser": {"type": "string"}}, ["query"])
def open_youtube(query, browser="chrome"):
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    where = _open(url, browser)
    return ok(f"Searched YouTube for '{query}' in {where}.", data=url)


@tool("search_web", "Search the web for something and show the results in Chrome. Use this for any request to search, look up or google something.",
      {"query": {"type": "string"},
       "engine": {"type": "string", "enum": ["google", "bing", "duckduckgo"]},
       "browser": {"type": "string"}}, ["query"])
def search_web(query, engine="google", browser="chrome"):
    base = {
        "google": "https://www.google.com/search?q=",
        "bing": "https://www.bing.com/search?q=",
        "duckduckgo": "https://duckduckgo.com/?q=",
    }.get(engine, "https://www.google.com/search?q=")
    where = _open(base + quote_plus(query), browser)
    return ok(f"Searched {engine} for '{query}' in {where}.")


@tool("search_wikipedia", "Look up a topic on Wikipedia, open the article in Chrome and return a summary",
      {"query": {"type": "string"}, "browser": {"type": "string"}}, ["query"])
def search_wikipedia(query, browser="chrome"):
    headers = {"User-Agent": "JOI-Desktop/1.0"}
    with httpx.Client(timeout=10, headers=headers) as c:
        r = c.get("https://en.wikipedia.org/w/api.php",
                  params={"action": "opensearch", "search": query, "limit": 1, "format": "json"})
        hits = r.json()[1] if r.status_code == 200 else []
        if not hits:
            return fail(f"No Wikipedia article found for '{query}'.")
        title = hits[0]
        slug = quote(title.replace(" ", "_"))
        s = c.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}")
        extract = s.json().get("extract", "") if s.status_code == 200 else ""
    url = f"https://en.wikipedia.org/wiki/{slug}"
    where = _open(url, browser)
    return ok(f"Opened the Wikipedia article '{title}' in {where}.",
              data={"title": title, "summary": extract[:1200]})


# ── Apps, processes, windows ─────────────────────────────────────────────────

APP_ALIASES = {
    "chrome": "chrome", "google chrome": "chrome", "notepad": "notepad",
    "calculator": "calc", "calc": "calc", "paint": "mspaint",
    "explorer": "explorer", "file explorer": "explorer", "task manager": "taskmgr",
    "vs code": "code", "vscode": "code", "spotify": "spotify", "discord": "discord",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
}


@tool("open_app", "Open an application by name",
      {"app_name": {"type": "string"}}, ["app_name"])
def open_app(app_name):
    exe = APP_ALIASES.get(app_name.lower().strip(), app_name)
    try:
        if IS_WIN:
            os.startfile(exe)  # works for registered apps like notepad, chrome, spotify
        else:
            subprocess.Popen(exe, shell=True)
        return ok(f"Opened {app_name}.")
    except OSError:
        try:
            subprocess.Popen(exe, shell=True)
            return ok(f"Opened {app_name}.")
        except Exception as e:
            return fail(f"Could not open {app_name}: {e}")


@tool("list_processes", "List running programs", {}, [])
def list_processes():
    names = sorted({p.info["name"] for p in psutil.process_iter(["name"]) if p.info["name"]})
    return ok(f"{len(names)} distinct programs running.", data=names)


@tool("kill_process", "Close a running program by its process name, e.g. 'chrome.exe'",
      {"name": {"type": "string"}}, ["name"], category="processes")
def kill_process(name):
    target = name.lower().replace(".exe", "").strip()
    killed = 0
    for p in psutil.process_iter(["name"]):
        base = (p.info["name"] or "").lower().replace(".exe", "")
        if base == target:
            try:
                p.kill()
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    if not killed:
        return fail(f"No running process named '{name}'.")
    return ok(f"Closed {killed} process(es) named '{name}'.")


def _foreground_title() -> str | None:
    if not IS_WIN:
        return None
    import ctypes
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    n = u.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, buf, n + 1)
    return buf.value or None


def _window_titles() -> list[str] | None:
    try:
        import pygetwindow as gw
        return sorted({w.title for w in gw.getAllWindows() if w.title and w.title.strip()})
    except Exception:
        return None


@tool("list_windows", "List open windows and which one is active", {}, [])
def list_windows():
    titles = _window_titles()
    if titles is None:
        return fail("Window listing needs pygetwindow on Windows (pip install pygetwindow).")
    return ok(f"{len(titles)} windows open.", data={"active": _foreground_title(), "windows": titles})


@tool("focus_window", "Bring the first window whose title contains the text to the front",
      {"title": {"type": "string"}}, ["title"])
def focus_window(title):
    try:
        import pygetwindow as gw
    except Exception:
        return fail("Needs pygetwindow (pip install pygetwindow).")
    matches = [w for w in gw.getWindowsWithTitle(title) if w.title]
    if not matches:
        return fail(f"No window matching '{title}'.")
    w = matches[0]
    try:
        w.activate()
    except Exception:
        w.minimize()
        w.restore()
    return ok(f"Focused '{w.title}'.")


_monitor = {"running": False, "events": deque(maxlen=300), "last": None}


def _monitor_loop(interval: int):
    while _monitor["running"]:
        title = _foreground_title()
        if title and title != _monitor["last"]:
            _monitor["last"] = title
            _monitor["events"].append({"time": datetime.now().isoformat(timespec="seconds"), "window": title})
        time.sleep(interval)


@tool("start_window_monitor", "Start logging every window switch in the background",
      {"interval_seconds": {"type": "integer"}}, [], category="window_monitor")
def start_window_monitor(interval_seconds=2):
    if _monitor["running"]:
        return ok("Window monitor is already running.")
    if not IS_WIN:
        return fail("Foreground window monitoring is implemented for Windows.")
    _monitor["running"] = True
    interval = max(1, min(int(interval_seconds), 30))
    threading.Thread(target=_monitor_loop, args=(interval,), daemon=True).start()
    return ok(f"Window monitor started, checking every {interval}s.")


@tool("stop_window_monitor", "Stop the background window monitor", {}, [])
def stop_window_monitor():
    _monitor["running"] = False
    return ok("Window monitor stopped.")


@tool("get_window_history", "Return recent window switches logged by the monitor",
      {"limit": {"type": "integer"}}, [], category="window_monitor")
def get_window_history(limit=30):
    events = list(_monitor["events"])[-int(limit):]
    return ok(f"{len(events)} recent window switches.", data=events)


def window_events() -> list[dict]:
    return list(_monitor["events"])


# ── Input: keyboard, mouse, clipboard ────────────────────────────────────────

def _focus_for_input(window_title):
    """Bring the named window to the front before sending keys. Returns an error message or None."""
    if not window_title:
        return None
    try:
        import pygetwindow as gw
    except Exception:
        return "Focusing windows needs pygetwindow."
    matches = [w for w in gw.getWindowsWithTitle(window_title) if w.title]
    if not matches:
        return f"No window matching '{window_title}' is open."
    try:
        matches[0].activate()
    except Exception:
        matches[0].minimize()
        matches[0].restore()
    time.sleep(0.4)
    return None


@tool("type_text", "Type text into a named window (e.g. window_title 'Chrome'). Only when the user asks to type.",
      {"text": {"type": "string"}, "window_title": {"type": "string"}}, ["text"], category="keyboard_mouse")
def type_text(text, window_title=None):
    err = _focus_for_input(window_title)
    if err:
        return fail(err)
    import pyautogui
    pyautogui.write(text, interval=0.02)
    return ok("Typed the text.")


@tool("press_keys", "Press a key or combination, e.g. 'enter', 'ctrl+c'. Pass window_title to target a window.",
      {"keys": {"type": "string"}, "window_title": {"type": "string"}}, ["keys"], category="keyboard_mouse")
def press_keys(keys, window_title=None):
    err = _focus_for_input(window_title)
    if err:
        return fail(err)
    import pyautogui
    combo = [k.strip().lower() for k in keys.split("+") if k.strip()]
    if not combo:
        return fail("No key given.")
    if len(combo) > 1:
        pyautogui.hotkey(*combo)
    else:
        pyautogui.press(combo[0])
    return ok(f"Pressed {keys}.")


@tool("click", "Click at screen coordinates",
      {"x": {"type": "integer"}, "y": {"type": "integer"},
       "button": {"type": "string", "enum": ["left", "right"]}}, ["x", "y"],
      category="keyboard_mouse")
def click(x, y, button="left"):
    import pyautogui
    pyautogui.click(int(x), int(y), button=button)
    return ok(f"Clicked at {x}, {y}.")


@tool("get_clipboard", "Read the current clipboard text", {}, [], category="clipboard")
def get_clipboard():
    import pyperclip
    return ok("Clipboard read.", data=pyperclip.paste())


@tool("set_clipboard", "Copy text to the clipboard", {"text": {"type": "string"}}, ["text"])
def set_clipboard(text):
    import pyperclip
    pyperclip.copy(text)
    return ok("Copied to clipboard.")


@tool("take_screenshot", "Capture the whole screen to a PNG in Pictures/JOI",
      {}, [], category="screenshot")
def take_screenshot():
    import pyautogui
    path = MEDIA_DIR / f"screen_{_ts()}.png"
    pyautogui.screenshot().save(path)
    return ok("Screenshot saved.", data=str(path))


# ── Camera, microphone, sensors ──────────────────────────────────────────────

@tool("capture_camera", "Take a photo with the default webcam and save it",
      {}, [], category="camera")
def capture_camera():
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return fail("No camera found, or another app is using it.")
    try:
        for _ in range(5):  # let auto-exposure settle
            cap.read()
        good, frame = cap.read()
    finally:
        cap.release()
    if not good:
        return fail("The camera did not return a frame.")
    path = MEDIA_DIR / f"camera_{_ts()}.jpg"
    cv2.imwrite(str(path), frame)
    return ok("Photo captured.", data=str(path))


@tool("record_microphone", "Record from the microphone for a number of seconds (max 30) and transcribe it",
      {"seconds": {"type": "integer"}}, [], category="microphone")
def record_microphone(seconds=5):
    import sounddevice as sd
    seconds = max(1, min(int(seconds), 30))
    rate = 16000
    data = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    path = MEDIA_DIR / f"mic_{_ts()}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    transcript = None
    try:
        import speech_recognition as sr
        rec = sr.Recognizer()
        with sr.AudioFile(str(path)) as src:
            transcript = rec.recognize_google(rec.record(src))
    except Exception:
        pass
    return ok("Recording saved.", data={"file": str(path), "transcript": transcript})


@tool("read_sensors", "Read battery, CPU frequency, and temperature or fan sensors the OS exposes",
      {}, [], category="sensors")
def read_sensors():
    data = {"battery": None, "cpu_freq_mhz": None, "temperatures": None, "fans": None}
    bat = psutil.sensors_battery()
    if bat:
        data["battery"] = {"percent": bat.percent, "plugged_in": bat.power_plugged,
                           "seconds_left": bat.secsleft}
    freq = psutil.cpu_freq()
    if freq:
        data["cpu_freq_mhz"] = round(freq.current)
    if hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures() or {}
            data["temperatures"] = {k: [{"label": t.label or k, "celsius": t.current} for t in v]
                                    for k, v in temps.items()} or None
        except Exception:
            pass
    if hasattr(psutil, "sensors_fans"):
        try:
            fans = psutil.sensors_fans() or {}
            data["fans"] = {k: [{"label": f.label or k, "rpm": f.current} for f in v]
                            for k, v in fans.items()} or None
        except Exception:
            pass
    note = ("Ambient light, accelerometer and GPS sensors need device-specific drivers "
            "and aren't available through this interface.")
    if not data["temperatures"]:
        note += " Temperature sensors aren't exposed by Windows to psutil."
    data["note"] = note
    return ok("Sensor readings collected.", data=data)


@tool("system_info", "CPU, memory, disk and battery summary", {}, [])
def system_info():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    bat = psutil.sensors_battery()
    data = {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "memory_percent": mem.percent,
        "disk_percent": disk.percent,
        "battery_percent": bat.percent if bat else None,
    }
    return ok("System summary.", data=data)


# ── USB devices ──────────────────────────────────────────────────────────────

def _usb_devices() -> list[dict]:
    if IS_WIN:
        ps = ("Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB*' } | "
              "Select-Object FriendlyName,InstanceId,Class,Status | ConvertTo-Json -Compress")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        raw = r.stdout.strip()
        if not raw:
            return []
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=15)
        return [{"FriendlyName": line.split(": ", 1)[-1].strip()} for line in r.stdout.splitlines() if line]
    except FileNotFoundError:
        return []


def _storage_volumes() -> list[dict]:
    vols = []
    for p in psutil.disk_partitions(all=False):
        removable = "removable" in p.opts.lower() or "/media/" in p.mountpoint or "/run/media/" in p.mountpoint
        if removable:
            vols.append({"mountpoint": p.mountpoint, "fstype": p.fstype, "device": p.device})
    return vols


def _serial_ports() -> list[dict]:
    try:
        from serial.tools import list_ports
        return [{"port": p.device, "description": p.description} for p in list_ports.comports()]
    except Exception:
        return []


@tool("list_usb_devices", "List connected USB devices, removable drives and serial ports (names only)", {}, [])
def list_usb_devices():
    data = {"usb_devices": _usb_devices(), "removable_drives": _storage_volumes(), "serial_ports": _serial_ports()}
    return ok("USB scan complete.", data=data)


_VIDPID = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$")


def _find_volume(target: str) -> Path | None:
    norm = target.rstrip("\\/").upper()
    for p in psutil.disk_partitions(all=False):
        if p.mountpoint.rstrip("\\/").upper() == norm:
            return Path(p.mountpoint)
    return None


@tool("access_usb_device",
      "Access a USB device. target is a drive mountpoint (E:\\), a serial port (COM3) or a VID:PID (046d:c52b). "
      "actions: list_files, read_file, write_file (drives); serial_read, serial_write (ports); device_info (VID:PID).",
      {"target": {"type": "string"},
       "action": {"type": "string", "enum": ["list_files", "read_file", "write_file",
                                             "serial_read", "serial_write", "device_info"]},
       "path": {"type": "string", "description": "path inside the drive, for file actions"},
       "data": {"type": "string", "description": "content to write or send"}},
      ["target", "action"], category="usb")
def access_usb_device(target, action, path=None, data=None):
    target = target.strip()

    if action in ("list_files", "read_file", "write_file"):
        root = _find_volume(target)
        if root is None:
            return fail(f"'{target}' is not a mounted removable drive.")
        full = (root / (path or "")).resolve()
        if not str(full).upper().startswith(str(root.resolve()).upper()):
            return fail("Path escapes the device.")
        if action == "list_files":
            if not full.is_dir():
                return fail("Not a folder on that device.")
            items = [{"name": i.name, "type": "DIR" if i.is_dir() else "FILE"} for i in sorted(full.iterdir())]
            return ok(f"{len(items)} items on {root}.", data=items)
        if action == "read_file":
            if not full.is_file():
                return fail("No such file on the device.")
            text = full.read_text(encoding="utf-8", errors="replace")
            return ok(f"Read {full.name}.", data=text[:8000])
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(data or "", encoding="utf-8")
        return ok(f"Wrote {full.name} to the device.")

    if action in ("serial_read", "serial_write"):
        import serial
        with serial.Serial(target, 115200, timeout=2) as port:
            if action == "serial_write":
                port.write((data or "").encode())
                return ok(f"Sent {len(data or '')} bytes to {target}.")
            received = port.read(512).decode(errors="replace")
            return ok(f"Read from {target}.", data=received)

    if action == "device_info":
        if not _VIDPID.match(target):
            return fail("device_info needs a VID:PID like 046d:c52b.")
        import usb.core
        vid, pid = (int(x, 16) for x in target.split(":"))
        dev = usb.core.find(idVendor=vid, idProduct=pid)
        if dev is None:
            return fail("No device with that ID is connected.")
        info = {"vendor_id": hex(vid), "product_id": hex(pid)}
        try:
            import usb.util
            info["manufacturer"] = usb.util.get_string(dev, dev.iManufacturer)
            info["product"] = usb.util.get_string(dev, dev.iProduct)
        except Exception:
            info["note"] = ("Descriptor strings need libusb and a WinUSB driver for this device "
                            "(use Zadig on Windows).")
        return ok("Device details.", data=info)

    return fail(f"Unknown USB action '{action}'.")


# ── Shell and files ──────────────────────────────────────────────────────────

@tool("run_command", "Run a shell command on this PC and return its output",
      {"command": {"type": "string"}, "timeout": {"type": "integer"}}, ["command"], category="shell")
def run_command(command, timeout=30):
    r = subprocess.run(command, shell=True, capture_output=True, text=True,
                       timeout=min(int(timeout), 120))
    out = (r.stdout + (("\n" + r.stderr) if r.stderr else ""))[-4000:]
    return ok(f"Command finished with exit code {r.returncode}.", data=out)


@tool("read_file", "Read a text file",
      {"path": {"type": "string"}}, ["path"])
def read_file(path):
    p = Path(path).expanduser()
    if not p.is_file():
        return fail(f"File not found: {path}")
    return ok(f"Read {p.name}.", data=p.read_text(encoding="utf-8", errors="replace")[:8000])


@tool("list_directory", "List the contents of a folder",
      {"path": {"type": "string"}}, [])
def list_directory(path="~"):
    p = Path(path).expanduser()
    if not p.is_dir():
        return fail(f"Not a folder: {path}")
    items = [{"name": i.name, "type": "DIR" if i.is_dir() else "FILE"} for i in sorted(p.iterdir())][:300]
    return ok(f"{len(items)} items in {p}.", data=items)


@tool("find_file", "Search for files whose name contains the text, under a folder (default: home)",
      {"name": {"type": "string"}, "folder": {"type": "string"}}, ["name"])
def find_file(name, folder="~"):
    base = Path(folder).expanduser()
    matches = []
    for p in base.rglob(f"*{name}*"):
        matches.append(str(p))
        if len(matches) >= 20:
            break
    return ok(f"{len(matches)} match(es).", data=matches)


@tool("write_file", "Create or overwrite a text file",
      {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"],
      category="files_write")
def write_file(path, content):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return ok(f"Wrote {p.name}.")


@tool("delete_file", "Permanently delete a file or folder",
      {"path": {"type": "string"}}, ["path"], category="files_write")
def delete_file(path):
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"Not found: {path}")
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return ok(f"Deleted {p.name}.")


@tool("power_control", "Shut down, restart, sleep, lock or cancel a pending shutdown on this PC",
      {"action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "lock", "cancel_shutdown"]}},
      ["action"], category="power")
def power_control(action):
    if not IS_WIN:
        return fail("Power control is implemented for Windows.")
    cmds = {
        "shutdown": "shutdown /s /t 10",
        "restart": "shutdown /r /t 10",
        "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "lock": "rundll32.exe user32.dll,LockWorkStation",
        "cancel_shutdown": "shutdown /a",
    }
    if action not in cmds:
        return fail(f"Unknown power action '{action}'.")
    subprocess.Popen(cmds[action], shell=True)
    return ok(f"{action.replace('_', ' ').capitalize()} command sent.")


# ── Web search (needs SERPER_API_KEY) ────────────────────────────────────────

@tool("web_search", "Search the web and return the top results (needs SERPER_API_KEY)",
      {"query": {"type": "string"}}, ["query"])
def web_search(query):
    from config import SERPER_API_KEY
    if not SERPER_API_KEY:
        return fail("Web search is off: add SERPER_API_KEY to .env.")
    r = httpx.post("https://google.serper.dev/search",
                   headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                   json={"q": query, "num": 5}, timeout=15)
    if r.status_code != 200:
        return fail(f"Search failed with HTTP {r.status_code}.")
    results = [{"title": o.get("title"), "link": o.get("link"), "snippet": o.get("snippet")}
               for o in r.json().get("organic", [])[:5]]
    return ok(f"{len(results)} results.", data=results)


# ── Execution ────────────────────────────────────────────────────────────────

def describe_call(name: str, args: dict) -> str:
    cat = REGISTRY[name]["category"]
    shown = ", ".join(f"{k}={str(v)[:60]!r}" for k, v in args.items())
    return f"{CATEGORY_TEXT.get(cat, cat)} ({name}{': ' + shown if shown else ''})"


async def execute_tool(name: str, args: dict, approved: bool = False) -> dict:
    """Run a tool. Returns a permission_required status when the user must approve first."""
    import asyncio

    spec = REGISTRY.get(name)
    if spec is None:
        return fail(f"Unknown tool '{name}'.")
    cat = spec["category"]
    if cat and not approved and not gate.is_allowed(cat):
        return {
            "success": False,
            "status": "permission_required",
            "category": cat,
            "tool": name,
            "args": args,
            "message": describe_call(name, args),
        }
    try:
        result = await asyncio.to_thread(spec["fn"], **args)
    except TypeError as e:
        result = fail(f"Bad parameters for {name}: {e}")
    except subprocess.TimeoutExpired:
        result = fail(f"{name} timed out.")
    except Exception as e:
        result = fail(f"{name} failed: {e}")
    gate.audit({"event": "tool", "tool": name, "category": cat,
                "approved": approved, "args_keys": sorted(args), "success": result.get("success")})
    return result
