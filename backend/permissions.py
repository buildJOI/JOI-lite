"""
Permission gate for risky capabilities.

Sensitive tools declare a category (camera, usb, shell, ...). If the category
has not been granted, the tool is NOT executed. Instead the agent asks the
user by voice or chat ("allow", "deny", "allow for this session") and only
then runs the tool. Every tool execution is written to an audit log.
"""
import json
import threading
from datetime import datetime

from config import AUDIT_LOG

CATEGORY_TEXT = {
    "camera": "use your camera",
    "microphone": "record audio from your microphone",
    "sensors": "read your PC's hardware sensors",
    "window_monitor": "watch which windows you switch between",
    "screenshot": "capture your screen",
    "clipboard": "read your clipboard",
    "usb": "access a USB device",
    "keyboard_mouse": "control your keyboard and mouse",
    "shell": "run a command on your PC",
    "files_write": "create, change or delete files",
    "processes": "close a running program",
    "power": "shut down, restart, sleep or lock your PC",
}

# These are never granted for a whole session; they always ask.
NO_SESSION = {"power"}


class PermissionGate:
    def __init__(self):
        self._granted: set[str] = set()
        self._lock = threading.Lock()

    def is_allowed(self, category: str) -> bool:
        with self._lock:
            return category in self._granted

    def grant_session(self, category: str) -> bool:
        if category in NO_SESSION:
            return False
        with self._lock:
            self._granted.add(category)
        self.audit({"event": "grant_session", "category": category})
        return True

    def revoke_all(self):
        with self._lock:
            self._granted.clear()
        self.audit({"event": "revoke_all"})

    def granted(self) -> list[str]:
        with self._lock:
            return sorted(self._granted)

    def audit(self, entry: dict):
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {"time": datetime.now().isoformat(timespec="seconds"), **entry}
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")


gate = PermissionGate()
