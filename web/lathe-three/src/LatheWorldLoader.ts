/**
 * LatheWorldLoader - loads a .lthworld directory and its member .lthpkg files.
 *
 * This is the Phase 3 @lathe/three bridge: it parses world sidecars,
 * loads linked member packages through LatheLoader, applies world
 * transforms, and surfaces traversal / certificate / signature evidence
 * without inventing missing visual or engine proof.
 */

import { LatheLoader, type LatheLoaderOptions, type LatheThreeResult, type MinimalObject3D } from "./LatheLoader.js";
import {
  parseLthworldManifest,
  parseMinimapEvidence,
  parseTraversalEvidence,
  parseWorldGraph,
} from "./parsers.js";
import type {
  LatheMinimapEvidence,
  LatheTraversalEvidence,
  LatheWonderCritiqueTrace,
  LatheWorldAsset,
  LatheWorldAssetPackageLink,
  LatheWorldEvidence,
  LatheWorldGraph,
  LthworldManifest,
} from "./types.js";

export interface LatheWorldLoaderOptions extends LatheLoaderOptions {
  /** Load nested asset .lthpkg directories. Defaults true. */
  loadAssets?: boolean;
}

export interface LatheWorldMemberResult {
  worldAsset: LatheWorldAsset;
  packageLink: LatheWorldAssetPackageLink | null;
  result: LatheThreeResult | null;
  loadStatus: "loaded" | "planned" | "missing" | "error";
  loadReason: string;
}

export interface LatheWorldResult {
  worldObject3D: MinimalObject3D;
  manifest: LthworldManifest;
  worldGraph: LatheWorldGraph;
  traversalEvidence: LatheTraversalEvidence;
  visualQualityGate: Record<string, unknown>;
  worldEvidence: LatheWorldEvidence | null;
  wonderCritiqueTrace: LatheWonderCritiqueTrace | null;
  reproEvidence: Record<string, unknown>;
  minimapEvidence: LatheMinimapEvidence | null;
  engineImportEvidence: Record<string, unknown> | null;
  signature: Record<string, unknown>;
  members: LatheWorldMemberResult[];
}

interface TransformableObject3D extends MinimalObject3D {
  position?: { set: (x: number, y: number, z: number) => unknown };
  rotation?: { y?: number; z?: number };
  scale?: {
    setScalar?: (value: number) => unknown;
    set?: (x: number, y: number, z: number) => unknown;
  };
}

function defaultWorldObjectFactory(): MinimalObject3D {
  return {
    name: "lathe.world",
    userData: {},
    add: () => undefined,
  };
}

function joinUrl(baseUrl: string, relativePath: string): string {
  if (/^[a-z]+:\/\//i.test(relativePath) || relativePath.startsWith("/")) {
    return relativePath;
  }
  return `${baseUrl}${relativePath.replace(/^\.\//, "")}`;
}

function resolveWorldUrls(worldUrl: string): { baseUrl: string; manifestUrl: string } {
  const isManifestUrl = /(^|\/)world_manifest\.json(?:[?#].*)?$/.test(worldUrl);
  if (isManifestUrl) {
    return {
      baseUrl: worldUrl.slice(0, worldUrl.lastIndexOf("/") + 1),
      manifestUrl: worldUrl,
    };
  }
  const baseUrl = worldUrl.endsWith("/") ? worldUrl : `${worldUrl}/`;
  return { baseUrl, manifestUrl: `${baseUrl}world_manifest.json` };
}

function applyWorldTransform(object3D: MinimalObject3D, asset: LatheWorldAsset): void {
  const transformable = object3D as TransformableObject3D;
  const [xCm, yCm, zCm] = asset.placement.position_cm;
  // Forge composes on an X/Z ground plane with Y as vertical. The
  // current viewer uses a z-up scene, so map world Z -> three Y and
  // world Y -> three Z.
  transformable.position?.set(xCm / 100, zCm / 100, yCm / 100);
  if (transformable.rotation) {
    if ("z" in transformable.rotation) {
      transformable.rotation.z = (asset.placement.rotation_y_deg * Math.PI) / 180;
    } else {
      transformable.rotation.y = (asset.placement.rotation_y_deg * Math.PI) / 180;
    }
  }
  if (asset.placement.scale !== 1) {
    if (transformable.scale?.setScalar) {
      transformable.scale.setScalar(asset.placement.scale);
    } else {
      transformable.scale?.set?.(
        asset.placement.scale,
        asset.placement.scale,
        asset.placement.scale,
      );
    }
  }
  object3D.userData = {
    ...object3D.userData,
    latheWorld: {
      world_asset_id: asset.world_asset_id,
      role: asset.role,
      placement: asset.placement,
      package_status: asset.package_status,
      evidence_status: asset.evidence_status,
    },
  };
}

export class LatheWorldLoader {
  private readonly assetLoader: LatheLoader;

  constructor(private readonly options: LatheWorldLoaderOptions = {}) {
    this.assetLoader = new LatheLoader(options);
  }

  async load(worldUrl: string): Promise<LatheWorldResult> {
    const fetchImpl = this.options.fetch ?? globalThis.fetch;
    if (typeof fetchImpl !== "function") {
      throw new Error(
        "LatheWorldLoader.load requires a fetch implementation; pass options.fetch in non-browser environments.",
      );
    }
    const { baseUrl, manifestUrl } = resolveWorldUrls(worldUrl);
    const manifest = parseLthworldManifest(await this.fetchJson(fetchImpl, manifestUrl));
    const sidecars = manifest.sidecar_files;
    const worldGraph = parseWorldGraph(
      await this.fetchJson(fetchImpl, joinUrl(baseUrl, sidecars.world_graph ?? "world_graph.json")),
    );
    const traversalEvidence = parseTraversalEvidence(
      await this.fetchJson(
        fetchImpl,
        joinUrl(baseUrl, sidecars.traversal_evidence ?? "traversal_evidence.json"),
      ),
    );
    const visualQualityGate = await this.fetchJson(
      fetchImpl,
      joinUrl(baseUrl, sidecars.visual_quality_gate ?? "visual_quality_gate.json"),
    ) as Record<string, unknown>;
    const worldEvidence = sidecars.world_evidence
      ? await this.fetchJson(fetchImpl, joinUrl(baseUrl, sidecars.world_evidence)) as LatheWorldEvidence
      : null;
    const wonderCritiqueTrace = sidecars.wonder_critique_trace
      ? await this.fetchJson(fetchImpl, joinUrl(baseUrl, sidecars.wonder_critique_trace)) as LatheWonderCritiqueTrace
      : null;
    const reproEvidence = await this.fetchJson(
      fetchImpl,
      joinUrl(baseUrl, sidecars.repro_evidence ?? "repro_evidence.json"),
    ) as Record<string, unknown>;
    const signature = await this.fetchJson(
      fetchImpl,
      joinUrl(baseUrl, sidecars.signature ?? "signature.json"),
    ) as Record<string, unknown>;
    const minimapEvidence = sidecars.minimap_evidence
      ? parseMinimapEvidence(
          await this.fetchJson(fetchImpl, joinUrl(baseUrl, sidecars.minimap_evidence)),
        )
      : null;
    const engineImportEvidence = sidecars.engine_import_evidence
      ? await this.fetchJson(fetchImpl, joinUrl(baseUrl, sidecars.engine_import_evidence)) as Record<string, unknown>
      : null;

    const worldObject3D =
      this.options.proxyObject3DFactory?.() ?? defaultWorldObjectFactory();
    worldObject3D.name = `lathe-world:${manifest.world_id}`;
    const members: LatheWorldMemberResult[] = [];
    const shouldLoadAssets = this.options.loadAssets !== false;
    for (const worldAsset of worldGraph.assets) {
      const packageLink = manifest.asset_package_summary.links[worldAsset.world_asset_id] ?? null;
      if (!shouldLoadAssets) {
        members.push({
          worldAsset,
          packageLink,
          result: null,
          loadStatus: "planned",
          loadReason: "asset_loading_disabled",
        });
        continue;
      }
      if (!packageLink || packageLink.status !== "linked" || !packageLink.package) {
        members.push({
          worldAsset,
          packageLink,
          result: null,
          loadStatus: packageLink ? "planned" : "missing",
          loadReason: packageLink?.reason ?? "world_asset_package_link_missing",
        });
        continue;
      }
      try {
        const result = await this.assetLoader.load(joinUrl(baseUrl, packageLink.package));
        applyWorldTransform(result.object3D, worldAsset);
        worldObject3D.add(result.object3D);
        members.push({
          worldAsset,
          packageLink,
          result,
          loadStatus: "loaded",
          loadReason: "",
        });
      } catch (err) {
        members.push({
          worldAsset,
          packageLink,
          result: null,
          loadStatus: "error",
          loadReason: (err as Error).message,
        });
      }
    }

    worldObject3D.userData = {
      ...worldObject3D.userData,
      latheWorld: {
        manifest,
        worldGraph,
        traversalEvidence,
        visualQualityGate,
        worldEvidence,
        wonderCritiqueTrace,
        reproEvidence,
        minimapEvidence,
        engineImportEvidence,
        signature,
        loadedMemberCount: members.filter((m) => m.loadStatus === "loaded").length,
      },
    };

    return {
      worldObject3D,
      manifest,
      worldGraph,
      traversalEvidence,
      visualQualityGate,
      worldEvidence,
      wonderCritiqueTrace,
      reproEvidence,
      minimapEvidence,
      engineImportEvidence,
      signature,
      members,
    };
  }

  private async fetchJson(
    fetchImpl: typeof fetch,
    url: string,
  ): Promise<unknown> {
    const res = await fetchImpl(url);
    if (!res.ok) {
      throw new Error(
        `LatheWorldLoader: failed to fetch ${url} - HTTP ${res.status} ${res.statusText}`,
      );
    }
    return await res.json();
  }
}
