// 3D neural-network brain for the landing hero.
//
// A real anatomical brain mesh (MRI-derived, see CREDITS.md) rendered as a
// glowing solid surface so the silhouette, hemispheres and gyri folds are
// unmistakable, with a neural network layered on its surface: glowing neurons
// sampled across the mesh, synapse lines between them, and amber signals firing
// along them. Bloom for the glow.
//
// Interactions: parallax tilt, hover lights nearby synapses, the cursor nudges
// nodes (repel), and a click fires a radial burst. Colors track the live CSS
// theme and are tuned separately for dark/light so the brain stays legible and
// easy on the eyes in both. The loop pauses when the landing isn't visible;
// falls back to a CSS glow when WebGL is unavailable or motion is reduced.

import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { MeshSurfaceSampler } from "three/examples/jsm/math/MeshSurfaceSampler.js";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { effectiveTheme } from "./theme";

const BRAIN_URL = new URL("./assets/brain.stl", import.meta.url).href;

// ---- tunables --------------------------------------------------------------
const AMBER = new THREE.Color("#ffb454"); // warm highlight, fixed across themes
const NEIGHBORS = 3; // synapses per node (nearest neighbours)
const AMBIENT_SIGNALS = 46; // signals continuously firing
const MAX_SIGNALS = 260; // pool size (ambient + bursts)
const TARGET_RADIUS = 12; // model is normalized to roughly this radius

type Tier = { nodes: number; bloom: boolean };

function pickTier(): Tier {
  const mobile = window.matchMedia("(max-width: 760px)").matches;
  const weak = (navigator.hardwareConcurrency ?? 8) <= 4;
  if (mobile) return { nodes: 1000, bloom: false };
  if (weak) return { nodes: 1500, bloom: true };
  return { nodes: 2000, bloom: true };
}

function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

// Uniform-grid nearest-neighbour search -> unique undirected edges.
function buildEdges(pos: Float32Array, count: number, cell: number): Uint32Array {
  const grid = new Map<string, number[]>();
  const key = (a: number, b: number, c: number) => a + "," + b + "," + c;
  const ci = (v: number) => Math.floor(v / cell);
  for (let i = 0; i < count; i++) {
    const k = key(ci(pos[i * 3]), ci(pos[i * 3 + 1]), ci(pos[i * 3 + 2]));
    (grid.get(k) ?? grid.set(k, []).get(k)!).push(i);
  }
  const seen = new Set<number>();
  const edges: number[] = [];
  const near: { j: number; d: number }[] = [];
  for (let i = 0; i < count; i++) {
    const x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
    const cx = ci(x), cy = ci(y), cz = ci(z);
    near.length = 0;
    for (let a = -1; a <= 1; a++)
      for (let b = -1; b <= 1; b++)
        for (let c = -1; c <= 1; c++) {
          const bucket = grid.get(key(cx + a, cy + b, cz + c));
          if (!bucket) continue;
          for (const j of bucket) {
            if (j === i) continue;
            const dx = pos[j * 3] - x, dy = pos[j * 3 + 1] - y, dz = pos[j * 3 + 2] - z;
            near.push({ j, d: dx * dx + dy * dy + dz * dz });
          }
        }
    near.sort((p, q) => p.d - q.d);
    for (let n = 0; n < Math.min(NEIGHBORS, near.length); n++) {
      const j = near[n].j;
      const a = Math.min(i, j), b = Math.max(i, j);
      const id = a * count + b;
      if (seen.has(id)) continue;
      seen.add(id);
      edges.push(a, b);
    }
  }
  return Uint32Array.from(edges);
}

// ---- shaders ---------------------------------------------------------------
const POINT_VERT = /* glsl */ `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aSeed;
  attribute float aAct;
  uniform float uTime;
  uniform float uPixelRatio;
  uniform float uSizeScale;
  varying vec3 vColor;
  varying float vGlow;
  void main() {
    vColor = aColor;
    float tw = 0.55 + 0.45 * sin(uTime * 1.6 + aSeed * 6.2831);
    float glow = tw + aAct;
    vGlow = glow;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    float size = aSize * (0.6 + 0.7 * glow) * uSizeScale;
    gl_PointSize = size * uPixelRatio * (150.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;
const POINT_FRAG = /* glsl */ `
  precision mediump float;
  varying vec3 vColor;
  varying float vGlow;
  void main() {
    float d = length(gl_PointCoord - vec2(0.5));
    if (d > 0.5) discard;
    float a = pow(smoothstep(0.5, 0.0, d), 2.0);
    gl_FragColor = vec4(vColor * (0.45 + 0.6 * vGlow), a * 0.9);
  }
`;
const LINE_VERT = /* glsl */ `
  attribute vec3 aColor;
  attribute float aAct;
  varying vec3 vColor;
  varying float vAct;
  void main() {
    vColor = aColor;
    vAct = aAct;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const LINE_FRAG = /* glsl */ `
  precision mediump float;
  uniform float uOpacity;
  varying vec3 vColor;
  varying float vAct;
  void main() {
    float a = uOpacity * (0.5 + 1.8 * vAct);
    gl_FragColor = vec4(vColor * (0.6 + 1.4 * vAct), a);
  }
`;
// Glowing brain surface: two-light diffuse (so gyri folds read) + fresnel rim.
const SURF_VERT = /* glsl */ `
  varying vec3 vN;
  varying vec3 vV;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;
const SURF_FRAG = /* glsl */ `
  precision highp float;
  uniform vec3 uDeep;     // shadowed base (sulci)
  uniform vec3 uLit;      // key-lit gyri
  uniform vec3 uRim;      // fresnel edge glow
  uniform vec3 uKeyDir;
  uniform vec3 uFillDir;
  uniform float uRimPow;
  uniform float uRimStr;
  uniform float uEmissive;
  varying vec3 vN;
  varying vec3 vV;
  void main() {
    vec3 N = normalize(vN);
    if (!gl_FrontFacing) N = -N;
    float key = max(dot(N, normalize(uKeyDir)), 0.0);
    float fill = max(dot(N, normalize(uFillDir)), 0.0);
    vec3 col = uDeep + uLit * key * 0.55 + uRim * fill * 0.16 + uLit * uEmissive;
    float fres = pow(1.0 - max(dot(N, normalize(vV)), 0.0), uRimPow);
    col += uRim * fres * uRimStr;
    gl_FragColor = vec4(col, 1.0);
  }
`;

type Signal = { edge: number; t: number; speed: number; recycle: boolean; on: boolean };

function loadGeometry(): Promise<THREE.BufferGeometry> {
  return new Promise((resolve, reject) => {
    new STLLoader().load(BRAIN_URL, (g) => resolve(g), undefined, reject);
  });
}

export async function initBrain(mount: HTMLElement): Promise<void> {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!hasWebGL()) {
    mount.parentElement?.classList.add("brain-failed");
    return;
  }

  let raw: THREE.BufferGeometry;
  try {
    raw = await loadGeometry();
  } catch {
    mount.parentElement?.classList.add("brain-failed");
    return;
  }

  // Normalize the mesh: smooth normals, center at origin, scale to view, and
  // orient so the shortest (top-bottom) axis is vertical for a clean turntable.
  raw.deleteAttribute("normal");
  let geo = mergeVertices(raw);
  geo.computeVertexNormals();
  geo.computeBoundingBox();
  const bb = geo.boundingBox!;
  const size = new THREE.Vector3().subVectors(bb.max, bb.min);
  const center = new THREE.Vector3().addVectors(bb.min, bb.max).multiplyScalar(0.5);
  geo.translate(-center.x, -center.y, -center.z);
  // Put the smallest extent on Y (anatomical superior-inferior is shortest).
  const dims = [size.x, size.y, size.z];
  const minAxis = dims.indexOf(Math.min(...dims));
  if (minAxis === 0) geo.rotateZ(Math.PI / 2); // x -> y
  else if (minAxis === 2) geo.rotateX(Math.PI / 2); // z -> y
  geo.computeBoundingSphere();
  const s = TARGET_RADIUS / (geo.boundingSphere!.radius || 1);
  geo.scale(s, s, s);
  geo.computeVertexNormals();

  const tier = pickTier();
  const count = tier.nodes;

  // Scene / camera / renderer ------------------------------------------------
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
  camera.position.set(0, 0, 34);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  renderer.setPixelRatio(dpr);
  mount.appendChild(renderer.domElement);

  const group = new THREE.Group();
  group.rotation.set(0.15, -0.5, 0); // recognizable 3/4 starting view
  scene.add(group);

  // Glowing brain surface ----------------------------------------------------
  const surfUniforms = {
    uDeep: { value: new THREE.Color() },
    uLit: { value: new THREE.Color() },
    uRim: { value: new THREE.Color() },
    uKeyDir: { value: new THREE.Vector3(0.4, 0.7, 0.8) },
    uFillDir: { value: new THREE.Vector3(-0.6, -0.2, 0.4) },
    uRimPow: { value: 2.6 },
    uRimStr: { value: 0.8 },
    uEmissive: { value: 0.03 },
  };
  const surfMat = new THREE.ShaderMaterial({
    uniforms: surfUniforms,
    vertexShader: SURF_VERT,
    fragmentShader: SURF_FRAG,
    side: THREE.DoubleSide,
  });
  const surfMesh = new THREE.Mesh(geo, surfMat);
  surfMesh.renderOrder = 0;
  group.add(surfMesh);

  // Neurons sampled across the real surface ----------------------------------
  const sampler = new MeshSurfaceSampler(surfMesh).build();
  const sp = new THREE.Vector3(), sn = new THREE.Vector3();
  const base = new Float32Array(count * 3); // rest positions (local)
  const seed = new Float32Array(count);
  const size2 = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    sampler.sample(sp, sn);
    base[i * 3] = sp.x + sn.x * 0.18; // lift just above the surface
    base[i * 3 + 1] = sp.y + sn.y * 0.18;
    base[i * 3 + 2] = sp.z + sn.z * 0.18;
    seed[i] = Math.random();
    size2[i] = 0.9 + Math.random() * 1.4;
  }
  const pos = base.slice(); // live positions (displaced)
  const vel = new Float32Array(count * 3);
  const act = new Float32Array(count);
  const edges = buildEdges(base, count, 1.6);
  const edgeCount = edges.length / 2;

  const adj: number[][] = Array.from({ length: count }, () => []);
  for (let e = 0; e < edgeCount; e++) {
    adj[edges[e * 2]].push(e);
    adj[edges[e * 2 + 1]].push(e);
  }

  const sharedUniforms = {
    uTime: { value: 0 },
    uPixelRatio: { value: dpr },
    uSizeScale: { value: 1 },
  };
  const nodeGeo = new THREE.BufferGeometry();
  nodeGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  nodeGeo.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
  nodeGeo.setAttribute("aSize", new THREE.BufferAttribute(size2, 1));
  nodeGeo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
  nodeGeo.setAttribute("aAct", new THREE.BufferAttribute(act, 1));
  const nodeMat = new THREE.ShaderMaterial({
    uniforms: sharedUniforms,
    vertexShader: POINT_VERT,
    fragmentShader: POINT_FRAG,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const nodePoints = new THREE.Points(nodeGeo, nodeMat);
  nodePoints.renderOrder = 1;
  group.add(nodePoints);

  // Synapses -----------------------------------------------------------------
  const linePos = new Float32Array(edgeCount * 2 * 3);
  const lineCol = new Float32Array(edgeCount * 2 * 3);
  const lineAct = new Float32Array(edgeCount * 2);
  for (let e = 0; e < edgeCount; e++) {
    const a = edges[e * 2], b = edges[e * 2 + 1];
    linePos.set([base[a * 3], base[a * 3 + 1], base[a * 3 + 2]], e * 6);
    linePos.set([base[b * 3], base[b * 3 + 1], base[b * 3 + 2]], e * 6 + 3);
  }
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
  lineGeo.setAttribute("aColor", new THREE.BufferAttribute(lineCol, 3));
  lineGeo.setAttribute("aAct", new THREE.BufferAttribute(lineAct, 1));
  const lineUniforms = { uOpacity: { value: 0.13 } };
  const lineMat = new THREE.ShaderMaterial({
    uniforms: lineUniforms,
    vertexShader: LINE_VERT,
    fragmentShader: LINE_FRAG,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const lineSeg = new THREE.LineSegments(lineGeo, lineMat);
  lineSeg.renderOrder = 1;
  group.add(lineSeg);

  // Signals ------------------------------------------------------------------
  const sigPos = new Float32Array(MAX_SIGNALS * 3);
  const sigCol = new Float32Array(MAX_SIGNALS * 3);
  const sigSize = new Float32Array(MAX_SIGNALS);
  const sigSeed = new Float32Array(MAX_SIGNALS);
  const sigAct = new Float32Array(MAX_SIGNALS);
  for (let i = 0; i < MAX_SIGNALS; i++) {
    sigCol.set([AMBER.r, AMBER.g, AMBER.b], i * 3);
    sigSeed[i] = Math.random();
    sigAct[i] = 0.9;
  }
  const signals: Signal[] = Array.from({ length: MAX_SIGNALS }, () => ({
    edge: 0, t: 0, speed: 0, recycle: false, on: false,
  }));
  const sigGeo = new THREE.BufferGeometry();
  sigGeo.setAttribute("position", new THREE.BufferAttribute(sigPos, 3));
  sigGeo.setAttribute("aColor", new THREE.BufferAttribute(sigCol, 3));
  sigGeo.setAttribute("aSize", new THREE.BufferAttribute(sigSize, 1));
  sigGeo.setAttribute("aSeed", new THREE.BufferAttribute(sigSeed, 1));
  sigGeo.setAttribute("aAct", new THREE.BufferAttribute(sigAct, 1));
  const sigMat = new THREE.ShaderMaterial({
    uniforms: sharedUniforms,
    vertexShader: POINT_VERT,
    fragmentShader: POINT_FRAG,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const sigPoints = new THREE.Points(sigGeo, sigMat);
  sigPoints.renderOrder = 2;
  group.add(sigPoints);

  const fireSignal = (edge: number, recycle: boolean): void => {
    for (let i = 0; i < MAX_SIGNALS; i++) {
      if (signals[i].on) continue;
      signals[i] = { edge, t: 0, speed: 1.1 + Math.random() * 1.2, recycle, on: true };
      sigSize[i] = 2.3 + Math.random() * 1.1;
      return;
    }
  };
  for (let i = 0; i < AMBIENT_SIGNALS; i++) {
    fireSignal((Math.random() * edgeCount) | 0, true);
    signals[i].t = Math.random();
  }

  // Bloom / composer ---------------------------------------------------------
  let composer: EffectComposer | null = null;
  let bloom: UnrealBloomPass | null = null;
  if (tier.bloom) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.35, 0.5, 0.5);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());
  }

  // Theme colors (tuned per mode for legibility + eye comfort) ---------------
  const cssColor = (name: string, fallback: string): THREE.Color => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return new THREE.Color(v || fallback);
  };
  const tmp = new THREE.Color();
  const applyTheme = (): void => {
    const light = effectiveTheme() === "light";
    const c1 = cssColor("--accent", "#a78bfa"); // violet
    const c2 = cssColor("--accent-2", "#22d3ee"); // cyan

    // Surface: dark mode glows softly on the dark page; light mode uses a
    // deeper, more saturated body so the brain stands out on the light page.
    surfUniforms.uLit.value.copy(c1);
    surfUniforms.uRim.value.copy(c2);
    if (light) {
      surfUniforms.uDeep.value.copy(c1).multiplyScalar(0.16).lerp(new THREE.Color("#1a1f4a"), 0.5);
      surfUniforms.uEmissive.value = 0.02;
      surfUniforms.uRimStr.value = 0.6;
    } else {
      surfUniforms.uDeep.value.copy(c1).multiplyScalar(0.06);
      surfUniforms.uEmissive.value = 0.03;
      surfUniforms.uRimStr.value = 0.8;
    }

    // Neuron + synapse colors: violet->cyan by depth along the model.
    for (let i = 0; i < count; i++) {
      const t = THREE.MathUtils.clamp((base[i * 3 + 2] / TARGET_RADIUS) * 0.5 + 0.5, 0, 1);
      tmp.copy(c1).lerp(c2, t);
      colors[i * 3] = tmp.r; colors[i * 3 + 1] = tmp.g; colors[i * 3 + 2] = tmp.b;
    }
    nodeGeo.getAttribute("aColor").needsUpdate = true;
    for (let e = 0; e < edgeCount; e++) {
      const a = edges[e * 2];
      const t = THREE.MathUtils.clamp((base[a * 3 + 2] / TARGET_RADIUS) * 0.5 + 0.5, 0, 1);
      tmp.copy(c1).lerp(c2, t);
      lineCol.set([tmp.r, tmp.g, tmp.b], e * 6);
      lineCol.set([tmp.r, tmp.g, tmp.b], e * 6 + 3);
    }
    lineGeo.getAttribute("aColor").needsUpdate = true;
    lineUniforms.uOpacity.value = light ? 0.2 : 0.13;
    if (bloom) bloom.strength = light ? 0.22 : 0.35;
  };
  applyTheme();

  // Interaction state --------------------------------------------------------
  const ndc = new THREE.Vector2();
  let pointerInside = false;
  const cursorLocal = new THREE.Vector3();
  let cursorValid = false;
  const rayc = new THREE.Raycaster();
  const plane = new THREE.Plane();
  const planeNormal = new THREE.Vector3();
  const hit = new THREE.Vector3();
  const targetRot = new THREE.Vector2();
  let shockOrigin: THREE.Vector3 | null = null;
  let shockT = 0;

  const updateCursorLocal = (): void => {
    camera.getWorldDirection(planeNormal);
    plane.setFromNormalAndCoplanarPoint(planeNormal, group.position);
    rayc.setFromCamera(ndc, camera);
    if (rayc.ray.intersectPlane(plane, hit)) {
      cursorLocal.copy(group.worldToLocal(hit.clone()));
      cursorValid = true;
    }
  };
  const onMove = (ev: PointerEvent): void => {
    const r = renderer.domElement.getBoundingClientRect();
    ndc.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    ndc.y = -(((ev.clientY - r.top) / r.height) * 2 - 1);
    pointerInside = true;
    targetRot.set(ndc.y * 0.25, ndc.x * 0.5);
    updateCursorLocal();
  };
  const onLeave = (): void => {
    pointerInside = false;
    cursorValid = false;
    targetRot.set(0, 0);
  };
  const onDown = (ev: PointerEvent): void => {
    onMove(ev);
    if (!cursorValid) return;
    let best = -1, bestD = Infinity;
    for (let i = 0; i < count; i++) {
      const dx = base[i * 3] - cursorLocal.x, dy = base[i * 3 + 1] - cursorLocal.y, dz = base[i * 3 + 2] - cursorLocal.z;
      const d = dx * dx + dy * dy + dz * dz;
      if (d < bestD) { bestD = d; best = i; }
    }
    if (best < 0) return;
    shockOrigin = new THREE.Vector3(base[best * 3], base[best * 3 + 1], base[best * 3 + 2]);
    shockT = 0;
    for (const e of adj[best]) fireSignal(e, false);
  };
  renderer.domElement.addEventListener("pointermove", onMove);
  renderer.domElement.addEventListener("pointerleave", onLeave);
  renderer.domElement.addEventListener("pointerdown", onDown);

  // Sizing -------------------------------------------------------------------
  const resize = (): void => {
    const w = mount.clientWidth || 1;
    const h = mount.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    composer?.setSize(w, h);
    bloom?.setSize(w, h);
  };
  const ro = new ResizeObserver(resize);
  ro.observe(mount);
  resize();

  // Theme + lifecycle observers ---------------------------------------------
  new MutationObserver(applyTheme).observe(document.documentElement, {
    attributes: true, attributeFilter: ["data-theme"],
  });
  window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", applyTheme);

  let onLanding =
    (document.documentElement.getAttribute("data-screen") ?? "landing") === "landing";
  let inView = true;
  let pageVisible = !document.hidden;
  new MutationObserver(() => {
    onLanding = (document.documentElement.getAttribute("data-screen") ?? "landing") === "landing";
    sync();
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-screen"] });
  new IntersectionObserver((es) => { inView = es[0].isIntersecting; sync(); }).observe(mount);
  document.addEventListener("visibilitychange", () => { pageVisible = !document.hidden; sync(); });

  // Animation ----------------------------------------------------------------
  const timer = new THREE.Timer();
  let raf = 0;
  let running = false;

  const step = (dt: number, time: number): void => {
    sharedUniforms.uTime.value = time;

    group.rotation.y += dt * 0.1 + (targetRot.y - group.rotation.y) * 0.04;
    group.rotation.x += (0.15 + targetRot.x - group.rotation.x) * 0.04;

    const repelR = 4.0, repelR2 = repelR * repelR;
    for (let i = 0; i < count; i++) {
      const ix = i * 3, iy = ix + 1, iz = ix + 2;
      let fx = (base[ix] - pos[ix]) * 6.0;
      let fy = (base[iy] - pos[iy]) * 6.0;
      let fz = (base[iz] - pos[iz]) * 6.0;
      if (cursorValid && pointerInside) {
        const dx = pos[ix] - cursorLocal.x, dy = pos[iy] - cursorLocal.y, dz = pos[iz] - cursorLocal.z;
        const d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < repelR2 && d2 > 1e-4) {
          const f = (1 - d2 / repelR2) * 26 / Math.sqrt(d2);
          fx += dx * f; fy += dy * f; fz += dz * f;
          act[i] = Math.min(1.4, act[i] + (1 - d2 / repelR2) * 0.5);
        }
      }
      vel[ix] = (vel[ix] + fx * dt) * 0.86;
      vel[iy] = (vel[iy] + fy * dt) * 0.86;
      vel[iz] = (vel[iz] + fz * dt) * 0.86;
      pos[ix] += vel[ix] * dt; pos[iy] += vel[iy] * dt; pos[iz] += vel[iz] * dt;
      act[i] *= 0.92;
    }

    if (cursorValid && pointerInside && Math.random() < 0.4) {
      let best = -1, bestD = Infinity;
      for (let i = 0; i < count; i++) {
        const dx = base[i * 3] - cursorLocal.x, dy = base[i * 3 + 1] - cursorLocal.y, dz = base[i * 3 + 2] - cursorLocal.z;
        const d = dx * dx + dy * dy + dz * dz;
        if (d < bestD) { bestD = d; best = i; }
      }
      if (best >= 0 && adj[best].length) fireSignal(adj[best][(Math.random() * adj[best].length) | 0], false);
    }

    if (shockOrigin) {
      shockT += dt;
      const ring = shockT * 16;
      for (let i = 0; i < count; i++) {
        const dx = base[i * 3] - shockOrigin.x, dy = base[i * 3 + 1] - shockOrigin.y, dz = base[i * 3 + 2] - shockOrigin.z;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (Math.abs(d - ring) < 2.2) act[i] = Math.min(1.8, act[i] + 0.9);
      }
      if (ring > TARGET_RADIUS * 3) shockOrigin = null;
    }
    nodeGeo.getAttribute("position").needsUpdate = true;
    nodeGeo.getAttribute("aAct").needsUpdate = true;

    for (let e = 0; e < edgeCount; e++) {
      lineAct[e * 2] = act[edges[e * 2]];
      lineAct[e * 2 + 1] = act[edges[e * 2 + 1]];
    }
    lineGeo.getAttribute("aAct").needsUpdate = true;

    for (let i = 0; i < MAX_SIGNALS; i++) {
      const sg = signals[i];
      if (!sg.on) { sigSize[i] = 0; continue; }
      sg.t += sg.speed * dt * 0.35;
      if (sg.t >= 1) {
        if (sg.recycle) { sg.edge = (Math.random() * edgeCount) | 0; sg.t = 0; sg.speed = 1.1 + Math.random() * 1.2; }
        else { sg.on = false; sigSize[i] = 0; continue; }
      }
      const a = edges[sg.edge * 2], b = edges[sg.edge * 2 + 1];
      const t = sg.t;
      sigPos[i * 3] = pos[a * 3] + (pos[b * 3] - pos[a * 3]) * t;
      sigPos[i * 3 + 1] = pos[a * 3 + 1] + (pos[b * 3 + 1] - pos[a * 3 + 1]) * t;
      sigPos[i * 3 + 2] = pos[a * 3 + 2] + (pos[b * 3 + 2] - pos[a * 3 + 2]) * t;
    }
    sigGeo.getAttribute("position").needsUpdate = true;
    sigGeo.getAttribute("aSize").needsUpdate = true;
  };

  const render = (): void => {
    if (composer) composer.render();
    else renderer.render(scene, camera);
  };

  const loop = (): void => {
    raf = requestAnimationFrame(loop);
    timer.update();
    step(Math.min(0.05, timer.getDelta()), timer.getElapsed());
    render();
  };

  function sync(): void {
    const want = onLanding && inView && pageVisible && !reduce;
    if (want && !running) { running = true; timer.update(); loop(); } // reset delta baseline
    else if (!want && running) { running = false; cancelAnimationFrame(raf); }
  }

  if (reduce) {
    step(0, 0);
    render();
  } else {
    sync();
  }
}
