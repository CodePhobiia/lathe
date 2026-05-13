/**
 * Lathe Web Viewer — MVP entry point.
 *
 * Per docs/product/three-lth-lathe-web-studio-v1-product-path.md
 * Phase C — drag/drop a .lthpkg, render via three.js, inspect
 * semantic parts + diagnostics + quality certificate.
 *
 * The viewer is intentionally minimal at v0.1.0 — it proves the
 * .lthpkg + @lathe/three loader chain works end to end. Repair loop,
 * before/after comparison, screenshot evidence capture, kit browser,
 * micro-scene inspector, hero diorama mode, and playability overlay
 * are documented as Phase 2-5 viewer modes in the floating-fantasy
 * northstar; they all hang off this same loader chain.
 */

import { LatheLoader, type LatheThreeResult } from "@lathe/three";
import {
  AmbientLight,
  AxesHelper,
  Color,
  DirectionalLight,
  GridHelper,
  Group,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const viewportCanvas = document.getElementById("viewport") as HTMLCanvasElement;
const dropOverlay = document.getElementById("drop-overlay") as HTMLDivElement;
const loadedLabel = document.getElementById("loaded-label") as HTMLDivElement;
const assetMetaEl = document.getElementById("asset-meta") as HTMLDivElement;
const partsEl = document.getElementById("semantic-parts") as HTMLDivElement;
const slotsEl = document.getElementById("material-slots") as HTMLDivElement;
const diagEl = document.getElementById("diagnostics") as HTMLDivElement;
const certEl = document.getElementById("certificate") as HTMLDivElement;

const renderer = new WebGLRenderer({ canvas: viewportCanvas, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
const scene = new Scene();
scene.background = new Color(0x14171c);

const camera = new PerspectiveCamera(50, 1, 0.1, 5000);
camera.position.set(420, 220, 420);
camera.up.set(0, 0, 1);

const controls = new OrbitControls(camera, viewportCanvas);
controls.target.set(0, 0, 0);
controls.enableDamping = true;

scene.add(new AmbientLight(0xffffff, 0.55));
const sun = new DirectionalLight(0xfff0d8, 1.1);
sun.position.set(150, 200, 250);
scene.add(sun);
scene.add(new GridHelper(600, 30, 0x3a3f48, 0x2a2e35));
scene.add(new AxesHelper(60));

const assetGroup = new Group();
scene.add(assetGroup);

function resize() {
  const host = viewportCanvas.parentElement as HTMLElement;
  const w = host.clientWidth;
  const h = host.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

function tick() {
  requestAnimationFrame(tick);
  controls.update();
  renderer.render(scene, camera);
}
tick();

// ---- Drag & drop wiring ----

let currentResult: LatheThreeResult | null = null;
const gltfLoader = new GLTFLoader();

const loader = new LatheLoader({
  gltfLoader,
  proxyObject3DFactory: () => {
    // A clearly-labeled proxy group for "unbuilt" mesh — empty.
    const g = new Group();
    g.name = "lathe.proxy_unbuilt";
    return g as unknown as ReturnType<typeof loader["options"]["proxyObject3DFactory"] & object>;
  },
});

async function loadFromUrl(url: string) {
  try {
    while (assetGroup.children.length > 0) assetGroup.remove(assetGroup.children[0]);
    const result = await loader.load(url);
    // Result.object3D conforms to the MinimalObject3D interface but in
    // practice the GLTFLoader path returns a real three.js Group.
    assetGroup.add(result.object3D as unknown as Group);
    currentResult = result;
    renderSidepanel(result);
    loadedLabel.textContent = `${result.manifest.asset_id} · L${result.evidence.certificate.achieved_level}/${result.evidence.certificate.target_level}`;
    dropOverlay.classList.add("hidden");
  } catch (err) {
    dropOverlay.classList.remove("hidden");
    dropOverlay.textContent = `Failed to load: ${(err as Error).message}`;
  }
}

const viewportHost = document.getElementById("viewport-host") as HTMLDivElement;
viewportHost.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropOverlay.classList.add("active");
});
viewportHost.addEventListener("dragleave", () => {
  dropOverlay.classList.remove("active");
});
viewportHost.addEventListener("drop", async (e) => {
  e.preventDefault();
  dropOverlay.classList.remove("active");
  const dt = e.dataTransfer;
  if (!dt) return;
  // Browsers don't allow directory drops directly via URL; the user
  // typically drops a server-hosted package URL, or selects via a
  // file-input. For MVP, we accept a text path drop (typed by the user).
  const text = dt.getData("text/plain");
  if (text) {
    await loadFromUrl(text.trim());
  }
});

// ---- View mode buttons ----

const modeButtons = document.querySelectorAll(
  "button.mode-btn",
) as NodeListOf<HTMLButtonElement>;
modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const mode = btn.dataset.mode ?? "render";
    applyMode(mode);
  });
});

function applyMode(_mode: string) {
  // MVP: mode switching is wired but only logged. Real switching
  // requires a material override pass on the loaded three.js mesh.
  console.log("Lathe Web Viewer: applyMode", _mode, currentResult?.manifest.asset_id);
}

// ---- Side panel rendering ----

function renderSidepanel(result: LatheThreeResult) {
  // Asset meta.
  const m = result.manifest;
  assetMetaEl.innerHTML = `
    <div class="meta-row"><span class="meta-key">asset_id</span><span class="meta-val">${escapeHtml(m.asset_id)}</span></div>
    <div class="meta-row"><span class="meta-key">family</span><span class="meta-val">${escapeHtml(m.family)}</span></div>
    <div class="meta-row"><span class="meta-key">style pack</span><span class="meta-val">${escapeHtml(m.style_pack_id)}</span></div>
    <div class="meta-row"><span class="meta-key">generator</span><span class="meta-val">${escapeHtml(m.generator_id)}</span></div>
    <div class="meta-row"><span class="meta-key">seed</span><span class="meta-val">${m.seed}</span></div>
    <div class="meta-row"><span class="meta-key">mesh.glb</span><span class="meta-val">${pill(result.meshIsReal ? "good" : "unbuilt", result.meshIsReal ? "real" : result.meshUnbuiltReason ?? "unbuilt")}</span></div>
  `;

  // Semantic parts.
  partsEl.innerHTML = result.semanticIndex.semantic_parts
    .map((p) => `<span class="pill">${escapeHtml(p)}</span>`)
    .join(" ");

  // Material slots.
  slotsEl.innerHTML = result.materialZones
    .map(
      (z) => `
      <div class="meta-row">
        <span class="meta-key">${escapeHtml(z.slot_id)}</span>
        <span class="meta-val">${escapeHtml(z.material_class)}</span>
      </div>`,
    )
    .join("");

  // Diagnostics.
  const findings = [
    ...result.diagnostics.generator_diagnostics,
    ...result.diagnostics.certificate_findings,
  ];
  if (findings.length === 0) {
    diagEl.innerHTML = `<div class="empty-state">No findings.</div>`;
  } else {
    diagEl.innerHTML = findings
      .map(
        (f, i) => `
        <details class="finding">
          <summary>${escapeHtml(f)}</summary>
          <div>${escapeHtml(result.diagnostics.certificate_repair_recommendations[i] ?? "")}</div>
        </details>`,
      )
      .join("");
  }

  // Certificate.
  const cert = result.evidence.certificate;
  certEl.innerHTML = `
    <div class="meta-row">
      <span class="meta-key">achieved</span>
      <span class="meta-val">${pill(cert.achieved_level >= cert.target_level ? "good" : "warn", `Level ${cert.achieved_level}`)}</span>
    </div>
    <div class="meta-row">
      <span class="meta-key">target</span>
      <span class="meta-val">Level ${cert.target_level}</span>
    </div>
    <div class="meta-row">
      <span class="meta-key">overall</span>
      <span class="meta-val">${(cert.overall_score * 100).toFixed(1)}%</span>
    </div>
    ${Object.entries(cert.metrics)
      .map(
        ([k, v]) => `
        <div class="meta-row">
          <span class="meta-key">${escapeHtml(k)}</span>
          <span class="meta-val">${(v * 100).toFixed(0)}%</span>
        </div>`,
      )
      .join("")}
  `;
}

function pill(severity: string, text: string): string {
  return `<span class="pill ${severity}">${escapeHtml(text)}</span>`;
}

function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
