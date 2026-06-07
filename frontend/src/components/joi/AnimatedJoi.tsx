import { useEffect, useRef, useState } from "react";
import { JoiMascot, type JoiExpression } from "./JoiMascot";

interface Props {
  expression: JoiExpression;
  size?: number;
  className?: string;
  /** 0-1 voice level; subtly scales the face while listening/speaking. */
  level?: number;
  /** -1..1 horizontal gaze offset (positive = right). */
  gazeX?: number;
  /** -1..1 vertical gaze offset (positive = down, toward the mic). */
  gazeY?: number;
  /** When true, the mouth area pulses on a speech cadence. */
  speaking?: boolean;
}

interface Layer {
  key: number;
  expr: JoiExpression;
  visible: boolean;
}

export function AnimatedJoi({
  expression,
  size = 480,
  className = "",
  level = 0,
  gazeX = 0,
  gazeY = 0,
  speaking = false,
}: Props) {
  const keyRef = useRef(1);
  const prevExpr = useRef<JoiExpression>(expression);
  const [layers, setLayers] = useState<Layer[]>([
    { key: 0, expr: expression, visible: true },
  ]);
  const [cadence, setCadence] = useState(0);

  useEffect(() => {
    if (prevExpr.current === expression) return;
    prevExpr.current = expression;
    const newKey = keyRef.current++;
    setLayers((prev) => [
      ...prev.map((l) => ({ ...l, visible: false })),
      { key: newKey, expr: expression, visible: true },
    ]);
    const t = setTimeout(() => {
      setLayers((prev) => prev.filter((l) => l.key === newKey));
    }, 420);
    return () => clearTimeout(t);
  }, [expression]);

  // Speech cadence — rhythmic open/close pulse for the mouth area.
  useEffect(() => {
    if (!speaking) {
      setCadence(0);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const dt = (t - start) / 1000;
      // mix two sine waves for organic syllables
      const v = (Math.sin(dt * 9) * 0.5 + Math.sin(dt * 14 + 1.3) * 0.5 + 1) / 2;
      setCadence(v);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [speaking]);

  const pulse = 1 + Math.min(0.06, Math.max(0, level) * 0.18);
  const gx = Math.max(-1, Math.min(1, gazeX)) * 6;
  const gy = Math.max(-1, Math.min(1, gazeY)) * 8;
  const mouthScale = speaking ? 1 + cadence * 0.08 : 1;

  return (
    <div
      className={`relative ${className}`}
      style={{
        width: size,
        height: size,
        transform: `scale(${pulse}) translate(${gx}px, ${gy}px)`,
        transition: "transform 120ms ease-out",
      }}
    >
      {layers.map((l) => (
        <div
          key={l.key}
          className="absolute inset-0"
          style={{
            opacity: l.visible ? 1 : 0,
            // Only scale for exit — never start at 0.94 which causes blank flash
            transform: l.visible ? "scale(1)" : "scale(0.97)",
            filter: l.visible ? "blur(0px)" : "blur(1.5px)",
            // Outgoing layers stay visible longer (400ms) so new one fades IN over them
            transition: l.visible
              ? "opacity 180ms ease-in, transform 180ms ease-out, filter 180ms ease-out"
              : "opacity 400ms ease-out, transform 400ms ease-out, filter 400ms ease-out",
          }}
        >
          <JoiMascot
            expression={l.expr}
            size={size}
            mouthOpen={speaking ? cadence : undefined}
          />
        </div>
      ))}
    </div>
  );
}