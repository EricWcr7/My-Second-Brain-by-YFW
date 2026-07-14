interface Point {
  x: number;
  y: number;
}

interface Signal {
  fromIndex: number;
  toIndex: number;
  phase: number;
}

const NODES: Point[] = [
  { x: 380, y: 407 }, { x: 500, y: 357 }, { x: 490, y: 454 },
  { x: 349, y: 506 }, { x: 472, y: 567 }, { x: 356, y: 601 },
  { x: 382, y: 705 }, { x: 548, y: 747 }, { x: 613, y: 319 },
  { x: 745, y: 336 }, { x: 745, y: 439 }, { x: 679, y: 504 },
  { x: 853, y: 391 }, { x: 940, y: 433 }, { x: 636, y: 569 },
  { x: 873, y: 505 }, { x: 965, y: 535 }, { x: 940, y: 613 },
  { x: 786, y: 641 }, { x: 884, y: 686 }, { x: 795, y: 721 },
  { x: 854, y: 773 }, { x: 696, y: 760 },
];

const EDGES: [number, number][] = [
  [0, 1], [0, 2], [0, 3], [1, 2], [1, 8], [2, 4], [3, 5], [3, 4],
  [4, 6], [4, 14], [6, 7], [7, 22], [8, 9], [8, 14], [9, 10], [10, 11],
  [10, 12], [11, 14], [12, 13], [12, 15], [13, 16], [14, 15], [14, 17],
  [14, 18], [14, 20], [15, 16], [16, 17], [17, 19], [18, 19], [18, 20],
  [19, 21], [20, 21], [20, 22],
];

const IDLE_PATHS: number[][] = [
  [0, 1, 8, 9, 10, 12, 15, 16, 17, 19, 21],
  [6, 7, 22, 20, 18, 14, 11, 10],
  [5, 3, 4, 6, 7],
];

const HUB = 14;
const WAKE_RADIUS = 180;
const MAX_PARTICLES = 8;
const IDLE_SEGMENT_MS = 1_700;

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
  let pointerInside = false;
  let touchUntil = -Infinity;
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
    return {
      x: (node.x / 1254) * width,
      y: (node.y / 1254) * height,
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
    const ambientNodes = new Map<number, number>();
    const ambientSignals: Signal[] = reduced || active.size
      ? []
      : IDLE_PATHS.map((path, index) => {
        const progress = ((now / IDLE_SEGMENT_MS) + index * 1.7) % (path.length - 1);
        const segment = Math.floor(progress);
        const phase = progress - segment;
        const fromIndex = path[segment];
        const toIndex = path[segment + 1];
        if (phase < 0.24) {
          ambientNodes.set(fromIndex, Math.max(ambientNodes.get(fromIndex) || 0, 0.42 * (1 - phase / 0.24)));
        }
        if (phase > 0.76) {
          ambientNodes.set(toIndex, Math.max(ambientNodes.get(toIndex) || 0, 0.42 * ((phase - 0.76) / 0.24)));
        }
        return { fromIndex, toIndex, phase };
      });

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
      if (strength > 0) {
        ctx.strokeStyle = rgba(palette.accent, 0.12 + strength * 0.7);
        ctx.lineWidth = 0.8 + strength * 1.2;
        ctx.setLineDash([]);
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);

    points.forEach((point, index) => {
      const p = index === HUB ? 1 : Math.max(active.get(index) || 0, ambientNodes.get(index) || 0);
      const d = displaced(point);
      const radius = index === HUB ? 10 : 5 + p * 3;
      if (p > 0) {
        const glow = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, radius * 4.5);
        glow.addColorStop(0, rgba(palette.accent, index === HUB ? 0.8 : p * 0.7));
        glow.addColorStop(1, rgba(palette.accent, 0));
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(d.x, d.y, radius * 4.5, 0, Math.PI * 2);
        ctx.fill();
      }
      if (p > 0) {
        ctx.beginPath();
        ctx.arc(d.x, d.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = rgba(palette.accent, 0.26 + p * 0.52);
        ctx.fill();
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = rgba(palette.accent, 0.72 + p * 0.28);
        ctx.stroke();
      }
    });

    const activeEdges = EDGES.filter(([a, b]) => active.has(a) || active.has(b));
    const signalEdges = activeEdges.slice(0, MAX_PARTICLES);
    signalEdges.forEach(([a, b], index) => {
      const fromIndex = b !== HUB && a !== HUB ? (distanceToHub(a) < distanceToHub(b) ? b : a) : a;
      const toIndex = fromIndex === a ? b : a;
      const from = displaced(points[fromIndex]);
      const to = displaced(points[toIndex]);
      const phase = ((now / 1150) + index / signalEdges.length) % 1;
      const x = from.x + (to.x - from.x) * phase;
      const y = from.y + (to.y - from.y) * phase;
      ctx.beginPath();
      ctx.arc(x, y, 2.2, 0, Math.PI * 2);
      ctx.fillStyle = palette.accent;
      ctx.shadowColor = palette.accent;
      ctx.shadowBlur = 10;
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    ambientSignals.forEach(({ fromIndex, toIndex, phase }) => {
      const from = points[fromIndex];
      const to = points[toIndex];
      for (let trail = 4; trail >= 0; trail -= 1) {
        const trailPhase = Math.max(0, phase - trail * 0.045);
        const strength = 1 - trail / 5;
        const x = from.x + (to.x - from.x) * trailPhase;
        const y = from.y + (to.y - from.y) * trailPhase;
        ctx.beginPath();
        ctx.arc(x, y, 1.1 + strength * 1.2, 0, Math.PI * 2);
        ctx.fillStyle = rgba(palette.accent, 0.08 + strength * 0.5);
        ctx.shadowColor = palette.accent;
        ctx.shadowBlur = trail === 0 ? 9 : 4;
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    });
  };

  const tick = (now: number) => {
    const elapsed = Math.min(64, now - previous);
    previous = now;
    const awake = pointerInside || now < touchUntil;
    const target = awake ? 1 : 0;
    wake += (target - wake) * Math.min(1, elapsed / 600);
    field.dataset.brainState = wake > 0.08 ? "awake" : "idle";
    field.style.setProperty("--brain-wake-radius", `${WAKE_RADIUS * wake}px`);
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
    field.style.setProperty("--brain-pointer-x", `${pointer.x}px`);
    field.style.setProperty("--brain-pointer-y", `${pointer.y}px`);
    if (event.pointerType === "touch") touchUntil = performance.now() + 900;
    else pointerInside = true;
  };

  const relax = () => {
    pointerInside = false;
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
      field.style.setProperty("--brain-wake-radius", "0px");
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

  field.addEventListener("pointerenter", wakeAt);
  field.addEventListener("pointermove", wakeAt);
  field.addEventListener("pointerdown", wakeAt);
  field.addEventListener("pointerleave", relax);
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
