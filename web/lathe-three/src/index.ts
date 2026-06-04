/**
 * @lathe/three — Lathe-native semantic 3D inspection layer over Three.js.
 *
 * Loads .lthpkg packages produced by lathe.asset_foundry.package_writer
 * and decorates Three.js Object3Ds with the Foundry's semantic
 * sidecars (parts, materials, sockets, diagnostics, operation
 * provenance, runtime evidence, quality certificate).
 *
 * Architecture invariant (per docs/product/three-lth-lathe-web-studio-v1-product-path.md):
 *  - Lathe Core is the source of truth.
 *  - Three.js renders.
 *  - @lathe/three loads + decorates + exposes the semantic data
 *    Lathe authored. It does NOT invent semantics.
 *  - No-fake-quality rule: when an artifact path's status is
 *    "unbuilt" or "proxy", surface it truthfully via the
 *    `LatheEvidence` and `LatheDiagnostics` returned by the loader.
 */

export {
  LatheLoader,
  type LatheThreeResult,
  type LatheLoaderOptions,
  type MinimalGltfLoader,
  type MinimalObject3D,
} from "./LatheLoader.js";

export {
  LatheWorldLoader,
  type LatheWorldLoaderOptions,
  type LatheWorldMemberResult,
  type LatheWorldResult,
} from "./LatheWorldLoader.js";

export {
  type LthpkgManifest,
  type LthworldManifest,
  type LatheSemanticIndex,
  type LatheMaterialZone,
  type LatheConstructionProvenance,
  type LatheEvidence,
  type LatheDiagnostics,
  type LatheRuntimeManifest,
  type LatheQualityCertificate,
  type LatheVisualQualityGate,
  type LatheRepairHistory,
  type LatheRepairRequest,
  type LatheSemanticSocket,
  type LatheMaterialSlot,
  type LatheCollisionSpec,
  type LatheLodSpec,
  type LatheNavSpec,
  type LatheWorldAsset,
  type LatheWorldAssetPackageLink,
  type LatheWorldAssetPackageSummary,
  type LatheWorldAssetPlacement,
  type LatheWorldCertificate,
  type LatheWorldGraph,
  type LatheWorldPackageMemberMetadata,
  type LatheWorldPathEdge,
  type LatheWorldPathNode,
  type LatheWorldStyleCompatibility,
  type LatheTraversalEvidence,
  type LatheMinimapEvidence,
  type LatheWorldEvidence,
  type LatheWonderCritiqueTrace,
} from "./types.js";

export {
  parseLthpkgManifest,
  parseSemanticIndex,
  parseDiagnostics,
  parseEvidence,
  parseRepairHistory,
  parseMaterials,
  parseOperations,
  parseRuntime,
  parseLthworldManifest,
  parseWorldGraph,
  parseTraversalEvidence,
  parseMinimapEvidence,
} from "./parsers.js";

export {
  LATHE_THREE_VERSION,
} from "./version.js";
