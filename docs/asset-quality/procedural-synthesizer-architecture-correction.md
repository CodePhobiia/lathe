# Procedural Synthesizer Architecture Correction

Date: 2026-05-11
Status: Architectural correction superseding the wrong-target sections of `procedural-synthesizer-architecture-spec.md` v2 and `lathe-northstar-full-implementation-plan.md` v2 (both 2026-05-11)
Trigger: Verification check #5 during Cycle 1 readiness review revealed that the v2 spec and v2 plan were aimed at a reporting-layer target, not a build-driving target

## TL;DR

The v2 spec and v2 plan targeted `evaluate_grammar_lowering` and the
`_RECIPES` registry as the place where the procedural synthesizer plants.
**That target is wrong.** `evaluate_grammar_lowering` is a validate-stage
reporter, not a build driver. Replacing it changes the validate-stage
report but does not change `lathe build` output.

The correct target is the shape backend's dispatch in
`lathe/shape/backend.py:85-103`, between `compile_mesh_program_candidate`
(procedural authoring) and `compile_scaffold_candidates` (family-aware
authoring). The synthesizer plants where `mesh_program{}` already plants:
its output feeds `compile_mesh_program_candidate` (or an analog), which
produces real geometry that flows through topology / UV / surface / package
unchanged.

This correction does not invalidate the v2 spec's data-type design
(StyleKnowledge / CompositionPolicy / FamilyAlias / DomainExtensionManifest,
typed attribute schemas, generator capability manifests, 8-stage pipeline)
or the v2 plan's cycle sequencing. Those parts stand. What changes is
**which function the synthesizer's pipeline output feeds**.

## What the v2 docs assumed (incorrectly)

The v2 spec §3.5 outer-loop pseudocode:

```python
def synthesize_shape_program(asset, runtime) -> SynthesisResult:
    # 8-stage pipeline produces a ShapeProgram
    ...
    return SynthesisResult(shape_program=program, ...)
```

The v2 plan Cycle 1 §4.3.4 routing change:

```python
def evaluate_grammar_lowering(asset, runtime):
    # ... route unknown families through synthesize_shape_program
```

The assumption was that `evaluate_grammar_lowering` was a build driver.
**It isn't.** Tracing the actual flow:

1. `evaluate_grammar_lowering` is wired ONLY in
   `lathe/core/stages/validate.py:54` as a function-validator.
2. Its output ends up in the validate-stage report's `grammar_lowering`
   section, alongside other certification metrics.
3. The actual shape stage (`lathe/core/stages/shape.py:run`) does not
   consume the grammar_lowering output.
4. The shape stage calls `_shape_run_backend` (in
   `lathe/shape/backend.py:run_shape_backend`).
5. The backend dispatches:
   - If `mesh_program{}` block in source: `compile_mesh_program_candidate`
   - Else: `compile_scaffold_candidates` (family-aware)
6. Both return scaffold-shaped results consumed by the rest of the
   pipeline.

So `_RECIPES` produces a parallel reporting stream — "what the grammar says
should be built" — but does NOT drive actual geometry. The 73 family-named
recipes are anti-modular at the reporting layer, but the build layer's
anti-modularity lives elsewhere (in `asset_graph.py`, `scaffold_compiler.py`,
`feature_fusion.py`, `structural_profiles.py`, `creative_grammar.py`,
`surface_grammar.py`, etc.).

## The corrected target

### Where the synthesizer plants

`lathe/shape/backend.py:85-103` — the shape backend's current dispatch:

```python
# CURRENT (lathe/shape/backend.py:85-103, abbreviated):
mesh_program_ast = mesh_program_ast_from_asset(asset)
if mesh_program_ast is not None:
    scaffold_result = compile_mesh_program_candidate(asset_graph, mesh_program_ast, ...)
else:
    scaffold_result = compile_scaffold_candidates(asset_graph, ...)
```

The corrected dispatch adds a third arm:

```python
# CORRECTED:
mesh_program_ast = mesh_program_ast_from_asset(asset)
synth_eligible = synthesizer_eligible(asset, runtime_config)
                    # ^ unknown family AND construction_graph present, OR
                    #   explicit asset["build"]["shape"]["mode"] == "procedural"
if mesh_program_ast is not None:
    scaffold_result = compile_mesh_program_candidate(asset_graph, mesh_program_ast, ...)
elif synth_eligible:
    synth_program = synthesize_procedural_program(asset, runtime_config, ...)
    scaffold_result = compile_procedural_program_candidate(asset_graph, synth_program, ...)
else:
    scaffold_result = compile_scaffold_candidates(asset_graph, ...)  # legacy family-aware
```

`compile_procedural_program_candidate` produces scaffold-shaped output by
the same mechanism as `compile_mesh_program_candidate` — lowering the
synthesizer's `ShapeProgram` (ShapeIR v2) to `ShapePrimitives` via the
existing `lower_to_v1` adapter, then calling the same downstream lowering
that the mesh_program path already uses.

### What this means for ShapeProgram output

The synthesizer's pipeline (the 8-stage compiler from v2 spec §3.5) still
produces a `ShapeProgram`. That part is unchanged. What changes is the
**consumer**:

- **v2 spec assumed:** consumer is `evaluate_grammar_lowering` (reporting).
- **Correction:** consumer is `compile_procedural_program_candidate`, which
  feeds the shape backend and produces real geometry.

This is actually cleaner architecturally:
- The synthesizer remains responsible for *what to build* (composing the
  ShapeProgram from authored intent).
- The shape backend remains responsible for *how to build it* (running
  the ShapeProgram through the kernel).
- The existing `lower_to_v1` adapter (which we already use for grammar
  lowering's v1_records reporting) is the bridge.

### What still needs to happen at the reporting layer

The 73-recipe `_RECIPES` registry in `grammar_lowering.py` is a separate
concern. Decommissioning it is now hygiene work (the validate-stage
grammar_lowering report becomes consistent with what the shape backend
actually built), not the core architectural win. Cycle 3 absorbs it as a
secondary cleanup.

The bigger win — making `lathe build` output procedural — lives at the
shape backend dispatch.

## Updated Cycle 1 deliverables

### What changes from v2 Cycle 1

The v2 plan Cycle 1 §4.3.4 routing change is replaced. Instead of routing
through `evaluate_grammar_lowering`, the routing change lives in
`lathe/shape/backend.py:run_shape_backend`. The synthesizer plants
alongside the existing `mesh_program{}` dispatch.

The acceptance bar tightens:

- **v2:** the synthesizer's ShapeProgram appears in the validate-stage
  report.
- **v3 (this correction):** the synthesizer's ShapeProgram drives the
  actual shape stage and produces a real GLB whose visible geometry
  reflects the synthesizer's composition decisions. A test fixture
  authored with no family, no `mesh_program{}` block, and only a
  construction graph builds end-to-end into a GLB containing the
  composed primary_volume + panels.

### What stays from v2 Cycle 1

Everything else:

- StyleKnowledge / CompositionPolicy / FamilyAlias / DomainExtensionManifest
  data types.
- Typed per-NODE_TYPE attribute schemas.
- Generator capability manifests.
- The 8-stage compiler pipeline.
- The `GeneratorRegistry` keyed by `(domain, node_type)`.
- The `test_no_family_dispatch.py` contract lint.
- The JSON knowledge pack format under `std/procedural/knowledge/`.
- The "no stubs" rule.
- The first-commit scope (primary_volume + panel generators, attached_to
  decorator, full pipeline, real knowledge packs).

### Updated routing diagram

```
Authored .lth source
  → parser → normalizer → resolver → checker → executor
  → SHAPE STAGE
      ├─ build_asset_graph(asset)
      ├─ DISPATCH:
      │   • mesh_program{} present? → compile_mesh_program_candidate
      │     (authored procedural path)
      │   • else, synthesizer eligible? → synthesize_procedural_program
      │                                  → compile_procedural_program_candidate
      │     (procedural synthesizer — NEW in Cycle 1)
      │   • else → compile_scaffold_candidates
      │     (legacy family-aware path)
      └─ scaffold_result → conformance fit → candidate selection
  → topology / uv / surface / validate / package
```

The dispatch ordering matters. mesh_program is the explicit authored
procedural path and stays primary. The synthesizer is the automatic
procedural path for assets whose authored intent doesn't include a
mesh_program block. The legacy scaffold path remains as fallback during
recipe decommissioning.

### Synthesizer eligibility predicate

The synthesizer activates when ALL hold:

- No `mesh_program{}` block in source.
- A construction graph is present (`runtime["construction_graph"]["nodes"]`
  has ≥ 1 entry) OR the authored asset has enough parts/intent to drive
  the synthesizer's pipeline.
- The active backend matches `lathe.shape.intent_mesh_handoff_v1`.

If the predicate fails, the legacy scaffold compiler runs. During
migration, families gradually move from "legacy scaffold" to
"synthesizer" by being added to a `_SYNTHESIZER_ELIGIBLE_FAMILIES`
allowlist (analog to v2's `_MIGRATED_TO_SYNTHESIZER` — but governing the
build path, not the report path).

## Updated Cycle 3 framing

Cycle 3 in the v2 plan was "Recipe Decommissioning" focused on `_RECIPES`.
The correction splits it:

### Cycle 3a: Synthesizer family migration (build-path)

- Migrate families from `compile_scaffold_candidates` (legacy) to
  `synthesize_procedural_program` (procedural). Per family:
  - Author FamilyAlias / Style / Policy JSON packs.
  - Verify build artifact equivalent-or-better via real GLB diff.
  - Add to `_SYNTHESIZER_ELIGIBLE_FAMILIES`.
- This is where the user's "Lathe is procedural" claim becomes
  structurally enforced.

### Cycle 3b: Recipe registry cleanup (report-path)

- Once all build-path families have migrated, the `_RECIPES` registry in
  `grammar_lowering.py` can be replaced with a thin adapter that runs the
  synthesizer over the same inputs and produces an equivalent ShapeProgram
  for the validate-stage report. This is hygiene work, not the core win.

## Updated Lane mapping

The v2 plan's Lane assignments shift:

- **Lane B (ShapeIR v2 As Drivers)** — primary, still. ShapeIR v2 now
  literally drives the shape backend, not just the validate report.
- **Lane C (Feature Ops And Modularity)** — primary, still.
- **Lane I (Authoring Surface And Stdlib Modularity)** — primary, still.
- **Lane A (Geometry Kernel And CSG)** — now partially advanced by Cycle 1
  too, because the synthesizer's output runs through the kernel via
  `compile_procedural_program_candidate` → `lower_to_v1` → kernel
  execution. Cycle 2 still handles the deeper kernel work.

The Blocker assignments stay:

- **B0, B1, B2, B5, B12** resolved by Cycle 1 + Cycle 3a (procedural
  build path).
- **B3, B4** resolved by Cycle 2 (kernel capability).
- **B6, B7, B8, B9** resolved by Cycle 4 (visible layers).
- **B10, B11** resolved by Cycle 5 (quality loop).

## Stable contracts preserved

Same as v2 §7:

- Public `.lth` source compatibility preserved.
- `lathe.shape.intent_mesh_handoff_v1` untouched (the synthesizer feeds
  the same contract via `compile_procedural_program_candidate`).
- `ShapeProgram` data class unchanged.
- The kernel execution layer unchanged.

The internal architecture change is purely additive: a new dispatch arm
in `run_shape_backend`, parallel to the existing `mesh_program_ast`
dispatch.

## Effort impact

Cycle 1's effort estimate (3-5 sessions) is roughly preserved. The
substrate (pipeline, registry, types, schemas, knowledge packs) is the
same code. What changes:

- Routing wires into `lathe/shape/backend.py` instead of
  `lathe/asset_quality/grammar_lowering.py`.
- A new function `synthesize_procedural_program` (the v2 spec's
  `synthesize_shape_program` renamed for clarity at the build layer).
- A new function `compile_procedural_program_candidate` in
  `lathe/shape/procedural_program_path.py` (sibling of
  `lathe/shape/mesh_program_path.py`) — wraps the v1 lowering and
  produces scaffold-shaped output.
- Acceptance bar's "real GLB" is now achievable in Cycle 1 because the
  synthesizer's output really drives the shape stage.

Plan v2's overall 66-115 session total holds.

## Implementation order for Cycle 1 (corrected)

1. Build the synthesizer substrate per v2 spec §5.1 (engine code,
   knowledge loader, attributes, registry, trace, hint_resolution,
   domain_extension contract).
2. Build the two generators (`primary_volume`, `panel`) and one
   decorator (`attached_to`) per v2 spec.
3. Author the JSON knowledge packs per v2 spec §5.2.
4. Write `lathe/shape/procedural_program_path.py` —
   `compile_procedural_program_candidate(asset_graph, synth_program, ...)`
   that mirrors `mesh_program_path.py` but consumes the synthesizer's
   ShapeProgram instead of a mesh_program AST.
5. Wire the dispatch in `lathe/shape/backend.py:run_shape_backend`:
   add the synthesizer-eligible arm between the mesh_program arm and the
   scaffold arm.
6. Write the `test_no_family_dispatch.py` contract lint.
7. Write the end-to-end fixture test: authored intent (construction
   graph: primary_volume + 2 panels + attached_to) + no recipe + no
   mesh_program block → real GLB with visible composed geometry.
8. Verify the 136+ test slice + the new tests green.
9. Commit. Push.

This is one production-grade slice. The synthesizer drives real
geometry on day one.

## Bottom line

The v2 architecture was right except for one detail: where the
pipeline's output feeds. The corrected target — `run_shape_backend`'s
dispatch — is the place where authored intent actually becomes geometry.
The synthesizer plants where `mesh_program{}` already plants. The shape
backend's existing architecture welcomes it as a third dispatch arm.

This correction document supersedes:

- v2 spec §3.5's `synthesize_shape_program` signature (now
  `synthesize_procedural_program`, fed into the shape backend).
- v2 spec §4 migration plan (Cycle 3 splits into 3a build-path and 3b
  report-path).
- v2 plan Cycle 1 §4.3.4 routing change (now in
  `lathe/shape/backend.py`, not `grammar_lowering.py`).
- v2 plan Cycle 1 §4.4 acceptance criteria (the "real GLB" requirement
  becomes literally achievable).

Everything else in v2 spec and v2 plan stands.

Future agents touching shape-program synthesis should read this
correction immediately after the v2 spec and v2 plan, and treat
this correction as authoritative wherever it conflicts.
