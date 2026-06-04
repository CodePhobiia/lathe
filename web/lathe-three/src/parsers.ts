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
  LatheRepairHistory,
  LatheRuntimeManifest,
  LatheSemanticIndex,
  LatheMinimapEvidence,
  LatheTraversalEvidence,
  LatheWorldGraph,
  LthworldManifest,
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
    external_backend_evidence:
      obj.external_backend_evidence as LatheEvidence["external_backend_evidence"],
    visual_quality_gate: obj.visual_quality_gate as LatheEvidence["visual_quality_gate"],
    rule_of_truth: requireString(
      obj.rule_of_truth,
      "evidence.json",
      "rule_of_truth",
    ),
  };
}

export function parseRepairHistory(raw: unknown): LatheRepairHistory {
  const obj = requireObject(raw, "repair-history.json", "");
  return {
    version: requireString(obj.version, "repair-history.json", "version"),
    asset_id: requireString(obj.asset_id, "repair-history.json", "asset_id"),
    status: requireString(obj.status, "repair-history.json", "status"),
    original_package: requireObject(
      obj.original_package,
      "repair-history.json",
      "original_package",
    ),
    diagnostic_ids: requireArray<string>(
      obj.diagnostic_ids,
      "repair-history.json",
      "diagnostic_ids",
    ),
    selected_repair_actions: requireArray<string>(
      obj.selected_repair_actions,
      "repair-history.json",
      "selected_repair_actions",
    ),
    patched_intent_identifiers: requireArray<string>(
      obj.patched_intent_identifiers,
      "repair-history.json",
      "patched_intent_identifiers",
    ),
    repair_target_layers: requireArray<string>(
      obj.repair_target_layers,
      "repair-history.json",
      "repair_target_layers",
    ),
    attempted_vs_actual: requireArray<Record<string, unknown>>(
      obj.attempted_vs_actual,
      "repair-history.json",
      "attempted_vs_actual",
    ),
    rebuilt_package: requireObject(
      obj.rebuilt_package,
      "repair-history.json",
      "rebuilt_package",
    ),
    metric_deltas: requireObject(
      obj.metric_deltas,
      "repair-history.json",
      "metric_deltas",
    ),
    preview_before_after: requireObject(
      obj.preview_before_after,
      "repair-history.json",
      "preview_before_after",
    ),
    notes: requireArray<string>(obj.notes, "repair-history.json", "notes"),
    rule_of_truth: requireString(
      obj.rule_of_truth,
      "repair-history.json",
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

export function parseLthworldManifest(raw: unknown): LthworldManifest {
  const obj = requireObject(raw, "world_manifest.json", "");
  return {
    version: requireString(obj.version, "world_manifest.json", "version"),
    world_id: requireString(obj.world_id, "world_manifest.json", "world_id"),
    prompt: requireString(obj.prompt, "world_manifest.json", "prompt"),
    seed: requireNumber(obj.seed, "world_manifest.json", "seed"),
    mode: requireString(obj.mode, "world_manifest.json", "mode"),
    style_pack_id: requireString(obj.style_pack_id, "world_manifest.json", "style_pack_id"),
    kit_id: requireString(obj.kit_id, "world_manifest.json", "kit_id"),
    asset_count: requireNumber(obj.asset_count, "world_manifest.json", "asset_count"),
    role_counts: requireObject(
      obj.role_counts,
      "world_manifest.json",
      "role_counts",
    ) as Record<string, number>,
    style_pack_ids: requireArray<string>(
      obj.style_pack_ids,
      "world_manifest.json",
      "style_pack_ids",
    ),
    sidecar_files: requireObject(
      obj.sidecar_files,
      "world_manifest.json",
      "sidecar_files",
    ) as Record<string, string>,
    world_graph_status: requireString(
      obj.world_graph_status,
      "world_manifest.json",
      "world_graph_status",
    ),
    traversal_status: requireString(
      obj.traversal_status,
      "world_manifest.json",
      "traversal_status",
    ),
    visual_claim_level: requireString(
      obj.visual_claim_level,
      "world_manifest.json",
      "visual_claim_level",
    ),
    world_certificate: requireObject(
      obj.world_certificate,
      "world_manifest.json",
      "world_certificate",
    ) as unknown as LthworldManifest["world_certificate"],
    style_compatibility: requireObject(
      obj.style_compatibility,
      "world_manifest.json",
      "style_compatibility",
    ) as unknown as LthworldManifest["style_compatibility"],
    certified: Boolean(obj.certified),
    asset_package_summary: requireObject(
      obj.asset_package_summary,
      "world_manifest.json",
      "asset_package_summary",
    ) as unknown as LthworldManifest["asset_package_summary"],
    artifact_statuses: requireObject(
      obj.artifact_statuses,
      "world_manifest.json",
      "artifact_statuses",
    ) as LthworldManifest["artifact_statuses"],
    diagnostics: requireArray<Record<string, unknown>>(
      obj.diagnostics,
      "world_manifest.json",
      "diagnostics",
    ),
  };
}

export function parseWorldGraph(raw: unknown): LatheWorldGraph {
  const obj = requireObject(raw, "world_graph.json", "");
  return {
    version: requireString(obj.version, "world_graph.json", "version"),
    world_id: requireString(obj.world_id, "world_graph.json", "world_id"),
    prompt: requireString(obj.prompt, "world_graph.json", "prompt"),
    seed: requireNumber(obj.seed, "world_graph.json", "seed"),
    style: requireObject(obj.style, "world_graph.json", "style") as LatheWorldGraph["style"],
    asset_count: requireNumber(obj.asset_count, "world_graph.json", "asset_count"),
    role_counts: requireObject(
      obj.role_counts,
      "world_graph.json",
      "role_counts",
    ) as Record<string, number>,
    style_pack_ids: requireArray<string>(
      obj.style_pack_ids,
      "world_graph.json",
      "style_pack_ids",
    ),
    assets: requireArray<LatheWorldGraph["assets"][number]>(
      obj.assets,
      "world_graph.json",
      "assets",
    ),
    path_nodes: requireArray<LatheWorldGraph["path_nodes"][number]>(
      obj.path_nodes,
      "world_graph.json",
      "path_nodes",
    ),
    path_edges: requireArray<LatheWorldGraph["path_edges"][number]>(
      obj.path_edges,
      "world_graph.json",
      "path_edges",
    ),
    hazard_zones: requireArray<Record<string, unknown>>(
      obj.hazard_zones,
      "world_graph.json",
      "hazard_zones",
    ),
    quest_anchors: requireArray<Record<string, unknown>>(
      obj.quest_anchors,
      "world_graph.json",
      "quest_anchors",
    ),
    player_spawn_node_id: requireString(
      obj.player_spawn_node_id,
      "world_graph.json",
      "player_spawn_node_id",
    ),
    diagnostics: requireArray<Record<string, unknown>>(
      obj.diagnostics,
      "world_graph.json",
      "diagnostics",
    ),
  };
}

export function parseTraversalEvidence(raw: unknown): LatheTraversalEvidence {
  const obj = requireObject(raw, "traversal_evidence.json", "");
  return {
    version: requireString(obj.version, "traversal_evidence.json", "version"),
    world_id: requireString(obj.world_id, "traversal_evidence.json", "world_id"),
    seed: requireNumber(obj.seed, "traversal_evidence.json", "seed"),
    nav_status: requireString(obj.nav_status, "traversal_evidence.json", "nav_status"),
    collision_status: requireString(
      obj.collision_status,
      "traversal_evidence.json",
      "collision_status",
    ),
    hazard_blocking_status: requireString(
      obj.hazard_blocking_status,
      "traversal_evidence.json",
      "hazard_blocking_status",
    ),
    walkable_surface_status: requireString(
      obj.walkable_surface_status,
      "traversal_evidence.json",
      "walkable_surface_status",
    ),
    mesh_extraction_status: requireString(
      obj.mesh_extraction_status,
      "traversal_evidence.json",
      "mesh_extraction_status",
    ),
    player_spawn: requireObject(
      obj.player_spawn,
      "traversal_evidence.json",
      "player_spawn",
    ),
    path_nodes: requireArray<LatheTraversalEvidence["path_nodes"][number]>(
      obj.path_nodes,
      "traversal_evidence.json",
      "path_nodes",
    ),
    path_edges: requireArray<LatheTraversalEvidence["path_edges"][number]>(
      obj.path_edges,
      "traversal_evidence.json",
      "path_edges",
    ),
    hazard_zones: requireArray<Record<string, unknown>>(
      obj.hazard_zones,
      "traversal_evidence.json",
      "hazard_zones",
    ),
    collision_compound: requireObject(
      obj.collision_compound,
      "traversal_evidence.json",
      "collision_compound",
    ),
    connectivity: requireObject(
      obj.connectivity,
      "traversal_evidence.json",
      "connectivity",
    ),
    spawn_safety_check: requireObject(
      obj.spawn_safety_check,
      "traversal_evidence.json",
      "spawn_safety_check",
    ),
    quest_anchors: requireArray<Record<string, unknown>>(
      obj.quest_anchors,
      "traversal_evidence.json",
      "quest_anchors",
    ),
    walkable_polygons: requireObject(
      obj.walkable_polygons,
      "traversal_evidence.json",
      "walkable_polygons",
    ) as LatheTraversalEvidence["walkable_polygons"],
  };
}

export function parseMinimapEvidence(raw: unknown): LatheMinimapEvidence {
  const obj = requireObject(raw, "minimap_evidence.json", "");
  return {
    version: requireString(obj.version, "minimap_evidence.json", "version"),
    status: requireString(obj.status, "minimap_evidence.json", "status"),
    path: requireString(obj.path, "minimap_evidence.json", "path"),
    width: requireNumber(obj.width, "minimap_evidence.json", "width"),
    height: requireNumber(obj.height, "minimap_evidence.json", "height"),
    source: requireString(obj.source, "minimap_evidence.json", "source"),
    sha256: requireString(obj.sha256, "minimap_evidence.json", "sha256"),
  };
}
