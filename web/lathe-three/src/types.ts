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
    provenance_summary?: {
      preserved: number;
      transformed: number;
      split: number;
      merged: number;
      generated: number;
      dropped: number;
      dropped_fields: Record<string, number>;
      provenance_loss_diagnostic: string;
    };
    nodes: Array<{
      operation_id: string;
      op: string;
      semantic_part: string;
      inputs: string[];
      params: Record<string, unknown>;
      required_capabilities: string[];
      fallback_policy: string;
      evidence_requirements: string[];
      bounds_cm?: [[number, number, number], [number, number, number]] | null;
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
    spatial_clusters?: Array<{
      cluster_id: string;
      operation_ids: string[];
      cluster_op_count: number;
      cluster_reason: string;
      bounds_cm: [[number, number, number], [number, number, number]] | null;
    }>;
    boolean_clusters?: Array<{
      cluster_id: string;
      operation_ids: string[];
      boolean_ops: string[];
      input_primitive_ids: string[];
      boolean_expression: string;
      preferred_backend: string;
      actual_execution_mode: string;
      fallback_diagnostic: string | null;
    }>;
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
    counts_by_claim_level?: Record<string, number>;
    records: Array<{
      operation_id: string;
      op_family: string;
      status: string;
      claim_level?: "typed_contract" | "execution_partial" | "artifact_real" | "product_complete" | string;
      supporting_kernels: string[];
      evidence_requirements: string[];
      fallback_reason: string | null;
      backend_required: string | null;
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
  decomposition_strategy?: string;
  proxy_component_count?: number;
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
  actual_triangle_counts?: number[];
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
  external_backend_evidence?: LatheExternalBackendEvidence[];
  visual_quality_gate?: LatheVisualQualityGate;
  rule_of_truth: string;
}

export interface LatheExternalBackendEvidence {
  operation_id: string;
  status: "blocked" | "real" | "unsupported" | string;
  blocker: string;
  backend_required: string;
  artifact_path: string | null;
  rule_of_truth: string;
}

export interface LatheVisualQualityGate {
  version: string;
  pipeline_certified: boolean;
  visual_quality_gate: "approved" | "review_required" | "not_verified" | "not_approved" | string;
  human_review_required: boolean;
  visual_claim_level: "visual_approved" | "pipeline_certified_only" | "not_verified" | "pipeline_failed" | string;
  blockers: string[];
  signals: Record<string, unknown>;
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

/** repair-history.json - optional before/after semantic repair evidence. */
export interface LatheRepairHistory {
  version: string;
  asset_id: string;
  status: string;
  original_package: Record<string, unknown>;
  diagnostic_ids: string[];
  selected_repair_actions: string[];
  patched_intent_identifiers: string[];
  repair_target_layers: string[];
  attempted_vs_actual: Array<Record<string, unknown>>;
  rebuilt_package: Record<string, unknown>;
  metric_deltas: Record<string, unknown>;
  preview_before_after: Record<string, unknown>;
  notes: string[];
  rule_of_truth: string;
}

/** Viewer-authored repair request. Lathe Core must execute it. */
export interface LatheRepairRequest {
  version: "lathe.web_viewer.repair_request_v1";
  request_id: string;
  asset_id: string;
  status: "request_exported" | "rebuild_pending" | "rebuild_blocked" | "repaired_package_loaded";
  execution_boundary: {
    requester: "lathe-web-viewer";
    executor: "lathe-core-cli-or-service";
    status: "not_executed_in_browser";
  };
  source_manifest: LthpkgManifest;
  source_repair_history: LatheRepairHistory | null;
  diagnostics: string[];
  repair_recommendations: string[];
  before_package: Record<string, unknown>;
  after_package: Record<string, unknown>;
  rule_of_truth: string;
}

/** world_manifest.json - the .lthworld top-level manifest. */
export interface LthworldManifest {
  version: string;
  world_id: string;
  prompt: string;
  seed: number;
  mode: string;
  style_pack_id: string;
  kit_id: string;
  asset_count: number;
  role_counts: Record<string, number>;
  style_pack_ids: string[];
  sidecar_files: Record<string, string>;
  world_graph_status: string;
  traversal_status: string;
  visual_claim_level: string;
  world_certificate: LatheWorldCertificate;
  style_compatibility: LatheWorldStyleCompatibility;
  certified: boolean;
  asset_package_summary: LatheWorldAssetPackageSummary;
  artifact_statuses: Record<string, Record<string, unknown>>;
  diagnostics: Array<Record<string, unknown>>;
}

export interface LatheWorldAssetPackageSummary {
  total: number;
  linked: number;
  planned: number;
  links: Record<string, LatheWorldAssetPackageLink>;
}

export interface LatheWorldAssetPackageLink {
  status: string;
  asset_id?: string;
  role?: string;
  package?: string;
  render_mesh_status?: string;
  collision_status?: string;
  nav_status?: string;
  generator_id?: string;
  source?: string;
  target?: string;
  reason?: string;
}

export interface LatheWorldCertificate {
  version: string;
  world_id: string;
  target_level: number;
  achieved_level: number;
  certified: boolean;
  metrics: Record<string, number>;
  findings: Array<Record<string, unknown>>;
  repair_recommendations: string[];
  style_compatibility: LatheWorldStyleCompatibility;
}

export interface LatheWorldStyleCompatibility {
  version: string;
  world_id: string;
  compatible: boolean;
  declared_style_packs: string[];
  declared_bands: string[];
  incompatible_pairs: string[][];
  diagnostics: string[];
  per_asset: Array<Record<string, unknown>>;
}

/** world_graph.json - Forge-composed world graph. */
export interface LatheWorldGraph {
  version: string;
  world_id: string;
  prompt: string;
  seed: number;
  style: {
    style_pack_id: string;
    kit_id: string;
    director_terms: string[];
    material_palette_id: string;
  };
  asset_count: number;
  role_counts: Record<string, number>;
  style_pack_ids: string[];
  assets: LatheWorldAsset[];
  path_nodes: LatheWorldPathNode[];
  path_edges: LatheWorldPathEdge[];
  hazard_zones: Array<Record<string, unknown>>;
  quest_anchors: Array<Record<string, unknown>>;
  player_spawn_node_id: string;
  diagnostics: Array<Record<string, unknown>>;
}

export interface LatheWorldAsset {
  world_asset_id: string;
  role: string;
  family: string;
  generator_id: string;
  asset_id: string;
  style_pack_id: string;
  seed: number;
  placement: LatheWorldAssetPlacement;
  package_ref: string;
  package_status: string;
  evidence_status: Record<string, string>;
  tags: string[];
}

export interface LatheWorldAssetPlacement {
  position_cm: [number, number, number];
  rotation_y_deg: number;
  scale: number;
  zone_id: string;
  anchor_id: string;
  socket_ref: string;
}

export interface LatheWorldPathNode {
  node_id: string;
  role: string;
  position_cm: [number, number, number];
  asset_ref: string;
  status: string;
}

export interface LatheWorldPathEdge {
  edge_id: string;
  from_node: string;
  to_node: string;
  route_id: string;
  control_points_cm: Array<[number, number, number]>;
  status: string;
  width_cm: number;
}

export interface LatheTraversalEvidence {
  version: string;
  world_id: string;
  seed: number;
  nav_status: string;
  collision_status: string;
  hazard_blocking_status: string;
  walkable_surface_status: string;
  mesh_extraction_status: string;
  player_spawn: Record<string, unknown>;
  path_nodes: LatheWorldPathNode[];
  path_edges: LatheWorldPathEdge[];
  hazard_zones: Array<Record<string, unknown>>;
  collision_compound: Record<string, unknown>;
  connectivity: Record<string, unknown>;
  spawn_safety_check: Record<string, unknown>;
  quest_anchors: Array<Record<string, unknown>>;
  walkable_polygons: {
    status: string;
    source: string;
    mesh_extraction_status: string;
    polygons: Array<Record<string, unknown>>;
  };
}

export interface LatheMinimapEvidence {
  version: string;
  status: string;
  path: string;
  width: number;
  height: number;
  source: string;
  sha256: string;
}

export interface LatheWorldEvidence {
  version: string;
  world_id: string;
  status: string;
  world_renders: Record<string, unknown>;
  asset_canonical_view_renders: Record<string, unknown>;
  wonder_critique_trace: Record<string, unknown>;
  repair_histories: Array<Record<string, unknown>>;
  engine_import_evidence: Record<string, unknown>;
  rule_of_truth: string;
}

export interface LatheWonderCritiqueTrace {
  version: string;
  status: string;
  world_id?: string;
  world_asset_id?: string;
  asset_id?: string;
  summary?: Record<string, unknown>;
  rounds?: Array<Record<string, unknown>>;
  rule_of_truth?: string;
}

export interface LatheWorldPackageMemberMetadata {
  world_asset_id: string;
  asset_id: string;
  role: string;
  package_status: string;
  package_path: string | null;
}
