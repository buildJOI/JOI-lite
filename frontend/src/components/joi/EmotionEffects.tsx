import { useEffect, useState } from "react";
import type { JoiExpression } from "./JoiMascot";

interface Props {
  expression: JoiExpression;
  size?: number;
}

/**
 * Overlay effects that float around the mascot per emotion:
 *  - love     → floating hearts
 *  - sad      → falling tears
 *  - sleep/sleepy → drifting Zzz
 *  - excited  → sunglasses drop + sparkles
 *  - frustrated → steam puffs + anger vein
 *  - laughing → bouncing "ha"
 */
export function EmotionEffects({ expression, size = 520 }: Props) {
  // Re-mount keyframes when expression changes so animations restart.
  const [key, setKey] = useState(0);
  useEffect(() => setKey((k) => k + 1), [expression]);

  return (
    <div
      key={key}
      className="pointer-events-none absolute inset-0 z-10 overflow-visible"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {expression === "love" && <Hearts />}
      {(expression === "sad" || expression === "concerned") && <Tears />}
      {(expression === "sleep" || expression === "sleepy") && <Zzz />}
      {expression === "excited" && <Sunglasses />}
      {expression === "frustrated" && <AngerFx />}
      {expression === "laughing" && <LaughFx />}
    </div>
  );
}

function Hearts() {
  const hearts = [
    { left: "18%", delay: "0s", scale: 1 },
    { left: "42%", delay: "0.7s", scale: 1.3 },
    { left: "66%", delay: "0.3s", scale: 0.9 },
    { left: "80%", delay: "1.1s", scale: 1.1 },
  ];
  return (
    <>
      <style>{`
        @keyframes fxHeart { 0%{opacity:0;transform:translateY(20px) scale(.6)} 15%{opacity:1} 100%{opacity:0;transform:translateY(-140px) scale(1.1)} }
      `}</style>
      {hearts.map((h, i) => (
        <div
          key={i}
          className="absolute top-[40%]"
          style={{
            left: h.left,
            animation: `fxHeart 2.6s ${h.delay} ease-out infinite`,
            transform: `scale(${h.scale})`,
            filter: "drop-shadow(0 0 12px rgba(237,122,166,0.7))",
          }}
        >
          <svg width="28" height="26" viewBox="0 0 28 26">
            <path d="M14 24 C 2 16, 2 4, 9 4 C 12 4, 14 7, 14 9 C 14 7, 16 4, 19 4 C 26 4, 26 16, 14 24Z" fill="#ed7aa6" stroke="#5a1638" strokeWidth="1.2" />
          </svg>
        </div>
      ))}
    </>
  );
}

function Tears() {
  return (
    <>
      <style>{`
        @keyframes fxTear { 0%{opacity:0;transform:translateY(0) scaleY(.6)} 15%{opacity:1} 100%{opacity:0;transform:translateY(110px) scaleY(1)} }
      `}</style>
      {[
        { left: "28%", delay: "0s" },
        { left: "62%", delay: "0.4s" },
        { left: "30%", delay: "1s" },
        { left: "64%", delay: "1.3s" },
      ].map((t, i) => (
        <div
          key={i}
          className="absolute top-[42%]"
          style={{
            left: t.left,
            animation: `fxTear 1.8s ${t.delay} ease-in infinite`,
            filter: "drop-shadow(0 0 6px rgba(120,200,255,0.7))",
          }}
        >
          <svg width="14" height="22" viewBox="0 0 14 22">
            <path d="M7 1 C 3 10, 1 15, 7 21 C 13 15, 11 10, 7 1Z" fill="#7cc3ff" stroke="#2a6da6" strokeWidth="0.8" />
          </svg>
        </div>
      ))}
    </>
  );
}

function Zzz() {
  return (
    <>
      <style>{`
        @keyframes fxZ { 0%{opacity:0;transform:translate(0,0) scale(.6)} 20%{opacity:1} 100%{opacity:0;transform:translate(40px,-80px) scale(1.4)} }
      `}</style>
      {[0, 0.8, 1.6].map((d, i) => (
        <div
          key={i}
          className="absolute right-[18%] top-[18%] font-pixel text-3xl"
          style={{
            color: "#a480cf",
            animation: `fxZ 2.4s ${d}s ease-out infinite`,
            textShadow: "0 0 12px rgba(164,128,207,0.6)",
          }}
        >
          z
        </div>
      ))}
    </>
  );
}

function Sunglasses() {
  return (
    <>
      <style>{`
        @keyframes fxShades { 0%{transform:translateY(-60%);opacity:0} 60%{transform:translateY(2%);opacity:1} 75%{transform:translateY(-2%)} 100%{transform:translateY(0);opacity:1} }
        @keyframes fxSpark { 0%,100%{opacity:0;transform:scale(.4)} 50%{opacity:1;transform:scale(1)} }
      `}</style>
      <div
        className="absolute left-1/2 top-[28%] -translate-x-1/2"
        style={{ animation: "fxShades 0.9s cubic-bezier(.5,1.8,.4,1) forwards" }}
      >
        <svg width="62%" height="auto" viewBox="0 0 200 70" style={{ width: "62%", minWidth: 220 }}>
          <rect x="10" y="20" width="80" height="40" rx="10" fill="#0a0a0a" stroke="#1a1a1a" strokeWidth="3" />
          <rect x="110" y="20" width="80" height="40" rx="10" fill="#0a0a0a" stroke="#1a1a1a" strokeWidth="3" />
          <rect x="88" y="30" width="24" height="6" fill="#1a1a1a" />
          <path d="M22 28 L40 50" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" opacity="0.85" />
          <path d="M122 28 L140 50" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" opacity="0.85" />
        </svg>
      </div>
      {[
        { left: "12%", top: "20%", d: "0s" },
        { left: "82%", top: "18%", d: "0.4s" },
        { left: "22%", top: "62%", d: "0.8s" },
        { left: "76%", top: "60%", d: "0.2s" },
      ].map((s, i) => (
        <div
          key={i}
          className="absolute"
          style={{
            left: s.left,
            top: s.top,
            color: "#FFC72A",
            animation: `fxSpark 1.4s ${s.d} ease-in-out infinite`,
            textShadow: "0 0 10px rgba(255,199,42,0.8)",
            fontSize: 22,
          }}
        >
          ✦
        </div>
      ))}
    </>
  );
}

function AngerFx() {
  return (
    <>
      <style>{`
        @keyframes fxSteam { 0%{opacity:0;transform:translateY(0) scale(.6)} 25%{opacity:.9} 100%{opacity:0;transform:translateY(-80px) scale(1.4)} }
        @keyframes fxVein { 0%,100%{opacity:.4;transform:scale(.95)} 50%{opacity:1;transform:scale(1.1)} }
      `}</style>
      {[
        { left: "18%", delay: "0s" },
        { left: "78%", delay: "0.4s" },
      ].map((s, i) => (
        <div
          key={i}
          className="absolute top-[12%] h-6 w-6 rounded-full"
          style={{
            left: s.left,
            background: "radial-gradient(circle, rgba(220,220,220,0.85), rgba(220,220,220,0) 70%)",
            animation: `fxSteam 1.5s ${s.delay} ease-out infinite`,
          }}
        />
      ))}
      <div
        className="absolute right-[22%] top-[20%]"
        style={{ animation: "fxVein 0.7s ease-in-out infinite" }}
      >
        <svg width="34" height="34" viewBox="0 0 40 40">
          <path
            d="M20 6 L24 16 L34 18 L26 22 L30 32 L20 26 L10 32 L14 22 L6 18 L16 16 Z"
            fill="#d73a1f"
            stroke="#5a1410"
            strokeWidth="1.5"
          />
        </svg>
      </div>
    </>
  );
}

function LaughFx() {
  return (
    <>
      <style>{`
        @keyframes fxHa { 0%{opacity:0;transform:translateY(10px) rotate(-8deg)} 20%{opacity:1} 100%{opacity:0;transform:translateY(-60px) rotate(8deg)} }
      `}</style>
      {[
        { left: "12%", delay: "0s" },
        { left: "78%", delay: "0.5s" },
        { left: "30%", delay: "1s" },
      ].map((h, i) => (
        <div
          key={i}
          className="absolute top-[30%] font-pixel text-xl"
          style={{
            left: h.left,
            color: "#FFC72A",
            animation: `fxHa 1.6s ${h.delay} ease-out infinite`,
            textShadow: "0 0 10px rgba(255,199,42,0.7)",
          }}
        >
          ha!
        </div>
      ))}
    </>
  );
}
