# JOI — Justified Operative Interface

A JARVIS-style, Blade Runner 2049 (JOI) inspired AI companion that runs on your own PC.
It chats with you in a browser UI, talks back, and can act on your computer: open apps,
search YouTube and Wikipedia in Chrome, read windows, use the camera, microphone, sensors
and USB devices. Every sensitive action asks your permission first, by chat or by voice.

## Features

- **Chat UI** (React + TanStack Start) with the JOI mascot and nine personality modes.
- **Desktop control**: open apps and URLs, search Google/Bing/DuckDuckGo, YouTube and Wikipedia
  (opens Chrome), list and focus windows, keyboard and mouse, clipboard, processes, files, power.
- **Permission gate**: camera, microphone, screenshots, sensors, window monitoring, USB, shell,
  file changes, closing programs and power actions all ask first. Replies: `allow`, `allow for this session`, `deny`.
- **Voice**: JOI's cloud voice via ElevenLabs (optional) and a microphone mode where you say "JOI, ..."
- **Audit log**: every tool run is recorded in `~/.joi/audit.log` (argument names only, never content).
- **Web search** (optional, Serper).

## Quick start

You need **Python 3.10+** and **Node.js 18+**.

```bash
git clone <your-repo-url> JOI
cd JOI
cp .env.example .env      # Windows: copy .env.example .env
# open .env and paste your GROQ_API_KEY (free at https://console.groq.com)

python run.py             # Windows, macOS or Linux
```

`python run.py` installs what is missing on the first run, starts the backend and the frontend,
waits until both are ready, and opens http://127.0.0.1:5173. Press **Ctrl+C** to stop everything.

Windows shortcut: double-click `start.bat`. macOS/Linux: `./start.sh`.

## Configuration (`.env`)

One file controls everything. Only the first key is required for chat.

| Variable | Required | What it does |
|---|---|---|
| `GROQ_API_KEY` | yes, for chat | The AI brain (Groq, Llama 3.3 70B). Free tier available. |
| `ELEVENLABS_API_KEY` | no | JOI speaks with an ElevenLabs voice in the browser. Without it, replies are text only. |
| `ELEVENLABS_VOICE_ID` | no | Which ElevenLabs voice to use. |
| `SERPER_API_KEY` | no | Enables the web search tool. |
| `JOI_VOICE` | no | `1` turns on microphone voice mode (say "JOI, ..."). Needs the optional packages. |
| `GROQ_MODEL` | no | Override the model name. |
| `JOI_PORT` | no | Backend port (default 8000). |
| `JOI_FRONTEND_PORT` | no | Frontend port (default 5173). |

`run.py` prints a warning instead of failing when a key is missing, so the app always starts.
Chat tells you what's missing.

## Optional features

The core install is enough for chat and desktop control. Camera, microphone recording, USB serial,
raw USB and microphone voice mode need extra packages:

```bash
pip install -r backend/requirements-optional.txt
```

`run.py` reports which optional features are off at startup.

- **Raw USB** (`pyusb`) needs libusb. On Windows, some devices need the WinUSB driver (Zadig).
- **Microphone recording** needs PortAudio (included in the Windows wheel).

## Permission model

| Runs without asking | Asks first |
|---|---|
| Open apps and URLs, YouTube, web and Wikipedia search, list and focus windows, system stats, read and list files, web search, USB name scan | Camera, microphone, screenshots, sensors, window-switch logging, clipboard, USB device access, keyboard and mouse, shell commands, file write and delete, closing programs, power actions |

- **Allow** runs the action once. **Allow for this session** remembers it until restart. Shell and power
  actions can never be granted for a whole session.
- Requests from voice and chat share the same rules.

Example: "JOI, take a photo" → "I need your permission to use your camera… Say allow, deny, or allow for this session."

## Example commands

- "Open YouTube and search for lo-fi jazz on Chrome"
- "Search Wikipedia for Blade Runner 2049 on Chrome"
- "What's my CPU and battery status?"
- "List the USB devices connected"
- "Take a photo" (asks permission)
- "Read the files on E:" (USB drive; asks permission)

## Project structure

```
JOI/
├── run.py                    one-command launcher (backend + frontend)
├── start.bat / start.sh      double-click / shell wrappers for run.py
├── .env.example              every setting, documented
├── backend/                  FastAPI backend: the brain and the PC control
│   ├── server.py             HTTP API (/api/chat, /api/moods, /api/permissions, ...)
│   ├── agent.py              Groq LLM loop, tool calling, permission replies
│   ├── tools.py              all tools (PC, browser, camera, mic, sensors, USB, files)
│   ├── permissions.py        permission gate and audit log
│   ├── voice.py              optional microphone voice loop
│   ├── tts.py                ElevenLabs cloud voice
│   ├── config.py             settings, read from .env
│   ├── requirements.txt      core packages
│   └── requirements-optional.txt
├── frontend/                 React UI (TanStack Start + Vite), dev server proxies /api
└── legacy/desktop-pyqt/      the original PyQt6 desktop app (not started by run.py)
```

## Architecture

```
Browser (React UI, :5173)
   │  /api/*  (Vite dev proxy)
   ▼
FastAPI backend (127.0.0.1:8000)
   ├── agent.py ── Groq LLM ── tool calls ──► tools.py ──► your PC
   │      │                                     ▲
   │      └── permission_required ──► permissions.py (ask → allow/deny)
   ├── tts.py ── ElevenLabs (optional voice)
   └── voice.py ── microphone loop (optional, JOI_VOICE=1)
```

## Security

- The backend listens on **127.0.0.1 only**. It is not reachable from your network.
- Requests from web origins other than the frontend are rejected (HTTP 403), so a random website cannot
  drive your PC through your browser.
- Sensitive tools cannot run without your approval. Everything is recorded in `~/.joi/audit.log`.
- Keys live only in `.env`, which is git-ignored. Never commit it.
- `pyautogui` failsafe: slam the mouse into a screen corner to abort keyboard/mouse control.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "GROQ_API_KEY is empty" warning, chat says it can't reach the model | Add the key to `.env` and restart. |
| "Port 8000 / 5173 is already in use" | Stop the other program or set `JOI_PORT` / `JOI_FRONTEND_PORT` in `.env`. |
| "Node.js (npm) was not found" | Install Node 18+ from https://nodejs.org and run again. |
| `npm install` fails | Delete `frontend/node_modules` and run `python run.py` again. The project already sets `legacy-peer-deps` in `frontend/.npmrc`. |
| Camera or USB tools say the feature is off | Install `backend/requirements-optional.txt`. |
| Window monitor / power / window list do nothing | These are Windows-only. |

## Notes and limits

- Window monitoring, power control and window listing are Windows-only.
- Sensors: only what the OS exposes (battery, CPU frequency, and temperature/fan sensors where available).
  Ambient light, accelerometer and GPS need device-specific drivers.
- Arbitrary USB devices need a driver (WinUSB via Zadig) before raw access works. Drives and serial ports work directly.
- The legacy PyQt app and the older web memory/mood engines are kept for reference only. They are not started
  by `run.py`.

## License

Personal project. Add a license before you publish it.
