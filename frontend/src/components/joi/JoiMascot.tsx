import { useEffect, useState, type ReactElement } from "react";

export type JoiExpression =
  | "happy"
  | "blink"
  | "lookDown"
  | "thinking"
  | "listening"
  | "speaking"
  | "excited"
  | "surprised"
  | "confused"
  | "sad"
  | "curious"
  | "concerned"
  | "sleep"
  | "laughing"
  | "wink"
  | "determined"
  | "cheeky"
  | "sleepy"
  | "frustrated"
  | "love"
  | "talking";

interface Props {
  expression?: JoiExpression;
  size?: number;
  className?: string;
  /** 0-1 cadence value drives mouth open/close during speech */
  mouthOpen?: number;
}

/**
 * Pixel-art JOI face inspired by classic 8-bit emoji art.
 * 32x32 grid, rendered as crisp SVG rects.
 *
 * Color codes:
 *  1 = outline (dark brown)
 *  2 = face fill (yellow)
 *  3 = face shadow (golden)
 *  4 = mouth outline (deep magenta)
 *  5 = white (teeth / eye highlight / shine)
 *  6 = blush / tongue (pink)
 *  7 = eye (black)
 *  8 = sleep Z (lavender)
 */

const COLORS: Record<number, string> = {
  1: "#3a230a",
  2: "#FFC72A",
  3: "#E89220",
  4: "#5a1638",
  5: "#ffffff",
  6: "#ed7aa6",
  7: "#1a0f04",
  8: "#a480cf",
};

// Build the round face: outline ring + fill + bottom-right shadow band.
const FACE: number[][] = (() => {
  const N = 32;
  const cx = 15.5;
  const cy = 16;
  const r = 14.8;
  const g: number[][] = Array.from({ length: N }, () => Array(N).fill(0));
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const d = Math.hypot(x - cx, y - cy);
      if (d <= r && d > r - 1.15) g[y][x] = 1;
      else if (d <= r - 1.15) {
        const sx = x - cx;
        const sy = y - cy;
        // Shadow band on the bottom + bottom-right inner edge
        if (d > r - 2.4 && sy + sx * 0.4 > 4) g[y][x] = 3;
        else g[y][x] = 2;
      }
    }
  }
  // Top-left shine (zigzag white highlight)
  const shine: [number, number][] = [
    [10, 4], [11, 4],
    [8, 5], [9, 5], [10, 5],
    [7, 6], [8, 6],
    [6, 7], [7, 7],
    [6, 8],
  ];
  for (const [x, y] of shine) if (g[y][x] === 2) g[y][x] = 5;
  return g;
})();

type Cell = [number, number, number];

function eyesFor(expr: JoiExpression): Cell[] {
  const cells: Cell[] = [];
  const add = (pts: [number, number][], c: number) => pts.forEach(([x, y]) => cells.push([x, y, c]));

  // Default eye anchors: left x=10..12, right x=19..21
  const tallLeft: [number, number][] = [];
  const tallRight: [number, number][] = [];
  for (let y = 11; y <= 17; y++) {
    for (let x = 10; x <= 12; x++) tallLeft.push([x, y]);
    for (let x = 19; x <= 21; x++) tallRight.push([x, y]);
  }

  switch (expr) {
    case "happy":
    case "curious": {
      add(tallLeft, 7);
      add(tallRight, 7);
      add([[12, 12], [21, 12]], 5); // white highlight top-right of each eye
      break;
    }
    case "excited":
    case "speaking": {
      add(tallLeft, 7);
      add(tallRight, 7);
      add([[12, 12], [21, 12], [11, 13], [20, 13]], 5);
      break;
    }
    case "blink": {
      add([
        [10, 14], [11, 14], [12, 14],
        [19, 14], [20, 14], [21, 14],
      ], 7);
      break;
    }
    case "lookDown":
    case "listening": {
      add([
        [10, 15], [11, 15], [12, 15],
        [10, 16], [11, 16], [12, 16],
        [10, 17], [11, 17], [12, 17],
        [19, 15], [20, 15], [21, 15],
        [19, 16], [20, 16], [21, 16],
        [19, 17], [20, 17], [21, 17],
      ], 7);
      break;
    }
    case "thinking":
    case "confused":
    case "concerned": {
      // brow + shorter eyes
      add([[9, 10], [10, 10], [11, 11], [12, 11]], 1);
      add([[19, 11], [20, 11], [21, 10], [22, 10]], 1);
      for (let y = 13; y <= 16; y++) {
        for (let x = 10; x <= 12; x++) cells.push([x, y, 7]);
        for (let x = 19; x <= 21; x++) cells.push([x, y, 7]);
      }
      add([[12, 13], [21, 13]], 5);
      break;
    }
    case "surprised": {
      for (let y = 11; y <= 18; y++) {
        for (let x = 9; x <= 12; x++) cells.push([x, y, 7]);
        for (let x = 19; x <= 22; x++) cells.push([x, y, 7]);
      }
      add([[11, 12], [12, 12], [21, 12], [22, 12]], 5);
      break;
    }
    case "sad": {
      add([
        [10, 13], [11, 13], [12, 13],
        [10, 14], [11, 14], [12, 14],
        [10, 15], [11, 15], [12, 15],
        [19, 13], [20, 13], [21, 13],
        [19, 14], [20, 14], [21, 14],
        [19, 15], [20, 15], [21, 15],
      ], 7);
      break;
    }
    case "sleep": {
      add([
        [10, 14], [11, 13], [12, 13],
        [19, 13], [20, 13], [21, 14],
      ], 1);
      add([[24, 6], [25, 6], [26, 6], [26, 7], [25, 8], [24, 9], [25, 9], [26, 9]], 8);
      break;
    }
    case "sleepy": {
      // half-lidded eyes
      add([[10, 13], [11, 13], [12, 13], [19, 13], [20, 13], [21, 13]], 1);
      add([
        [10, 14], [11, 14], [12, 14],
        [19, 14], [20, 14], [21, 14],
        [10, 15], [11, 15], [12, 15],
        [19, 15], [20, 15], [21, 15],
      ], 7);
      add([[24, 6], [25, 6], [26, 6], [26, 7], [25, 8], [24, 9], [25, 9], [26, 9]], 8);
      break;
    }
    case "laughing": {
      // ^_^ closed arcs
      add([
        [9, 13], [12, 13], [10, 14], [11, 14],
        [19, 13], [22, 13], [20, 14], [21, 14],
      ], 1);
      break;
    }
    case "wink": {
      // left open eye + right closed
      for (let y = 11; y <= 17; y++) for (let x = 10; x <= 12; x++) cells.push([x, y, 7]);
      add([[12, 12]], 5);
      add([[19, 14], [20, 14], [21, 14], [19, 13], [22, 13]], 1);
      break;
    }
    case "determined": {
      // angled brows + small focused eyes
      add([[9, 11], [10, 11], [11, 12], [12, 12]], 1);
      add([[19, 12], [20, 12], [21, 11], [22, 11]], 1);
      for (let y = 14; y <= 16; y++) {
        for (let x = 10; x <= 12; x++) cells.push([x, y, 7]);
        for (let x = 19; x <= 21; x++) cells.push([x, y, 7]);
      }
      add([[12, 14], [21, 14]], 5);
      break;
    }
    case "cheeky": {
      // one winked eye + one open
      for (let y = 11; y <= 17; y++) for (let x = 19; x <= 21; x++) cells.push([x, y, 7]);
      add([[21, 12]], 5);
      add([[9, 13], [10, 14], [11, 14], [12, 13]], 1);
      break;
    }
    case "frustrated": {
      // >< angry tight eyes
      add([
        [9, 12], [10, 13], [11, 14], [12, 15], [12, 12], [11, 13], [10, 14], [9, 15],
        [19, 12], [20, 13], [21, 14], [22, 15], [22, 12], [21, 13], [20, 14], [19, 15],
      ], 1);
      break;
    }
    case "love": {
      // heart eyes (pink)
      const heart: [number, number][] = [
        [9, 12], [10, 12], [12, 12], [13, 12],
        [9, 13], [10, 13], [11, 13], [12, 13], [13, 13],
        [10, 14], [11, 14], [12, 14],
        [11, 15],
      ];
      heart.forEach(([x, y]) => cells.push([x - 1, y, 6]));
      heart.forEach(([x, y]) => cells.push([x + 9, y, 6]));
      // highlights
      add([[9, 12], [18, 12]], 5);
      break;
    }
    case "talking": {
      add(tallLeft, 7);
      add(tallRight, 7);
      add([[12, 12], [21, 12]], 5);
      break;
    }
  }
  return cells;
}

function blushFor(_expr: JoiExpression): Cell[] {
  return [
    [6, 19, 6], [7, 19, 6], [8, 19, 6],
    [23, 19, 6], [24, 19, 6], [25, 19, 6],
  ];
}

function mouthFor(expr: JoiExpression): Cell[] {
  const cells: Cell[] = [];
  const add = (pts: [number, number][], c: number) => pts.forEach(([x, y]) => cells.push([x, y, c]));

  switch (expr) {
    case "happy":
    case "curious":
    case "listening":
    case "lookDown":
    case "blink": {
      // Open smile w/ teeth bar + tongue (signature look)
      add([
        [12, 20], [13, 20], [14, 20], [15, 20], [16, 20], [17, 20], [18, 20], [19, 20],
        [11, 21], [20, 21],
        [11, 22], [20, 22],
        [12, 23], [19, 23],
        [13, 24], [14, 24], [15, 24], [16, 24], [17, 24], [18, 24],
      ], 4);
      // teeth (white bar)
      add([[13, 21], [14, 21], [15, 21], [16, 21], [17, 21], [18, 21]], 5);
      // tongue (pink)
      add([[13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22]], 6);
      add([[13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23]], 6);
      break;
    }
    case "excited":
    case "speaking":
    case "surprised": {
      add([
        [11, 19], [12, 19], [13, 19], [14, 19], [15, 19], [16, 19], [17, 19], [18, 19], [19, 19], [20, 19],
        [10, 20], [21, 20],
        [10, 21], [21, 21],
        [10, 22], [21, 22],
        [11, 23], [20, 23],
        [12, 24], [13, 24], [14, 24], [15, 24], [16, 24], [17, 24], [18, 24], [19, 24],
      ], 4);
      add([[12, 20], [13, 20], [14, 20], [15, 20], [16, 20], [17, 20], [18, 20], [19, 20]], 5);
      add([
        [11, 21], [12, 21], [13, 21], [14, 21], [15, 21], [16, 21], [17, 21], [18, 21], [19, 21], [20, 21],
        [11, 22], [12, 22], [13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22], [19, 22], [20, 22],
        [12, 23], [13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23], [19, 23],
      ], 6);
      break;
    }
    case "sad":
    case "concerned": {
      add([
        [11, 24], [12, 23], [13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22], [19, 23], [20, 24],
      ], 4);
      break;
    }
    case "confused":
    case "thinking": {
      add([
        [12, 23], [13, 23], [14, 23], [15, 22], [16, 22], [17, 21], [18, 21], [19, 21],
      ], 4);
      break;
    }
    case "sleep":
    case "sleepy": {
      add([[14, 22], [15, 22], [16, 22], [17, 22]], 4);
      break;
    }
    case "laughing": {
      // wide open laugh
      add([
        [10, 19], [11, 19], [12, 19], [13, 19], [14, 19], [15, 19], [16, 19], [17, 19], [18, 19], [19, 19], [20, 19], [21, 19],
        [10, 20], [21, 20], [10, 21], [21, 21], [10, 22], [21, 22],
        [11, 23], [20, 23], [12, 24], [13, 24], [14, 24], [15, 24], [16, 24], [17, 24], [18, 24], [19, 24],
      ], 4);
      add([[11, 20], [12, 20], [13, 20], [14, 20], [15, 20], [16, 20], [17, 20], [18, 20], [19, 20], [20, 20]], 5);
      add([
        [11, 21], [12, 21], [13, 21], [14, 21], [15, 21], [16, 21], [17, 21], [18, 21], [19, 21], [20, 21],
        [11, 22], [12, 22], [13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22], [19, 22], [20, 22],
        [12, 23], [13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23], [19, 23],
      ], 6);
      break;
    }
    case "wink":
    case "cheeky": {
      // smile + sticking tongue out
      add([
        [12, 20], [13, 20], [14, 20], [15, 20], [16, 20], [17, 20], [18, 20], [19, 20],
        [11, 21], [20, 21], [12, 22], [19, 22],
        [13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23],
      ], 4);
      add([[14, 21], [15, 21], [16, 21], [17, 21]], 5);
      add([[14, 22], [15, 22], [16, 22], [17, 22], [14, 23], [15, 23], [16, 23], [17, 23], [15, 24], [16, 24]], 6);
      break;
    }
    case "determined": {
      // small smirk
      add([[13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22]], 4);
      break;
    }
    case "frustrated": {
      // gritted teeth
      add([
        [11, 21], [12, 21], [13, 21], [14, 21], [15, 21], [16, 21], [17, 21], [18, 21], [19, 21], [20, 21],
        [11, 23], [12, 23], [13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23], [19, 23], [20, 23],
        [11, 22], [20, 22],
      ], 4);
      add([
        [12, 22], [13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22], [19, 22],
      ], 5);
      add([[13, 22], [15, 22], [17, 22], [19, 22]], 4);
      break;
    }
    case "love": {
      // open smile + tongue (same as happy)
      add([
        [12, 20], [13, 20], [14, 20], [15, 20], [16, 20], [17, 20], [18, 20], [19, 20],
        [11, 21], [20, 21], [11, 22], [20, 22], [12, 23], [19, 23],
        [13, 24], [14, 24], [15, 24], [16, 24], [17, 24], [18, 24],
      ], 4);
      add([[13, 21], [14, 21], [15, 21], [16, 21], [17, 21], [18, 21]], 5);
      add([[13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22], [13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23]], 6);
      break;
    }
    case "talking": {
      add([
        [13, 20], [14, 20], [15, 20], [16, 20], [17, 20], [18, 20],
        [12, 21], [19, 21], [12, 22], [19, 22], [13, 23], [14, 23], [15, 23], [16, 23], [17, 23], [18, 23],
      ], 4);
      add([[13, 22], [14, 22], [15, 22], [16, 22], [17, 22], [18, 22]], 6);
      break;
    }
  }
  return cells;
}

export function JoiMascot({ expression = "happy", size = 480, className = "", mouthOpen }: Props) {
  const [blink, setBlink] = useState(false);

  useEffect(() => {
    if (expression !== "happy") return;
    let t: ReturnType<typeof setTimeout>;
    const loop = () => {
      setBlink(true);
      setTimeout(() => setBlink(false), 130);
      t = setTimeout(loop, 2500 + Math.random() * 3500);
    };
    t = setTimeout(loop, 1500 + Math.random() * 2000);
    return () => clearTimeout(t);
  }, [expression]);

  const effective: JoiExpression = blink && expression === "happy" ? "blink" : expression;

  // When speaking, pulse mouth between "talking" (open) and a smaller open
  const effectiveMouth: JoiExpression =
    mouthOpen !== undefined && expression === "talking"
      ? mouthOpen > 0.5 ? "excited" : "talking"
      : effective;

  // Compose grid: face → blush → eyes → mouth (later layers overwrite)
  const grid = FACE.map((row) => row.slice());
  const overlay: Cell[] = [
    ...blushFor(effective),
    ...eyesFor(effective),
    ...mouthFor(effectiveMouth),
  ];
  for (const [x, y, c] of overlay) {
    if (grid[y] && grid[y][x] !== undefined && grid[y][x] !== 0) grid[y][x] = c;
  }

  const rects: ReactElement[] = [];
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      const v = grid[y][x];
      if (v === 0) continue;
      rects.push(
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={COLORS[v]} />
      );
    }
  }

  return (
    <svg
      viewBox="0 0 32 32"
      width={size}
      height={size}
      shapeRendering="crispEdges"
      className={className}
      style={{
        imageRendering: "pixelated",
        filter:
          "drop-shadow(0 0 30px rgba(255,199,42,0.35)) drop-shadow(0 0 60px rgba(248,157,37,0.25))",
      }}
      aria-label="JOI mascot"
      role="img"
    >
      {rects}
    </svg>
  );
}