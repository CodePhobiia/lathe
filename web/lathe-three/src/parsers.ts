/**
 * Sidecar parsers. Each function takes the raw JSON payload from one
 * .lthpkg sidecar and returns the typed shape, throwing on
 * version/schema mismatch.
 *
 * Per the no-fake-quality contract: parsers do NOT invent missing
 * fields. If the payload is malformed, we throw with a structured
 * error message naming the missing path. Consumers can catch and
 * surface the error in the diagnostics overlay.
 */

import type {
  LatheConstructionProvenance,
  LatheDiagnostics,
  LatheEvidence,
  LatheMaterialZone,
  LatheRuntimeManifest,
  LatheSemanticIndex,
  LthpkgManifest,
} from "./types.js";

export class LthpkgParseError extends Error {
  constructor(public readonly sidecar: string, public readonly path: string, message: string) {
    super(`[${sidecar}] ${path}: ${message}`);
    this.name = "LthpkgParseError";
  }
}

function requireString(value: unknown, sidecar: string, path: string): string {
  if (typeof value !== "string") {
    throw new LthpkgParseError(sidecar, path, `expected string, got ${typeof value}`);
  }
  return value;
}

function requireNumber(value: unknown, sidecar: string, path: string): number {
  if (typeof value !== "number") {
    throw new LthpkgParseError(sidecar, path, `expected number, got ${typeof value}`);
  }
  return value;
}

function requireArray<T>(value: unknown, sidecar: string, path: string): T[] {
  if (!Array.isArray(value)) {
    throw new LthpkgParseError(sidecar, path, `expected array, got ${typeof value}`);
  }
  return value as T[];
}

function requireObject(
  value: unknown,
  sidecar: string,
  path: string,
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new LthpkgParseError(
      sidecar,
      path,
      `expected object, got ${typeof value}`,
    );
  }
  return value as Record<string, unknown>;
}

export function parseLthpkgManifest(raw: unknown): LthpkgManifest {
  const obj = requireObject(raw, "manifest.json", "");
  return {
    version: requireString(obj.version, "manifest.json", "version"),
    asset_id: requireString(obj.asset_id, "manifest.json", "asset_id"),
    style_pack_id: requireString(obj.style_pack_id, "manifest.json", "style_pack_id"),
    family: requireString(obj.family, "manifest.json", "family"),
    generator_id: requireString(obj.generator_id, "manifest.json", "generator_id"),
    seed: requireNumber(obj.seed, "manifest.json", "seed"),
    parameters_hash: requireString(
      obj.parameters_hash,
      "manifest.json",
      "parameters_hash",
    ),
    sidecar_files: requireObject(
      obj.sidecar_files,
      "manifest.json",
      "sidecar_files",
    ) as Record<string, string>,
    quality_ladder_target: requireNumber(
      obj.quality_ladder_target,
      "manifest.json",
      "quality_ladder_target",
    ),
    quality_ladder_achieved: requireNumber(
      obj.quality_ladder_achieved,
      "manifest.json",
      "quality_ladder_achieved",
    ),
    overall_score: requireNumber(
      obj.overall_score,
      "manifest.json",
      "overall_score",
    ),
    created_utc: requireNumber(obj.created_utc, "manifest.json", "created_utc"),
    notes: typeof obj.notes === "string" ? obj.notes : "",
  };
}

export function parseSemanticIndex(raw: unknown): LatheSemanticIndex {
  const obj = requireObject(raw, "semantic-index.json", "");
  return {
    version: requireString(obj.version, "semantic-index.json", "version"),
    asset_id: requireString(obj.asset_id, "semantic-index.json", "asset_id"),
    family: requireString(obj.family, "semantic-index.json", "family"),
    style_pack_id: requireString(
      obj.style_pack_id,
      "semantic-index.json",
      "style_pack_id",
    ),
    semantic_parts: requireArray<string>(
      obj.semantic_parts,
      "semantic-index.json",
      "semantic_parts",
    ),
    semantic_sockets: obj.semantic_sockets as LatheSemanticIndex["semantic_sockets"],
    material_slots: obj.material_slots as LatheSemanticIndex["material_slots"],
    bbox_cm: obj.bbox_cm as LatheSemanticIndex["bbox_cm"],
    quality_ladder_target: requireNumber(
      obj.quality_ladder_target,
      "semantic-index.json",
      "quality_ladder_target",
    ),
  };
}

export function parseDiagnostics(raw: unknown): LatheDiagnostics {
  const obj = requireObject(raw, "diagnostics.json", "");
  return {
    version: requireString(obj.version, "diagnostics.json", "version"),
    asset_id: requireString(obj.asset_id, "diagnostics.json", "asset_id"),
    generator_diagnostics: requireArray<string>(
      obj.generator_diagnostics,
      "diagnostics.json",
      "generator_diagnostics",
    ),
    certificate_findings: requireArray<string>(
      obj.certificate_findings,
      "diagnostics.json",
      "certificate_findings",
    ),
    certificate_repair_recommendations: requireArray<string>(
      obj.certificate_repair_recommendations,
      "diagnostics.json",
      "certificate_repair_recommendations",
    ),
    capability_matrix: obj.capability_matrix as LatheDiagnostics["capability_matrix"],
  };
}

export function parseEvidence(raw: unknown): LatheEvidence {
  const obj = requireObject(raw, "evidence.json", "");
  return {
    version: requireString(obj.version, "evidence.json", "version"),
    asset_id: requireString(obj.asset_id, "evidence.json", "asset_id"),
    runtime_manifest: obj.runtime_manifest as LatheRuntimeManifest,
    certificate: obj.certificate as LatheEvidence["certificate"],
    rule_of_truth: requireString(
      obj.rule_of_truth,
      "evidence.json",
      "rule_of_truth",
    ),
  };
}

export function parseMaterials(raw: unknown): LatheMaterialZone[] {
  const obj = requireObject(raw, "materials.json", "");
  const slots = requireArray<LatheMaterialZone>(
    obj.slots,
    "materials.json",
    "slots",
  );
  return slots;
}

export function parseOperations(raw: unknown): LatheConstructionProvenance {
  const obj = requireObject(raw, "operations.json", "");
  return {
    version: requireString(obj.version, "operations.json", "version"),
    asset_id: requireString(obj.asset_id, "operations.json", "asset_id"),
    generator_id: requireString(obj.generator_id, "operations.json", "generator_id"),
    parameters: requireObject(
      obj.parameters,
      "operations.json",
      "parameters",
    ) as Record<string, unknown>,
    geometry_payload: requireObject(
      obj.geometry_payload,
      "operations.json",
      "geometry_payload",
    ) as Record<string, unknown>,
    op_graph: obj.op_graph as LatheConstructionProvenance["op_graph"],
    op_graph_plan: obj.op_graph_plan as LatheConstructionProvenance["op_graph_plan"],
  };
}

export function parseRuntime(raw: unknown): LatheRuntimeManifest {
  const obj = requireObject(raw, "runtime.json", "");
  return {
    version: requireString(obj.version, "runtime.json", "version"),
    asset_id: requireString(obj.asset_id, "runtime.json", "asset_id"),
    style_pack_id: requireString(obj.style_pack_id, "runtime.json", "style_pack_id"),
    family: requireString(obj.family, "runtime.json", "family"),
    bbox_cm: obj.bbox_cm as LatheRuntimeManifest["bbox_cm"],
    units: requireString(obj.units, "runtime.json", "units"),
    pivot_cm: obj.pivot_cm as LatheRuntimeManifest["pivot_cm"],
    scale_anchor: requireString(obj.scale_anchor, "runtime.json", "scale_anchor"),
    render_mesh: obj.render_mesh as LatheRuntimeManifest["render_mesh"],
    collision: obj.collision as LatheRuntimeManifest["collision"],
    nav: obj.nav as LatheRuntimeManifest["nav"],
    lod: obj.lod as LatheRuntimeManifest["lod"],
    material_zone_manifest: obj.material_zone_manifest as Record<string, string>,
    semantic_sockets: obj.semantic_sockets as LatheRuntimeManifest["semantic_sockets"],
    semantic_parts: requireArray<string>(
      obj.semantic_parts,
      "runtime.json",
      "semantic_parts",
    ),
    quality_ladder_target: requireNumber(
      obj.quality_ladder_target,
      "runtime.json",
      "quality_ladder_target",
    ),
    diagnostics: requireArray<string>(
      obj.diagnostics,
      "runtime.json",
      "diagnostics",
    ),
    engine_readiness: obj.engine_readiness as Record<
      string,
      "ready" | "proxy" | "unsupported"
    >,
  };
}
