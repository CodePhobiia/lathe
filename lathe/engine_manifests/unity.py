"""Unity engine manifest adapter (STAGE-10).

Emits ``<asset>.lathe_for_unity.yaml``. Unity's GLTFast/UnityGLTF importers
consume the glb directly; this sidecar describes the LODGroup component and
Transform hierarchy the downstream ScriptedImporter should construct:

  - A root ``GameObject`` with ``tags`` on the Unity ``Tag`` / ``Label`` system
  - A ``LODGroup`` component with per-LOD ``screenRelativeTransitionHeight``
    and the mesh reference for each LOD
  - Empty ``GameObject`` nodes for each socket/pivot (Unity attachment convention)
  - ``MeshCollider`` entries for ``collision_hull.glb`` and per-part hulls

The YAML is hand-formatted (no third-party yaml dependency required in the
core package) to keep the adapter self-contained.
"""

from __future__ import annotations

from typing import Any


def _yaml_scalar(value: Any) -> str:
    text = str(value)
    if not text:
        return '""'
    if all(char.isalnum() or char in "._-/" for char in text):
        return text
    return '"' + text.replace('"', '\\"') + '"'


def emit_unity_manifest(context: dict[str, Any], asset_name: str) -> str:
    """Build the Unity sidecar YAML as a string (caller writes to disk)."""
    lines: list[str] = []
    lines.append("%YAML 1.1")
    lines.append("# Lathe Unity import manifest (schemaVersion 1)")
    lines.append("schemaVersion: 1")
    lines.append("engine: unity")
    lines.append('engineVersion: ">=2022.3"')
    lines.append(f"assetName: {asset_name}")
    lines.append("rootGameObject:")
    lines.append(f"  name: {asset_name}")
    tags = list(context.get("gameplay_tags", []))
    lines.append("  tags:")
    for tag in tags:
        lines.append(f"    - {tag}")
    lines.append("  components:")
    lines.append("    - type: LODGroup")
    lines.append("      lods:")
    for lod in context.get("lods", []):
        if not isinstance(lod, dict):
            continue
        coverage = lod.get("screen_coverage")
        if coverage is None:
            coverage = 0.0
        lines.append(f"        - level: {int(lod.get('level', 0))}")
        lines.append(f"          meshUri: {lod.get('mesh_uri')}")
        lines.append(f"          screenRelativeTransitionHeight: {float(coverage):.4f}")
        lines.append(f"          distanceMin: {float(lod.get('distance_min', 0.0) or 0.0):.3f}")
        dist_max = lod.get("distance_max")
        if dist_max is None:
            lines.append("          distanceMax: ~")
        else:
            lines.append(f"          distanceMax: {float(dist_max):.3f}")
        lines.append(f"          triangleCount: {int(lod.get('triangle_count') or 0)}")
    # Sockets
    lines.append("  sockets:")
    for sock in context.get("sockets", []):
        if not isinstance(sock, dict) or not sock.get("id"):
            continue
        lines.append(f"    - name: socket_{sock['id']}")
        lines.append(f"      anchorId: {sock['id']}")
        lines.append(f"      socketType: {sock.get('socket_type') or sock.get('kind') or 'attach'}")
        origin = list(sock.get("origin", [0.0, 0.0, 0.0]))
        lines.append(f"      origin: [{origin[0]}, {origin[1]}, {origin[2]}]")
        axis = list(sock.get("axis", [0.0, 1.0, 0.0]))
        lines.append(f"      axis: [{axis[0]}, {axis[1]}, {axis[2]}]")
        parent = sock.get("parent_part_id")
        if parent:
            lines.append(f"      parentPartId: {parent}")
    # Pivots
    lines.append("  pivots:")
    for piv in context.get("pivots", []):
        if not isinstance(piv, dict) or not piv.get("id"):
            continue
        lines.append(f"    - name: pivot_{piv['id']}")
        lines.append(f"      anchorId: {piv['id']}")
        lines.append(f"      pivotType: {piv.get('pivot_type') or 'center'}")
        origin = list(piv.get("origin", [0.0, 0.0, 0.0]))
        lines.append(f"      origin: [{origin[0]}, {origin[1]}, {origin[2]}]")
    # Collisions
    lines.append("  collision:")
    for col in context.get("collisions", []):
        if not isinstance(col, dict):
            continue
        lines.append(f"    - id: {col.get('id', 'hull')}")
        lines.append(f"      kind: {col.get('kind', 'hull')}")
        lines.append(f"      meshUri: {col.get('uri')}")
        parent = col.get("parent_part_id")
        if parent:
            lines.append(f"      parentPartId: {parent}")
    # Materials
    lines.append("  materials:")
    for mat in context.get("materials", []):
        if not isinstance(mat, dict) or not mat.get("id"):
            continue
        lines.append(f"    - id: {mat['id']}")
        display = mat.get("display_name") or mat["id"]
        lines.append(f'      displayName: "{display}"')
    _append_surface_material_semantics(lines, context)
    _append_texture_conventions(lines, context)
    _append_construction_provenance(lines, context)
    _append_runtime_semantics(lines, context)
    return "\n".join(lines) + "\n"


def _append_surface_material_semantics(lines: list[str], context: dict[str, Any]) -> None:
    semantics = context.get("surface_material_semantics")
    if not isinstance(semantics, dict):
        conventions = context.get("texture_conventions")
        conventions = conventions if isinstance(conventions, dict) else {}
        semantics = conventions.get("surface_material_semantics")
    if not isinstance(semantics, dict):
        return
    zones = [zone for zone in semantics.get("zones") or [] if isinstance(zone, dict)]
    if not zones:
        return
    lines.append("  surfaceMaterialSemantics:")
    lines.append(f"    schema: {_yaml_scalar(semantics.get('schema') or 'lathe.surface_material_semantics.v1')}")
    role_counts = semantics.get("role_counts")
    if isinstance(role_counts, dict) and role_counts:
        lines.append("    roleCounts:")
        for role, count in sorted(role_counts.items()):
            lines.append(f"      {_yaml_scalar(role)}: {int(count)}")
    lines.append("    zones:")
    for zone in zones:
        part = zone.get("part")
        if not part:
            continue
        lines.append(f"      - part: {_yaml_scalar(part)}")
        lines.append(f"        material: {_yaml_scalar(zone.get('material') or '')}")
        role = zone.get("semantic_surface_role")
        if role:
            lines.append(f"        semanticSurfaceRole: {_yaml_scalar(role)}")
        hint = zone.get("topology_material_hint")
        if hint:
            lines.append(f"        topologyMaterialHint: {_yaml_scalar(hint)}")
        source = zone.get("material_source")
        if source:
            lines.append(f"        materialSource: {_yaml_scalar(source)}")
        features = [str(item) for item in zone.get("surface_features") or [] if str(item)]
        if features:
            lines.append("        surfaceFeatures:")
            for feature in features:
                lines.append(f"          - {_yaml_scalar(feature)}")
        wear_layers = [item for item in zone.get("wear_layers") or [] if isinstance(item, dict)]
        if wear_layers:
            lines.append("        wearLayers:")
            for layer in wear_layers:
                lines.append(f"          - kind: {_yaml_scalar(layer.get('kind') or '')}")
                if layer.get("intensity") is not None:
                    lines.append(f"            intensity: {float(layer.get('intensity') or 0.0):.4f}")


def _append_texture_conventions(lines: list[str], context: dict[str, Any]) -> None:
    conventions = context.get("texture_conventions")
    textures = list(context.get("textures") or [])
    if not isinstance(conventions, dict) and not textures:
        return
    conventions = conventions if isinstance(conventions, dict) else {}
    lines.append("  textureConventions:")
    lines.append(f"    schema: {_yaml_scalar(conventions.get('schema') or 'lathe.texture_conventions.v1')}")
    normal = conventions.get("normal_map")
    if isinstance(normal, dict):
        lines.append("    normalMap:")
        lines.append(f"      space: {_yaml_scalar(normal.get('space') or 'tangent')}")
        lines.append(f"      basis: {_yaml_scalar(normal.get('basis') or 'mesh_uv_tangent')}")
        lines.append(
            "      sourceConvention: "
            f"{_yaml_scalar(normal.get('source_convention') or 'positive_bitangent_green_channel')}"
        )
        lines.append(f"      greenChannel: {_yaml_scalar(normal.get('green_channel') or 'positive_bitangent')}")
        lines.append(f"      encoding: {_yaml_scalar(normal.get('encoding') or 'rgb_unit_signed_8bit')}")
        lines.append(f"      zPolicy: {_yaml_scalar(normal.get('z_policy') or 'renormalized_from_xy')}")
        neutral = normal.get("neutral_rgb")
        if isinstance(neutral, list) and len(neutral) >= 3:
            lines.append("      neutralRgb:")
            for value in neutral[:3]:
                lines.append(f"        - {int(value)}")
        lines.append(
            "      worldSpaceFaceNormalBake: "
            f"{str(bool(normal.get('world_space_face_normal_bake'))).lower()}"
        )
        base_source = normal.get("base_source")
        if base_source:
            lines.append(f"      baseSource: {_yaml_scalar(base_source)}")
        detail_source = normal.get("detail_source")
        if detail_source:
            lines.append(f"      detailSource: {_yaml_scalar(detail_source)}")
    lines.append("    textures:")
    for texture in textures:
        if not isinstance(texture, dict) or not texture.get("name"):
            continue
        lines.append(f"      - name: {_yaml_scalar(texture.get('name'))}")
        lines.append(f"        uri: {_yaml_scalar(texture.get('uri') or '')}")
        lines.append(f"        usage: {_yaml_scalar(texture.get('usage') or texture.get('name'))}")
        lines.append(f"        colorSpace: {_yaml_scalar(texture.get('color_space') or 'non_color_linear')}")
        lines.append(f"        sampleAs: {_yaml_scalar(texture.get('sample_as') or 'data')}")
        if texture.get("normal_space"):
            lines.append(f"        normalSpace: {_yaml_scalar(texture.get('normal_space'))}")
            lines.append(f"        normalBasis: {_yaml_scalar(texture.get('normal_basis') or 'mesh_uv_tangent')}")
            lines.append(f"        greenChannel: {_yaml_scalar(texture.get('green_channel') or 'positive_bitangent')}")
            if texture.get("source_convention"):
                lines.append(f"        sourceConvention: {_yaml_scalar(texture.get('source_convention'))}")
            if texture.get("encoding"):
                lines.append(f"        encoding: {_yaml_scalar(texture.get('encoding'))}")
            if texture.get("z_policy"):
                lines.append(f"        zPolicy: {_yaml_scalar(texture.get('z_policy'))}")
        channels = texture.get("channels")
        if isinstance(channels, dict) and channels:
            lines.append("        channels:")
            for channel, purpose in channels.items():
                lines.append(f"          {_yaml_scalar(channel)}: {_yaml_scalar(purpose)}")


def _append_construction_provenance(lines: list[str], context: dict[str, Any]) -> None:
    provenance = context.get("construction_provenance")
    if not isinstance(provenance, dict):
        return
    lines.append("  latheConstructionProvenance:")
    lines.append(f"    schema: {_yaml_scalar(provenance.get('schema') or 'lathe.package.construction_provenance.v1')}")
    selected = provenance.get("selected_candidate_id")
    if selected:
        lines.append(f"    selectedCandidateId: {_yaml_scalar(selected)}")
    shape_mode = provenance.get("shape_mode")
    if shape_mode:
        lines.append(f"    shapeMode: {_yaml_scalar(shape_mode)}")
    geometry_kernel = provenance.get("geometry_kernel")
    if geometry_kernel:
        lines.append(f"    geometryKernel: {_yaml_scalar(geometry_kernel)}")
    lines.append(f"    kernelProgramSucceeded: {str(bool(provenance.get('kernel_program_succeeded'))).lower()}")
    lines.append(f"    kernelProgramManifestCount: {int(provenance.get('kernel_program_manifest_count') or 0)}")
    lines.append(f"    operationRecordCount: {int(provenance.get('operation_record_count') or 0)}")
    lines.append(f"    kernelFeatureDetailCount: {int(provenance.get('kernel_feature_detail_count') or 0)}")
    lines.append(f"    kernelEdgeTreatmentCount: {int(provenance.get('kernel_edge_treatment_count') or 0)}")
    lines.append(f"    kernelPatternInstanceCount: {int(provenance.get('kernel_pattern_instance_count') or 0)}")
    lines.append(f"    kernelDeformCount: {int(provenance.get('kernel_deform_count') or 0)}")
    lines.append(f"    kernelProfilePathCount: {int(provenance.get('kernel_profile_path_count') or 0)}")
    lines.append(f"    kernelEdgeControlCount: {int(provenance.get('kernel_edge_control_count') or 0)}")
    lines.append(f"    kernelComponentAssemblyCount: {int(provenance.get('kernel_component_assembly_count') or 0)}")
    lines.append(f"    kernelSdfFieldCount: {int(provenance.get('kernel_sdf_field_count') or 0)}")
    lines.append(f"    kernelTerrainFieldCount: {int(provenance.get('kernel_terrain_field_count') or 0)}")
    lines.append(f"    kernelScatterCount: {int(provenance.get('kernel_scatter_count') or 0)}")
    lines.append(f"    kernelSurfaceDamageCount: {int(provenance.get('kernel_surface_damage_count') or 0)}")
    manifests = provenance.get("kernel_program_manifests")
    if isinstance(manifests, list) and manifests:
        lines.append("    kernelProgramManifests:")
        for manifest in manifests[:16]:
            if not isinstance(manifest, dict):
                continue
            lines.append(f"      - programKind: {_yaml_scalar(manifest.get('program_kind') or '')}")
            route = manifest.get("route")
            if route:
                lines.append(f"        route: {_yaml_scalar(route)}")
            backend = manifest.get("backend")
            if backend:
                lines.append(f"        backend: {_yaml_scalar(backend)}")
            lines.append(f"        operandCount: {int(manifest.get('operand_count') or 0)}")
            lines.append(f"        operationCount: {int(manifest.get('operation_count') or 0)}")
            lines.append(
                "        semanticOperationRecordCount: "
                f"{int(manifest.get('semantic_operation_record_count') or 0)}"
            )
            required = manifest.get("required_capabilities")
            if isinstance(required, list) and required:
                lines.append("        requiredCapabilities:")
                for capability in required:
                    lines.append(f"          - {_yaml_scalar(capability)}")
    summary = provenance.get("face_operation_summary")
    if isinstance(summary, dict) and summary:
        lines.append("    faceOperationSummary:")
        lines.append(f"      faceCount: {int(summary.get('face_count') or 0)}")
        lines.append(f"      operationCount: {int(summary.get('operation_count') or 0)}")
        operations = summary.get("operations")
        if isinstance(operations, dict) and operations:
            lines.append("      operations:")
            for operation_id, count in operations.items():
                lines.append(f"        {_yaml_scalar(operation_id)}: {int(count or 0)}")
    records = provenance.get("operation_records")
    if isinstance(records, list) and records:
        lines.append("    operationRecords:")
        for record in records[:64]:
            if not isinstance(record, dict):
                continue
            operation_id = record.get("operation_id") or record.get("id") or ""
            operation = record.get("operation") or record.get("repair_action") or ""
            lines.append(f"      - operationId: {_yaml_scalar(operation_id)}")
            if operation:
                lines.append(f"        operation: {_yaml_scalar(operation)}")
            part = record.get("part")
            if part:
                lines.append(f"        part: {_yaml_scalar(part)}")
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_feature_details",
        yaml_key="kernelFeatureDetails",
        kind_key="feature_kind",
        count_key="feature_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_edge_treatments",
        yaml_key="kernelEdgeTreatments",
        kind_key="treatment_kind",
        count_key="treatment_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_pattern_instances",
        yaml_key="kernelPatternInstances",
        kind_key="pattern_kind",
        count_key="instance_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_deforms",
        yaml_key="kernelDeforms",
        kind_key="operation",
        count_key="result_face_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_profile_paths",
        yaml_key="kernelProfilePaths",
        kind_key="profile_kind",
        count_key="result_face_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_edge_controls",
        yaml_key="kernelEdgeControls",
        kind_key="edge_control_kind",
        count_key="result_face_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_component_assemblies",
        yaml_key="kernelComponentAssemblies",
        kind_key="assembly_kind",
        count_key="result_face_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_sdf_fields",
        yaml_key="kernelSdfFields",
        kind_key="field_kind",
        count_key="result_face_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_terrain_fields",
        yaml_key="kernelTerrainFields",
        kind_key="terrain_kind",
        count_key="result_face_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_scatters",
        yaml_key="kernelScatters",
        kind_key="scatter_kind",
        count_key="instance_count",
    )
    _append_kernel_provenance_records(
        lines,
        provenance,
        key="kernel_surface_damage",
        yaml_key="kernelSurfaceDamage",
        kind_key="damage_kind",
        count_key="damage_count",
    )


def _append_kernel_provenance_records(
    lines: list[str],
    provenance: dict[str, Any],
    *,
    key: str,
    yaml_key: str,
    kind_key: str,
    count_key: str,
) -> None:
    records = provenance.get(key)
    if not isinstance(records, list) or not records:
        return
    lines.append(f"    {yaml_key}:")
    for record in records[:32]:
        if not isinstance(record, dict):
            continue
        operation = record.get("operation") or record.get("semantic_operation") or ""
        lines.append(f"      - operation: {_yaml_scalar(operation)}")
        kind = record.get(kind_key)
        if kind:
            lines.append(f"        kind: {_yaml_scalar(kind)}")
        source_part = record.get("source_part")
        if source_part:
            lines.append(f"        sourcePart: {_yaml_scalar(source_part)}")
        method = record.get("method")
        if method:
            lines.append(f"        method: {_yaml_scalar(method)}")
        if count_key in record:
            lines.append(f"        count: {int(record.get(count_key) or 0)}")


def _append_runtime_semantics(lines: list[str], context: dict[str, Any]) -> None:
    semantics = context.get("runtime_semantics")
    if not isinstance(semantics, dict):
        return
    systems = semantics.get("systems")
    if not isinstance(systems, dict):
        return
    lines.append("  latheRuntimeSemantics:")
    schema = semantics.get("schema")
    lines.append(f"    schema: {_yaml_scalar(schema or 'lathe.engine_runtime_semantics.v1')}")
    lines.append("    systems:")
    for name, system in systems.items():
        if not isinstance(name, str) or not isinstance(system, dict):
            continue
        lines.append(f"      {name}:")
        lines.append(f"        active: {str(bool(system.get('active'))).lower()}")
        source = system.get("source")
        if source:
            lines.append(f"        source: {_yaml_scalar(source)}")
        active_fields = system.get("active_fields")
        if isinstance(active_fields, list) and active_fields:
            lines.append("        activeFields:")
            for field in active_fields:
                lines.append(f"          - {_yaml_scalar(field)}")
        else:
            lines.append("        activeFields: []")
        counts = system.get("counts")
        if isinstance(counts, dict):
            lines.append("        counts:")
            for field, count in counts.items():
                if isinstance(field, str) and isinstance(count, int):
                    lines.append(f"          {field}: {count}")
        ids = system.get("ids")
        if isinstance(ids, dict) and ids:
            lines.append("        ids:")
            for field, values in ids.items():
                if not isinstance(field, str) or not isinstance(values, list):
                    continue
                lines.append(f"          {field}:")
                for value in values:
                    lines.append(f"            - {_yaml_scalar(value)}")
