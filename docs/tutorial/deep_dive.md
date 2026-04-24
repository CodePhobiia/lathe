# Deep dive — reading order into the specs

By now you have run the [Quickstart](../quickstart.md), authored a [first asset](first_asset.md), and seen the [reconstruct flow](second_asset_reconstruct.md). This page is a map: which spec covers what, and the order that will build your mental model fastest without getting lost in layers that assume earlier layers.

## Suggested reading order

**1. Why the language exists** — [`docs/lathe_manifesto.md`](../lathe_manifesto.md)
: The motivation: declarative intent for 3D assets, why "build everything to a spec, validate against it" beats one-shot generation, and the stance on provider neutrality. Read this first if you want to understand *why* Lathe looks the way it does — it's short, opinionated, and sets up the rest.

**2. Product framing** — [`docs/lathe_prd.md`](../lathe_prd.md)
: The product requirements document. Personas, jobs-to-be-done, what counts as a win, what is explicitly out of scope. Useful for understanding design trade-offs when you disagree with a spec decision. Pair with [`docs/personas.md`](../personas.md), [`docs/jtbd.md`](../jtbd.md), [`docs/icp.md`](../icp.md) if you want the full context.

**3. The v0.1 base language** — [`spec/lathe-v0.1.md`](https://github.com/talmerri/lathe/blob/main/spec/lathe-v0.1.md)
: Canonical reference for the core surface: `module`, `import`, `profile`, `contract`, `critic`, `asset`, `variant`, stage names, the normalized AST shape. When `grammar/lathe.lark`, `schema/lathe.schema.json`, and this spec agree, you are looking at stable behavior. Treat this as the authoritative base — every later V1.x spec layers on it.

**4. V1.0 — first runnable stack** — [`docs/Specs/Lathe-V1.0-Spec.md`](../Specs/Lathe-V1.0-Spec.md)
: Introduces the first concrete backend stack (`lathe.stack.hard_surface_game_asset_v1`), the shape bundle contract (`lathe.shape.intent_mesh_handoff_v1`), and the fallback semantics. Read this to understand how `.lth` source becomes actual geometry — the hero examples (`sci_fi_wall_panel`, `service_cabinet`, `control_pedestal`, `supply_container`) target this stack.

**5. V1.1 — references, fits, kits** — [`docs/Specs/Lathe-V1.1-Spec.md`](../Specs/Lathe-V1.1-Spec.md)
: Adds `library`, `kit`, `reference_set`, `reconstruct_policy`, `adapt_policy`, `assembly_policy`, `fit_profile`, `transfer_rule`. Asset-level blocks: `fit`, `transfer`, `reuse`, `constraints`, `ingest`, `assembly_rules`. This is the spec behind the [reconstruct tutorial](second_asset_reconstruct.md). New IRs: `fit_ir`, `transfer_ir`, `kit_ir`, `reference_ir`, `reuse_ir`.

**6. V1.2 — governed surface authoring** — [`docs/Specs/Lathe-V1.2-Spec.md`](../Specs/Lathe-V1.2-Spec.md)
: Introduces `surface_backend`, `surface_policy`, `decal_library`, `mask_program`, `trim_sheet`, and the surface-side IRs (`surface_control_pack`, `atlas_assembly_ir`, `surface_validation_ir`, `surface_repair_ir`, `surface_backend_report`). Read this once you care about deterministic, auditable texture authoring — including how Codex ImageGen shows up as a governed backend with explicit fallback.

**7. V1.3 — Blender-backed execution** — [`docs/Specs/Lathe-V1.3-Spec.md`](../Specs/Lathe-V1.3-Spec.md)
: Execution planning through Blender: bake/render intent, retained `.blend` artifacts, the bake/render contract. This is where the architecture hands serious authoring work off to a real DCC while keeping the manifest deterministic.

**8. V1.3.1 — the Codex bridge** — [`docs/Specs/Lathe-V1.3.1-Spec.md`](../Specs/Lathe-V1.3.1-Spec.md)
: The Codex-operated Blender bridge: `lathe/bridge/blender_plan.py`, the `lathe bridge doctor|plan` CLI, `lathe inspect`, `lathe export-blend`, `lathe inspect-blend`. Read this when you want an AI coding agent to drive Blender on behalf of a `.lth` source without hand-scripting per-asset.

## Architecture companions

Alongside the specs, the architecture pages give you a running-code view of the same layers:

- [Pipeline](../architecture/pipeline.md) — stage-by-stage flow (`refs → intent → shape → topology → uv → surface → execution → rig → interfaces → physics → optimize → validate → package → publish`).
- [Shape stage](../architecture/shape_stage.md) — the one probabilistic stage, the `intent → AssetGraph → blueprint → ShapeIR → fused geometry → authoritative mesh → optional proposals → conformance fit` internal flow.
- [Backends](../architecture/backends.md) — how stacks bind stages, how the attempted-vs-actual pattern works, and the deterministic reference-path fallbacks.

## What to read in which situation

| If you are...                                             | Start with                                                               |
| --------------------------------------------------------- | ------------------------------------------------------------------------ |
| New to Lathe, want the big picture                         | manifesto → v0.1 spec → V1.0 spec                                        |
| Writing assets, want the language surface                  | v0.1 spec → [first_asset](first_asset.md)                                |
| Debugging a failed build                                   | [pipeline](../architecture/pipeline.md) → relevant stage spec → `trace.json` |
| Building a reference-driven asset                          | V1.1 spec → [reconstruct tutorial](second_asset_reconstruct.md)          |
| Customizing surface authoring                              | V1.2 spec → `std/surface_programs/`                                       |
| Setting up the Blender/Codex bridge                        | V1.3 spec → V1.3.1 spec → [`docs/codex_integration.md`](../codex_integration.md) |
| Wiring a new backend or provider                           | [backends](../architecture/backends.md) → V1.0 stack spec → `lathe/backends.py` |

## Intentional scaffolds

These are still scaffolds in v0.1 — spec language may describe the target shape, but the runner is not fully wired:

- `publish` runner — publication registry integrations.
- Canonical `fmt` — a stable code formatter for `.lth` sources.
- Full multi-round autonomous repair loops — partial implementation lands progressively across later specs.

When reading, treat these as roadmap markers, not as claims of current behavior.

## Next

- Cookbook (BL-28) — task-shaped recipes: "author a kit", "write a reconstruct policy", "add a new backend" (ships separately; check `docs/cookbook/`).
