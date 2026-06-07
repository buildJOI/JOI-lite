"""
JOI Desktop Agent — tool execution layer.
Optimized for low-spec hardware (i3-5005U, 4GB RAM).
All blocking calls run in executor so FastAPI stays non-blocking.
Risky actions pass through permission.py before executing.
"""

import os
import subprocess
import asyncio
import psutil
import webbrowser
from pathlib import Path
from datetime import datetime
from functools import partial

from permission import request_permission


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


def ok(msg, data=None):
    return {"success": True,  "message": msg, "data": data}

def fail(msg):
    return {"success": False, "message": msg, "data": None}

def denied(action):
    return {"success": False, "message": f"Permission denied by user for: {action}", "data": None}


# ── App control ───────────────────────────────────────────────────────────────

COMMON_APPS = {
    "notepad":      "notepad.exe",
    "calculator":   "calc.exe",
    "paint":        "mspaint.exe",
    "explorer":     "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd":          "cmd.exe",
    "powershell":   "powershell.exe",
    "chrome":       "chrome.exe",
    "firefox":      "firefox.exe",
    "edge":         "msedge.exe",
    "vlc":          "vlc.exe",
    "spotify":      "spotify.exe",
    "discord":      "discord.exe",
    "vs code":      "code.exe",
    "vscode":       "code.exe",
    "word":         "winword.exe",
    "excel":        "excel.exe",
    "powerpoint":   "powerpnt.exe",
}


async def open_app(app_name: str) -> dict:
    exe = COMMON_APPS.get(app_name.lower().strip(), app_name)
    try:
        await _run(subprocess.Popen, exe, shell=True)
        return ok(f"Opening {app_name}, sir.")
    except Exception as e:
        return fail(f"Could not open {app_name}: {e}")


async def close_app(app_name: str) -> dict:
    exe_base = Path(COMMON_APPS.get(app_name.lower().strip(), app_name)).stem.lower()
    killed = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if exe_base in proc.info['name'].lower():
                proc.kill()
                killed.append(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if killed:
        return ok(f"Terminated {', '.join(set(killed))}, sir.")
    return fail(f"No running process found for '{app_name}'.")


async def list_running_apps() -> dict:
    seen, apps = set(), []
    for proc in psutil.process_iter(['name']):
        try:
            n = proc.info['name']
            if n and n not in seen:
                seen.add(n)
                apps.append(n)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return ok(f"{len(apps)} processes running.", data=sorted(apps))


# ── File operations ───────────────────────────────────────────────────────────

async def read_file(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"File not found: {path}")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        # Truncate large files to save memory
        if len(content) > 8000:
            content = content[:8000] + "\n\n[... truncated for memory efficiency ...]"
        return ok(f"Read {p.name}.", data=content)
    except Exception as e:
        return fail(f"Read error: {e}")


async def write_file(path: str, content: str) -> dict:
    p = Path(path).expanduser()
    if not request_permission("write_file", str(p)):
        return denied("write_file")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ok(f"Written to {p.name}, sir.")
    except Exception as e:
        return fail(f"Write error: {e}")


async def list_directory(path: str = ".") -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"Path not found: {path}")
    try:
        items = []
        for item in sorted(p.iterdir()):
            items.append({
                "name": item.name,
                "type": "DIR" if item.is_dir() else "FILE",
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return ok(f"{len(items)} items in {p}.", data=items)
    except Exception as e:
        return fail(f"Directory error: {e}")


async def find_file(filename: str, search_path: str = "C:/Users") -> dict:
    matches = []
    try:
        for p in Path(search_path).expanduser().rglob(f"*{filename}*"):
            matches.append(str(p))
            if len(matches) >= 15:
                break
        return ok(f"Found {len(matches)} match(es).", data=matches)
    except Exception as e:
        return fail(f"Search error: {e}")


async def open_file(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"File not found: {path}")
    try:
        os.startfile(str(p))
        return ok(f"Opened {p.name}, sir.")
    except Exception as e:
        return fail(f"Open error: {e}")


async def delete_file(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"File not found: {path}")
    if not request_permission("delete_file", str(p)):
        return denied("delete_file")
    try:
        if p.is_dir():
            import shutil
            await _run(shutil.rmtree, p)
        else:
            p.unlink()
        return ok(f"Deleted {p.name}, sir.")
    except Exception as e:
        return fail(f"Delete error: {e}")


# ── System control ────────────────────────────────────────────────────────────

async def get_system_info() -> dict:
    cpu   = psutil.cpu_percent(interval=0.3)
    mem   = psutil.virtual_memory()
    disk  = psutil.disk_usage("/")
    bat   = psutil.sensors_battery()
    data  = {
        "cpu_percent":      cpu,
        "memory_percent":   mem.percent,
        "memory_used_gb":   round(mem.used  / 1e9, 2),
        "memory_total_gb":  round(mem.total / 1e9, 2),
        "disk_percent":     disk.percent,
        "disk_free_gb":     round(disk.free  / 1e9, 2),
        "battery_percent":  bat.percent       if bat else None,
        "plugged_in":       bat.power_plugged if bat else None,
    }
    bat_str = f" · Battery {bat.percent}%{'⚡' if bat.power_plugged else ''}" if bat else ""
    summary = f"CPU {cpu}% · RAM {mem.percent}% · Disk {disk.percent}%{bat_str}"
    return ok(summary, data=data)


async def set_volume(level: int) -> dict:
    level = max(0, min(100, level))
    try:
        # Lightest approach: nircmd (if installed) or PowerShell
        script = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"$v = {level}; "
            f"Add-Type -TypeDefinition '"
            f"using System.Runtime.InteropServices; "
            f"public class Vol {{ [DllImport(\"user32.dll\")] public static extern void keybd_event(byte b,byte s,int f,int e); }}"
            f"'; "
        )
        # Simpler: use nircmd if available, else PowerShell audio API
        cmd = f'powershell -c "& {{Add-Type -Name Vol -Namespace _ -MemberDefinition \'[DllImport(\\\"winmm.dll\\\")]public static extern int waveOutSetVolume(IntPtr h,uint v);\';$v={level}/100.0;$i=[uint32]($v*0xFFFF);$_::Vol::waveOutSetVolume([IntPtr]::Zero,$i*65537)}}"'
        await _run(subprocess.run, cmd, shell=True, capture_output=True, timeout=5)
        return ok(f"Volume set to {level}%, sir.")
    except Exception as e:
        return fail(f"Volume error: {e}")


async def set_brightness(level: int) -> dict:
    level = max(0, min(100, level))
    try:
        cmd = (
            f'powershell -c "(Get-WmiObject -Namespace root/WMI '
            f'-Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"'
        )
        await _run(subprocess.run, cmd, shell=True, capture_output=True, timeout=5)
        return ok(f"Brightness set to {level}%, sir.")
    except Exception as e:
        return fail(f"Brightness error: {e}")


async def shutdown_pc(delay: int = 10) -> dict:
    if not request_permission("shutdown", f"Shutting down in {delay} seconds."):
        return denied("shutdown")
    await _run(subprocess.run, f"shutdown /s /t {delay}", shell=True)
    return ok(f"Shutdown in {delay}s, sir. Goodbye.")


async def restart_pc(delay: int = 10) -> dict:
    if not request_permission("restart", f"Restarting in {delay} seconds."):
        return denied("restart")
    await _run(subprocess.run, f"shutdown /r /t {delay}", shell=True)
    return ok(f"Restarting in {delay}s, sir.")


async def sleep_pc() -> dict:
    if not request_permission("sleep", "System will enter sleep mode."):
        return denied("sleep")
    await _run(subprocess.run, "rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
    return ok("Goodnight, sir.")


async def lock_screen() -> dict:
    if not request_permission("lock_screen", "Screen will be locked."):
        return denied("lock_screen")
    await _run(subprocess.run, "rundll32.exe user32.dll,LockWorkStation", shell=True)
    return ok("Screen locked, sir.")


async def take_screenshot(save_path: str = None) -> dict:
    if not save_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = str(Path.home() / f"Desktop/joi_{ts}.png")
    try:
        import pyautogui
        img = await _run(pyautogui.screenshot)
        img.save(save_path)
        return ok(f"Screenshot saved to Desktop, sir.", data=save_path)
    except Exception as e:
        return fail(f"Screenshot error: {e}")


async def get_clipboard() -> dict:
    try:
        import pyperclip
        return ok("Clipboard retrieved.", data=pyperclip.paste())
    except Exception as e:
        return fail(f"Clipboard error: {e}")


async def set_clipboard(text: str) -> dict:
    try:
        import pyperclip
        pyperclip.copy(text)
        return ok("Copied to clipboard, sir.")
    except Exception as e:
        return fail(f"Clipboard error: {e}")


# ── Browser ───────────────────────────────────────────────────────────────────

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

def _find_chrome() -> str | None:
    for p in CHROME_PATHS:
        if Path(p).exists():
            return p
    return None


async def open_url(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    chrome = _find_chrome()
    try:
        if chrome:
            # Open in Chrome as a new tab
            await _run(subprocess.Popen, [chrome, url])
        else:
            # Fallback to system default browser
            await _run(webbrowser.open_new_tab, url)
        return ok(f"Opened {url} in Chrome, sir.")
    except Exception as e:
        return fail(f"Browser error: {e}")


async def search_web(query: str) -> dict:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return await open_url(url)


async def open_youtube(query: str) -> dict:
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    return await open_url(url)


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_MAP = {
    "open_app":       open_app,
    "close_app":      close_app,
    "list_apps":      list_running_apps,
    "read_file":      read_file,
    "write_file":     write_file,
    "list_directory": list_directory,
    "find_file":      find_file,
    "open_file":      open_file,
    "delete_file":    delete_file,
    "system_info":    get_system_info,
    "set_volume":     set_volume,
    "set_brightness": set_brightness,
    "shutdown":       shutdown_pc,
    "restart":        restart_pc,
    "sleep":          sleep_pc,
    "lock_screen":    lock_screen,
    "screenshot":     take_screenshot,
    "get_clipboard":  get_clipboard,
    "set_clipboard":  set_clipboard,
    "open_url":       open_url,
    "search_web":     search_web,
    "open_youtube":   open_youtube,
}

# Which tools are risky (for the LLM's awareness)
RISKY_TOOLS = {"delete_file", "write_file", "shutdown", "restart", "sleep", "lock_screen"}

# Tool schemas for the LLM to understand what's available
TOOL_SCHEMAS = [
    {"name": "open_app",       "desc": "Open an application by name",                       "params": {"app_name": "str"}},
    {"name": "close_app",      "desc": "Close/kill a running application by name",           "params": {"app_name": "str"}},
    {"name": "list_apps",      "desc": "List all currently running processes",               "params": {}},
    {"name": "read_file",      "desc": "Read and return contents of a file",                 "params": {"path": "str"}},
    {"name": "write_file",     "desc": "Write content to a file (requires permission)",      "params": {"path": "str", "content": "str"}},
    {"name": "list_directory", "desc": "List files and folders in a directory",              "params": {"path": "str"}},
    {"name": "find_file",      "desc": "Search for a file by name",                          "params": {"filename": "str", "search_path": "str (optional)"}},
    {"name": "open_file",      "desc": "Open a file with its default application",           "params": {"path": "str"}},
    {"name": "delete_file",    "desc": "Delete a file or folder (requires permission)",      "params": {"path": "str"}},
    {"name": "system_info",    "desc": "Get CPU, RAM, disk, battery status",                 "params": {}},
    {"name": "set_volume",     "desc": "Set system volume (0-100)",                          "params": {"level": "int"}},
    {"name": "set_brightness", "desc": "Set screen brightness (0-100)",                      "params": {"level": "int"}},
    {"name": "shutdown",       "desc": "Shut down the computer (requires permission)",       "params": {"delay": "int (seconds, default 10)"}},
    {"name": "restart",        "desc": "Restart the computer (requires permission)",         "params": {"delay": "int (seconds, default 10)"}},
    {"name": "sleep",          "desc": "Put computer to sleep (requires permission)",        "params": {}},
    {"name": "lock_screen",    "desc": "Lock the screen (requires permission)",              "params": {}},
    {"name": "screenshot",     "desc": "Take a screenshot and save to Desktop",              "params": {"save_path": "str (optional)"}},
    {"name": "get_clipboard",  "desc": "Read current clipboard content",                     "params": {}},
    {"name": "set_clipboard",  "desc": "Copy text to clipboard",                             "params": {"text": "str"}},
    {"name": "open_url",       "desc": "Open a URL in the default browser",                  "params": {"url": "str"}},
    {"name": "search_web",     "desc": "Google search and open results in browser",          "params": {"query": "str"}},
    {"name": "open_youtube",   "desc": "Search YouTube and open results in browser",         "params": {"query": "str"}},
]


async def execute_tool(tool_name: str, **kwargs) -> dict:
    func = TOOL_MAP.get(tool_name)
    if not func:
        return fail(f"Unknown tool: '{tool_name}'. Available: {list(TOOL_MAP.keys())}")
    try:
        return await func(**kwargs)
    except TypeError as e:
        return fail(f"Wrong parameters for '{tool_name}': {e}")
    except Exception as e:
<<<<<<< HEAD
        return fail(f"Tool error: {e}")
=======
        return fail(f"Tool error: {e}")
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
