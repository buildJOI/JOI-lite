"""
JOI — Justified Operative Interface
PyQt6 Desktop App — Human-like interaction

Features:
- Streaming LLM responses (words appear as generated)
- Voice output starts speaking WHILE text is still streaming
- Voice input: Ctrl+Shift+Space (push-to-talk) or mic button
- Interrupt: press Ctrl+Shift+Space or mic button while JOI is speaking to cut her off
- Tool execution with live feedback
- Floating HUD overlay
"""

import sys, os, json, re, threading, asyncio, queue, time
from pathlib import Path
from datetime import datetime

# ── PyQt6 ─────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QScrollArea, QFrame,
    QSystemTrayIcon, QMenu, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QThread, QObject, pyqtSignal, QTimer, QRect,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QColor, QFont, QPixmap, QPainter, QPen, QBrush,
    QIcon, QKeySequence, QShortcut, QGuiApplication,
)

# ── JOI backend ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_MOODS, DEFAULT_MOOD, GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL
from model_handler import _build_system_prompt, parse_tool_call, strip_tool_call
from desktop_agent import execute_tool
from tool_websearch import web_search
<<<<<<< HEAD
=======
from voice_handler import generate_joi_audio
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)

# ── Colours ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#03070f", "panel":   "#070d1a", "border":  "#0e2a4a",
    "accent":  "#00c8ff", "accent2": "#ff6aff", "green":   "#00ff88",
    "amber":   "#ffb700", "red":     "#ff4444", "text":    "#c8dff0",
    "dim":     "#4a6a8a", "joi_msg": "#021828", "user_msg":"#0d1220",
}

# ═══════════════════════════════════════════════════════════════════════════════
# VOICE OUTPUT — speaks sentences as they arrive, interruptible
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceOutput:
    """
    Streams TTS sentence-by-sentence using pyttsx3 (offline, zero latency).
    Falls back to ElevenLabs if configured.
    Runs on its own thread so UI never blocks.
    """
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._speaking = False
        self._engine = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _init_engine(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 165)     # slightly slower = clearer
            engine.setProperty('volume', 0.95)
            # Pick a female voice if available
            voices = engine.getProperty('voices')
            for v in voices:
                if 'female' in v.name.lower() or 'zira' in v.name.lower() or 'hazel' in v.name.lower():
                    engine.setProperty('voice', v.id)
                    break
            return engine
        except Exception as e:
            print(f"[Voice] pyttsx3 init failed: {e}")
            return None

    def _run(self):
        self._engine = self._init_engine()
        while True:
<<<<<<< HEAD
=======
            # Drain and reset when interrupted
            if self._stop_event.is_set():
                while not self._queue.empty():
                    try: self._queue.get_nowait()
                    except: pass
                self._stop_event.clear()
                self._speaking = False
                continue
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
            try:
                sentence = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if sentence is None:
                continue
<<<<<<< HEAD
            if self._stop_event.is_set():
                # Drain queue on interrupt
=======
            # Re-check after dequeue (interrupt may have arrived while blocked)
            if self._stop_event.is_set():
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
                while not self._queue.empty():
                    try: self._queue.get_nowait()
                    except: pass
                self._stop_event.clear()
<<<<<<< HEAD
=======
                self._speaking = False
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
                continue
            self._speaking = True
            self._speak_sentence(sentence)
            self._speaking = False

    def _speak_sentence(self, text: str):
<<<<<<< HEAD
        if not self._engine or not text.strip():
            return
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            print(f"[Voice] speak error: {e}")
=======
        if not text.strip():
            return
        if self._engine:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
                return
            except Exception as e:
                print(f"[Voice] pyttsx3 speak error: {e}")
        # Fallback: ElevenLabs → play via sounddevice if available
        try:
            audio_b64 = generate_joi_audio(text)
            if audio_b64:
                import base64, io
                audio_bytes = base64.b64decode(audio_b64)
                try:
                    import sounddevice as sd
                    import soundfile as sf
                    data, samplerate = sf.read(io.BytesIO(audio_bytes))
                    sd.play(data, samplerate)
                    sd.wait()
                except ImportError:
                    # sounddevice not installed — silently skip
                    pass
        except Exception as e:
            print(f"[Voice] ElevenLabs fallback error: {e}")
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)

    def speak(self, sentence: str):
        """Queue a sentence for speaking. Starts immediately."""
        self._queue.put(sentence)

    def interrupt(self):
        """Stop current speech and clear queue."""
        self._stop_event.set()
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass

    @property
    def is_speaking(self) -> bool:
        return self._speaking or not self._queue.empty()


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE INPUT — push-to-talk on background thread
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceInputThread(QThread):
    transcribed = pyqtSignal(str)
    listening   = pyqtSignal(bool)   # True = started, False = done
    error       = pyqtSignal(str)

    def run(self):
        self.listening.emit(True)
        try:
            import speech_recognition as sr
            rec = sr.Recognizer()
            rec.energy_threshold = 300
            rec.pause_threshold  = 0.7
            rec.dynamic_energy_threshold = True
            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source, duration=0.4)
                try:
                    audio = rec.listen(source, timeout=8, phrase_time_limit=15)
                except sr.WaitTimeoutError:
                    self.error.emit("No speech detected, sir.")
                    return
            text = rec.recognize_google(audio)
            self.transcribed.emit(text.strip())
        except ImportError:
            self.error.emit("SpeechRecognition not installed: pip install SpeechRecognition pyaudio")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.listening.emit(False)


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMING LLM WORKER
# Emits tokens as they arrive. Splits into sentences for voice.
# ═══════════════════════════════════════════════════════════════════════════════

class StreamWorker(QObject):
    # Emitted per token (for typewriter display)
    token_received   = pyqtSignal(str)
    # Emitted when a complete sentence is ready (for TTS)
    sentence_ready   = pyqtSignal(str)
    # Emitted when a tool call is detected
    tool_called      = pyqtSignal(str, bool, str)   # tool_name, success, message
    # Emitted when full response is done
    response_done    = pyqtSignal(str)
    error_occurred   = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self.history: list[dict] = []
        self._interrupted = False

    def submit(self, user_text: str, mood: str):
        self._interrupted = False
        asyncio.run_coroutine_threadsafe(
            self._process(user_text, mood), self._loop
        )

    def interrupt(self):
        self._interrupted = True

    def clear_history(self):
        self.history.clear()

    # ── Sentence splitter ─────────────────────────────────────────────────────
    @staticmethod
    def _split_sentences(buffer: str) -> tuple[list[str], str]:
        """
        Split buffer into complete sentences.
        Returns (complete_sentences, remainder).
        """
        pattern = r'(?<=[.!?])\s+'
        parts = re.split(pattern, buffer)
        if len(parts) <= 1:
            return [], buffer
        complete = parts[:-1]
        remainder = parts[-1]
        return complete, remainder

    # ── Main async process ────────────────────────────────────────────────────
    async def _process(self, user_text: str, mood: str):
        try:
            import httpx

            augmented = user_text
            if "search for" in user_text.lower() or user_text.lower().startswith("search:"):
                q = user_text.removeprefix("search:").strip()
                ctx = await web_search(q)
                augmented = f"{user_text}\n\n[Web context]\n{ctx}"

            messages = [{"role": "system", "content": _build_system_prompt(mood)}]
            messages.extend(self.history)
            messages.append({"role": "user", "content": augmented})

            full_reply = ""
            tool_results = []

            for _round in range(4):
                if self._interrupted:
                    break

                # ── Streaming call ────────────────────────────────────────────
                streamed_text = ""
                sentence_buffer = ""

                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream(
                        "POST",
                        f"{GROQ_BASE_URL}/v1/chat/completions",
                        json={
                            "model":       GROQ_MODEL,
                            "messages":    messages,
                            "temperature": 0.80,
                            "max_tokens":  600,
                            "stream":      True,
                        },
                        headers={
                            "Authorization": f"Bearer {GROQ_API_KEY}",
                            "Content-Type":  "application/json",
                        },
                    ) as response:
                        async for line in response.aiter_lines():
                            if self._interrupted:
                                break
                            if not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                token = chunk["choices"][0]["delta"].get("content", "")
                                if not token:
                                    continue

                                streamed_text    += token
                                sentence_buffer  += token

                                # Emit token for display
                                self.token_received.emit(token)

                                # Check if we have complete sentences to speak
                                sentences, sentence_buffer = self._split_sentences(sentence_buffer)
                                for s in sentences:
                                    clean = strip_tool_call(s).strip()
                                    if clean:
                                        self.sentence_ready.emit(clean)

                            except (json.JSONDecodeError, KeyError):
                                continue

                # Emit any remaining sentence buffer
                if sentence_buffer.strip() and not self._interrupted:
                    clean = strip_tool_call(sentence_buffer).strip()
                    if clean:
                        self.sentence_ready.emit(clean)

                # ── Tool call detection ───────────────────────────────────────
                tc = parse_tool_call(streamed_text)
                if not tc:
                    full_reply = strip_tool_call(streamed_text).strip()
                    break

                # Execute tool
                result = await execute_tool(tc["tool"], **tc["params"])
                tool_results.append({"tool": tc["tool"], "result": result})
                self.tool_called.emit(
                    tc["tool"],
                    result["success"],
                    result["message"]
                )

                # Feed result back
                messages.append({"role": "assistant", "content": streamed_text})
                tool_name = tc["tool"]
                tool_msg  = result["message"]
                data_str  = str(result.get("data", ""))[:1200]
                status    = "succeeded" if result["success"] else "failed or was denied"
                messages.append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM: Tool '{tool_name}' {status}. "
                        f"Message: {tool_msg}. Data: {data_str}. "
                        f"Now reply naturally. Do NOT emit TOOL_CALL.]"
                    )
                })
                full_reply = ""  # will be filled next round

            if not full_reply:
                full_reply = strip_tool_call(streamed_text).strip()

            # Persist
            self.history.append({"role": "user",      "content": user_text})
            self.history.append({"role": "assistant",  "content": full_reply})
            if len(self.history) > 30:
                self.history = self.history[-30:]

            self.response_done.emit(full_reply)

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT DISPLAY WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class ChatDisplay(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {C['bg']}; }}
            QScrollBar:vertical {{ background: {C['bg']}; width: 4px; border: none; }}
            QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self._container = QWidget()
        self._container.setStyleSheet(f"background: {C['bg']};")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        self.setWidget(self._container)

        # Active streaming label
        self._stream_bubble: QLabel | None = None
        self._stream_text = ""

    def _make_label(self, text: str, sender: str, mood: str = "") -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background: transparent;")
        row = QHBoxLayout(outer)
        row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setMaximumWidth(580)

        ts = datetime.now().strftime("%H:%M")

        if sender == "sys":
            lbl.setText(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"""
                font-family: 'Courier New', monospace; font-size: 9px;
                letter-spacing: 2px; color: {C['dim']}; padding: 2px;
            """)
            row.addStretch(); row.addWidget(lbl); row.addStretch()
            return outer

        meta = f"JOI [{mood.upper()}] // {ts}" if sender == "joi" else f"YOU // {ts}"
        full_text = f'<span style="font-size:8px;letter-spacing:1px;color:{C["dim"]}">{meta}</span><br>{text}'
        lbl.setText(full_text)
        lbl.setTextFormat(Qt.TextFormat.RichText)

        if sender == "joi":
            lbl.setStyleSheet(f"""
                font-family: 'Rajdhani', Arial, sans-serif; font-size: 13px;
                color: {C['text']}; background: {C['joi_msg']};
                border: 1px solid {C['border']}; border-left: 2px solid {C['accent']};
                padding: 10px 14px; border-radius: 2px;
            """)
            row.addWidget(lbl); row.addStretch()
        else:
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl.setStyleSheet(f"""
                font-family: 'Rajdhani', Arial, sans-serif; font-size: 13px;
                color: #d0c0e0; background: {C['user_msg']};
                border: 1px solid {C['border']}; border-right: 2px solid {C['accent2']};
                padding: 10px 14px; border-radius: 2px;
            """)
            row.addStretch(); row.addWidget(lbl)
        return outer

    def add_sys(self, text: str):
        w = self._make_label(text, "sys")
        self._layout.insertWidget(self._layout.count() - 1, w)
        self._scroll_bottom()

    def add_user(self, text: str):
        w = self._make_label(text, "user")
        self._layout.insertWidget(self._layout.count() - 1, w)
        self._scroll_bottom()

    def add_tool_badge(self, tool: str, success: bool, message: str):
        denied = "denied" in message.lower()
        color  = C["accent2"] if denied else (C["green"] if success else C["red"])
        icon   = "🔒" if denied else ("✓" if success else "✗")
        lbl = QLabel(f"{icon} TOOL: {tool.upper()} — {message}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"""
            font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 1px;
            color: {color}; border: 1px solid {color}; background: {color}18;
            padding: 3px 10px; border-radius: 2px; margin: 0px 30px;
        """)
        self._layout.insertWidget(self._layout.count() - 1, lbl)
        self._scroll_bottom()

    # ── Streaming support ─────────────────────────────────────────────────────

    def start_stream(self, mood: str):
        """Create an empty JOI bubble that will be filled token by token."""
        self._stream_text = ""
        self._stream_mood = mood
        self._stream_bubble = QLabel()
        self._stream_bubble.setWordWrap(True)
        self._stream_bubble.setTextFormat(Qt.TextFormat.RichText)
        self._stream_bubble.setMaximumWidth(580)
        self._stream_bubble.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._stream_bubble.setStyleSheet(f"""
            font-family: 'Rajdhani', Arial, sans-serif; font-size: 13px;
            color: {C['text']}; background: {C['joi_msg']};
            border: 1px solid {C['border']}; border-left: 2px solid {C['accent']};
            padding: 10px 14px; border-radius: 2px;
        """)
        ts = datetime.now().strftime("%H:%M")
        self._stream_meta = f"JOI [{mood.upper()}] // {ts}"
        self._update_stream_bubble()

        outer = QWidget(); outer.setStyleSheet("background:transparent;")
        row = QHBoxLayout(outer); row.setContentsMargins(0,0,0,0)
        row.addWidget(self._stream_bubble); row.addStretch()
        self._layout.insertWidget(self._layout.count() - 1, outer)
        self._scroll_bottom()

    def append_token(self, token: str):
        """Append a streaming token to the current bubble."""
        if self._stream_bubble is None:
            return
        # Strip any TOOL_CALL fragments from display
        self._stream_text += token
        display = strip_tool_call(self._stream_text)
        self._update_stream_bubble(display)
        self._scroll_bottom()

    def _update_stream_bubble(self, text: str = ""):
        if self._stream_bubble is None:
            return
        cursor = "▋"
        meta = f'<span style="font-size:8px;letter-spacing:1px;color:{C["dim"]}">{self._stream_meta}</span><br>'
        self._stream_bubble.setText(meta + text + cursor)

    def end_stream(self):
        """Finalize the streaming bubble (remove cursor)."""
        if self._stream_bubble is None:
            return
        display = strip_tool_call(self._stream_text)
        meta = f'<span style="font-size:8px;letter-spacing:1px;color:{C["dim"]}">{self._stream_meta}</span><br>'
        self._stream_bubble.setText(meta + display)
        self._stream_bubble = None
        self._stream_text   = ""

    def clear(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stream_bubble = None

    def _scroll_bottom(self):
        QTimer.singleShot(30, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()))


# ═══════════════════════════════════════════════════════════════════════════════
# FLOATING HUD
# ═══════════════════════════════════════════════════════════════════════════════

class FloatingHUD(QWidget):
    send_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__(None,
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 200)
        self._drag_pos = None
        self._setup()
        # Position bottom-right
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(screen.width() - 384, screen.height() - 230)

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(7,13,26,225);
                border: 1px solid {C['accent']};
                border-radius: 4px;
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(10,8,10,8)
        fl.setSpacing(6)

        # Title row
        tr = QHBoxLayout()
        title = QLabel("J·O·I  HUD")
        title.setStyleSheet(f"font-family:'Courier New',monospace;font-size:9px;letter-spacing:3px;color:{C['accent']};")
        tr.addWidget(title); tr.addStretch()
        close = QPushButton("✕")
        close.setFixedSize(16,16)
        close.setStyleSheet(f"QPushButton{{color:{C['dim']};background:transparent;border:none;font-size:10px;}}QPushButton:hover{{color:{C['accent2']};}}")
        close.clicked.connect(self.hide)
        tr.addWidget(close)
        fl.addLayout(tr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C['border']};max-height:1px;"); fl.addWidget(sep)

        self._reply = QLabel("Standing by, sir.")
        self._reply.setWordWrap(True)
        self._reply.setFixedHeight(80)
        self._reply.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._reply.setStyleSheet(f"""
            font-family:'Rajdhani',Arial,sans-serif;font-size:12px;
            color:{C['text']};border-left:2px solid {C['accent']};
            padding:4px 8px;background:transparent;
        """)
        fl.addWidget(self._reply)

        ir = QHBoxLayout()
        self._input = QTextEdit()
        self._input.setMaximumHeight(36)
        self._input.setPlaceholderText("Quick directive...")
        self._input.setStyleSheet(f"""
            QTextEdit{{background:rgba(5,13,26,180);border:1px solid {C['border']};
            border-radius:2px;color:{C['text']};font-family:'Rajdhani',Arial;font-size:12px;padding:4px 8px;}}
            QTextEdit:focus{{border-color:{C['accent']};}}
        """)
        self._input.installEventFilter(self)
        ir.addWidget(self._input)
        send = QPushButton("→")
        send.setFixedSize(28,28)
        send.setStyleSheet(f"QPushButton{{color:{C['accent']};background:transparent;border:1px solid {C['accent']};border-radius:2px;font-size:13px;}}QPushButton:hover{{background:{C['accent']}22;}}")
        send.clicked.connect(self._send)
        ir.addWidget(send)
        fl.addLayout(ir)
        layout.addWidget(frame)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send(); return True
        return super().eventFilter(obj, event)

    def _send(self):
        t = self._input.toPlainText().strip()
        if t:
            self._input.clear()
            self._reply.setText("◉ processing...")
            self.send_requested.emit(t)

    def update_reply(self, text: str):
        self._reply.setText(text[:200] + ("..." if len(text) > 200 else ""))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class JOIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JOI — Justified Operative Interface")
        self.setMinimumSize(780, 560)
        self.resize(960, 660)
        self.setStyleSheet(f"QMainWindow,QWidget{{background:{C['bg']};color:{C['text']};}}")

        self._mood       = DEFAULT_MOOD
        self._is_busy    = False   # True while streaming
        self._is_listening = False

        # Backend
        self._worker  = StreamWorker()
        self._voice_out = VoiceOutput()

        # Wire signals
        self._worker.token_received.connect(self._on_token)
        self._worker.sentence_ready.connect(self._voice_out.speak)
        self._worker.tool_called.connect(self._on_tool)
        self._worker.response_done.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)

        self._hud = FloatingHUD()
        self._hud.send_requested.connect(self._submit)

        self._voice_thread: VoiceInputThread | None = None

        self._setup_ui()
        self._setup_tray()
        self._setup_shortcuts()
        self._boot()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        c = QWidget(); self.setCentralWidget(c)
        ml = QVBoxLayout(c); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(50)
        hdr.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)

        logo = QLabel("J·O·I")
        logo.setStyleSheet(f"font-family:'Orbitron','Courier New',monospace;font-size:18px;letter-spacing:6px;color:{C['accent']};")
        hl.addWidget(logo)

        sub = QLabel("JUSTIFIED OPERATIVE INTERFACE")
        sub.setStyleSheet(f"font-family:'Courier New',monospace;font-size:8px;letter-spacing:3px;color:{C['dim']};margin-left:8px;")
        hl.addWidget(sub); hl.addStretch()

        self._status_lbl = QLabel("◉ INIT")
        self._status_lbl.setStyleSheet(f"font-family:'Courier New',monospace;font-size:9px;letter-spacing:2px;color:{C['amber']};margin-right:10px;")
        hl.addWidget(self._status_lbl)

        hud_btn = self._small_btn("HUD", C["accent2"])
        hud_btn.setToolTip("Toggle HUD (Ctrl+H)")
        hud_btn.clicked.connect(self._toggle_hud)
        hl.addWidget(hud_btn)

        clr_btn = self._small_btn("CLR", C["amber"])
        clr_btn.clicked.connect(self._clear)
        hl.addWidget(clr_btn)
        ml.addWidget(hdr)

        # Mood bar
        mb = QWidget(); mb.setFixedHeight(34)
        mb.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        mbl = QHBoxLayout(mb); mbl.setContentsMargins(12,3,12,3); mbl.setSpacing(5)
        lbl = QLabel("MODE //")
        lbl.setStyleSheet(f"font-family:'Courier New',monospace;font-size:9px;letter-spacing:2px;color:{C['dim']};")
        mbl.addWidget(lbl)
        self._mood_btns: dict[str,QPushButton] = {}
        for m in ALL_MOODS:
            b = QPushButton(m.upper())
            b.setCheckable(True); b.setChecked(m == self._mood)
            b.clicked.connect(lambda _, mood=m: self._set_mood(mood))
            b.setStyleSheet(self._mood_style(m == self._mood))
            self._mood_btns[m] = b
            mbl.addWidget(b)
        mbl.addStretch()
        ml.addWidget(mb)

        # Chat display
        self._chat = ChatDisplay()
        ml.addWidget(self._chat)

        # Input area
        ia = QWidget(); ia.setFixedHeight(90)
        ia.setStyleSheet(f"background:{C['panel']};border-top:1px solid {C['border']};")
        ial = QVBoxLayout(ia); ial.setContentsMargins(12,8,12,8); ial.setSpacing(6)

        ir = QHBoxLayout(); ir.setSpacing(8)

        self._input = QTextEdit()
        self._input.setMaximumHeight(54)
        self._input.setPlaceholderText("Issue a directive, sir... (Enter = send, Shift+Enter = newline)")
        self._input.setStyleSheet(f"""
            QTextEdit{{background:#050d1a;border:1px solid {C['border']};border-radius:2px;
            color:{C['text']};font-family:'Rajdhani',Arial;font-size:13px;padding:6px 10px;}}
            QTextEdit:focus{{border-color:{C['accent']};}}
        """)
        self._input.installEventFilter(self)
        ir.addWidget(self._input)

        # Mic button (big, prominent)
        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(46, 46)
        self._mic_btn.setToolTip("Voice input (Ctrl+Shift+Space)\nClick while JOI is speaking to interrupt")
        self._mic_btn.clicked.connect(self._toggle_voice)
        self._mic_btn.setStyleSheet(self._mic_style(False))
        ir.addWidget(self._mic_btn)

        self._send_btn = QPushButton("TRANSMIT")
        self._send_btn.setFixedSize(90, 46)
        self._send_btn.clicked.connect(self._send_text)
        self._send_btn.setStyleSheet(f"""
            QPushButton{{font-family:'Orbitron','Courier New',monospace;font-size:8px;
            letter-spacing:2px;color:{C['accent']};background:transparent;
            border:1px solid {C['accent']};border-radius:2px;}}
            QPushButton:hover{{background:{C['accent']}22;}}
            QPushButton:disabled{{color:{C['dim']};border-color:{C['border']};}}
        """)
        ir.addWidget(self._send_btn)
        ial.addLayout(ir)

        # Status hint
        self._hint = QLabel("  Ctrl+Shift+Space = voice  ·  Ctrl+H = HUD  ·  Ctrl+W = clear  ·  🎤 = interrupt JOI")
        self._hint.setStyleSheet(f"font-family:'Courier New',monospace;font-size:8px;letter-spacing:1px;color:{C['dim']};")
        ial.addWidget(self._hint)
        ml.addWidget(ia)

    def _small_btn(self, text: str, color: str) -> QPushButton:
        b = QPushButton(text)
        b.setFixedSize(54, 28)
        b.setStyleSheet(f"""
            QPushButton{{font-family:'Orbitron','Courier New',monospace;font-size:8px;
            letter-spacing:2px;color:{color};background:transparent;
            border:1px solid {color};border-radius:2px;}}
            QPushButton:hover{{background:{color}22;}}
        """)
        return b

    def _mood_style(self, active: bool) -> str:
        if active:
            return f"""QPushButton{{font-family:'Rajdhani',Arial;font-size:9px;font-weight:600;
                letter-spacing:1px;color:{C['accent']};background:{C['accent']}15;
                border:1px solid {C['accent']};padding:2px 8px;border-radius:2px;}}"""
        return f"""QPushButton{{font-family:'Rajdhani',Arial;font-size:9px;font-weight:600;
            letter-spacing:1px;color:{C['dim']};background:transparent;
            border:1px solid {C['border']};padding:2px 8px;border-radius:2px;}}
            QPushButton:hover{{color:{C['accent']};border-color:{C['accent']};}}"""

    def _mic_style(self, active: bool) -> str:
        color = C["accent2"] if active else C["dim"]
        bg    = f"{C['accent2']}22" if active else "transparent"
        border= C["accent2"] if active else C["border"]
        return f"""QPushButton{{font-size:18px;color:{color};background:{bg};
            border:1px solid {border};border-radius:4px;}}
            QPushButton:hover{{background:{C['accent2']}22;border-color:{C['accent2']};}}"""

    # ── Event filter for Enter key ────────────────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_text(); return True
        return super().eventFilter(obj, event)

    # ── Shortcuts ─────────────────────────────────────────────────────────────
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+H"),            self, self._toggle_hud)
        QShortcut(QKeySequence("Ctrl+W"),            self, self._clear)
        QShortcut(QKeySequence("Ctrl+Shift+Space"),  self, self._toggle_voice)

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _setup_tray(self):
        px = QPixmap(32,32); px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(7,13,26))); p.setPen(QPen(QColor(0,200,255),2))
        p.drawEllipse(2,2,28,28)
        p.setPen(QPen(QColor(0,200,255),2))
        p.drawText(QRect(0,0,32,32), Qt.AlignmentFlag.AlignCenter, "J")
        p.end()
        self._tray = QSystemTrayIcon(QIcon(px), self)
        self._tray.setToolTip("JOI — Justified Operative Interface")
        menu = QMenu()
        menu.setStyleSheet(f"background:{C['panel']};color:{C['text']};border:1px solid {C['border']};")
        menu.addAction("Open JOI").triggered.connect(self._show)
        menu.addAction("Toggle HUD").triggered.connect(self._toggle_hud)
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(QApplication.quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda r: self._show() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self._tray.show()

    # ── Boot ──────────────────────────────────────────────────────────────────
    def _boot(self):
        lines = [
            ("— JUSTIFIED OPERATIVE INTERFACE // BOOT —", 0),
            ("GROQ NEURAL CORE // LLAMA 3.3 70B", 200),
            ("DESKTOP AGENT // 22 TOOLS LOADED", 380),
            ("VOICE I/O // ONLINE", 540),
            ("PERMISSION SYSTEM // ACTIVE", 700),
        ]
        for t, d in lines:
            QTimer.singleShot(d, lambda text=t: self._chat.add_sys(text))

        def _greet():
            self._set_status("◉ ONLINE", C["green"])
            self._submit(
                "Give a one-sentence JARVIS-style boot greeting. "
                "You are JOI, just online, addressing the user as sir. Be brief."
            )
        QTimer.singleShot(900, _greet)

    # ── Core actions ──────────────────────────────────────────────────────────

    def _send_text(self):
        text = self._input.toPlainText().strip()
        if not text or self._is_busy:
            return
        self._input.clear()
        self._chat.add_user(text)
        self._submit(text)

    def _submit(self, text: str):
        if not text:
            return
        self._is_busy = True
        self._send_btn.setEnabled(False)
        self._set_status("◉ STREAMING", C["amber"])
        self._chat.start_stream(self._mood)
        self._worker.submit(text, self._mood)

    def _set_mood(self, mood: str):
        self._mood = mood
        for m, b in self._mood_btns.items():
            active = m == mood
            b.setChecked(active)
            b.setStyleSheet(self._mood_style(active))
        self._chat.add_sys(f"// OPERATIVE MODE → {mood.upper()}")

    # ── Voice ─────────────────────────────────────────────────────────────────

    def _toggle_voice(self):
        """
        If JOI is speaking → interrupt her.
        If JOI is streaming → interrupt stream + speech.
        If idle → start listening.
        """
        if self._voice_out.is_speaking or self._is_busy:
            # Interrupt
            self._voice_out.interrupt()
            self._worker.interrupt()
            self._chat.end_stream()
            self._is_busy = False
            self._send_btn.setEnabled(True)
            self._set_status("◉ INTERRUPTED", C["amber"])
            self._mic_btn.setStyleSheet(self._mic_style(False))
            self._chat.add_sys("// INTERRUPTED BY USER")
            return

        if self._is_listening:
            return

        # Start listening
        self._is_listening = True
        self._mic_btn.setStyleSheet(self._mic_style(True))
        self._set_status("◉ LISTENING...", C["accent2"])
        self._chat.add_sys("// VOICE INPUT — speak your directive, sir")

        self._voice_thread = VoiceInputThread()
        self._voice_thread.transcribed.connect(self._on_voice_text)
        self._voice_thread.error.connect(self._on_voice_error)
        self._voice_thread.listening.connect(lambda active: None)
        self._voice_thread.finished.connect(lambda: setattr(self, '_is_listening', False))
        self._voice_thread.start()

    def _on_voice_text(self, text: str):
        self._mic_btn.setStyleSheet(self._mic_style(False))
        self._set_status("◉ ONLINE", C["green"])
        self._chat.add_user(f"🎤 {text}")
        self._submit(text)

    def _on_voice_error(self, msg: str):
        self._mic_btn.setStyleSheet(self._mic_style(False))
        self._set_status("◉ ONLINE", C["green"])
        self._chat.add_sys(f"⚠ Voice: {msg}")

    # ── Worker callbacks ──────────────────────────────────────────────────────

    def _on_token(self, token: str):
        self._chat.append_token(token)

    def _on_tool(self, tool: str, success: bool, message: str):
        self._chat.end_stream()
        self._chat.add_tool_badge(tool, success, message)
        self._chat.start_stream(self._mood)

    def _on_done(self, full_reply: str):
        self._chat.end_stream()
        self._hud.update_reply(full_reply)
        self._is_busy = False
        self._send_btn.setEnabled(True)
        self._set_status("◉ ONLINE", C["green"])

    def _on_error(self, msg: str):
        self._chat.end_stream()
        self._chat.add_sys(f"⚠ {msg.splitlines()[0]}")
        self._is_busy = False
        self._send_btn.setEnabled(True)
        self._set_status("◉ ERROR", C["red"])

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = C["accent"]):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"font-family:'Courier New',monospace;font-size:9px;"
            f"letter-spacing:2px;color:{color};margin-right:10px;")

    def _toggle_hud(self):
        self._hud.hide() if self._hud.isVisible() else (self._hud.show(), self._hud.raise_())

    def _clear(self):
        self._worker.clear_history()
        self._chat.clear()
        self._chat.add_sys("— SESSION MEMORY PURGED —")

    def _show(self):
        self.show(); self.raise_(); self.activateWindow()

    def closeEvent(self, event):
        event.ignore(); self.hide()
        self._tray.showMessage("JOI", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 1500)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JOI")
    app.setQuitOnLastWindowClosed(False)

    if not GROQ_API_KEY:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "JOI — Config Error",
            "GROQ_API_KEY not set.\n\nAdd it to your .env and restart.")
        sys.exit(1)

    w = JOIWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()