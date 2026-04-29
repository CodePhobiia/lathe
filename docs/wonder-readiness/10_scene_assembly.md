# Scene Assembly IR

Phase 11 adds a deterministic Scene Assembly IR over existing Scene Graph JSON.
The layer does not execute Blender or asset compilers. It records identity,
selection, material, render-index, and package-relative proxy artifact paths
that the deterministic package builder now uses for proxy PNG renders and proxy
GLB export.

`lathe.scene.assembly.assemble_scene(scene_graph)` emits a
`lathe.scene_assembly.v1` payload backed by
`schema/scene_assembly.schema.json`.

The IR contains:

- `regions` copied with stable `region_id` values and bounds.
- `collections` keyed by region, with deterministic `object_ids`.
- `materials` with preserved `material_id` values and deterministic
  `material_index` values.
- `objects` sorted by `object_id`, preserving transforms, object metadata,
  source fields, material assignments, estimated bounds, contact hints, and
  planned object proxy paths.
- `cameras` and `lights` with stable `camera_id` and `light_id` values.
- `object_index` records with deterministic `render_index` and material index
  references for selection and ID-pass consumers.
- `object_selection_payloads` using `object_id`, `render_index`, and
  `material_index` fields.
- `exports` with source-declared paths plus package-relative planned proxy
  artifact paths.

Assembly helpers also expose deterministic transform math and unit conversion:

- `transform_position(transform)` and `transform_scale(transform)` normalize
  Scene Graph transforms into numeric vectors.
- `convert_vector_units(vector, from_units=..., to_units=...)` supports meters,
  centimeters, millimeters, and Roblox-style studs.
- `estimate_transform_bounds(transform)` emits axis-aligned proxy bounds.
- `contact_hints_for_bounds(bounds)` emits conservative floor-clearance and
  resting-surface hints for later renderer/export lanes.

Validation is split between JSON Schema and semantic invariants:

- `get_scene_assembly_schema()` loads the committed schema.
- `check_scene_assembly_ir(payload)` checks duplicate IDs, index uniqueness,
  object/material links, selection payload consistency, target references, and
  package path safety.
- `validate_scene_assembly_payload(payload)` runs both layers and returns
  machine-readable diagnostics.

Blender-backed rendering remains deferred. The current paths are explicit proxy
records so downstream package writers can preserve identity and selection data
while the deterministic proxy runtime produces local PNG/GLB evidence without
claiming final mesh, lighting, or engine import quality.
