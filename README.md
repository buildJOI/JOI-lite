# JOI: Justified Operative Interface

JOI is a personal AI companion for your Windows PC, inspired by the character from *Blade Runner 2049*. She chats with you in a desktop window, listens when you speak, answers out loud, and can act on your computer: open apps, search the web in Chrome, read windows, and work with the camera, microphone, sensors, and USB devices. Anything sensitive asks your permission first.

## Features

- **Desktop app window** built with pywebview (falls back to your browser if WebView2 isn't available).
- **Chat and voice in one place.** Typed messages and spoken commands appear in the same conversation.
- **Hands-free voice.** Say "JOI" and your request. For 45 seconds after she answers, you can keep talking without the name.
- **PC control:** open applications and URLs, search Google, Bing, DuckDuckGo, YouTube and Wikipedia in Chrome, list and focus windows, control the keyboard, mouse and clipboard, manage processes and files, and shut down, restart, sleep or lock the PC.
- **Permission system.** Camera, microphone, screenshots, sensors, window monitoring, USB, shell commands, file changes, closing programs and power actions ask first. Reply naturally ("yes", "sure", "go ahead", "no thanks"). A yes covers that kind of action for the session. Power actions always ask.
- **Audit log.** Every tool run is recorded in `~/.joi/audit.log`, with argument names only.
- **Nine personality modes**, from playful to analytical.
- **Optional cloud voice** through ElevenLabs.
- **Optional web search** through Serper.
- **Wake listener** (`wake.py`) starts the whole app when you say "JOI wake up".

## Requirements

- Windows 10 or 11
- Python 3.10 or newer (3.12 or 3.14 both work)
- Node.js 18 or newer
- A free Groq API key from https://console.groq.com
- Microsoft Edge WebView2 Runtime (already installed on most Windows 10 and 11 machines)
- Optional: a microphone for voice mode

## Quick start

```bat
git clone https://github.com/buildJOI/JOI-lite.git
cd JOI-lite
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
copy .env.example .env
```

Open `.env` and set `GROQ_API_KEY`. Then start JOI:

```bat
python run.py
```

The first start installs the frontend packages and can take several minutes. JOI's window opens when the interface is ready. Closing the window stops everything.

To use the optional features, install them too:

```bat
pip install -r backend\requirements-optional.txt
```

## Configuration

Every setting lives in `.env`. Only `GROQ_API_KEY` is required.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | (empty) | Language model (required for chat) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model name. Check Groq's model list if it's retired. |
| `ELEVENLABS_API_KEY` | (empty) | Natural voice for replies in the browser |
| `ELEVENLABS_VOICE_ID` | `EXAVITQu4vr4xnSDxMaL` | Which ElevenLabs voice to use |
| `SERPER_API_KEY` | (empty) | Enables the `web_search` tool |
| `JOI_VOICE` | `0` | `1` turns on the microphone conversation |
| `JOI_PORT` | `8000` | Backend port |
| `JOI_FRONTEND_PORT` | `5173` | Interface port |

## Using JOI

**Typing:** type in the chat box as usual.

**Voice:** set `JOI_VOICE=1`. JOI tells you in the chat when the microphone is listening. Every phrase you say appears in the chat, so you can confirm she heard you.

**Example requests:**
- "JOI, open YouTube and search for lo-fi jazz."
- "Search Wikipedia for Blade Runner 2049 in Chrome."
- "What's my CPU and battery status?"
- "List the USB devices connected to this PC."
- "Take a photo." (JOI asks first.)

**Wake listener:** run `python wake.py` in a separate window. Say "JOI wake up" to start the whole app. Requires the optional packages.

## Permissions

| Runs without asking | Asks first |
|---|---|
| Open apps and URLs, web, YouTube and Wikipedia search, list and focus windows, system stats, read and list files, USB name scan | Camera, microphone, screenshots, sensors, window-switch logging, clipboard, USB device access, keyboard and mouse, shell commands, file changes, closing programs, power actions |

"Yes" allows that action for the session. "Just once" allows it one time. Power actions always ask.

## Project structure

```
JOI-lite/
├── run.py                  one-command launcher: backend, frontend, app window
├── wake.py                 optional "JOI wake up" listener
├── start.bat / start.sh    double-click or shell wrappers for run.py
├── .env.example            every setting, documented
├── backend/                FastAPI backend: the brain and PC control
│   ├── server.py           HTTP API (/api/chat, /api/voice/feed, /api/permissions, ...)
│   ├── agent.py            language model loop, tool calls, permission replies
│   ├── tools.py            all tools (PC, browser, camera, microphone, sensors, USB, files)
│   ├── permissions.py      permission gate and audit log
│   ├── voice.py            microphone conversation loop
│   ├── mic.py              recording until you stop speaking, plus transcription
│   ├── tts.py              ElevenLabs and local voice output
│   └── config.py           settings read from .env
├── frontend/               React interface (TanStack Start + Vite)
└── legacy/                 earlier PyQt desktop app, kept for reference (not started by run.py)
```

## How it works

```
JOI window (pywebview)  ──►  React interface (Vite, port 5173)
                                  │  /api/* (dev proxy)
                                  ▼
                       FastAPI backend (127.0.0.1:8000)
                        ├── agent.py ──► Groq language model
                        │      └──► tools.py ──► your PC
                        │             └── permission_required ──► permissions.py
                        ├── voice.py ──► mic.py ──► speech-to-text
                        │      └──► voice feed ──► chat
                        └── tts.py ──► ElevenLabs (optional)
```

## Security

- The backend listens on `127.0.0.1` only. Other devices on your network can't reach it.
- Requests from web pages other than the JOI interface are rejected, so a website you visit can't control your PC.
- Sensitive actions need your approval, and every action is written to `~/.joi/audit.log`.
- Secrets live only in `.env`, which is excluded from version control.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Chat says "Groq 429" | You've reached Groq's usage limit. Wait for it to reset, or set `GROQ_MODEL` to another model. |
| Chat says "model does not exist" | Groq retired the model. Set `GROQ_MODEL` to a current model name. |
| The app window doesn't open | Install or repair the Microsoft Edge WebView2 Runtime. JOI opens in your browser in the meantime. |
| "Port 5173 / 8000 is already in use" | Another JOI session is still running. Close it, or change the port in `.env`. |
| Microphone doesn't respond | Check the first messages in the chat. They report whether the microphone is listening, off, or failing. |
| `pyaudio` fails to install | You don't need it. JOI uses `sounddevice` instead. |
| Vite takes several minutes to start | Normal on the first run on Windows. Adding the project folder to your antivirus exclusions speeds it up. |

## Legacy code

The `legacy/` folder holds the earlier PyQt6 desktop app. It's kept for reference and isn't started by `run.py`.

## License

Personal project. Add a license before you publish it.
