"""
JOI Permission System
Risky actions (delete, shutdown, restart, sleep, lock) require confirmation.
Safe actions (open app, read file, volume, etc.) are auto-approved.
Uses tkinter — zero extra dependencies, built into Python.
"""

import tkinter as tk
from tkinter import ttk
import threading

# Actions that require explicit user confirmation
RISKY_ACTIONS = {
    "delete_file",
    "shutdown",
    "restart",
    "sleep",
    "lock_screen",
    "write_file",   # writing can overwrite — ask once
}

# Human-readable descriptions for the popup
ACTION_DESCRIPTIONS = {
    "delete_file":  ("🗑️  Delete File",      "JOI wants to permanently delete a file."),
    "shutdown":     ("⚠️  Shutdown",          "JOI wants to shut down your computer."),
    "restart":      ("🔄  Restart",           "JOI wants to restart your computer."),
    "sleep":        ("💤  Sleep",             "JOI wants to put your computer to sleep."),
    "lock_screen":  ("🔒  Lock Screen",       "JOI wants to lock your screen."),
    "write_file":   ("📝  Write File",        "JOI wants to create or overwrite a file."),
}


def _show_dialog(action: str, detail: str, result_holder: list):
    """Run the permission dialog on the main thread."""
    root = tk.Tk()
    root.withdraw()

    win = tk.Toplevel(root)
    win.title("JOI — Permission Required")
    win.geometry("420x220")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.configure(bg="#03070f")

    # Center on screen
    win.update_idletasks()
    x = (win.winfo_screenwidth() - 420) // 2
    y = (win.winfo_screenheight() - 220) // 2
    win.geometry(f"+{x}+{y}")

    title_text, desc_text = ACTION_DESCRIPTIONS.get(
        action, ("⚙️  Action Required", f"JOI wants to perform: {action}")
    )

    # Title
    tk.Label(
        win, text=title_text,
        font=("Courier New", 13, "bold"),
        fg="#00c8ff", bg="#03070f"
    ).pack(pady=(18, 4))

    # Description
    tk.Label(
        win, text=desc_text,
        font=("Courier New", 9),
        fg="#c8dff0", bg="#03070f"
    ).pack(pady=2)

    # Detail (path, params etc.)
    if detail:
        tk.Label(
            win, text=detail,
            font=("Courier New", 8),
            fg="#4a6a8a", bg="#03070f",
            wraplength=380
        ).pack(pady=4)

    # Separator
    tk.Frame(win, height=1, bg="#0e2a4a").pack(fill="x", padx=20, pady=8)

    # Buttons
    btn_frame = tk.Frame(win, bg="#03070f")
    btn_frame.pack()

    def approve():
        result_holder.append(True)
        win.destroy()
        root.destroy()

    def deny():
        result_holder.append(False)
        win.destroy()
        root.destroy()

    tk.Button(
        btn_frame, text="  ALLOW  ",
        font=("Courier New", 9, "bold"),
        fg="#03070f", bg="#00c8ff",
        relief="flat", cursor="hand2",
        command=approve, padx=10
    ).pack(side="left", padx=12)

    tk.Button(
        btn_frame, text="  DENY  ",
        font=("Courier New", 9, "bold"),
        fg="#c8dff0", bg="#0e2a4a",
        relief="flat", cursor="hand2",
        command=deny, padx=10
    ).pack(side="left", padx=12)

    # Auto-deny after 30 seconds
    def auto_deny():
        result_holder.append(False)
        try:
            win.destroy()
            root.destroy()
        except Exception:
            pass

    win.after(30000, auto_deny)
    win.protocol("WM_DELETE_WINDOW", deny)
    root.mainloop()


def request_permission(action: str, detail: str = "") -> bool:
    """
    Returns True if user approves, False if denied.
    Safe actions return True immediately without a dialog.
    """
    if action not in RISKY_ACTIONS:
        return True  # auto-approve

    result_holder = []
    t = threading.Thread(target=_show_dialog, args=(action, detail, result_holder), daemon=True)
    t.start()
    t.join(timeout=35)

    return bool(result_holder and result_holder[0])
