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

import {
  LatheLoader,
  LatheWorldLoader,
  type LatheThreeResult,
  type LatheWorldResult,
  type LatheRepairRequest,
  type MinimalObject3D,
} from "@lathe/three";
import {
  AmbientLight,
  AxesHelper,
  BufferGeometry,
  Color,
  DirectionalLight,
  GridHelper,
  Group,
  Line,
  LineBasicMaterial,
  Mesh,
  MeshBasicMaterial,
  MeshNormalMaterial,
  PerspectiveCamera,
  Scene,
  SphereGeometry,
  Vector3,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const viewportCanvas = document.getElementById("viewport") as HTMLCanvasElement;
const dropOverlay = document.getElementById("drop-overlay") as HTMLDivElement;
const loadedLabel = document.getElementById("loaded-label") as HTMLDivElement;
const packageUrlInput = document.getElementById("package-url") as HTMLInputElement;
const loadPackageUrlBtn = document.getElementById(
  "load-package-url",
) as HTMLButtonElement;
const assetMetaEl = document.getElementById("asset-meta") as HTMLDivElement;
const partsEl = document.getElementById("semantic-parts") as HTMLDivElement;
const slotsEl = document.getElementById("material-slots") as HTMLDivElement;
const diagEl = document.getElementById("diagnostics") as HTMLDivElement;
const certEl = document.getElementById("certificate") as HTMLDivElement;
const repairActionsEl = document.getElementById("repair-actions") as HTMLDivElement;
const captureScreenshotBtn = document.getElementById(
  "capture-screenshot",
) as HTMLButtonElement;
const exportRepairRequestBtn = document.getElementById(
  "export-repair-request",
) as HTMLButtonElement;
const playabilityHud = document.getElementById("playability-hud") as HTMLDivElement;
const minimapHud = document.getElementById("minimap-hud") as HTMLCanvasElement;
const playabilityStatus = document.getElementById("playability-status") as HTMLDivElement;

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

let currentResult: LatheThreeResult | null = null;
let currentWorldResult: LatheWorldResult | null = null;
const gltfLoader = new GLTFLoader();
const originalMaterials = new WeakMap<object, unknown>();
const modeMaterials: unknown[] = [];
const pressedKeys = new Set<string>();
let activeMode = "render";
let lastFrameMs = performance.now();
let playerMarker: Mesh | null = null;
let playerPosition = new Vector3();

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
  const now = performance.now();
  const dt = Math.min(0.05, Math.max(0, (now - lastFrameMs) / 1000));
  lastFrameMs = now;
  updatePlayability(dt);
  if (controls.enabled) {
    controls.update();
  }
  renderer.render(scene, camera);
}
tick();

// ---- Drag & drop wiring ----

const loader = new LatheLoader({
  gltfLoader,
  proxyObject3DFactory: () => {
    // A clearly-labeled proxy group for "unbuilt" mesh; the side panel
    // carries the reason so the viewer never silently invents geometry.
    const g = new Group();
    g.name = "lathe.proxy_unbuilt";
    return g as unknown as MinimalObject3D;
  },
});
const worldLoader = new LatheWorldLoader({
  gltfLoader,
  proxyObject3DFactory: () => {
    const g = new Group();
    g.name = "lathe.proxy_unbuilt";
    return g as unknown as MinimalObject3D;
  },
});

async function loadFromUrl(url: string) {
  if (looksLikeWorldUrl(url)) {
    await loadWorldFromUrl(url);
    return;
  }
  try {
    packageUrlInput.value = url;
    while (assetGroup.children.length > 0) assetGroup.remove(assetGroup.children[0]);
    playerMarker = null;
    const result = await loader.load(url);
    // Result.object3D conforms to the MinimalObject3D interface but in
    // practice the GLTFLoader path returns a real three.js Group.
    assetGroup.add(result.object3D as unknown as Group);
    currentResult = result;
    currentWorldResult = null;
    playabilityHud.classList.remove("active");
    controls.enabled = true;
    renderSidepanel(result);
    loadedLabel.textContent = `${result.manifest.asset_id} · L${result.evidence.certificate.achieved_level}/${result.evidence.certificate.target_level}`;
    captureScreenshotBtn.disabled = false;
    exportRepairRequestBtn.disabled = false;
    dropOverlay.classList.add("hidden");
  } catch (err) {
    dropOverlay.classList.remove("hidden");
    dropOverlay.textContent = `Failed to load: ${(err as Error).message}`;
  }
}

async function loadWorldFromUrl(url: string) {
  try {
    packageUrlInput.value = url;
    while (assetGroup.children.length > 0) assetGroup.remove(assetGroup.children[0]);
    playerMarker = null;
    const result = await worldLoader.load(url);
    assetGroup.add(result.worldObject3D as unknown as Group);
    addWorldOverlays(result);
    currentWorldResult = result;
    currentResult = null;
    renderWorldSidepanel(result);
    applyMode(activeMode);
    loadedLabel.textContent = `${result.manifest.world_id} · L${result.manifest.world_certificate.achieved_level}/${result.manifest.world_certificate.target_level}`;
    captureScreenshotBtn.disabled = false;
    exportRepairRequestBtn.disabled = true;
    dropOverlay.classList.add("hidden");
  } catch (err) {
    dropOverlay.classList.remove("hidden");
    dropOverlay.textContent = `Failed to load world: ${(err as Error).message}`;
  }
}

function looksLikeWorldUrl(url: string): boolean {
  return /(^|\/)[^/]*\.lthworld(?:\/|$)/.test(url)
    || /(^|\/)world_manifest\.json(?:[?#].*)?$/.test(url);
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

loadPackageUrlBtn.addEventListener("click", async () => {
  const url = packageUrlInput.value.trim();
  if (!url) return;
  await loadFromUrl(url);
});

packageUrlInput.addEventListener("keydown", async (e) => {
  if (e.key !== "Enter") return;
  const url = packageUrlInput.value.trim();
  if (!url) return;
  await loadFromUrl(url);
});

loadInitialPackageFromQuery();

window.addEventListener("keydown", (e) => {
  const target = e.target as HTMLElement | null;
  if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;
  pressedKeys.add(e.key.toLowerCase());
});

window.addEventListener("keyup", (e) => {
  pressedKeys.delete(e.key.toLowerCase());
});

captureScreenshotBtn.addEventListener("click", () => {
  if (!currentResult && !currentWorldResult) return;
  const name = currentWorldResult?.manifest.world_id ?? currentResult?.manifest.asset_id ?? "lathe";
  triggerDownload(
    `${name}-viewer-evidence.png`,
    renderer.domElement.toDataURL("image/png"),
  );
});

exportRepairRequestBtn.addEventListener("click", () => {
  if (!currentResult) return;
  const findings = [
    ...currentResult.diagnostics.generator_diagnostics,
    ...currentResult.diagnostics.certificate_findings,
  ];
  const requestId = `${currentResult.manifest.asset_id}:${Date.now().toString(36)}`;
  const request: LatheRepairRequest = {
    version: "lathe.web_viewer.repair_request_v1",
    request_id: requestId,
    asset_id: currentResult.manifest.asset_id,
    status: "request_exported",
    execution_boundary: {
      requester: "lathe-web-viewer",
      executor: "lathe-core-cli-or-service",
      status: "not_executed_in_browser",
    },
    source_manifest: currentResult.manifest,
    source_repair_history: currentResult.repairHistory,
    diagnostics: findings,
    repair_recommendations:
      currentResult.diagnostics.certificate_repair_recommendations,
    before_package: {
      manifest_url: currentResult.manifest.sidecar_files.manifest ?? "manifest.json",
      asset_id: currentResult.manifest.asset_id,
      mesh_is_real: currentResult.meshIsReal,
      visual_claim_level:
        currentResult.evidence.visual_quality_gate?.visual_claim_level ?? "not_verified",
    },
    after_package: {
      status: "rebuild_pending",
      manifest_url: null,
      package_id: null,
    },
    rule_of_truth:
      "Viewer exports a repair request only; Lathe CLI/service must execute rebuild and package before/after evidence.",
  };
  triggerDownload(
    `${currentResult.manifest.asset_id}-repair-request.json`,
    `data:application/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(request, null, 2),
    )}`,
  );
});

function loadInitialPackageFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const packageUrl = params.get("world") ?? params.get("package") ?? params.get("manifest");
  if (!packageUrl) return;
  void loadFromUrl(packageUrl);
}

function latheWorldPointToThree(point: [number, number, number] | number[]): Vector3 {
  const xCm = Number(point[0] ?? 0);
  const yCm = Number(point[1] ?? 0);
  const zCm = Number(point[2] ?? 0);
  return new Vector3(xCm / 100, zCm / 100, yCm / 100);
}

function addWorldOverlays(result: LatheWorldResult) {
  const overlayGroup = new Group();
  overlayGroup.name = "lathe.world_overlays";
  const pathMaterial = new LineBasicMaterial({ color: 0xe1bd77, linewidth: 2 });
  const walkableMaterial = new LineBasicMaterial({ color: 0x61d989, linewidth: 1 });
  const hazardMaterial = new LineBasicMaterial({ color: 0xc43f5a, linewidth: 1 });
  const spawnMaterial = new MeshBasicMaterial({ color: 0xffffff });
  const questMaterial = new MeshBasicMaterial({ color: 0xffee5f });
  modeMaterials.push(pathMaterial, walkableMaterial, hazardMaterial, spawnMaterial, questMaterial);

  for (const edge of result.traversalEvidence.path_edges) {
    const geometry = new BufferGeometry().setFromPoints(
      edge.control_points_cm.map((point) => latheWorldPointToThree(point)),
    );
    const line = new Line(geometry, pathMaterial);
    line.name = `lathe.path:${edge.edge_id}`;
    overlayGroup.add(line);
  }

  for (const polygonRecord of result.traversalEvidence.walkable_polygons.polygons) {
    const rawPolygon = polygonRecord.polygon_cm;
    if (!Array.isArray(rawPolygon) || rawPolygon.length < 3) continue;
    const points = rawPolygon
      .filter((p): p is number[] => Array.isArray(p))
      .map((point) => latheWorldPointToThree(point));
    if (points.length < 3) continue;
    points.push(points[0].clone());
    const geometry = new BufferGeometry().setFromPoints(points);
    const line = new Line(geometry, walkableMaterial);
    line.name = `lathe.walkable:${String(polygonRecord.polygon_id ?? "polygon")}`;
    overlayGroup.add(line);
  }

  const hazardComponents = result.traversalEvidence.collision_compound.hazards;
  if (Array.isArray(hazardComponents)) {
    for (const hazard of hazardComponents) {
      if (typeof hazard !== "object" || hazard === null) continue;
      const rawPolygon = (hazard as Record<string, unknown>).polygon_cm;
      if (!Array.isArray(rawPolygon) || rawPolygon.length < 3) continue;
      const points = rawPolygon
        .filter((p): p is number[] => Array.isArray(p))
        .map((point) => latheWorldPointToThree(point));
      if (points.length < 3) continue;
      points.push(points[0].clone());
      const geometry = new BufferGeometry().setFromPoints(points);
      const line = new Line(geometry, hazardMaterial);
      line.name = `lathe.hazard:${String((hazard as Record<string, unknown>).component_id ?? "hazard")}`;
      overlayGroup.add(line);
    }
  }

  for (const node of result.traversalEvidence.path_nodes) {
    const material = node.node_id === result.worldGraph.player_spawn_node_id
      ? spawnMaterial
      : node.role === "quest_destination"
        ? questMaterial
        : null;
    if (!material) continue;
    const marker = new Mesh(new SphereGeometry(0.08, 12, 8), material);
    marker.name = `lathe.anchor:${node.node_id}`;
    marker.position.copy(latheWorldPointToThree(node.position_cm));
    overlayGroup.add(marker);
  }

  assetGroup.add(overlayGroup);
}

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

function applyMode(mode: string) {
  activeMode = mode;
  playabilityHud.classList.toggle("active", mode === "playability" && Boolean(currentWorldResult));
  controls.enabled = mode !== "playability";
  if (currentWorldResult) {
    applyWorldCameraMode(mode, currentWorldResult);
    if (mode === "playability") {
      initializePlayability(currentWorldResult);
    }
  }
  const materialMode = ["micro_scene", "hero", "playability"].includes(mode)
    ? "render"
    : mode;
  disposeModeMaterials();
  traverseSceneMeshes(assetGroup, (mesh) => {
    if (!originalMaterials.has(mesh)) {
      originalMaterials.set(mesh, mesh.material);
    }
    if (materialMode === "render") {
      mesh.material = originalMaterials.get(mesh);
      return;
    }
    if (materialMode === "wireframe") {
      const material = new MeshBasicMaterial({
        color: 0xd8dee9,
        wireframe: true,
        transparent: true,
        opacity: 0.82,
      });
      modeMaterials.push(material);
      mesh.material = material;
      return;
    }
    if (materialMode === "material_ids") {
      const material = new MeshBasicMaterial({
        color: colorForString(mesh.name || mesh.userData?.name || currentResult?.manifest.asset_id || "lathe"),
      });
      modeMaterials.push(material);
      mesh.material = material;
      return;
    }
    if (materialMode === "normals") {
      const material = new MeshNormalMaterial({ flatShading: true });
      modeMaterials.push(material);
      mesh.material = material;
      return;
    }
    mesh.material = originalMaterials.get(mesh);
  });
}

function applyWorldCameraMode(mode: string, result: LatheWorldResult) {
  if (mode === "hero") {
    camera.position.set(-7.8, -8.2, 4.3);
    controls.target.set(0.4, -1.6, 0.4);
  } else if (mode === "playability") {
    const spawn = result.traversalEvidence.player_spawn.position_cm;
    const spawnVector = Array.isArray(spawn)
      ? latheWorldPointToThree(spawn as number[])
      : new Vector3(0, 0, 0);
    camera.position.set(spawnVector.x - 3.2, spawnVector.y - 3.6, spawnVector.z + 1.8);
    controls.target.copy(spawnVector);
  } else if (mode === "micro_scene") {
    camera.position.set(7.2, 7.6, 7.0);
    controls.target.set(0, 0, 0);
  }
  camera.updateProjectionMatrix();
}

type Point2 = [number, number];

function initializePlayability(result: LatheWorldResult) {
  const spawn = result.traversalEvidence.player_spawn.position_cm;
  const spawnVector = Array.isArray(spawn)
    ? latheWorldPointToThree(spawn as number[])
    : new Vector3(0, 0, 0);
  playerPosition = spawnVector.clone();
  playerPosition.y += 0.24;
  if (!playerMarker) {
    playerMarker = new Mesh(
      new SphereGeometry(0.14, 16, 10),
      new MeshBasicMaterial({ color: 0x7ee8ff }),
    );
    playerMarker.name = "lathe.playability_player";
    assetGroup.add(playerMarker);
  }
  playerMarker.visible = true;
  playerMarker.position.copy(playerPosition);
  camera.position.copy(playerPosition.clone().add(new Vector3(-4.2, -5.2, 3.0)));
  controls.target.copy(playerPosition);
  drawMinimap(result);
  updatePlayabilityHud(result);
}

function updatePlayability(dt: number) {
  if (activeMode !== "playability" || !currentWorldResult) {
    if (playerMarker) playerMarker.visible = false;
    return;
  }
  if (!playerMarker) {
    initializePlayability(currentWorldResult);
    return;
  }
  const direction = new Vector3(0, 0, 0);
  if (pressedKeys.has("w") || pressedKeys.has("arrowup")) direction.z -= 1;
  if (pressedKeys.has("s") || pressedKeys.has("arrowdown")) direction.z += 1;
  if (pressedKeys.has("a") || pressedKeys.has("arrowleft")) direction.x -= 1;
  if (pressedKeys.has("d") || pressedKeys.has("arrowright")) direction.x += 1;
  if (direction.lengthSq() > 0) {
    direction.normalize().multiplyScalar(2.4 * dt);
    const candidate = playerPosition.clone().add(direction);
    if (isWalkablePoint(currentWorldResult, candidate.x, candidate.z)) {
      playerPosition.copy(candidate);
    } else {
      const xOnly = playerPosition.clone();
      xOnly.x = candidate.x;
      const zOnly = playerPosition.clone();
      zOnly.z = candidate.z;
      if (isWalkablePoint(currentWorldResult, xOnly.x, xOnly.z)) {
        playerPosition.copy(xOnly);
      } else if (isWalkablePoint(currentWorldResult, zOnly.x, zOnly.z)) {
        playerPosition.copy(zOnly);
      }
    }
  }
  playerMarker.visible = true;
  playerMarker.position.copy(playerPosition);
  const desiredCamera = playerPosition.clone().add(new Vector3(-4.2, -5.2, 3.0));
  camera.position.lerp(desiredCamera, 0.22);
  controls.target.copy(playerPosition);
  camera.lookAt(playerPosition);
  drawMinimap(currentWorldResult);
  updatePlayabilityHud(currentWorldResult);
}

function isWalkablePoint(result: LatheWorldResult, x: number, z: number): boolean {
  const point: Point2 = [x, z];
  const walkable = traversalWalkablePolygons(result).some((polygon) => pointInPolygon(point, polygon));
  if (!walkable) return false;
  return !traversalHazardPolygons(result).some((polygon) => pointInPolygon(point, polygon));
}

function traversalWalkablePolygons(result: LatheWorldResult): Point2[][] {
  return result.traversalEvidence.walkable_polygons.polygons
    .map((record) => polygonToXZ(record))
    .filter((polygon) => polygon.length >= 3);
}

function traversalHazardPolygons(result: LatheWorldResult): Point2[][] {
  const hazards = result.traversalEvidence.collision_compound.hazards;
  if (!Array.isArray(hazards)) return [];
  return hazards
    .map((record) => polygonToXZ(record as Record<string, unknown>))
    .filter((polygon) => polygon.length >= 3);
}

function polygonToXZ(record: Record<string, unknown>): Point2[] {
  const rawPolygon = record.polygon_cm;
  if (!Array.isArray(rawPolygon)) return [];
  return rawPolygon
    .filter((p): p is number[] => Array.isArray(p))
    .map((point) => {
      const v = latheWorldPointToThree(point);
      return [v.x, v.z] as Point2;
    });
}

function pointInPolygon(point: Point2, polygon: Point2[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0];
    const zi = polygon[i][1];
    const xj = polygon[j][0];
    const zj = polygon[j][1];
    const intersects =
      (zi > point[1]) !== (zj > point[1])
      && point[0] < ((xj - xi) * (point[1] - zi)) / (zj - zi || 1e-6) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

function drawMinimap(result: LatheWorldResult) {
  const ctx = minimapHud.getContext("2d");
  if (!ctx) return;
  const w = minimapHud.width;
  const h = minimapHud.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#11151b";
  ctx.fillRect(0, 0, w, h);
  const walkable = traversalWalkablePolygons(result);
  const hazards = traversalHazardPolygons(result);
  const pathPoints = result.traversalEvidence.path_edges.flatMap((edge) =>
    edge.control_points_cm.map((point) => {
      const v = latheWorldPointToThree(point);
      return [v.x, v.z] as Point2;
    }),
  );
  const allPoints = [...walkable.flat(), ...hazards.flat(), ...pathPoints, [playerPosition.x, playerPosition.z] as Point2];
  const xs = allPoints.map((p) => p[0]);
  const zs = allPoints.map((p) => p[1]);
  const minX = Math.min(...xs, -1);
  const maxX = Math.max(...xs, 1);
  const minZ = Math.min(...zs, -1);
  const maxZ = Math.max(...zs, 1);
  const sx = (x: number) => 10 + ((x - minX) / Math.max(0.001, maxX - minX)) * (w - 20);
  const sz = (z: number) => h - 10 - ((z - minZ) / Math.max(0.001, maxZ - minZ)) * (h - 20);
  drawMiniPolygons(ctx, walkable, sx, sz, "rgba(97, 217, 137, 0.28)", "#61d989");
  drawMiniPolygons(ctx, hazards, sx, sz, "rgba(196, 63, 90, 0.26)", "#c43f5a");
  ctx.strokeStyle = "#e1bd77";
  ctx.lineWidth = 2;
  for (const edge of result.traversalEvidence.path_edges) {
    const points = edge.control_points_cm.map((point) => {
      const v = latheWorldPointToThree(point);
      return [v.x, v.z] as Point2;
    });
    drawMiniLine(ctx, points, sx, sz);
  }
  ctx.fillStyle = "#7ee8ff";
  ctx.beginPath();
  ctx.arc(sx(playerPosition.x), sz(playerPosition.z), 4, 0, Math.PI * 2);
  ctx.fill();
}

function drawMiniPolygons(
  ctx: CanvasRenderingContext2D,
  polygons: Point2[][],
  sx: (x: number) => number,
  sz: (z: number) => number,
  fill: string,
  stroke: string,
) {
  ctx.fillStyle = fill;
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 1;
  for (const polygon of polygons) {
    if (polygon.length < 3) continue;
    ctx.beginPath();
    ctx.moveTo(sx(polygon[0][0]), sz(polygon[0][1]));
    for (const point of polygon.slice(1)) {
      ctx.lineTo(sx(point[0]), sz(point[1]));
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
}

function drawMiniLine(
  ctx: CanvasRenderingContext2D,
  points: Point2[],
  sx: (x: number) => number,
  sz: (z: number) => number,
) {
  if (points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(sx(points[0][0]), sz(points[0][1]));
  for (const point of points.slice(1)) {
    ctx.lineTo(sx(point[0]), sz(point[1]));
  }
  ctx.stroke();
}

function updatePlayabilityHud(result: LatheWorldResult) {
  const cert = result.manifest.world_certificate;
  const engineStatus = String(result.engineImportEvidence?.status ?? "not_verified");
  const signatureHashes = result.signature.file_hashes;
  const signatureOk =
    typeof signatureHashes === "object"
    && signatureHashes !== null
    && Object.keys(signatureHashes).length > 0;
  playabilityStatus.innerHTML = [
    `<span class="meta-key">certificate</span><span>Level ${cert.achieved_level}</span>`,
    `<span class="meta-key">signed</span><span>${signatureOk ? "valid" : "not verified"}</span>`,
    `<span class="meta-key">engine</span><span>${escapeHtml(engineStatus)}</span>`,
    `<span class="meta-key">repair</span><span>${escapeHtml(String(result.wonderCritiqueTrace?.status ?? "not_verified"))}</span>`,
  ].join("");
}

function traverseSceneMeshes(root: Group, callback: (mesh: any) => void) {
  root.traverse((obj: any) => {
    if (obj?.isMesh && "material" in obj) {
      callback(obj);
    }
  });
}

function disposeModeMaterials() {
  while (modeMaterials.length > 0) {
    const material = modeMaterials.pop() as { dispose?: () => void } | undefined;
    material?.dispose?.();
  }
}

function colorForString(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  const hue = Math.abs(hash) % 360;
  const c = 0.62;
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1));
  const [r, g, b] =
    hue < 60
      ? [c, x, 0]
      : hue < 120
        ? [x, c, 0]
        : hue < 180
          ? [0, c, x]
          : hue < 240
            ? [0, x, c]
            : hue < 300
              ? [x, 0, c]
              : [c, 0, x];
  const m = 0.24;
  return (
    (Math.round((r + m) * 255) << 16)
    | (Math.round((g + m) * 255) << 8)
    | Math.round((b + m) * 255)
  );
}

// ---- Side panel rendering ----

function renderWorldSidepanel(result: LatheWorldResult) {
  const m = result.manifest;
  const cert = m.world_certificate;
  const traversal = result.traversalEvidence;
  const loadedMembers = result.members.filter((member) => member.loadStatus === "loaded").length;
  const engineStatus = String(result.engineImportEvidence?.status ?? "not_verified");
  const repairTraceStatus = String(result.wonderCritiqueTrace?.status ?? "not_verified");
  const signatureFileHashes = result.signature.file_hashes;
  const signatureFileCount =
    typeof signatureFileHashes === "object" && signatureFileHashes !== null
      ? Object.keys(signatureFileHashes).length
      : 0;
  assetMetaEl.innerHTML = `
    <div class="meta-row"><span class="meta-key">world_id</span><span class="meta-val">${escapeHtml(m.world_id)}</span></div>
    <div class="meta-row"><span class="meta-key">kit</span><span class="meta-val">${escapeHtml(m.kit_id)}</span></div>
    <div class="meta-row"><span class="meta-key">style pack</span><span class="meta-val">${escapeHtml(m.style_pack_id)}</span></div>
    <div class="meta-row"><span class="meta-key">assets</span><span class="meta-val">${loadedMembers}/${m.asset_count}</span></div>
    <div class="meta-row"><span class="meta-key">packages</span><span class="meta-val">${m.asset_package_summary.linked}/${m.asset_package_summary.total}</span></div>
    <div class="meta-row"><span class="meta-key">traversal</span><span class="meta-val">${pill(traversal.nav_status === "real" ? "good" : "warn", traversal.nav_status)}</span></div>
    <div class="meta-row"><span class="meta-key">collision</span><span class="meta-val">${pill(traversal.collision_status === "real" ? "good" : "warn", traversal.collision_status)}</span></div>
    <div class="meta-row"><span class="meta-key">minimap</span><span class="meta-val">${pill(result.minimapEvidence?.status === "real" ? "good" : "warn", result.minimapEvidence?.status ?? "not_verified")}</span></div>
    <div class="meta-row"><span class="meta-key">engine import</span><span class="meta-val">${pill(["imported", "validated", "validated_proxy"].includes(engineStatus) ? "good" : "warn", engineStatus)}</span></div>
  `;

  partsEl.innerHTML = Object.entries(m.role_counts)
    .map(([role, count]) => `<span class="pill">${escapeHtml(role)} ${count}</span>`)
    .join(" ");

  slotsEl.innerHTML = [
    `<div class="meta-row"><span class="meta-key">path nodes</span><span class="meta-val">${traversal.path_nodes.length}</span></div>`,
    `<div class="meta-row"><span class="meta-key">path edges</span><span class="meta-val">${traversal.path_edges.length}</span></div>`,
    `<div class="meta-row"><span class="meta-key">walkable polygons</span><span class="meta-val">${traversal.walkable_polygons.polygons.length}</span></div>`,
    `<div class="meta-row"><span class="meta-key">mesh extraction</span><span class="meta-val">${escapeHtml(traversal.mesh_extraction_status)}</span></div>`,
    `<div class="meta-row"><span class="meta-key">signature files</span><span class="meta-val">${signatureFileCount}</span></div>`,
  ].join("");

  const worldFindings = [
    ...m.diagnostics.map((d) => `${String(d.code ?? "WORLD")}: ${String(d.message ?? d)}`),
    ...cert.findings.map((f) => `${String(f.code ?? "CERT")}: ${String(f.message ?? f)}`),
    ...result.members
      .filter((member) => member.loadStatus === "error")
      .map((member) => `${member.worldAsset.world_asset_id}: ${member.loadReason}`),
  ];
  if (worldFindings.length === 0) {
    diagEl.innerHTML = `<div class="empty-state">No world findings.</div>`;
  } else {
    diagEl.innerHTML = worldFindings
      .map(
        (finding) => `
        <details class="finding">
          <summary>${escapeHtml(finding)}</summary>
          <div>${escapeHtml(cert.repair_recommendations.join(", ") || "not_verified")}</div>
        </details>`,
      )
      .join("");
  }

  repairActionsEl.innerHTML = `
    <div class="meta-row"><span class="meta-key">repair trace</span><span class="meta-val">${pill(repairTraceStatus === "real" ? "good" : "warn", repairTraceStatus)}</span></div>
    <div class="meta-row"><span class="meta-key">quest anchor</span><span class="meta-val">${traversal.quest_anchors.length}</span></div>
    <div class="meta-row"><span class="meta-key">spawn safety</span><span class="meta-val">${pill(String(traversal.spawn_safety_check.status) === "real" ? "good" : "warn", String(traversal.spawn_safety_check.status ?? "not_verified"))}</span></div>
  `;

  certEl.innerHTML = `
    <div class="meta-row">
      <span class="meta-key">achieved</span>
      <span class="meta-val">${pill(cert.achieved_level >= cert.target_level ? "good" : "warn", `Level ${cert.achieved_level}`)}</span>
    </div>
    <div class="meta-row"><span class="meta-key">target</span><span class="meta-val">Level ${cert.target_level}</span></div>
    <div class="meta-row"><span class="meta-key">certified</span><span class="meta-val">${pill(cert.certified ? "good" : "warn", String(cert.certified))}</span></div>
    <div class="meta-row"><span class="meta-key">style</span><span class="meta-val">${pill(m.style_compatibility.compatible ? "good" : "bad", m.style_compatibility.compatible ? "compatible" : "incompatible")}</span></div>
    ${Object.entries(cert.metrics)
      .map(
        ([key, value]) => `
        <div class="meta-row">
          <span class="meta-key">${escapeHtml(key)}</span>
          <span class="meta-val">${(value * 100).toFixed(0)}%</span>
        </div>`,
      )
      .join("")}
  `;
}

function renderSidepanel(result: LatheThreeResult) {
  // Asset meta.
  const m = result.manifest;
  const visualGate = result.evidence.visual_quality_gate;
  assetMetaEl.innerHTML = `
    <div class="meta-row"><span class="meta-key">asset_id</span><span class="meta-val">${escapeHtml(m.asset_id)}</span></div>
    <div class="meta-row"><span class="meta-key">family</span><span class="meta-val">${escapeHtml(m.family)}</span></div>
    <div class="meta-row"><span class="meta-key">style pack</span><span class="meta-val">${escapeHtml(m.style_pack_id)}</span></div>
    <div class="meta-row"><span class="meta-key">generator</span><span class="meta-val">${escapeHtml(m.generator_id)}</span></div>
    <div class="meta-row"><span class="meta-key">seed</span><span class="meta-val">${m.seed}</span></div>
    <div class="meta-row"><span class="meta-key">mesh.glb</span><span class="meta-val">${pill(result.meshIsReal ? "good" : "unbuilt", result.meshIsReal ? "real" : result.meshUnbuiltReason ?? "unbuilt")}</span></div>
    <div class="meta-row"><span class="meta-key">visual</span><span class="meta-val">${pill(visualGate?.visual_quality_gate === "approved" ? "good" : "warn", visualGate?.visual_claim_level ?? "not_verified")}</span></div>
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
  const externalBackendFindings =
    result.evidence.external_backend_evidence?.map(
      (e) =>
        `${e.operation_id}: ${e.status} (${e.blocker}; requires ${e.backend_required})`,
    ) ?? [];
  const findings = [
    ...result.diagnostics.generator_diagnostics,
    ...result.diagnostics.certificate_findings,
    ...externalBackendFindings,
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

  const repairRecommendations =
    result.diagnostics.certificate_repair_recommendations.filter(Boolean);
  const repairHistory = result.repairHistory;
  const repairHistoryRows = repairHistory
    ? [
        `<div class="meta-row"><span class="meta-key">history</span><span class="meta-val">${escapeHtml(repairHistory.status)}</span></div>`,
        `<div class="meta-row"><span class="meta-key">target</span><span class="meta-val">${escapeHtml(repairHistory.repair_target_layers.join(", ") || "not_verified")}</span></div>`,
        `<div class="meta-row"><span class="meta-key">rebuild</span><span class="meta-val">${escapeHtml(String(repairHistory.rebuilt_package.status ?? "not_verified"))}</span></div>`,
      ]
    : [`<div class="empty-state">No repair history sidecar.</div>`];
  const recommendationRows =
    repairRecommendations.length === 0
      ? [`<div class="empty-state">No repair recommendations.</div>`]
      : repairRecommendations.map(
          (r) =>
            `<div class="meta-row"><span class="meta-val">${escapeHtml(r)}</span></div>`,
        );
  repairActionsEl.innerHTML = [...repairHistoryRows, ...recommendationRows].join("");

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

function triggerDownload(filename: string, href: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
