interface Point {
  x: number;
  y: number;
}

const NODES: Point[] = [
  { x: 80, y: 95 }, { x: 78, y: 125 }, { x: 82, y: 155 },
  { x: 115, y: 80 }, { x: 113, y: 110 }, { x: 117, y: 140 },
  { x: 150, y: 72 }, { x: 160, y: 118 }, { x: 150, y: 162 },
  { x: 190, y: 78 }, { x: 188, y: 108 }, { x: 192, y: 138 },
  { x: 190, y: 166 }, { x: 225, y: 92 }, { x: 223, y: 124 },
  { x: 227, y: 154 },
];

const EDGES: [number, number][] = [
  [0, 3], [0, 4], [1, 4], [1, 5], [2, 5], [3, 6], [4, 7], [5, 7],
  [6, 7], [7, 8], [6, 9], [7, 10], [7, 11], [8, 12], [9, 13], [10, 13],
  [11, 14], [12, 15], [13, 14], [14, 15],
];

const HUB = 7;
const WAKE_RADIUS = 180;
const MAX_PARTICLES = 8;

export function initBrainField(): void {
  const field = document.getElementById("brain-field");
  const canvas = document.getElementById("brain-canvas") as HTMLCanvasElement | null;
  if (!field || !canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  let width = 1;
  let height = 1;
  let ratio = 1;
  let visible = false;
  let frame = 0;
  let previous = performance.now();
  let lastInteraction = -Infinity;
  let wake = 0;
  let pointer: Point = { x: 0, y: 0 };
  let palette = readPalette();

  const resize = () => {
    const rect = field.getBoundingClientRect();
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    ratio = Math.min(2, devicePixelRatio || 1);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    if (motion.matches) draw(performance.now(), true);
  };

  const toCanvas = (node: Point): Point => {
    const scale = Math.min((width * 0.72) / 320, (height * 0.49) / 240);
    return {
      x: width * 0.5 + (node.x - 160) * scale,
      y: height * 0.47 + (node.y - 120) * scale,
    };
  };

  const proximity = (point: Point): number => {
    const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y);
    return Math.max(0, 1 - distance / WAKE_RADIUS) * wake;
  };

  const displaced = (point: Point): Point => {
    const p = proximity(point);
    if (!p) return point;
    const distance = Math.max(1, Math.hypot(pointer.x - point.x, pointer.y - point.y));
    const pull = Math.min(8, p * 8);
    return {
      x: point.x + ((pointer.x - point.x) / distance) * pull,
      y: point.y + ((pointer.y - point.y) / distance) * pull,
    };
  };

  const draw = (now: number, reduced = false) => {
    ctx.clearRect(0, 0, width, height);
    const points = NODES.map(toCanvas);
    const strongest = points
      .map((point, index) => ({ index, strength: reduced ? 0 : proximity(point) }))
      .sort((a, b) => b.strength - a.strength)
      .slice(0, 5);
    const active = new Map(strongest.filter((item) => item.strength > 0).map((item) => [item.index, item.strength]));

    ctx.lineCap = "round";
    for (const [fromIndex, toIndex] of EDGES) {
      const from = displaced(points[fromIndex]);
      const to = displaced(points[toIndex]);
      const strength = Math.max(active.get(fromIndex) || 0, active.get(toIndex) || 0);
      const midX = (from.x + to.x) / 2;
      const midY = (from.y + to.y) / 2;
      const controlPull = strength * 8;
      const distance = Math.max(1, Math.hypot(pointer.x - midX, pointer.y - midY));
      const controlX = midX + ((pointer.x - midX) / distance) * controlPull;
      const controlY = midY + ((pointer.y - midY) / distance) * controlPull;
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.quadraticCurveTo(controlX, controlY, to.x, to.y);
      ctx.strokeStyle = strength > 0 ? rgba(palette.accent, 0.32 + strength * 0.62) : rgba(palette.blue, 0.28);
      ctx.lineWidth = strength > 0 ? 1 + strength : 0.75;
      ctx.setLineDash(strength > 0 ? [] : [4, 7]);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    points.forEach((point, index) => {
      const p = active.get(index) || 0;
      const d = displaced(point);
      const radius = index === HUB ? 8 : 4.2 + p * 2.5;
      if (p > 0 || index === HUB) {
        const glow = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, radius * 4.5);
        glow.addColorStop(0, rgba(palette.accent, index === HUB ? 0.8 : p * 0.7));
        glow.addColorStop(1, rgba(palette.accent, 0));
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(d.x, d.y, radius * 4.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(d.x, d.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = index === HUB || p > 0.52 ? palette.accent : palette.surface;
      ctx.fill();
      ctx.lineWidth = 1.4;
      ctx.strokeStyle = p > 0 ? rgba(palette.accent, 0.8 + p * 0.2) : rgba(palette.blue, 0.72);
      ctx.stroke();
    });

    const activeEdges = EDGES.filter(([a, b]) => active.has(a) || active.has(b));
    const signalEdges = activeEdges.length ? activeEdges.slice(0, MAX_PARTICLES) : [EDGES[Math.floor(now / 4000) % EDGES.length]];
    signalEdges.forEach(([a, b], index) => {
      const fromIndex = activeEdges.length && b !== HUB && a !== HUB ? (distanceToHub(a) < distanceToHub(b) ? b : a) : a;
      const toIndex = fromIndex === a ? b : a;
      const from = displaced(points[fromIndex]);
      const to = displaced(points[toIndex]);
      const phase = ((now / (activeEdges.length ? 1150 : 3600)) + index / signalEdges.length) % 1;
      const x = from.x + (to.x - from.x) * phase;
      const y = from.y + (to.y - from.y) * phase;
      ctx.beginPath();
      ctx.arc(x, y, activeEdges.length ? 2.2 : 1.6, 0, Math.PI * 2);
      ctx.fillStyle = palette.accent;
      ctx.shadowColor = palette.accent;
      ctx.shadowBlur = activeEdges.length ? 10 : 5;
      ctx.fill();
      ctx.shadowBlur = 0;
    });
  };

  const tick = (now: number) => {
    const elapsed = Math.min(64, now - previous);
    previous = now;
    const awake = now - lastInteraction < 900;
    const target = awake ? 1 : 0;
    wake += (target - wake) * Math.min(1, elapsed / 600);
    field.dataset.brainState = wake > 0.08 ? "awake" : "idle";
    const px = ((pointer.x / width) - 0.5) * 8 * wake;
    const py = ((pointer.y / height) - 0.5) * 8 * wake;
    field.style.setProperty("--brain-shift-x", `${Math.max(-4, Math.min(4, px))}px`);
    field.style.setProperty("--brain-shift-y", `${Math.max(-4, Math.min(4, py))}px`);
    draw(now);
    if (visible && !motion.matches) frame = requestAnimationFrame(tick);
  };

  const wakeAt = (event: PointerEvent) => {
    const rect = field.getBoundingClientRect();
    pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    lastInteraction = performance.now();
  };

  const start = () => {
    if (frame || motion.matches || !visible) return;
    previous = performance.now();
    frame = requestAnimationFrame(tick);
  };
  const stop = () => {
    cancelAnimationFrame(frame);
    frame = 0;
  };
  const onMotion = () => {
    if (motion.matches) {
      stop();
      field.dataset.brainState = "reduced";
      wake = 0;
      draw(performance.now(), true);
    } else {
      field.dataset.brainState = "idle";
      start();
    }
  };

  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) start();
    else stop();
  });
  const resizeObserver = new ResizeObserver(resize);
  const themeObserver = new MutationObserver(() => {
    palette = readPalette();
    if (motion.matches) draw(performance.now(), true);
  });

  field.addEventListener("pointermove", wakeAt);
  field.addEventListener("pointerdown", wakeAt);
  motion.addEventListener("change", onMotion);
  observer.observe(field);
  resizeObserver.observe(field);
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  resize();
  onMotion();
}

function distanceToHub(index: number): number {
  const node = NODES[index];
  const hub = NODES[HUB];
  return Math.hypot(node.x - hub.x, node.y - hub.y);
}

function readPalette(): { accent: string; blue: string; surface: string } {
  const style = getComputedStyle(document.documentElement);
  return {
    accent: style.getPropertyValue("--accent").trim() || "#56cdd0",
    blue: style.getPropertyValue("--blue").trim() || "#6b9abd",
    surface: style.getPropertyValue("--surface-1").trim() || "#0d151c",
  };
}

function rgba(hex: string, alpha: number): string {
  const value = hex.replace("#", "").trim();
  if (!/^[0-9a-f]{6}$/i.test(value)) return hex;
  const n = Number.parseInt(value, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${Math.max(0, Math.min(1, alpha))})`;
}
