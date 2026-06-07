/**
 * JOI backend API client
 * All requests go through /api (proxied to FastAPI in dev, env-var in prod).
 */

const BASE =
  typeof import.meta !== "undefined" && (import.meta as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL
    ? (import.meta as { env: { VITE_API_URL: string } }).env.VITE_API_URL
    : "";

// In dev the Vite proxy rewrites /api → backend root, so we can always use /api.
// In prod VITE_API_URL is the full backend URL (e.g. https://api.yourdomain.com).
const API = BASE ? BASE : "/api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ChatResponse {
  session_id: string;
  response: string;
  emotion: string;
  audio_b64: string | null;
}

export interface MoodsResponse {
  moods: string[];
  default: string;
}

// ─── Requests ─────────────────────────────────────────────────────────────────

export async function sendChat(
  message: string,
  sessionId: string | null,
  mood: string
): Promise<ChatResponse> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      mood,
    }),
  });
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  return res.json() as Promise<ChatResponse>;
}

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

// ─── Audio playback helper ────────────────────────────────────────────────────

/**
 * Decode a base64 MP3 from the backend and play it via the Web Audio API.
 * Returns a stop() function so the caller can interrupt mid-playback.
 */
export function playAudioB64(b64: string): { stop: () => void } {
  let source: AudioBufferSourceNode | null = null;
  let ctx: AudioContext | null = null;

  (async () => {
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

      const Ctx =
        (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext })
          .AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
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