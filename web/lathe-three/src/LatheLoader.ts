/**
 * LatheLoader — loads an .lthpkg into Three.js while preserving
 * Lathe's semantic sidecars.
 *
 * Per PROD/three-lth-lathe-web-studio-v1-product-path.md Phase B:
 *
 *   import { LatheLoader } from "@lathe/three";
 *   const loader = new LatheLoader();
 *   const result = await loader.load("/assets/violet_crystal_cluster_a.lthpkg");
 *   scene.add(result.object3D);
 *
 * The loader:
 *   1. fetches manifest.json
 *   2. fetches every sidecar named in sidecar_files
 *   3. fetches mesh.glb when present + loads via GLTFLoader if user
 *      provided a `gltfLoader`; otherwise emits a structured proxy
 *      Object3D and records the unbuilt state in `result.exportEvidence`.
 *   4. decorates the resulting Object3D with semantic userData
 *      (parts, sockets, material slots, diagnostics, evidence,
 *      provenance, certificate).
 *
 * Per the no-fake-quality rule, missing mesh.glb does NOT produce a
 * fake mesh — it produces a clearly-labeled `unbuilt` proxy that the
 * web viewer's diagnostics panel surfaces.
 *
 * The loader is intentionally renderer-agnostic — it never imports
 * THREE directly. Instead, it accepts a small Three.js-shaped
 * interface via constructor options so consumers can wire their own
 * GLTFLoader / Object3D constructors. This keeps the package small
 * and avoids forcing a specific three.js version on consumers.
 */

import {
  parseDiagnostics,
  parseEvidence,
  parseLthpkgManifest,
  parseMaterials,
  parseOperations,
  parseRepairHistory,
  parseRuntime,
  parseSemanticIndex,
  LthpkgParseError,
} from "./parsers.js";
import type {
  LatheConstructionProvenance,
  LatheDiagnostics,
  LatheEvidence,
  LatheMaterialZone,
  LatheRepairHistory,
  LatheRuntimeManifest,
  LatheSemanticIndex,
  LthpkgManifest,
} from "./types.js";

/**
 * Minimal Three.js shape — we don't import THREE to avoid forcing a
 * specific version. Consumers pass a GLTF loader factory + an
 * Object3D constructor via options.
 */
export interface MinimalObject3D {
  name: string;
  userData: Record<string, unknown>;
  add(child: MinimalObject3D): unknown;
}

export interface MinimalGltfLoader {
  loadAsync(url: string): Promise<{ scene: MinimalObject3D }>;
}

export interface LatheLoaderOptions {
  /** Optional GLTFLoader instance used when mesh.glb is present. */
  gltfLoader?: MinimalGltfLoader;
  /** Factory for the proxy Object3D when mesh.glb is unbuilt. */
  proxyObject3DFactory?: () => MinimalObject3D;
  /** Custom fetch (defaults to globalThis.fetch). */
  fetch?: typeof fetch;
}

/** The full loader result — Three.js Object3D + every sidecar. */
export interface LatheThreeResult {
  object3D: MinimalObject3D;
  manifest: LthpkgManifest;
  semanticIndex: LatheSemanticIndex;
  materialZones: LatheMaterialZone[];
  diagnostics: LatheDiagnostics;
  provenance: LatheConstructionProvenance;
  evidence: LatheEvidence;
  repairHistory: LatheRepairHistory | null;
  exportEvidence: LatheRuntimeManifest;
  /** True when mesh.glb was loaded as real geometry. */
  meshIsReal: boolean;
  /** When false, names why (so the diagnostics overlay surfaces it). */
  meshUnbuiltReason: string | null;
}

function _defaultProxyFactory(): MinimalObject3D {
  // A bare object — the consumer's web viewer can substitute a proxy
  // cube/cylinder/wireframe as needed. We just guarantee userData is
  // populated.
  const o: MinimalObject3D = {
    name: "lathe.proxy_unbuilt",
    userData: {},
    add: () => undefined,
  };
  return o;
}

export class LatheLoader {
  constructor(private readonly options: LatheLoaderOptions = {}) {}

  async load(packageUrl: string): Promise<LatheThreeResult> {
    const fetchImpl = this.options.fetch ?? globalThis.fetch;
    if (typeof fetchImpl !== "function") {
      throw new Error(
        "LatheLoader.load requires a fetch implementation; pass options.fetch in non-browser environments.",
      );
    }
    const isManifestUrl = /(^|\/)manifest\.json(?:[?#].*)?$/.test(packageUrl);
    const manifestUrl = isManifestUrl
      ? packageUrl
      : packageUrl.endsWith("/")
        ? `${packageUrl}manifest.json`
        : `${packageUrl}/manifest.json`;
    const baseUrl = isManifestUrl
      ? packageUrl.slice(0, packageUrl.lastIndexOf("/") + 1)
      : packageUrl.endsWith("/")
        ? packageUrl
        : `${packageUrl}/`;

    // 1. Manifest.
    const manifestRaw = await this._fetchJson(fetchImpl, manifestUrl);
    const manifest = parseLthpkgManifest(manifestRaw);
    const sidecars = manifest.sidecar_files;

    // 2. Required sidecars.
    const semanticIndex = parseSemanticIndex(
      await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.semantic_index ?? "semantic-index.json"}`),
    );
    const materialZones = parseMaterials(
      await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.materials ?? "materials.json"}`),
    );
    const provenance = parseOperations(
      await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.operations ?? "operations.json"}`),
    );
    const diagnostics = parseDiagnostics(
      await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.diagnostics ?? "diagnostics.json"}`),
    );
    const evidence = parseEvidence(
      await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.evidence ?? "evidence.json"}`),
    );
    const runtime = parseRuntime(
      await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.runtime ?? "runtime.json"}`),
    );
    const repairHistory = sidecars.repair_history
      ? parseRepairHistory(
          await this._fetchJson(fetchImpl, `${baseUrl}${sidecars.repair_history}`),
        )
      : null;

    // 3. Mesh.glb when present.
    let object3D: MinimalObject3D;
    let meshIsReal = false;
    let meshUnbuiltReason: string | null = null;
    const meshFile = sidecars.mesh_glb;
    const renderStatus = runtime.render_mesh.status;
    if (
      meshFile &&
      renderStatus === "real" &&
      this.options.gltfLoader
    ) {
      try {
        const gltf = await this.options.gltfLoader.loadAsync(`${baseUrl}${meshFile}`);
        object3D = gltf.scene;
        meshIsReal = true;
      } catch (err) {
        meshIsReal = false;
        meshUnbuiltReason = `glb_load_failed: ${(err as Error).message}`;
        const factory =
          this.options.proxyObject3DFactory ?? _defaultProxyFactory;
        object3D = factory();
      }
    } else {
      meshUnbuiltReason =
        meshFile == null
          ? "mesh_glb_not_in_sidecar_files"
          : renderStatus !== "real"
            ? `render_mesh_status_${renderStatus}`
            : "no_gltf_loader_configured";
      const factory =
        this.options.proxyObject3DFactory ?? _defaultProxyFactory;
      object3D = factory();
    }

    // 4. Decorate Object3D.userData with the semantic sidecars.
    object3D.name = `lathe:${manifest.asset_id}`;
    object3D.userData = {
      ...object3D.userData,
      lathe: {
        manifest,
        semanticIndex,
        materialZones,
        provenance,
        diagnostics,
        evidence,
        repairHistory,
        exportEvidence: runtime,
        meshIsReal,
        meshUnbuiltReason,
      },
    };

    return {
      object3D,
      manifest,
      semanticIndex,
      materialZones,
      diagnostics,
      provenance,
      evidence,
      repairHistory,
      exportEvidence: runtime,
      meshIsReal,
      meshUnbuiltReason,
    };
  }

  private async _fetchJson(
    fetchImpl: typeof fetch,
    url: string,
  ): Promise<unknown> {
    const res = await fetchImpl(url);
    if (!res.ok) {
      throw new Error(
        `LatheLoader: failed to fetch ${url} — HTTP ${res.status} ${res.statusText}`,
      );
    }
    try {
      return await res.json();
    } catch (err) {
      throw new LthpkgParseError(
        url,
        "",
        `invalid JSON: ${(err as Error).message}`,
      );
    }
  }
}
