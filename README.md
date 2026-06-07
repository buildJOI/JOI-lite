# JOI-Lite — Justified Operative Interface

[![Status](https://img.shields.io/badge/status-active_development-blue)]()
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

**A voice-enabled, memory-driven AI companion with adaptive personality, live emotion expression, and a modern React frontend.**

---

## Overview

JOI-Lite is an advanced AI assistant that combines conversational intelligence, persistent semantic memory, and voice interaction into a unified system. Unlike traditional chatbots, JOI is designed to simulate continuity, emotional awareness, and adaptive behavior across sessions.

The system consists of two independent parts that run side by side:

- **Backend** — FastAPI server (`server.py`) handling AI, memory, voice, and tool use
- **Frontend** — React + TanStack Router app with JOI's animated mascot, emotion reactions, and chat UI

---

## What's New in This Version

- React + TypeScript frontend replacing the old single-file HTML UI
- JOI's face reacts in real time to backend-tagged emotions
- Scrollable conversation history panel (clock button)
- Mood selector — switch JOI's personality mid-conversation
- ElevenLabs voice playback via Web Audio API
- Semantic memory using FAISS + sentence-transformers
- CORS configured for local dev and production
- Full Python 3.13 and 3.14 compatibility notes

---

## Project Structure

```
JOI-lite-v2/
│
├── server.py               ← FastAPI backend (main entry point)
├── model_handler.py        ← Groq LLM + emotion tagging
├── voice_handler.py        ← ElevenLabs TTS
├── voice_input.py          ← Microphone / speech recognition (desktop only)
├── memory.py               ← FAISS semantic memory
├── config.py               ← Moods, personality prompts, constants
├── desktop_agent.py        ← OS-level tool use (desktop agent)
├── tool_websearch.py       ← Web search tool
├── permission.py           ← Tool permission layer
├── tray_app.py             ← System tray launcher
├── app.py                  ← Alt entry point
├── requirements.txt        ← Backend Python dependencies
├── .env                    ← API keys (create this yourself)
│
├── frontend/               ← React frontend
│   ├── src/
│   │   ├── routes/
│   │   │   ├── chat.tsx    ← Main chat page (JOI mascot + messages)
│   │   │   └── index.tsx   ← Landing page
│   │   ├── components/
│   │   │   ├── joi/        ← Animated mascot, emotion effects, sparkles
│   │   │   └── ui/         ← shadcn/ui component library
│   │   ├── lib/
│   │   │   ├── api/joi.ts  ← Backend API client (sendChat, fetchMoods, playAudio)
│   │   │   └── voice.ts    ← Browser voice capture
│   │   └── styles.css
│   ├── .env                ← VITE_API_URL (created during setup)
│   ├── vite.config.ts
│   └── package.json
│
└── JOI-app/                ← PyQt6 desktop app (separate, optional)
    ├── joi_app.py
    ├── voice_handler.py
    └── requirements.txt
```

---

## Prerequisites

| Tool | Minimum version | Check |
|---|---|---|
| Python | 3.13 or 3.14 | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | any | `git --version` |

You will also need API keys for:

| Service | Required | Purpose |
|---|---|---|
| [Groq](https://console.groq.com) | **Yes** | LLM responses |
| [ElevenLabs](https://elevenlabs.io) | No | Voice audio |
| [Serper](https://serper.dev) | No | Web search tool |

---

## 1 — Environment Setup

Create a `.env` file in the `JOI-lite-v2/` root folder (same folder as `server.py`):

```
GROQ_API_KEY=your_groq_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
SERPER_API_KEY=your_serper_key_here
```

Leave `ELEVENLABS_API_KEY` and `SERPER_API_KEY` blank or remove them if you don't have those keys — JOI will still work, just without voice audio and web search.

---

## 2 — Backend Setup

Open a terminal and navigate to the project root:

```bash
cd JOI-lite-v2
```

### Python 3.13

```bash
# Fix markdown fences left in source files (run once)
py -3.13 fix.py

# Install dependencies
py -3.13 -m pip install -r requirements.txt

# PyAudio requires PortAudio — skip it for the web frontend
# Open requirements.txt and comment out: # pyaudio>=0.2.14
# Then re-run the install above

# Start the backend
py -3.13 -m uvicorn server:app --reload --port 8000
```

### Python 3.14

PyAudio has no prebuilt wheel for Python 3.14 yet. Comment it out in `requirements.txt` before installing.

```bash
# Fix markdown fences left in source files (run once)
py -3.14 fix.py

# Comment out pyaudio in requirements.txt first, then:
py -3.14 -m pip install -r requirements.txt

# faiss-cpu may also fail on 3.14 — install separately if needed:
py -3.14 -m pip install faiss-cpu --pre

# Start the backend
py -3.14 -m uvicorn server:app --reload --port 8000
```

### Verify backend is running

Open these URLs in your browser — both should return JSON:

```
http://localhost:8000/health   →  {"status": "ok"}
http://localhost:8000/moods    →  {"moods": [...], "default": "default"}
```

---

## 3 — Frontend Setup

Open a **second terminal**:

```bash
cd JOI-lite-v2/frontend
```

The frontend works with any Node.js 18+ and does not depend on which Python version you are using.

```bash
# Install dependencies
npm install --legacy-peer-deps

# Start the dev server
npm run dev
```

You should see:

```
  ➜  Local:   http://localhost:3000/
```

Open `http://localhost:3000` in your browser. Navigate to `/chat` to talk to JOI.

---

## 4 — Running Both Together (Quick Reference)

### Terminal 1 — Backend

**Python 3.13:**
```bash
cd JOI-lite-v2
py -3.13 -m uvicorn server:app --reload --port 8000
```

**Python 3.14:**
```bash
cd JOI-lite-v2
py -3.14 -m uvicorn server:app --reload --port 8000
```

### Terminal 2 — Frontend

```bash
cd JOI-lite-v2/frontend
npm run dev
```

Then open: **`http://localhost:3000/chat`**

---

## 5 — Using JOI

| Action | How |
|---|---|
| Send a text message | Click the keyboard icon (bottom right) → type → Enter |
| Switch JOI's mood | Click the ⚙ settings icon (top right) → choose a mood |
| View full chat history | Click the 🕐 clock icon (bottom left) → scrollable panel slides in |
| Voice input | Tap the microphone button — browser mic permission required |

---

## Troubleshooting

### Backend

| Error | Fix |
|---|---|
| `SyntaxError: invalid syntax` on `memory.py` or any `.py` | Run `py -3.13 fix.py` — strips leftover markdown fences from source files |
| `ModuleNotFoundError: No module named 'psutil'` | Run `py -3.13 -m pip install psutil` — use the same Python as uvicorn |
| `GROQ_API_KEY is not set` warning | Add the key to `JOI-lite-v2/.env` |
| `Failed building wheel for pyaudio` | Comment out `pyaudio` in `requirements.txt` — not needed for the web frontend |
| `faiss-cpu` fails on Python 3.14 | Try `py -3.14 -m pip install faiss-cpu --pre` or comment it out temporarily |
| `OPTIONS /chat → 400` in uvicorn logs | CORS error — open `server.py` and set `allow_origins=["*"]` for local dev |

### Frontend

| Error | Fix |
|---|---|
| `npm install` ERESOLVE conflict | Use `npm install --legacy-peer-deps` |
| Blank page / no response from JOI | Check that the backend is running on port 8000 |
| Mood picker shows nothing | Backend `/moods` unreachable — restart the backend |
| Audio does not play | Normal without `ELEVENLABS_API_KEY` — text responses still work |
| Port 3000 already in use | Vite picks the next free port automatically — use the URL it prints |

---

## Architecture

```
Browser (http://localhost:3000)
        │
        │  fetch /api/chat, /api/moods, /api/health
        ▼
Vite Dev Proxy (/api → localhost:8000)
        │
        ▼
FastAPI Backend (server.py — port 8000)
        │
        ├── model_handler.py   ← Groq API, emotion tagging, tool parsing
        ├── memory.py          ← FAISS vector store, sentence-transformers
        ├── voice_handler.py   ← ElevenLabs TTS → base64 MP3
        ├── tool_websearch.py  ← Serper web search
        └── desktop_agent.py  ← OS tool use (file, app, system control)
```

---

## Roadmap

### Phase 1 — Current
- Conversational AI with contextual awareness
- Persistent semantic memory (FAISS)
- Emotion-driven face reactions
- Mood / personality switching
- Voice input and ElevenLabs TTS
- Modern React frontend

### Phase 2 — Desktop Integration
- Full PyQt6 desktop app (JOI-app/)
- Operating system interaction
- Application control and automation
- File system navigation via AI

### Phase 3 — Hardware Integration
- IoT device control
- Microcontroller support (Arduino, Raspberry Pi)
- Sensor-driven contextual responses

### Phase 4 — Advanced AI
- Local model execution (Ollama, Hugging Face)
- Multimodal processing (text, voice, vision)
- Emotion detection from speech tone

### Phase 5 — Embodied Interface
- Enhanced 3D avatar
- Real-time facial expression rendering
- Gesture-based interaction
- AR/VR compatibility

### Phase 6 — Experimental
- Projection-based visualization
- Spatial interaction environments
- Holographic presence research

---

## Design Philosophy

JOI-Lite is built on three core principles:

1. **Continuity** — The system remembers and evolves with the user across sessions
2. **Adaptability** — Behavior adjusts dynamically to context, tone, and mood
3. **Extensibility** — The architecture supports expansion beyond software into physical and immersive systems

---

## Security

- Never commit `.env` or API keys to version control
- The `.gitignore` should include `.env`, `memory.json`, `memory.index`
- Set `allow_origins` to your specific frontend domain before deploying to production — do not leave `["*"]` in production

---

## Contributing

Contributions are currently limited to maintain architectural consistency. You may:

- Open issues
- Suggest features
- Report bugs

---

## License

MIT License

---

## Author

**Jithin Jeevan**
BCA Student — Artificial Intelligence and Systems Development

---

*JOI-Lite is not a chatbot. It is an early-stage system exploring the transition from conversational AI → persistent intelligence → interactive systems → digital companions.*
