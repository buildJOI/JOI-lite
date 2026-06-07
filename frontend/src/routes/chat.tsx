import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { Clock, Keyboard, Mic, Send, Settings, X } from "lucide-react";
import { type JoiExpression } from "@/components/joi/JoiMascot";
import { AnimatedJoi } from "@/components/joi/AnimatedJoi";
import { EmotionEffects } from "@/components/joi/EmotionEffects";
import { SparkleField } from "@/components/joi/SparkleField";
import { startVoiceCapture, blendToneEmotion, type VoiceHandle } from "@/lib/voice";
import { streamChat, fetchMoods, playAudioB64 } from "@/lib/api/joi";

export const Route = createFileRoute("/chat")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "JOI — companion" },
      { name: "description", content: "Talk with JOI, your living digital companion." },
    ],
  }),
  component: ChatPage,
});

type Role = "joi" | "user";
interface Message {
  id: string;
  role: Role;
  text: string;
  at: Date;
}

const GREETINGS = [
  "Welcome back.",
  "Good to see you again.",
  "Ready to build something today?",
  "I've been waiting.",
  "Let's continue where we left off.",
];

type MicState = "idle" | "listening" | "thinking" | "speaking";

function formatTime(d: Date) {
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function detectEmotion(text: string): JoiExpression {
  const t = text.toLowerCase();
  if (/(love|adore|❤|heart|crush|romantic|sweetheart)/.test(t)) return "love";
  if (/(lol|lmao|haha|hehe|rofl|funny|joke|hilarious)/.test(t)) return "laughing";
  if (/(😉|wink|just kidding|jk\b|kidding)/.test(t)) return "wink";
  if (/(let's go|let's do|i can|i will|i'll|crush it|focus|grind|determined|ready)/.test(t)) return "determined";
  if (/(tease|cheeky|naughty|sneaky|playful|silly)/.test(t)) return "cheeky";
  if (/(tired|sleepy|exhausted|drained|nap|yawn)/.test(t)) return "sleepy";
  if (/(angry|mad|annoyed|frustrat|hate|ugh|argh|stupid|damn)/.test(t)) return "frustrated";
  if (/(!|amazing|awesome|great|yay|wow|incredible|fantastic)/.test(t)) return "excited";
  if (/(surprise|whoa|woah|really\?|no way|seriously)/.test(t)) return "surprised";
  if (/(sad|sorry|cry|lonely|miss|hurt|down|depressed)/.test(t)) return "sad";
  if (/(confused|huh|unclear|don't get|dont get|what do you mean)/.test(t)) return "confused";
  if (/(worried|concern|problem|issue|broken|error|wrong|help)/.test(t)) return "concerned";
  if (/(\?|how|why|what|when|where|who)/.test(t)) return "curious";
  return "happy";
}

function ChatPage() {
  const greeting = useMemo(() => GREETINGS[Math.floor(Math.random() * GREETINGS.length)], []);
  const [messages, setMessages] = useState<Message[]>(() => [
    { id: "g0", role: "joi", text: greeting, at: new Date() },
  ]);
  const [expression, setExpression] = useState<JoiExpression>("happy");
  const [micState, setMicState] = useState<MicState>("idle");
  const [showKeyboard, setShowKeyboard] = useState(false);
  const [input, setInput] = useState("");
  const [booted, setBooted] = useState(false);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const [partialTranscript, setPartialTranscript] = useState("");

  // Mood state — loaded from backend on mount
  const [mood, setMood] = useState("default");
  const [availableMoods, setAvailableMoods] = useState<string[]>([]);
  const [showMoodPicker, setShowMoodPicker] = useState(false);

  // Session persisted across page lifetime
  const sessionId = useRef<string | null>(null);

  const voiceHandle = useRef<VoiceHandle | null>(null);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const audioHandle = useRef<{ stop: () => void } | null>(null);

  // Boot: fade-in + load moods from backend
  useEffect(() => {
    const t = setTimeout(() => setBooted(true), 80);
    fetchMoods()
      .then(({ moods, default: def }) => {
        setAvailableMoods(moods);
        setMood(def);
      })
      .catch(() => {
        // Backend unreachable — use hardcoded fallback so the UI still works
        setAvailableMoods(["default", "analytical", "tactical", "empathetic", "playful", "creative", "professional", "investigative", "bold"]);
      });
    return () => clearTimeout(t);
  }, []);

  // Idle → sleep after 60s
  const armIdle = () => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      setExpression((cur) => (cur === "happy" ? "sleep" : cur));
    }, 60000);
  };
  useEffect(() => {
    armIdle();
    const wake = () => {
      setExpression((cur) => (cur === "sleep" || cur === "sleepy" ? "happy" : cur));
      armIdle();
    };
    window.addEventListener("mousemove", wake);
    window.addEventListener("keydown", wake);
    window.addEventListener("touchstart", wake);
    return () => {
      window.removeEventListener("mousemove", wake);
      window.removeEventListener("keydown", wake);
      window.removeEventListener("touchstart", wake);
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage = (text: string, overrideEmotion?: JoiExpression) => {
    const clean = text.trim();
    if (!clean) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", text: clean, at: new Date() };
    setMessages((m) => [...m, userMsg]);
    setInput("");

    // Briefly mirror user emotion on JOI's face, then shift to thinking
    const userEmo = overrideEmotion ?? detectEmotion(clean);
    setExpression(userEmo);
    setMicState("thinking");
    setTimeout(() => setExpression("thinking"), 520);

    streamChat(
      clean,
      sessionId.current,
      mood,
      (data) => {
        // Each SSE event — "thinking aloud" arrives first, then the final result
        sessionId.current = data.session_id;

        const emo = overrideEmotion ?? (data.emotion as JoiExpression) ?? detectEmotion(data.response);
        setExpression("talking");
        setMicState("speaking");
        setMessages((m) => [
          ...m,
          { id: crypto.randomUUID(), role: "joi", text: data.response, at: new Date() },
        ]);

        if (data.audio_b64) {
          audioHandle.current?.stop();
          audioHandle.current = playAudioB64(data.audio_b64);
        }

        if (data.done) {
          setTimeout(() => {
            setExpression(emo);
            setMicState("idle");
          }, 1300);
          armIdle();
        }
      },
      (err) => {
        console.error("[JOI] chat error", err);
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: "joi",
            text: "I couldn't reach the server right now. Is the backend running?",
            at: new Date(),
          },
        ]);
        setExpression("concerned");
        setMicState("idle");
        setTimeout(() => setExpression("happy"), 2000);
        armIdle();
      },
    );
  };

  const handleMicTap = () => {
    if (micState === "idle") {
      setMicState("listening");
      setExpression("listening");
      setPartialTranscript("");
      voiceHandle.current = startVoiceCapture({
        onLevel: (lv) => setVoiceLevel(lv),
        onPartial: (t) => {
          setPartialTranscript(t);
          if (/(\?)\s*$/.test(t)) setExpression("curious");
        },
        onResult: ({ transcript, tone }) => {
          const textEmo = detectEmotion(transcript);
          const finalEmo = blendToneEmotion(textEmo, tone);
          setVoiceLevel(0);
          setPartialTranscript("");
          if (transcript === "(silence)") {
            setMicState("idle");
            setExpression("confused");
            setTimeout(() => setExpression("happy"), 1200);
            return;
          }
          void sendMessage(transcript, finalEmo);
        },
        onEnd: () => {
          voiceHandle.current = null;
        },
        onError: () => {
          setMicState("idle");
          setExpression("concerned");
          setTimeout(() => setExpression("happy"), 1400);
        },
      });
    } else if (micState === "listening") {
      voiceHandle.current?.stop();
    }
  };

  // Input focus → look down toward the keyboard
  const lastEmotion = useRef<JoiExpression>("happy");
  useEffect(() => {
    if (expression !== "lookDown") lastEmotion.current = expression;
  }, [expression]);
  const onInputFocus = () => setExpression("lookDown");
  const onInputBlur = () => setExpression((c) => (c === "lookDown" ? lastEmotion.current : c));

  const feedRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll feed to bottom on every new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const micRing =
    micState === "listening"
      ? "border-destructive glow-attention animate-joi-pulse-ring"
      : micState === "thinking"
        ? "border-secondary"
        : micState === "speaking"
          ? "border-primary glow-primary"
          : "border-primary/50 glow-primary";

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Radial background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 animate-[joi-radial-pulse_8s_ease-in-out_infinite]"
        style={{
          background:
            "radial-gradient(ellipse 55% 50% at 50% 50%, rgba(255,199,42,0.14), transparent 65%), radial-gradient(ellipse 40% 30% at 50% 60%, rgba(248,157,37,0.10), transparent 70%)",
        }}
      />

      <SparkleField density={42} />

      {/* Top bar */}
      <header className="absolute left-0 right-0 top-0 z-20 flex items-center justify-between px-5 py-4 sm:px-8">
        <Link to="/" className="block">
          <div className="font-pixel text-2xl tracking-wider text-primary">
            JOI <span className="text-secondary">✦</span>
          </div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">your AI companion</div>
        </Link>

        {/* Settings / mood picker trigger */}
        <div className="relative">
          <button
            aria-label="Settings"
            onClick={() => setShowMoodPicker((s) => !s)}
            className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-surface/60 text-muted-foreground transition hover:text-foreground"
          >
            <Settings size={18} />
          </button>

          {showMoodPicker && availableMoods.length > 0 && (
            <div className="absolute right-0 top-12 z-30 glass-card rounded-xl p-3 shadow-xl min-w-[170px] animate-joi-fade-in">
              <p className="font-pixel text-[10px] uppercase tracking-widest text-muted-foreground mb-2 px-1">
                Mood
              </p>
              {availableMoods.map((m) => (
                <button
                  key={m}
                  onClick={() => { setMood(m); setShowMoodPicker(false); }}
                  className={`w-full text-left rounded-lg px-3 py-1.5 text-sm transition capitalize ${
                    m === mood
                      ? "bg-primary/20 text-primary font-semibold"
                      : "text-foreground hover:bg-surface"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {/* Center mascot */}
      <div
        className={`absolute left-1/2 top-1/2 z-[1] -translate-x-1/2 -translate-y-1/2 transition-all duration-700 ${
          booted ? "opacity-100 scale-100" : "opacity-0 scale-95"
        }`}
      >
        <div className="animate-joi-float">
          <div className="relative animate-joi-breathe">
            <AnimatedJoi
              expression={expression}
              size={520}
              level={voiceLevel}
              gazeY={micState === "listening" ? 0.6 + voiceLevel * 0.3 : 0}
              gazeX={micState === "listening" ? (voiceLevel - 0.5) * 0.4 : 0}
              speaking={micState === "speaking"}
              className="h-[min(70vh,70vw)] w-[min(70vh,70vw)]"
            />
            <EmotionEffects expression={expression} size={520} />
          </div>
        </div>
      </div>

      {/* Active mood badge */}
      <div className="absolute top-[72px] left-1/2 -translate-x-1/2 z-20">
        <span className="font-pixel text-[10px] uppercase tracking-widest text-muted-foreground/60 px-3 py-1 glass-card rounded-full">
          {mood}
        </span>
      </div>

      {/* Scrollable history — slides in from right */}
      {/* ── Unified scrollable chat feed ── sits above mascot, transparent bg */}
      <div className="absolute inset-x-0 top-20 bottom-36 z-10 pointer-events-none">
        <div
          ref={feedRef}
          className="h-full overflow-y-auto pointer-events-auto px-4 py-3 flex flex-col gap-3"
          style={{
            maskImage: "linear-gradient(to bottom, transparent 0%, black 6%, black 88%, transparent 100%)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 6%, black 88%, transparent 100%)",
            scrollbarWidth: "thin",
            scrollbarColor: "rgba(255,199,42,0.2) transparent",
          }}
        >
          {/* Spacer so first message doesn't sit behind mascot on desktop */}
          <div className="flex-1 min-h-[30vh] md:min-h-[35vh]" aria-hidden />
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex animate-joi-fade-in ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {/* Desktop: pin JOI left, user right with gap for mascot */}
              <div className={`w-full max-w-[min(320px,38vw)] md:max-w-[300px] ${m.role === "user" ? "md:ml-auto" : ""}`}>
                <ChatBubble message={m} side={m.role === "user" ? "right" : "left"} compact />
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Bottom controls */}
      <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-6 sm:px-8">
        <div className="mx-auto flex max-w-5xl items-end justify-between gap-3">
          <button
            aria-label="Scroll to bottom"
            onClick={() => bottomRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="grid h-11 w-11 place-items-center rounded-xl border border-border bg-surface/60 text-muted-foreground transition hover:text-foreground"
          >
            <Clock size={18} />
          </button>

          <div className="flex flex-1 flex-col items-center gap-2">
            {showKeyboard && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void sendMessage(input);
                }}
                className="glass-card flex w-full max-w-md items-center gap-2 rounded-full px-4 py-2 animate-joi-fade-in"
              >
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onFocus={onInputFocus}
                  onBlur={onInputBlur}
                  placeholder="Say something to JOI…"
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
                  aria-label="Message JOI"
                />
                <button
                  type="submit"
                  className="grid h-8 w-8 place-items-center rounded-full bg-primary text-primary-foreground"
                  aria-label="Send"
                >
                  <Send size={14} />
                </button>
              </form>
            )}

            <button
              onClick={handleMicTap}
              aria-label="Tap to speak"
              className={`group relative grid h-20 w-20 place-items-center rounded-full border-2 bg-surface/70 backdrop-blur transition ${micRing}`}
              style={
                micState === "listening"
                  ? { boxShadow: `0 0 ${20 + voiceLevel * 60}px rgba(215,58,31,${0.25 + voiceLevel * 0.6})` }
                  : undefined
              }
            >
              <Mic size={28} className="text-primary" />
              {micState === "speaking" && (
                <span className="pointer-events-none absolute inset-0 animate-ping rounded-full border border-primary/40" />
              )}
              {micState === "listening" && (
                <span
                  className="pointer-events-none absolute inset-0 rounded-full border border-destructive/60"
                  style={{ transform: `scale(${1 + voiceLevel * 0.35})`, transition: "transform 80ms linear" }}
                />
              )}
            </button>
            <div className="font-pixel text-xs uppercase tracking-widest text-muted-foreground">
              {micState === "idle" && "Tap to speak"}
              {micState === "listening" && (partialTranscript ? `"${partialTranscript}"` : "Listening…")}
              {micState === "thinking" && "Thinking…"}
              {micState === "speaking" && "Speaking…"}
            </div>
          </div>

          <button
            aria-label={showKeyboard ? "Close keyboard" : "Open keyboard"}
            onClick={() => {
              setShowKeyboard((s) => !s);
              setTimeout(() => inputRef.current?.focus(), 50);
            }}
            className="grid h-11 w-11 place-items-center rounded-xl border border-border bg-surface/60 text-muted-foreground transition hover:text-foreground"
          >
            {showKeyboard ? <X size={18} /> : <Keyboard size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({
  message,
  side,
  compact = false,
}: {
  message: Message;
  side: "left" | "right";
  compact?: boolean;
}) {
  const isUser = side === "right";
  return (
    <div className={`pointer-events-auto animate-joi-fade-in ${isUser ? "items-end" : "items-start"} flex flex-col`}>
      <div className={`mb-1 font-pixel text-[11px] tracking-widest ${isUser ? "text-destructive" : "text-primary"}`}>
        {isUser ? "YOU" : "JOI"}
      </div>
      <div
        className={`glass-card rounded-2xl px-4 py-3 text-sm ${compact ? "max-w-[78vw]" : "max-w-[320px]"} ${
          isUser
            ? "border-destructive/30 text-foreground"
            : "border-primary/25 text-foreground"
        }`}
        style={{
          boxShadow: isUser
            ? "inset 0 0 0 1px rgba(215,58,31,0.25)"
            : "inset 0 0 0 1px rgba(255,199,42,0.22)",
        }}
      >
        <p className="leading-relaxed">{message.text}</p>
        <div className={`mt-2 text-[10px] uppercase tracking-widest text-muted-foreground/70 ${isUser ? "text-right" : ""}`}>
          {formatTime(message.at)} {isUser && <span className="text-destructive">✓✓</span>}
        </div>
      </div>
    </div>
  );
}