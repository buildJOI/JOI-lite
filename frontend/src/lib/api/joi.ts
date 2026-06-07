/**
 * JOI backend API client
 * Uses Server-Sent Events (SSE) for streaming multi-step responses.
 */

const BASE =
  typeof import.meta !== "undefined" &&
  (import.meta as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL
    ? (import.meta as { env: { VITE_API_URL: string } }).env.VITE_API_URL
    : "";

// In dev the Vite proxy rewrites /api → backend root.
// In prod VITE_API_URL is the full backend address.
const API = BASE ? BASE : "/api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ChatResponse {
  session_id: string;
  response: string;
  emotion: string;
  audio_b64: string | null;
  done: boolean;
}

export interface MoodsResponse {
  moods: string[];
  default: string;
}

// ─── Streaming chat (SSE) ─────────────────────────────────────────────────────

/**
 * Stream chat messages from JOI via Server-Sent Events.
 * onMessage is called once per SSE message event.
 * The backend can emit 2+ messages per user prompt (thinking → result).
 * Returns a cancel function.
 */
export function streamChat(
  message: string,
  sessionId: string | null,
  mood: string,
  onMessage: (msg: ChatResponse) => void,
  onError: (err: Error) => void,
): () => void {
  let cancelled = false;

  (async () => {
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId, mood }),
      });

      if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (!cancelled) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        // SSE frames are separated by double newline
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";

        for (const frame of frames) {
          const eventMatch = frame.match(/^event: (\w+)/m);
          const dataMatch = frame.match(/^data: (.+)/m);
          if (!dataMatch) continue;
          const eventType = eventMatch?.[1] ?? "message";
          if (eventType === "done") return;
          if (eventType === "message") {
            try {
              const parsed = JSON.parse(dataMatch[1]) as ChatResponse;
              onMessage(parsed);
            } catch {
              /* malformed frame — skip */
            }
          }
        }
      }
    } catch (e) {
      if (!cancelled) onError(e instanceof Error ? e : new Error(String(e)));
    }
  })();

  return () => {
    cancelled = true;
  };
}

// ─── Other endpoints ──────────────────────────────────────────────────────────

export async function fetchMoods(): Promise<MoodsResponse> {
  const res = await fetch(`${API}/moods`);
  if (!res.ok) throw new Error(`Moods request failed: ${res.status}`);
  return res.json() as Promise<MoodsResponse>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

// ─── Audio playback ───────────────────────────────────────────────────────────

export function playAudioB64(b64: string): { stop: () => void } {
  let source: AudioBufferSourceNode | null = null;
  let ctx: AudioContext | null = null;

  (async () => {
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

      const Ctx =
        (
          window as unknown as {
            AudioContext?: typeof AudioContext;
            webkitAudioContext?: typeof AudioContext;
          }
        ).AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!Ctx) return;
      ctx = new Ctx();
      const buffer = await ctx.decodeAudioData(bytes.buffer);
      source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start(0);
    } catch (e) {
      console.warn("[JOI audio] playback error", e);
    }
  })();

  return {
    stop: () => {
      try {
        source?.stop();
        ctx?.close();
      } catch {
        /* ignore */
      }
    },
  };
}