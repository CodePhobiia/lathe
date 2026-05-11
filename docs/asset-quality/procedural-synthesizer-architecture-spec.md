# Procedural Synthesizer Architecture Specification

Date: 2026-05-11
Status: Canonical architecture spec for the language-to-kernel bridge upgrade
Scope: Replacing family-name dispatch in shape program synthesis with generic procedural composition driven by the construction graph and informed by declarative family knowledge packs
Related: `docs/asset-quality/lathe-implementation-northstar.md`, `docs/asset-quality/lathe-implementation-northstar-current-audit.md`

This spec describes the architecture that turns Lathe's shape-program
synthesis layer from a registry of 73 family-specific code-dispatched
recipes into a single procedural engine that consumes typed
construction-graph nodes plus declarative family knowledge packs.

## 0. Why This Spec Exists

The northstar identifies the language-versus-kernel imbalance as the
core problem (§3). The kernel cannot honor the breadth the language
promises because most of the breadth is encoded as fixed per-family
blueprints that dispatch on family name and discard authored intent.

The user has stated the procedural principle clearly:

```text
Lathe must be modular, and the key here is procedural generation.
We should not specify any specific asset.
```

This spec is the architecture that operationalizes that principle in
the shape-program synthesis layer without throwing away the domain
knowledge currently encoded in 14,145 lines of family recipes. The
family knowledge migrates from dispatched code into declarative data
that the procedural engine consumes as suggested defaults.

## 1. Northstar Placement

### 1.1 Which Lanes Does This Address

This spec advances four northstar lanes simultaneously:

| Lane | Section | What This Work Resolves |
|---|---|---|
| Lane B | §10 Lane B "ShapeIR v2 As Drivers" | Makes construction-graph nodes the primary driver of shape program emission, fulfilling "Lower design brief, construction graph, and ShapeIR v2 ops into executable op records." |
| Lane C | §10 Lane C "Feature Ops And Modularity" | Replaces family-specific emitters with reusable per-node-type generators dispatched by tag/role, not family. |
| Lane I | §10 Lane I "Authoring Surface And Stdlib Modularity" | Moves family rules to stdlib-style declarative data. New families become small data packs, not 200-line recipe functions. |
| Blocker B12 | §7 B12 "Chest-Specific Code Is A Product Smell" | Eliminates family-name dispatch from the synthesis path entirely. Family becomes metadata, never a discriminator. |

### 1.2 Phase Placement

The northstar's phase ladder (§11) places this work at:

```text
Phase 2 (Real Surface And Kernel Bridge, 2-4 months)
  -> deliverable: ShapeIR/ShapeIR v2 -> KernelProgram lowering
  -> this spec extends that lowering upstream into shape-program
     SYNTHESIS, not just downstream lowering execution
```

It also is the structural foundation Phase 3 builds on:

```text
Phase 3 (Procedural Domain Libraries, 6-9 months)
  -> deliverables: WFC and CGA-style modular assembly,
     SpeedTree-inspired vegetation vocabulary, scatter as
     production multiplier
  -> all of these are procedural-composition systems that require
     a generic synthesizer substrate; this spec is that substrate
```

Without this work, Phase 3 inherits the family-dispatch anti-pattern
and ends up with more hardcoded blueprints per domain (vegetation,
terrain, WFC) rather than one generic engine driving all domains.

### 1.3 Decision Filter Pass (Northstar §14)

1. What visible claim does this make true? — "Lathe synthesizes any
   asset from authored construction graph + brief, without per-family
   dispatched code."
2. Which asset or fixture proves it? — Verified against industrial
   crate, mechanical door, weapon prop, vehicle prop, lighting prop,
   plus at least one non-recipe-covered fixture authored at
   verification time.
3. Which artifact path will show it? — The
   `payload["shape_program"]` field of `evaluate_grammar_lowering`
   contains identical or equivalent ops regardless of whether the
   recipe path or synthesizer path produced it.
4. Which diagnostic or report field will judge it? — New
   `synthesizer_trace` field on the grammar-lowering payload records
   which generator emitted each op, plus which family knowledge pack
   biased it. Plus an explicit `family_dispatch_used: bool` flag that
   must trend to `false` across the migration.
5. Which repair route will use it? — Repair planner consumes the same
   construction graph the synthesizer consumes, so repair operations
   become construction-graph mutations rather than recipe edits.
6. Does it preserve `.lth` compatibility and
   `lathe.shape.intent_mesh_handoff_v1`? — Yes, both are upstream
   boundaries this spec sits underneath.
7. Does it avoid chest-only or one-family-only logic? — Yes, by
   construction. Family-name dispatch is removed entirely.
8. If it falls back, will users see attempted vs actual behavior? —
   Yes, `synthesizer_trace` records `attempted_via: family_knowledge`
   vs `attempted_via: graph_only_inference` plus fallback reasons.
9. What is the narrowest test or build that proves the change? —
   `tests/unit/test_asset_quality_procedural_synthesizer.py` plus the
   existing `test_asset_quality_grammar_lowering.py` continue to pass.
10. What claim remains explicitly not verified? — Visual quality.
    The synthesizer produces equivalent ShapeProgram structure; visual
    quality verification belongs to downstream stages.

## 2. Current State Diagnosis

### 2.1 The Anti-Pattern

`lathe/asset_quality/grammar_lowering.py` is 14,145 lines. It contains
**73 family-specific recipes** registered in a `_RECIPES` dict keyed
by family name:

```python
_RECIPES: dict[str, Any] = {
    "industrial_crate": industrial_crate_recipe,
    "mechanical_door": _mechanical_door_recipe,
    "service_cabinet": _service_cabinet_recipe,
    # ... 70 more ...
}
```

The `evaluate_grammar_lowering` function dispatches:

```python
recipe = _RECIPES.get(family)
if recipe is None:
    result = _empty_recipe(family, asset_name)
else:
    result = recipe(brief, parts, graph_nodes)
```

Each recipe currently discards its inputs. Example from
`industrial_crate_recipe` (line 13535):

```python
del brief, parts, graph_nodes
# ... emit fixed 10-op program for "industrial_crate" ...
```

### 2.2 What This Costs

- **Authored intent is ignored.** A brief that says "tall narrow
  crate" produces the same output as one that says "wide squat crate"
  because the recipe ignores the brief.
- **Adding a family requires Python code.** Each new asset family is
  a ~200-line recipe function, not a data pack.
- **Family-name routing leaks into downstream stages.** The 73 family
  names propagate through ShapeProgram.family field and become
  dispatch keys for shape backend, surface defaults, validators, and
  more.
- **Domain expansion is anti-scalable.** Phase 3's WFC, CGA,
  vegetation, terrain work risks repeating the same per-family
  blueprint anti-pattern in new domains.

### 2.3 What Already Exists That We Can Use

The procedural vocabulary is already defined in
`lathe/asset_quality/construction_graph.py`:

**`NODE_TYPES`** (20 generic component roles):

```
primary_volume, frame, panel, inset, trim, guard, rail, bracket,
vent, conduit, latch, weld, socket, mount, handle, hinge, fastener,
decal_zone, wear_zone, material_zone
```

**`EDGE_TYPES`** (graph relations):

```
attached_to, inset_into, wraps_around, mirrors, aligned_with,
supports, cuts, ...
```

`evaluate_construction_graph` produces typed graph nodes from
authored intent. The procedural engine this spec describes consumes
those typed nodes.

`lathe/asset_quality/shape_ir_v2.py` already defines the operation
families the engine emits into:

```
SOLID_OPS (36), BOOLEAN_OPS (11), EDGE_OPS (4), SOP_OPS (16),
REPETITION_OPS (8), INTEGRATION_OPS (4), WEAR_OPS (4) = 83 total
```

The data substrate exists. The missing piece is the engine that
maps `(node_type, attributes, edges, brief, family_hints?) -> ShapeOp`
generically.

## 3. Proposed Architecture

### 3.1 The Flow

```
asset[intent].parts                                                    \
asset[intent].brief                                                     \
runtime[construction_graph].nodes                                        \
runtime[construction_graph].edges                                         > inputs
runtime[design_brief]                                                    /
family_knowledge_packs[family]?      <-- optional, declarative          /
                                                                       /
                                |
                                v
                    ProceduralSynthesizer
                                |
                    +-----------+-----------+
                    |                       |
              walk graph nodes       walk graph edges
                    |                       |
                    v                       v
        NODE_TYPE_GENERATORS[t]    EDGE_TYPE_DECORATORS[e]
        (one per NODE_TYPE,         (relational ops:
         outputs ShapeOps for         booleans, mirrors,
         this node)                   alignments, attachments)
                    |                       |
                    +-----------+-----------+
                                |
                                v
                          ShapeProgram
                                |
                                v
                   lower_to_v1 (existing)
                                |
                                v
                   kernel execution (existing)
```

### 3.2 Core Data Types

#### 3.2.1 FamilyKnowledge

```python
@dataclass(frozen=True)
class FamilyKnowledge:
    """Declarative family bias for the procedural synthesizer.

    NEVER consumed by code that dispatches on family name. Always
    consumed as merge-into-defaults data. If absent, the synthesizer
    falls back to brief-only inference.
    """

    family_id: str                                  # metadata only
    composition_hints: dict[str, dict[str, Any]]    # node_type -> hints
    edge_hints: dict[str, dict[str, Any]]           # edge_type -> hints
    style_band: str                                 # routes to material defaults
    silhouette_priors: dict[str, float]             # dominance ratios
    proportion_priors: dict[str, dict[str, float]]  # node_type -> axis weights
    required_node_types: tuple[str, ...]            # MUST be present for valid pack
    suggested_node_types: tuple[str, ...]           # added if absent in graph
```

A pack is **data only**. There is no `FamilyKnowledge.emit_ops()`
method. The synthesizer reads packs as defaults; generators do the
work.

#### 3.2.2 SynthesizerContext

```python
@dataclass(frozen=True)
class SynthesizerContext:
    """Per-synthesis-call immutable context."""

    brief: Mapping[str, Any]
    parts: tuple[str, ...]
    graph_nodes: tuple[Mapping[str, Any], ...]
    graph_edges: tuple[Mapping[str, Any], ...]
    family_knowledge: FamilyKnowledge | None
    asset_name: str
```

Synthesizer functions take only `(node, context)` or
`(edge, context)`. No global state.

#### 3.2.3 NodeTypeGenerator

```python
NodeTypeGenerator = Callable[
    [Mapping[str, Any], SynthesizerContext],
    Iterable[ShapeOp],
]
```

One generator per `NODE_TYPE`. Each generator is generic — it knows
how a `primary_volume` becomes geometry, not how an
"industrial_crate primary_volume" becomes geometry.

Family hints inform parameters, never structure:

```python
def _primary_volume_generator(
    node: Mapping[str, Any],
    ctx: SynthesizerContext,
) -> Iterable[ShapeOp]:
    # 1. Read node attributes (authored intent — first class)
    attrs = node.get("attributes", {})

    # 2. Read brief proportions (authored intent — first class)
    brief_proportions = ctx.brief.get("proportions", {})

    # 3. Read family hints if present (suggested defaults — second class)
    family_hint = (
        ctx.family_knowledge.composition_hints.get("primary_volume", {})
        if ctx.family_knowledge is not None
        else {}
    )

    # 4. Merge: brief/attrs win; family hints fill gaps; absolute defaults
    #    fill remaining gaps. NO family-name lookup anywhere.
    shape = (
        attrs.get("shape")
        or brief_proportions.get("primary_shape")
        or family_hint.get("shape")
        or "box"
    )
    ...
    yield ShapeOp(op="solid.box" if shape == "box" else f"solid.{shape}", ...)
```

#### 3.2.4 EdgeTypeDecorator

```python
EdgeTypeDecorator = Callable[
    [Mapping[str, Any], SynthesizerContext, list[ShapeOp]],
    Iterable[ShapeOp],
]
```

Operates on edges between graph nodes. Emits relational ops:
mirrors, booleans, alignments, scatter-on-surface, attached-to
constraints. Receives the current list of emitted ops so it can
emit ops that reference earlier records.

### 3.3 The Generator Registry

```python
_NODE_TYPE_GENERATORS: Mapping[str, NodeTypeGenerator] = {
    "primary_volume": _primary_volume_generator,
    "frame":          _frame_generator,
    "panel":          _panel_generator,
    "inset":          _inset_generator,
    "trim":           _trim_generator,
    "guard":          _guard_generator,
    "rail":           _rail_generator,
    "bracket":        _bracket_generator,
    "vent":           _vent_generator,
    "conduit":        _conduit_generator,
    "latch":          _latch_generator,
    "weld":           _weld_generator,
    "socket":         _socket_generator,
    "mount":          _mount_generator,
    "handle":         _handle_generator,
    "hinge":          _hinge_generator,
    "fastener":       _fastener_generator,
    "decal_zone":     _decal_zone_generator,
    "wear_zone":      _wear_zone_generator,
    "material_zone":  _material_zone_generator,
}

_EDGE_TYPE_DECORATORS: Mapping[str, EdgeTypeDecorator] = {
    "attached_to":    _attached_to_decorator,
    "inset_into":     _inset_into_decorator,
    "wraps_around":   _wraps_around_decorator,
    "mirrors":        _mirrors_decorator,
    "aligned_with":   _aligned_with_decorator,
    "supports":       _supports_decorator,
    "cuts":           _cuts_decorator,
    ...
}
```

The registry size is bounded by `NODE_TYPES` (20) and `EDGE_TYPES`,
not by family count. Every new family added to the system increases
the data layer (one pack), not the code layer (zero new generators).

### 3.4 Family Hint Resolution Rules

The synthesizer merges hints with strict precedence so authored
intent always wins over family bias:

```
priority order (highest wins):
  1. authored node attributes (graph_node["attributes"])
  2. authored brief fields
  3. authored parts list (presence/absence of named parts)
  4. family knowledge composition_hints[node_type]
  5. family knowledge proportion_priors[node_type]
  6. generator-internal absolute defaults
```

Rule for suggested_node_types: if `family_knowledge.suggested_node_types`
includes a node type that is absent from the graph AND no authored
intent contradicts adding it, the synthesizer adds a synthesized
graph node of that type and runs its generator. Authored intent
contradicting the suggestion (e.g., `intent.parts` lists no
"fastener" and brief specifies "smooth-form") suppresses the
addition.

Rule for required_node_types: if the graph lacks a required type,
the synthesizer emits a diagnostic rather than silently failing.

### 3.5 The Outer Loop

```python
def synthesize_shape_program(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> SynthesisResult:
    ctx = _build_context(asset, runtime)
    ops: list[ShapeOp] = []
    trace: list[dict[str, Any]] = []

    # 1. Expand graph with family-suggested nodes (when not contradicted)
    expanded_nodes = _expand_with_suggestions(ctx)

    # 2. Per-node generation
    for node in expanded_nodes:
        generator = _NODE_TYPE_GENERATORS.get(node["node_type"])
        if generator is None:
            trace.append({"kind": "unknown_node_type", "node": node, ...})
            continue
        node_ops = list(generator(node, ctx))
        for op in node_ops:
            ops.append(op)
            trace.append({
                "kind": "node_op",
                "node_id": node["node_id"],
                "node_type": node["node_type"],
                "op": op.op,
                "attempted_via": (
                    "family_knowledge_pack"
                    if ctx.family_knowledge is not None
                    else "graph_only_inference"
                ),
            })

    # 3. Per-edge decoration
    for edge in ctx.graph_edges:
        decorator = _EDGE_TYPE_DECORATORS.get(edge["edge_type"])
        if decorator is None:
            trace.append({"kind": "unknown_edge_type", "edge": edge, ...})
            continue
        edge_ops = list(decorator(edge, ctx, ops))
        for op in edge_ops:
            ops.append(op)
            trace.append({"kind": "edge_op", ...})

    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name=ctx.asset_name,
        family=ctx.family_knowledge.family_id if ctx.family_knowledge else None,
        ops=tuple(ops),
    )
    return SynthesisResult(
        shape_program=program,
        synthesized_graph_nodes=_synthesized_only(expanded_nodes, ctx),
        synthesizer_trace=tuple(trace),
        family_dispatch_used=False,  # always, by construction
    )
```

Note that `program.family` carries the family id as a metadata tag,
but no code downstream dispatches on it. It is for reporting and
audit, never for behavior selection.

## 4. Migration Strategy

### 4.1 Coexistence Phase (first N sessions)

The procedural synthesizer co-exists with `_RECIPES`. The dispatch
inside `evaluate_grammar_lowering` becomes:

```python
def evaluate_grammar_lowering(asset, runtime):
    ...
    family = _resolve_family(brief)
    recipe = _RECIPES.get(family)

    if family in _MIGRATED_TO_SYNTHESIZER:
        result = synthesize_shape_program(asset, runtime)
    elif recipe is not None:
        result = recipe(brief, parts, graph_nodes)
    else:
        result = synthesize_shape_program(asset, runtime)  # unknowns route here
    ...
```

`_MIGRATED_TO_SYNTHESIZER` is an explicit allowlist. A family moves
from `_RECIPES` to `_MIGRATED_TO_SYNTHESIZER` only after the
synthesizer produces an equivalent or improved ShapeProgram for it.

### 4.2 Migration Order

Sequenced by complexity and risk, lowest first:

1. **Unknown families first.** Today they route to `_empty_recipe`
   (zero ops). Routing them to the synthesizer immediately upgrades
   them from empty-program to whatever the construction graph
   describes. No risk, only gain.
2. **Simple recipes second.** Recipes that emit a small fixed program
   per family migrate first (e.g., `surface_material_sample_recipe`,
   `set_dressing_prop_recipe`). Quick equivalence verification.
3. **Hard-surface fixtures third.** `industrial_crate`, `mechanical_door`,
   `service_cabinet`. These are the Sprint 0 guardrails — careful
   verification, side-by-side ShapeProgram diff before flipping.
4. **Composite system bundles last.** `world_system_assembly`,
   `engine_facing_runtime_bundle_system`, etc. — these encode large
   bundle compositions and may need new generator capabilities (e.g.,
   recursive sub-asset assembly) before the synthesizer can produce
   equivalents.

### 4.3 Per-Recipe Migration Steps

For each recipe:

1. **Identify the construction graph the recipe currently emits
   under.** Inspect the recipe's emitted ops and group them by their
   semantic component role.
2. **Author a `FamilyKnowledge` data pack** that captures the recipe's
   structural decisions as declarative hints.
3. **Verify equivalence**: run synthesizer with the new pack,
   diff the resulting ShapeProgram against the recipe's. Differences
   are acceptable IF the synthesized program is more authored-intent-
   driven (e.g., it now actually consumes the brief).
4. **Add the family to `_MIGRATED_TO_SYNTHESIZER`.**
5. **Delete the recipe function** and its registration in `_RECIPES`.
6. **Commit.** One family per commit, ideally.

### 4.4 Decommissioning

When `_RECIPES` is empty:

1. Replace the dispatch in `evaluate_grammar_lowering` with a direct
   call to `synthesize_shape_program`.
2. Remove `_RECIPES`, `_MIGRATED_TO_SYNTHESIZER`, and all
   `_*_recipe` functions.
3. Move `_INDUSTRIAL_CRATE_LOWERERS` and per-requirement lowerer
   constants either into the generator that needed them, or delete
   them if the generator's generic logic supersedes them.
4. Reduce `grammar_lowering.py` from 14,145 lines to whatever the
   synthesizer plus its support utilities require (target: under
   2,000 lines).

## 5. Component Inventory (Files To Create)

```
lathe/asset_quality/procedural_synthesizer/
    __init__.py                 # public API: synthesize_shape_program, FamilyKnowledge
    context.py                  # SynthesizerContext, _build_context
    synthesizer.py              # the outer loop and registry plumbing
    generators/
        __init__.py             # _NODE_TYPE_GENERATORS registry assembly
        primary_volume.py
        frame.py
        panel.py
        inset.py
        trim.py
        guard.py
        rail.py
        bracket.py
        vent.py
        conduit.py
        latch.py
        weld.py
        socket.py
        mount.py
        handle.py
        hinge.py
        fastener.py
        decal_zone.py
        wear_zone.py
        material_zone.py
    decorators/
        __init__.py             # _EDGE_TYPE_DECORATORS registry assembly
        attached_to.py
        inset_into.py
        wraps_around.py
        mirrors.py
        aligned_with.py
        supports.py
        cuts.py
    knowledge/
        __init__.py             # registry of FamilyKnowledge packs
        industrial_crate.py     # one file per family pack as it migrates
        mechanical_door.py
        ...
    hint_resolution.py          # the merge-with-priority logic
    trace.py                    # SynthesizerTrace data class
```

Each generator file is **bounded** in size — target under 300 lines.
Each decorator file similarly.

## 6. Acceptance Criteria

### 6.1 Per-Slice Acceptance

A node-type generator is "done" when:

- It emits `ShapeOps` whose `v2_op` membership is bounded to
  `ALL_OPS`.
- It consumes node attributes, brief fields, and family hints with
  the priority order specified in §3.4.
- It produces deterministic output for identical input.
- It emits a `synthesizer_trace` entry for every op.
- It is unit-tested with at least three input scenarios:
  graph-only, graph + brief, graph + brief + family hints.

### 6.2 Per-Recipe Migration Acceptance

A recipe is "migrated" when:

- A `FamilyKnowledge` data pack exists in `knowledge/<family>.py`.
- The synthesizer's output ShapeProgram passes equivalence-or-better
  diff against the original recipe's output across three test
  scenarios (default brief, varied brief, varied parts).
- The recipe function and its `_RECIPES` registration are deleted.
- The family appears in `_MIGRATED_TO_SYNTHESIZER` (during
  coexistence) or is no longer dispatched anywhere (after
  decommissioning).
- Every test in `tests/unit/test_asset_quality_grammar_lowering.py`
  that referenced the family continues to pass, updated for the new
  expected outputs where intent-driven differences are present.

### 6.3 Architecture-Level Acceptance

The architecture is "complete" when:

- `_RECIPES` is removed from the codebase.
- `evaluate_grammar_lowering` dispatches only to
  `synthesize_shape_program`.
- `grep -r 'family ==' lathe/` returns no hits in synthesis,
  geometry, surface, or validator code paths. Metadata-only retention
  in trace/report fields is acceptable.
- A test fixture authored with an unknown family produces a non-empty,
  geometrically valid ShapeProgram driven entirely by the
  construction graph.
- A test fixture authored with the same family but different briefs
  produces different ShapeProgram outputs (proving intent dominance
  over family bias).

## 7. Stable Contracts Preserved

Under the northstar's §5 stable-contracts list, this work touches:

- **Public `.lth` source compatibility**: preserved. The `.lth`
  surface that produces a brief/intent/parts/graph still flows into
  the synthesizer identically.
- **`lathe.shape.intent_mesh_handoff_v1`**: untouched. This work is
  upstream of the shape-stage handoff.
- **`profile`, `contract`, `critic`, `asset`, `variant` surface**:
  untouched.
- **Topology, UV, surface, package contracts**: untouched.
- **Attempted-vs-actual tracing**: extended. The synthesizer adds
  `attempted_via: family_knowledge_pack | graph_only_inference` to
  the trace.

What changes is the **internal** synthesis substrate — explicitly
allowed under §5: "Internal architecture can evolve aggressively
underneath the stable handoff when it is additive and
truth-preserving."

## 8. Explicit Non-Goals

This spec does NOT:

- Expand the public `.lth` language surface.
- Change the `ShapeProgram` data class shape (still emits the same
  `(version, asset_name, family, ops)` tuple).
- Change the lowering or kernel-execution layer (covered by the
  northstar S0-7 KernelProgram seam work, already underway).
- Replace the construction graph or design brief representations.
- Add new operation kinds to `ShapeIR v2`.
- Make claims about visual quality (downstream stages decide that).
- Migrate provider/learned-quality-claim paths (out of scope per
  northstar §2).

## 9. Open Questions / Decisions Required

Recorded for resolution during implementation, not pre-required:

1. **Sub-asset composition** — recipes for bundle-style families
   (`world_system_assembly`, `engine_facing_runtime_bundle_system`)
   today emit references to sub-assets. How does the synthesizer
   express recursive composition? Candidate: an `assembly` node type
   added to `NODE_TYPES` that references a child construction graph.
2. **Domain extension** — Phase 3 work adds vegetation, terrain,
   WFC, CGA. These have their own composition vocabularies. Do we
   extend `NODE_TYPES` to cover them (and risk the set growing
   unbounded), or do we layer domain-specific synthesizers above
   the hard-surface one? Candidate: per-domain extension packs that
   add their own `NODE_TYPES` subset, dispatched by the brief's
   `domain` field rather than family field.
3. **Backward compatibility for pinned tests** — the existing
   `test_asset_quality_grammar_lowering.py` pins recipe behavior
   tightly (exact op counts, primitive types). During migration we
   need a policy: synthesizer changes that diverge from the recipe
   are acceptable if intent-driven; pure-regression divergences are
   not. The trace field provides the audit trail.
4. **Family knowledge pack source format** — Python dataclass in
   `lathe/asset_quality/procedural_synthesizer/knowledge/`, OR YAML/
   TOML data files loaded at startup? Python is simpler for now;
   data-file format is the natural next step for true stdlib parity
   (so non-Python authors can add families).
5. **Edge decoration ordering** — when multiple edge decorators
   could apply (e.g., a node is both `attached_to` X and `mirrors`
   Y), which runs first? Candidate: declarative priority in
   `_EDGE_TYPE_DECORATORS`, with deterministic tie-breaking by
   `edge["edge_id"]`.

## 10. Risk And Mitigation

| Risk | Mitigation |
|---|---|
| 73-recipe migration produces ShapeProgram regressions invisible until rendering | Per-recipe equivalence diff before migration; coexistence phase keeps fallback on. |
| Generators grow to recipe-equivalent complexity (each becomes a 200-line monster) | Per-node-type generator size budget: under 300 lines. If a generator exceeds it, factor into sub-generators by structural attribute. |
| Family knowledge packs become covertly procedural (people add logic to packs) | Pack data classes are `frozen=True` and contain only literal dicts/tuples/strings/floats. No callables. Lint rule enforces. |
| Construction graph is too coarse for some families' decisions | Add `NODE_TYPES` only when the new type generalizes across ≥3 unrelated families. Resist single-family node types. |
| Synthesizer becomes the single point of failure for all asset synthesis | Generators are independent; one broken generator only breaks programs that use that node type. Comprehensive per-generator unit tests. |
| Migration takes longer than estimated | Migration is incremental; each per-recipe migration is independently shippable. Coexistence phase has no end date until the last recipe migrates. |

## 11. Estimated Effort

Bounded estimates assuming production-grade verification per step:

| Phase | Effort | Output |
|---|---|---|
| Foundation: types, context, registry plumbing, trace schema | 1-2 sessions | `procedural_synthesizer/__init__.py`, `context.py`, `synthesizer.py`, `trace.py`, plus skeletons |
| First 5 generators (primary_volume, panel, fastener, trim, decal_zone) | 2-4 sessions | Core component-role coverage |
| Remaining 15 generators | 6-10 sessions | Full NODE_TYPES coverage |
| Edge decorators (≈8) | 2-4 sessions | Full EDGE_TYPES coverage |
| First 10 recipe migrations (simple recipes) | 3-5 sessions | Synthesizer proves out on real families |
| Hard-surface migrations (crate, door, weapon, vehicle, console) | 4-6 sessions | Sprint 0 guardrails fully migrated |
| Remaining 50+ recipe migrations | 10-20 sessions | Decommissioning ready |
| `_RECIPES` removal + cleanup | 1-2 sessions | Architecture complete |

Total: roughly 30-55 sessions of focused work. Aligned with the
northstar's Phase 2 to Phase 3 timeline (2-4 months to 6-9 months).
Each individual session ships a real, verifiable, production-grade
slice — no MVPs, no scaffolding.

## 12. Implementation Sequencing Within This Spec

Per the northstar §18 "What To Implement Next" pattern, the first
concrete sessions execute in this order:

1. Create `lathe/asset_quality/procedural_synthesizer/` package
   skeleton with `FamilyKnowledge`, `SynthesizerContext`, the empty
   `_NODE_TYPE_GENERATORS` and `_EDGE_TYPE_DECORATORS` registries,
   and the trace schema.
2. Wire `evaluate_grammar_lowering` to route unknown families
   through `synthesize_shape_program` instead of `_empty_recipe`.
   Synthesizer returns an empty program (no generators yet) so this
   step is a no-op in observable behavior; it's the integration
   point.
3. Implement `_primary_volume_generator` with full hint-resolution
   semantics. Add corresponding `tests/unit/test_procedural_synthesizer_primary_volume.py`.
4. Implement `_panel_generator`. Add tests.
5. Implement `_fastener_generator`. Add tests.
6. Author the first `FamilyKnowledge` pack for a simple recipe.
7. Migrate that recipe through the equivalence diff. Add it to
   `_MIGRATED_TO_SYNTHESIZER`. Commit.
8. Continue.

The first commit-sized chunk is steps 1 plus 2 plus 3. That's a
single session of work, producing a real procedural-engine
foundation plus a working `primary_volume` generator that any future
session can build on.

## 13. Bottom Line

This spec converts the language-versus-kernel imbalance the northstar
diagnoses (§3) into a concrete, multi-session, production-grade
architecture. It honors the user's procedural-generation principle
absolutely: no code dispatches on asset name. Family knowledge is
preserved as data, not lost. New families become declarative packs,
not Python functions. Phase 3 domain expansion (vegetation, terrain,
WFC, CGA) inherits a generic engine instead of repeating the
family-blueprint anti-pattern.

The northstar gets a stronger spine. The kernel gets a synthesis
layer that respects its capabilities. The user gets the modular
procedural engine they specified.

This spec is the canonical source of truth for the procedural
synthesizer work. Future implementation agents should start here for
any task that touches `lathe/asset_quality/grammar_lowering.py` or
shape-program synthesis upstream of `lower_to_v1`.
