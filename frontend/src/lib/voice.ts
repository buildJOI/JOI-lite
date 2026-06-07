import type { JoiExpression } from "@/components/joi/JoiMascot";

export interface VoiceTone {
  /** Peak RMS during capture (0-1ish). */
  peak: number;
  /** Average RMS during capture (0-1ish). */
  avg: number;
  /** Approx ratio of frames considered "voiced" (rms > floor). */
  activity: number;
}

export interface VoiceResult {
  transcript: string;
  tone: VoiceTone;
}

export interface VoiceHandle {
  stop: () => void;
}

interface StartOpts {
  onLevel?: (level: number) => void;
  onPartial?: (text: string) => void;
  onResult: (r: VoiceResult) => void;
  onEnd?: () => void;
  onError?: (e: unknown) => void;
}

/**
 * Capture a short utterance from the mic using the Web Speech API for
 * transcription and a WebAudio AnalyserNode for amplitude / "tone" cues.
 * Falls back to a stubbed transcript when SpeechRecognition isn't available.
 */
export function startVoiceCapture(opts: StartOpts): VoiceHandle {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  const SR = w.SpeechRecognition || w.webkitSpeechRecognition;

  let recog: SpeechRecognitionLike | null = null;
  let stream: MediaStream | null = null;
  let audioCtx: AudioContext | null = null;
  let raf = 0;
  let stopped = false;

  let peak = 0;
  let sum = 0;
  let samples = 0;
  let voiced = 0;
  let transcript = "";

  const cleanup = () => {
    if (stopped) return;
    stopped = true;
    cancelAnimationFrame(raf);
    stream?.getTracks().forEach((t) => t.stop());
    audioCtx?.close().catch(() => {});
    opts.onEnd?.();
  };

  const fire = () => {
    opts.onResult({
      transcript: transcript.trim() || "(silence)",
      tone: {
        peak,
        avg: samples ? sum / samples : 0,
        activity: samples ? voiced / samples : 0,
      },
    });
  };

  navigator.mediaDevices
    .getUserMedia({ audio: true })
    .then((s) => {
      stream = s;
      const Ctx =
        (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext })
          .AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      audioCtx = new Ctx();
      const src = audioCtx.createMediaStreamSource(s);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      const tick = () => {
        if (stopped) return;
        analyser.getByteTimeDomainData(data);
        let acc = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          acc += v * v;
        }
        const rms = Math.sqrt(acc / data.length);
        peak = Math.max(peak, rms);
        sum += rms;
        samples++;
        if (rms > 0.04) voiced++;
        opts.onLevel?.(Math.min(1, rms * 2.2));
        raf = requestAnimationFrame(tick);
      };
      tick();
    })
    .catch((e) => opts.onError?.(e));

  if (SR) {
    recog = new SR();
    recog.continuous = false;
    recog.interimResults = true;
    recog.lang = "en-US";
    recog.onresult = (e: SpeechRecognitionEventLike) => {
      let t = "";
      for (let i = 0; i < e.results.length; i++) {
        t += e.results[i][0].transcript;
      }
      transcript = t;
      opts.onPartial?.(t);
    };
    recog.onerror = (e: unknown) => opts.onError?.(e);
    recog.onend = () => {
      fire();
      cleanup();
    };
    try {
      recog.start();
    } catch (e) {
      opts.onError?.(e);
    }
    // safety cap
    setTimeout(() => {
      try {
        recog?.stop();
      } catch {
        /* ignore */
      }
    }, 7000);
  } else {
    // No SpeechRecognition available — listen for 2.5s then return a placeholder
    setTimeout(() => {
      transcript = "Hey JOI, what's up?";
      fire();
      cleanup();
    }, 2500);
  }

  return {
    stop: () => {
      try {
        recog?.stop();
      } catch {
        /* ignore */
      }
      if (!SR) {
        fire();
        cleanup();
      }
    },
  };
}

/**
 * Blend a text-derived emotion with vocal tone cues so loud / quiet / flat
 * delivery shifts which sprite JOI uses.
 */
export function blendToneEmotion(
  textEmotion: JoiExpression,
  tone: VoiceTone
): JoiExpression {
  const loud = tone.peak > 0.32 || tone.avg > 0.16;
  const quiet = tone.peak < 0.08 && tone.activity > 0.05;
  const silent = tone.activity < 0.04;

  if (silent) return "curious";
  if (loud) {
    if (textEmotion === "sad" || textEmotion === "concerned" || textEmotion === "frustrated")
      return "frustrated";
    if (textEmotion === "curious" || textEmotion === "confused") return "surprised";
    if (textEmotion === "love") return "love";
    if (textEmotion === "laughing") return "laughing";
    if (textEmotion === "happy") return "excited";
    return "excited";
  }
  if (quiet) {
    if (textEmotion === "happy" || textEmotion === "excited") return "sleepy";
    if (textEmotion === "sad") return "sad";
    if (textEmotion === "concerned") return "concerned";
    return "sleepy";
  }
  return textEmotion;
}

// Minimal local types so we don't depend on lib.dom Speech types being present
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: unknown) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
interface SpeechRecognitionEventLike {
  results: ArrayLike<ArrayLike<{ transcript: string }>> & { length: number };
}
