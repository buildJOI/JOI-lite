import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  size: number;
  life: number;
  maxLife: number;
  drift: number;
}

interface Props {
  density?: number; // particles count target
  className?: string;
}

export function SparkleField({ density = 38, className = "" }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const particles: Particle[] = [];
    const make = (): Particle => ({
      x: Math.random() * w,
      y: Math.random() * h,
      size: 1.2 + Math.random() * 2.6,
      life: 0,
      maxLife: 180 + Math.random() * 260,
      drift: (Math.random() - 0.5) * 0.15,
    });
    for (let i = 0; i < density; i++) {
      const p = make();
      p.life = Math.random() * p.maxLife;
      particles.push(p);
    }

    const drawSparkle = (p: Particle, alpha: number) => {
      const r = p.size;
      ctx.save();
      ctx.translate(p.x, p.y);
      // glow
      const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, r * 6);
      grad.addColorStop(0, `rgba(234, 242, 215, ${0.5 * alpha})`);
      grad.addColorStop(0.4, `rgba(164, 128, 207, ${0.25 * alpha})`);
      grad.addColorStop(1, "rgba(164, 128, 207, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(0, 0, r * 6, 0, Math.PI * 2);
      ctx.fill();
      // 4-point star
      ctx.fillStyle = `rgba(234, 242, 215, ${0.95 * alpha})`;
      ctx.beginPath();
      ctx.moveTo(0, -r * 2.2);
      ctx.lineTo(r * 0.5, -r * 0.5);
      ctx.lineTo(r * 2.2, 0);
      ctx.lineTo(r * 0.5, r * 0.5);
      ctx.lineTo(0, r * 2.2);
      ctx.lineTo(-r * 0.5, r * 0.5);
      ctx.lineTo(-r * 2.2, 0);
      ctx.lineTo(-r * 0.5, -r * 0.5);
      ctx.closePath();
      ctx.fill();
      // core
      ctx.fillStyle = `rgba(164, 128, 207, ${alpha})`;
      ctx.beginPath();
      ctx.arc(0, 0, r * 0.6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    };

    let raf = 0;
    const tick = () => {
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.life += 1;
        p.y -= 0.08;
        p.x += p.drift;
        const t = p.life / p.maxLife;
        const alpha = Math.sin(Math.PI * t); // ease in/out
        drawSparkle(p, Math.max(0, alpha));
        if (p.life >= p.maxLife || p.y < -10 || p.x < -10 || p.x > w + 10) {
          particles[i] = make();
          particles[i].life = 0;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [density]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      aria-hidden="true"
    />
  );
}
