# Recipe 07 — Registering a custom backend

## Goal

Add a new backend to the Lathe compiler — say, a proprietary UV unwrapper or a studio-specific packaging format — and wire it into a stack so assets can select it. This recipe covers the in-tree registration path that ships in v0.1 and notes the entry-points path that Plan 03 will introduce.

## Prerequisites

- Lathe v0.1+ checked out as an editable install (`pip install -e .[dev]`).
- Familiarity with the stage contracts documented in [`lathe/backends.py`](https://github.com/talmerri/lathe/blob/main/lathe/backends.py).
- A decision on which stage your backend targets: `shape`, `topology`, `uv`, or `package` (the stages that accept backend selection — see `BACKEND_SELECTION_STAGES`).

## Walkthrough

### Step 1 — pick a stage contract

Every backend must honor the stage contract. Open `lathe/backends.py` and read the `contract.inputs` / `contract.outputs` block for the stage you are adding to. For example, for a new UV backend you must:

- Consume `topology_bundle`, `build.uv.sets`, `build.uv.tile_mode`, `build.uv.padding`.
- Emit a `uv_bundle` with `mesh_uri`, `uv_sets[].name`, `uv_sets[].coverage`, `packing_report.chart_count`, and `provenance.backend_id`.
- Guarantee base UVs are uniquely unwrapped into 0..1 space and emit a lightmap set when requested.

Any backend that cannot meet all `guarantees` fails the compatibility check in `evaluate_backend(...)`.

### Step 2 — declare the backend

Add a new entry to the `BACKENDS` dict in `lathe/backends.py` (in-tree registration is the v0.1 path):

```python
"mystudio.uv.box_pack_v1": {
    "id": "mystudio.uv.box_pack_v1",
    "version": "0.1.0",
    "stage": "uv",
    "toolchain": ["trimesh", "mystudio_boxpack"],
    "runtime_executor": "mystudio.runtime.uv.box_pack_v1",
    "determinism_class": "deterministic",
    "supported_asset_kinds": ["hard_surface_prop", "env_module"],
    "supported_tile_modes": ["zero_to_one"],
    "supported_unwrap": ["auto"],
    "supported_sets": ["base", "lightmap"],
    "contract": {
        "summary": "Proprietary box-packing UV backend tuned for studio-standard texel densities.",
        "inputs": {
            "required": ["topology_bundle", "build.uv.sets", "build.uv.tile_mode", "build.uv.padding"],
            "optional": ["build.uv.texel_density", "build.uv.pack_rotate"],
        },
        "outputs": {
            "artifact": "uv_bundle",
            "required_fields": [
                "mesh_uri",
                "uv_sets[].name",
                "uv_sets[].coverage",
                "packing_report.chart_count",
                "provenance.backend_id",
            ],
            "guarantees": [
                "base UVs are uniquely unwrapped into 0..1 space",
                "lightmap UV set is emitted when requested",
                "packing report is available for diagnostics",
            ],
        },
    },
},
```

The `id` must be globally unique and follow the `<owner>.<stage>.<name>_vN` convention. Supported-* fields drive compatibility checks — list exactly what you support.

### Step 3 — implement the runtime executor

The executor lives at the path named in `runtime_executor`. Create `mystudio/runtime/uv/box_pack_v1.py` (outside `lathe/` keeps the studio code isolated) and register it on the executor dispatch table during package init:

```python
from lathe.executor import register_runtime_executor

def run(stage_inputs: dict) -> dict:
    topology = stage_inputs["topology_bundle"]
    sets = stage_inputs["build.uv.sets"]
    # ... do the unwrap ...
    return {
        "artifact": "uv_bundle",
        "mesh_uri": out_uri,
        "uv_sets": [{"name": name, "coverage": 0.94} for name in sets],
        "packing_report": {"chart_count": 12},
        "provenance": {"backend_id": "mystudio.uv.box_pack_v1", "backend_version": "0.1.0"},
    }

register_runtime_executor("mystudio.runtime.uv.box_pack_v1", run)
```

Fallback semantics: if your executor raises, the shape-stage-style attempted-vs-actual pattern does not apply here (UV is a deterministic stage). Instead, the executor's failure is recorded and the build fails unless you explicitly opt into fallback by also declaring the canonical reference UV backend in the stack constraints.

### Step 4 — declare a stack (or extend an existing one)

Either add your backend to an existing stack or declare a new stack in `STACKS`:

```python
"mystudio.stack.hard_surface_game_asset_v1": {
    "id": "mystudio.stack.hard_surface_game_asset_v1",
    "name": "MyStudio hard-surface game asset v1",
    "description": "Like lathe.stack.hard_surface_game_asset_v1 but with the studio UV backend.",
    "supported_asset_kinds": ["hard_surface_prop", "env_module", "mechanical_assembly"],
    "supported_package_formats": ["usd", "glb", "gltf", "obj"],
    "stage_backends": {
        "shape": "lathe.shape.intent_mesh_handoff_v1",
        "topology": "lathe.topology.blender_hard_surface_v1",
        "uv": "mystudio.uv.box_pack_v1",
        "package": "lathe.package.openusd_gltf_v1",
    },
    "constraints": [
        "uv.tile_mode must be zero_to_one",
        "uv.unwrap must be auto",
    ],
    "selection_reason": "Preferred for studio props that need the in-house packer.",
},
```

### Step 5 — select your backend from a `.lth`

There are two ways to route to the new backend:

1. **Implicit via stack selection** — if your stack scores higher for the asset, Lathe picks it automatically. `select_stack(asset)` walks `STACKS` and returns the first compatible stack.
2. **Explicit selection** — declare `build.uv.backend = "mystudio.uv.box_pack_v1"` in the asset's `.lth`. The checker then verifies compatibility against the resolved stack.

### Step 6 — confirm registration

```bash
python -m lathe.cli backends
```

The new backend shows up with its version and stage. Then:

```bash
python -m lathe.cli plan examples/courier_drone.lth courier_drone
```

Should now show `uv.backend = mystudio.uv.box_pack_v1` if stack selection picked your stack.

## Output

There is no new `dist/` shape — the output follows the stage's existing contract. What changes is the `build_report.json`:

```json
{
  "uv": {
    "selected_backend_id": "mystudio.uv.box_pack_v1",
    "actual_backend_id": "mystudio.uv.box_pack_v1",
    "selected_reason": "stack mystudio.stack.hard_surface_game_asset_v1"
  }
}
```

If your executor failed and the stack permitted fallback, `actual_backend_id` will be the fallback reference backend (e.g. `lathe.uv.reference_v1`).

## Fallback semantics

Each stage has its own fallback policy:

| Stage | Fallback |
|---|---|
| `shape` | always falls back to `lathe.provider.shape.reference_conditioned_v1` unless `--strict-shape-provider` is set. |
| `topology` | falls back to `lathe.topology.reference_v1` when Blender is unavailable or the adapter errors with `strict: false`. |
| `uv` | falls back to `lathe.uv.reference_v1` when xatlas is unavailable or strict mode is off. |
| `package` | does not fall back — missing toolchain is a hard error. |

Custom backends opt into fallback by *not* setting their stage's `strict` flag in the runtime config. Strict mode turns fallback into an error, which is what you want in CI.

## Variations

- **Scope to a kind** — restrict `supported_asset_kinds` to `["mechanical_assembly"]` if your backend only targets drones and doors.
- **Alternate determinism class** — if your backend is seeded-probabilistic, set `determinism_class = "seeded"` (like the shape stage) and make sure your executor honors the passed seed.
- **Entry-points (future)** — once Plan 03 lands, the in-tree `BACKENDS` dict will be replaced by a `lathe.backends` entry-point group. You will declare your backend in a separate distribution's `pyproject.toml`:

```toml
[project.entry-points."lathe.backends"]
mystudio_uv_box_pack_v1 = "mystudio.backends.uv_box_pack:BACKEND"
```

## Troubleshooting

- `check: error: unknown backend mystudio.uv.box_pack_v1` — the backend is not in `BACKENDS`, or you have not reinstalled after editing (`pip install -e .`).
- `plan: no compatible stack` — your new stack's `supported_package_formats` does not cover the asset's `package.formats`.
- `executor: runtime_executor 'mystudio.runtime.uv.box_pack_v1' not registered` — the `register_runtime_executor` call did not fire. Make sure your module is imported at startup.

## See also

- [Architecture — Backends](../architecture/backends.md).
- API: [`lathe.backends`](../api/backends.md), [`lathe.executor`](../api/executor.md), [`lathe.capabilities`](../api/capabilities.md).
- [Plan 03 — Architecture](https://github.com/talmerri/lathe/blob/main/plans/03_architecture.md) for the entry-points migration path.
