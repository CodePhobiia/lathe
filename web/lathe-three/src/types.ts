/**
 * Type definitions matching the .lthpkg sidecar JSON shapes emitted
 * by lathe.asset_foundry.package_writer.
 *
 * These types are the public surface @lathe/three consumers (the web
 * viewer, the playground/studio, Wonder's repair loop) depend on.
 * Changes here must stay in lockstep with the Python contract
 * versions defined in lathe/asset_foundry/*.py.
 */

/** manifest.json — the .lthpkg top-level manifest. */
export interface LthpkgManifest {
  version: string;
  asset_id: string;
  style_pack_id: string;
  family: string;
  generator_id: string;
  seed: number;
  parameters_hash: string;
  sidecar_files: Record<string, string>;
  quality_ladder_target: number;
  quality_ladder_achieved: number;
  overall_score: number;
  created_utc: number;
  notes: string;
}

/** semantic-index.json — parts, sockets, material slots, bbox. */
export interface LatheSemanticIndex {
  version: string;
  asset_id: string;
  family: string;
  style_pack_id: string;
  semantic_parts: string[];
  semantic_sockets: LatheSemanticSocket[];
  material_slots: LatheMaterialSlot[];
  bbox_cm: [
    [number, number, number],
    [number, number, number]
  ];
  quality_ladder_target: number;
}

/** A semantic socket / attachment point. */
export interface LatheSemanticSocket {
  socket_id: string;
  role: string;
  position_cm: [number, number, number];
  orientation_quat: [number, number, number, number];
  capacity: number;
  allowed_attachments: string[];
}

/** A material slot binding zones to a material class. */
export interface LatheMaterialSlot {
  slot_id: string;
  zone_id_prefix: string;
  material_class: string;
  palette_token: string;
  uv_policy: string;
}

/** materials.json — material slot list. */
export interface LatheMaterialZone {
  slot_id: string;
  zone_id_prefix: string;
  material_class: string;
  palette_token: string;
  uv_policy: string;
}

/** operations.json — generator parameters + op graph + plan. */
export interface LatheConstructionProvenance {
  version: string;
  asset_id: string;
  generator_id: string;
  parameters: Record<string, unknown>;
  geometry_payload: Record<string, unknown>;
  op_graph?: {
    version: string;
    node_count: number;
    nodes: Array<{
      operation_id: string;
      op: string;
      semantic_part: string;
      inputs: string[];
      params: Record<string, unknown>;
      required_capabilities: string[];
      fallback_policy: string;
      evidence_requirements: string[];
      attribute_mapping: {
        preserved: string[];
        transformed: string[];
        split: string[];
        merged: string[];
        generated: string[];
        dropped: string[];
      };
    }>;
  };
  op_graph_plan?: {
    asset_id: string;
    graph_version: string;
    lanes_by_op: Record<string, string>;
    capability_by_op: Record<string, string>;
    unsupported_ops: string[];
    fallback_ops: string[];
    not_started_ops: string[];
    missing_from_matrix: string[];
    topo_order: string[];
  };
}

/** diagnostics.json — generator diagnostics + capability slice. */
export interface LatheDiagnostics {
  version: string;
  asset_id: string;
  generator_diagnostics: string[];
  certificate_findings: string[];
  certificate_repair_recommendations: string[];
  capability_matrix: {
    version: string;
    record_count: number;
    counts_by_status: Record<string, number>;
    counts_by_family: Record<string, number>;
    records: Array<{
      operation_id: string;
      op_family: string;
      status: string;
      supporting_kernels: string[];
      evidence_requirements: string[];
      fallback_reason: string | null;
      notes: string;
    }>;
  };
}

/** runtime.json — runtime artifact manifest. */
export interface LatheRuntimeManifest {
  version: string;
  asset_id: string;
  style_pack_id: string;
  family: string;
  bbox_cm: [
    [number, number, number],
    [number, number, number]
  ];
  units: string;
  pivot_cm: [number, number, number];
  scale_anchor: string;
  render_mesh: {
    artifact_path: string | null;
    status: "real" | "proxy" | "unbuilt";
    status_reason: string;
  };
  collision: LatheCollisionSpec;
  nav: LatheNavSpec;
  lod: LatheLodSpec;
  material_zone_manifest: Record<string, string>;
  semantic_sockets: LatheSemanticSocket[];
  semantic_parts: string[];
  quality_ladder_target: number;
  diagnostics: string[];
  engine_readiness: Record<string, "ready" | "proxy" | "unsupported">;
}

export interface LatheCollisionSpec {
  strategy: string;
  proxy_artifact_path: string | null;
  proxy_status: "real" | "proxy" | "unbuilt";
  proxy_status_reason: string;
  walkable_zones: string[];
  blocking_zones: string[];
  hazard_zones: string[];
}

export interface LatheNavSpec {
  contributes: boolean;
  walkable_polygon_artifact_path: string | null;
  nav_status: "real" | "proxy" | "unbuilt";
  nav_status_reason: string;
  walkable_zones: string[];
}

export interface LatheLodSpec {
  lod_levels: number;
  target_triangle_counts: number[];
  lod_artifact_paths: string[];
  lod_status: "real" | "proxy" | "unbuilt";
  lod_status_reason: string;
  preserve_silhouette: boolean;
}

/** evidence.json — runtime manifest + certificate + truth contract. */
export interface LatheEvidence {
  version: string;
  asset_id: string;
  runtime_manifest: LatheRuntimeManifest;
  certificate: LatheQualityCertificate;
  rule_of_truth: string;
}

/** The quality certificate per asset. */
export interface LatheQualityCertificate {
  version: string;
  asset_id: string;
  style_pack_id: string;
  achieved_level: number;
  target_level: number;
  overall_score: number;
  metrics: Record<string, number>;
  findings: string[];
  repair_recommendations: string[];
}
