# Procedural Synthesizer Architecture Specification

Date: 2026-05-11 (revision iteration 1: same day)
Status: Canonical architecture spec for the language-to-kernel bridge upgrade
Scope: Replacing family-name dispatch in shape program synthesis with a procedural compiler pipeline driven by typed construction-graph nodes, biased by orthogonal declarative knowledge packs (style, policy, family-alias), and extensible by domain
Related: `docs/asset-quality/lathe-implementation-northstar.md`, `docs/asset-quality/lathe-implementation-northstar-current-audit.md`, `docs/asset-quality/lathe-northstar-full-implementation-plan.md`

This spec describes the architecture that turns Lathe's shape-program
synthesis layer from a registry of 73 family-specific code-dispatched
recipes into a procedural compiler pipeline. The pipeline consumes
typed construction-graph nodes, expands reusable composition policies
(matched by authored intent, never by family name), validates typed
per-NODE_TYPE attribute schemas, and emits ShapeOps through
domain-extensible generators with declared capability manifests.

## Revision History

- **2026-05-11 v1 (initial)** — first draft. Used a single
  `FamilyKnowledge` data class that included `required_node_types`
  and `suggested_node_types` fields. Used a linear "walk nodes then
  walk edges" outer loop. Knowledge packs proposed as Python files
  per family. Registry hardcoded by node type. First implementation
  slice was a no-op skeleton.
- **2026-05-11 v2 (this revision)** — review iteration resolved six
  findings:
  1. FamilyKnowledge split into three orthogonal concepts:
     `StyleKnowledge` (parameter biasing only), `CompositionPolicy`
     (reusable, non-family-keyed graph rules), `FamilyAlias`
     (pure-metadata pointer that cannot add structure). The
     `required_node_types` and `suggested_node_types` fields are
     removed from all knowledge data classes.
  2. Knowledge packs moved to declarative JSON files under
     `std/procedural/knowledge/{style,policy,aliases}/` with
     schema validation at startup. No Python knowledge files.
  3. Generator registry made domain-extensible by key
     `(domain, node_type)`. Phase 3 domains (vegetation, terrain,
     WFC, CGA) plug in without touching the hard-surface registry.
  4. Typed per-NODE_TYPE attribute schemas added. The
     `ConstructionNode.attributes` dict is validated against the
     schema before generators consume it.
  5. Linear outer loop replaced with an 8-stage compiler pipeline:
     resolve_context → normalize_graph → expand_policies →
     validate_attributes → topo_order → emit_node_ops →
     emit_edge_ops → validate_ops.
  6. First implementation slice updated to require real ShapeProgram
     output (not a no-op skeleton): `primary_volume` + `panel`
     generators, `attached_to` decorator, full pipeline, real
     JSON knowledge packs, all in the first commit.
  Plus the domain-extension open question was resolved as a
  shared-core + per-domain-package model.

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
asset[intent].parts                                                       \
asset[intent].brief                                                        \
runtime[construction_graph].nodes (typed)                                   \
runtime[construction_graph].edges                                            > inputs
runtime[design_brief]                                                       /
family_alias? -> resolves to (StyleKnowledge, CompositionPolicy[])         /
                  (or brief specifies them directly)                      /
                                |
                                v
              ProceduralSynthesizer (8-stage compiler pipeline)
                                |
        Stage 1: resolve_context  -> typed SynthesizerContext
        Stage 2: normalize_graph  -> canonical graph
        Stage 3: expand_policies  -> graph + policy-added nodes
        Stage 4: validate_attrs   -> typed-attribute graph
        Stage 5: topo_order       -> deterministic node + edge order
        Stage 6: emit_node_ops    -> per-node generators run
        Stage 7: emit_edge_ops    -> per-edge decorators run
        Stage 8: validate_ops     -> every emitted op in ALL_OPS
                                |
                                v
                          ShapeProgram
                                |
                                v
                   lower_to_v1 (existing)
                                |
                                v
                   kernel execution (existing)

Family alias appears only at Stage 1 (resolves style + policies) and
in the trace metadata. No stage consults family identity for behavior.
```

### 3.2 Core Data Types

Revision note (review iteration 1, 2026-05-11): the earlier draft of
this section defined a single `FamilyKnowledge` data class that
included `required_node_types` and `suggested_node_types` fields.
That design failed review because those fields would let a family
pack add structure to the construction graph — recipes-in-data
clothing. This revision splits the concept into three orthogonal
pieces with strict capability boundaries, none of which can add
structural nodes by name.

#### 3.2.1 StyleKnowledge — Parameter Biasing Only

```python
@dataclass(frozen=True)
class StyleKnowledge:
    """Declarative parameter bias for generators. Never adds structure.

    Loaded from std/procedural/knowledge/style/*.json at startup.
    Schema validated. Contains no callables, no Python logic, no
    emitters. The synthesizer reads style knowledge as suggested
    parameter defaults; generators consume them through the
    hint-resolution priority chain (§3.5).
    """

    style_id: str                                      # e.g. "industrial_pbr_v1"
    style_band: str                                    # routes to material defaults
    proportion_priors: dict[str, dict[str, float]]     # node_type -> axis weights
    silhouette_priors: dict[str, float]                # dominance ratios
    density_priors: dict[str, dict[str, float]]        # node_type -> density hints
    parameter_priors: dict[str, dict[str, Any]]        # node_type -> field -> value
```

Hard boundary: a `StyleKnowledge` pack cannot add or require any
`NODE_TYPE`. It can only suggest values for fields the generator
would have read anyway. A generator that receives style knowledge
for a node type whose graph node is absent ignores it entirely —
the style cannot create the node.

#### 3.2.2 CompositionPolicy — Reusable Procedural Structure (Not Family-Keyed)

```python
@dataclass(frozen=True)
class CompositionPolicy:
    """Reusable graph-composition rule. Never keyed by family.

    A policy describes a structural pattern that applies whenever
    its precondition matches the authored intent. Examples:

      - "panelized_hard_surface_object":
          IF brief.composition == "panelized" AND graph has primary_volume,
          THEN ensure graph contains: panels (one per major face),
               fasteners (corner pattern), edge_trim (top edges).
      - "radial_mechanical_assembly":
          IF brief.composition == "radial" AND graph has primary_volume,
          THEN ensure graph contains: central_hub, spokes, rim.

    Policies are declarative data, loaded from
    std/procedural/knowledge/policy/*.json. They reference the
    NODE_TYPES vocabulary, not family names. A single policy applies
    to any asset whose authored intent matches its precondition —
    crates, doors, terminals, cabinets, whatever.

    Critical: a policy adds STRUCTURE by expanding the construction
    graph BEFORE generators run. But it does so by matching a
    precondition on AUTHORED INTENT, not by family name. The graph
    expansion is traced so a future inspector can see which policy
    added which node and why.
    """

    policy_id: str                                  # e.g. "panelized_hard_surface_object"
    precondition: PolicyPrecondition                # see §3.2.3
    expansions: tuple[PolicyExpansion, ...]         # see §3.2.4
    domain: str                                     # e.g. "hard_surface", "vegetation"


@dataclass(frozen=True)
class PolicyPrecondition:
    """When a policy applies. Pure-data predicates over authored intent.

    No callables. No family-name checks. Predicates are JSON-expressible
    so they can live in declarative knowledge files.
    """

    requires_node_types: tuple[str, ...]            # graph must contain these
    forbids_node_types: tuple[str, ...]             # graph must NOT contain these
    requires_brief_fields: dict[str, Any]           # brief must have these values
    requires_parts_any: tuple[str, ...]             # at least one of these parts
    forbids_parts_any: tuple[str, ...]              # none of these parts
    requires_intent_tags: tuple[str, ...]           # asset-level tag requirements


@dataclass(frozen=True)
class PolicyExpansion:
    """What a policy adds to the construction graph when it applies.

    Adds nodes by NODE_TYPE (never by family name). Records the
    policy_id that added the node so traces can attribute structure
    correctly.
    """

    add_node_type: str                              # must be in NODE_TYPES
    count: int | CountFromBrief                     # may resolve from authored intent
    placement: PlacementHint                        # pure-data placement rule
    attributes_template: dict[str, Any]             # node attributes
    edges_to_existing: tuple[EdgeTemplate, ...]     # edges this expansion creates
```

#### 3.2.3 FamilyAlias — Pure Metadata Lookup

```python
@dataclass(frozen=True)
class FamilyAlias:
    """Family name -> (style_id, policy_ids[]) lookup. METADATA ONLY.

    A FamilyAlias is the ONLY place where a family name appears in
    knowledge data, and it does NOTHING except point at non-family-
    keyed packs. It cannot reference custom code; it cannot add
    nodes; it cannot override the structural composition that the
    matched policies produce.

    Loaded from std/procedural/knowledge/aliases/*.json.

    Example:
      {
        "family_id": "industrial_crate",
        "style_id": "industrial_pbr_v1",
        "policy_ids": ["panelized_hard_surface_object", "industrial_density_v1"],
        "domain": "hard_surface"
      }

    A user can author a brief that names the family alias OR that
    directly specifies (style_id, policy_ids). Either path produces
    identical behavior, because the dispatch is on the resolved
    style + policies, never the family alias itself.
    """

    family_id: str
    style_id: str
    policy_ids: tuple[str, ...]
    domain: str
```

#### 3.2.4 TypedNodeAttributes — Per-NODE_TYPE Schemas

```python
# One schema per NODE_TYPE. The dict-of-Any in ConstructionNode is
# validated against the typed schema before generators consume it.

@dataclass(frozen=True)
class PrimaryVolumeAttributes:
    """Typed attribute contract for node_type='primary_volume'."""

    shape: Literal["box", "rounded_box", "cylinder", "sphere",
                   "extruded_profile", "revolved_profile"]
    dimensions_cm: dict[str, float]    # axis -> length
    symmetry: tuple[Literal["x", "y", "z"], ...]
    rounding_cm: float = 0.0
    scale_intent: Literal["small_prop", "human_scale", "structure"] = "human_scale"


@dataclass(frozen=True)
class PanelAttributes:
    """Typed attribute contract for node_type='panel'."""

    plane: Literal["xy", "xz", "yz"]
    inset_depth_cm: float
    border_policy: Literal["beveled", "sharp", "rounded", "trim_band"]
    thickness_cm: float
    region_id: str | None = None       # links to a face/material zone


@dataclass(frozen=True)
class FastenerAttributes:
    """Typed attribute contract for node_type='fastener'."""

    count: int
    pattern: Literal["grid", "linear", "radial", "corners"]
    seating_target_node_id: str        # the node this fastener attaches to
    fastener_kind: Literal["bolt", "rivet", "screw"] = "bolt"


@dataclass(frozen=True)
class MaterialZoneAttributes:
    """Typed attribute contract for node_type='material_zone'."""

    target_node_id: str                # the node this zone applies to
    mask_kind: Literal["panel", "edge", "scratch", "grime", "decal"]
    contrast_intent: Literal["readable", "subtle", "high"]
    material_id: str | None = None
```

Schemas exist for every NODE_TYPE. The synthesizer validates
attributes before generators run. Attribute validation failures
emit `attribute_schema_violation` diagnostics rather than crashing.

#### 3.2.5 SynthesizerContext

```python
@dataclass(frozen=True)
class SynthesizerContext:
    """Per-synthesis-call immutable context.

    Note: there is no `family_knowledge` field — that concept was
    split into resolved (style, policies). The family alias name, if
    any, is preserved only in the trace for audit purposes.
    """

    brief: Mapping[str, Any]
    parts: tuple[str, ...]
    graph_nodes: tuple[ConstructionNode, ...]      # typed, post-validation
    graph_edges: tuple[ConstructionEdge, ...]
    style: StyleKnowledge | None                   # resolved from alias OR brief
    policies: tuple[CompositionPolicy, ...]        # resolved from alias OR brief
    domain: str                                    # routes to domain generators
    asset_name: str
    family_alias: str | None                       # metadata-only, never dispatched on
```

Synthesizer functions take only `(node, context)` or
`(edge, context)`. No global state.

#### 3.2.6 NodeTypeGenerator With Capability Manifest

```python
@dataclass(frozen=True)
class GeneratorCapabilityManifest:
    """Declares what a generator does. Inspectable at registration time."""

    node_type: str                                 # which NODE_TYPE this handles
    domain: str                                    # "hard_surface" | "vegetation" | ...
    consumed_attributes: tuple[str, ...]           # which typed attribute fields read
    consumed_style_fields: tuple[str, ...]         # which StyleKnowledge fields read
    emitted_op_kinds: tuple[str, ...]              # ShapeIR v2 ops this can emit
    required_kernel_capabilities: tuple[str, ...]  # kernel features needed
    fallback_diagnostics: tuple[str, ...]          # diagnostics on degraded path
    output_kind: Literal[                          # what this generator produces
        "visible_geometry",
        "material_mask",
        "metadata_only",
    ]


@dataclass(frozen=True)
class NodeTypeGenerator:
    """A generator is the manifest plus the implementation.

    The manifest is data; the implementation is a callable. The
    synthesizer inspects manifests at registration time to detect
    incomplete coverage and at run time to attribute trace entries.
    """

    manifest: GeneratorCapabilityManifest
    implementation: Callable[
        [ConstructionNode, SynthesizerContext],
        Iterable[ShapeOp],
    ]
```

Symmetric `EdgeTypeDecorator` with `manifest + implementation` shape.

Style biasing flows through `StyleKnowledge`. Generators consume
typed attributes plus style fields named in their manifest — they
never inspect family identity:

```python
_PRIMARY_VOLUME_MANIFEST = GeneratorCapabilityManifest(
    node_type="primary_volume",
    domain="hard_surface",
    consumed_attributes=("shape", "dimensions_cm", "symmetry", "rounding_cm"),
    consumed_style_fields=("proportion_priors", "parameter_priors"),
    emitted_op_kinds=("solid.box", "solid.rounded_box", "solid.cylinder",
                      "solid.sphere", "solid.extruded_profile",
                      "solid.revolved_profile"),
    required_kernel_capabilities=("solid.box", "solid.rounded_box"),
    fallback_diagnostics=("primary_volume_unsupported_shape",
                          "primary_volume_dimension_default_used"),
    output_kind="visible_geometry",
)


def _primary_volume_impl(
    node: ConstructionNode,
    ctx: SynthesizerContext,
) -> Iterable[ShapeOp]:
    # Typed attributes — already schema-validated by the pipeline
    attrs: PrimaryVolumeAttributes = node.typed_attributes

    # Style biasing — second class, only fills gaps
    style_priors = (
        ctx.style.parameter_priors.get("primary_volume", {})
        if ctx.style is not None
        else {}
    )

    # Merge: typed attrs win; style fills gaps; absolute defaults last.
    # NO family-name lookup. NO conditional on ctx.family_alias.
    shape = attrs.shape  # already required by schema
    dims = attrs.dimensions_cm
    rounding = attrs.rounding_cm or style_priors.get("rounding_cm", 0.0)

    op = ShapeOp(
        op=f"solid.{shape}",
        target=node.node_id,
        parameters={**dims, "rounding_cm": rounding},
        purpose="procedural_primary_volume",
    )
    yield op
```

#### 3.2.7 EdgeTypeDecorator

```python
@dataclass(frozen=True)
class EdgeTypeDecorator:
    """Symmetric to NodeTypeGenerator. Decorates a graph edge.

    The decorator may emit ops that reference earlier-emitted ops
    (e.g., a 'mirrors' edge emits an op.mirror that points at the
    target node's ops). The compiler pipeline orders decorators so
    referenced ops always emit first.
    """

    manifest: EdgeDecoratorCapabilityManifest
    implementation: Callable[
        [ConstructionEdge, SynthesizerContext, OpResolver],
        Iterable[ShapeOp],
    ]
```

Operates on edges between graph nodes. Emits relational ops:
mirrors, booleans, alignments, scatter-on-surface, attached-to
constraints. Receives the current list of emitted ops so it can
emit ops that reference earlier records.

### 3.3 The Generator Registry (Domain-Extensible Plugin)

The registry is keyed by `(domain, node_type)`. Domains register their
generators independently. Hard-surface, vegetation, terrain, WFC,
CGA, animation — each domain plugs into the same shared core without
bloating any other domain's registry.

```python
class GeneratorRegistry:
    """Plugin-extensible registry. No hardcoded family knowledge.

    Domains register generators at import time via:

        registry.register_generator(
            NodeTypeGenerator(manifest=..., implementation=...)
        )

    Registration is idempotent — re-registering the same (domain,
    node_type) replaces the previous registration with a trace entry,
    not silently. Manifest inspection happens at registration time so
    incomplete coverage surfaces as a diagnostic.
    """

    def register_generator(self, gen: NodeTypeGenerator) -> None: ...
    def register_decorator(self, dec: EdgeTypeDecorator) -> None: ...
    def resolve_generator(
        self, domain: str, node_type: str,
    ) -> NodeTypeGenerator | None:
        # 1. Try (domain, node_type) exact match
        # 2. Fall back to (default_domain="core", node_type) — for
        #    shared types like material_zone that work cross-domain
        # 3. Return None and let the pipeline emit
        #    `unknown_node_type_for_domain` diagnostic
        ...


# Hard-surface generators register themselves at import time:
#   lathe/asset_quality/procedural_synthesizer/generators/hard_surface/__init__.py
#
#   from . import primary_volume, panel, fastener, ...
#   primary_volume.register(REGISTRY)
#   panel.register(REGISTRY)
#   ...
#
# Vegetation does the same in:
#   lathe/asset_quality/procedural_synthesizer/generators/vegetation/__init__.py
#
# Domain extension packs (Phase 3) plug in without touching the
# hard-surface tree. Each domain has its own NODE_TYPES extension
# subset.
```

The registry size grows linearly with NODE_TYPES across domains. It
never grows with family count.

### 3.4 Hint Resolution Rules

Strict priority chain. Authored intent always wins over style bias.
Policies add structure to the graph before this chain runs, but they
add via NODE_TYPES, not by family identity.

```
priority order (highest wins) for any field value:
  1. typed node attribute (already schema-validated)
  2. authored brief field
  3. authored parts list (presence/absence)
  4. style.parameter_priors[node_type][field]
  5. style.proportion_priors[node_type] / density_priors / silhouette_priors
  6. generator-internal absolute defaults
```

Every resolution writes a `hint_resolution_trace` entry recording
the source priority level that won.

CompositionPolicy expansions are NOT part of the hint chain — they
run earlier, in the compiler pipeline's `expand_policies` step
(§3.5). A policy adds nodes; generators consume nodes. The two
concerns are separate.

### 3.5 The Compiler Pipeline

Replaces the earlier draft's linear "walk nodes then walk edges"
loop. Real procedural composition requires staged processing with
explicit graph normalization, dependency ordering, validation gates,
and trace attribution. Each stage has a single responsibility and a
typed input/output.

```python
def synthesize_shape_program(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> SynthesisResult:
    """Procedural compilation pipeline. Eight ordered stages."""

    # Stage 1: Resolve context from authored sources
    ctx = _resolve_context(asset, runtime)
    #   - parse brief, parts, intent tags
    #   - resolve family_alias -> (style, policy_ids) if alias given
    #   - load StyleKnowledge pack by style_id
    #   - load CompositionPolicy packs by policy_ids
    #   - record family_alias in trace metadata only

    # Stage 2: Normalize the authored construction graph
    raw_graph = runtime.get("construction_graph", {})
    normalized_graph = _normalize_graph(raw_graph, ctx)
    #   - dedupe node_ids
    #   - canonicalize edge directions
    #   - resolve string node references to node_id pointers
    #   - reject unknown node_types with diagnostic

    # Stage 3: Expand graph with applicable composition policies
    expanded_graph = _expand_policies(normalized_graph, ctx)
    #   - for each loaded policy:
    #     - test precondition against authored intent (NOT family)
    #     - if matches AND no forbid conflict: apply expansion
    #     - record `policy_added_node` trace entry per added node
    #   - policies run in deterministic order by policy_id

    # Stage 4: Validate typed attributes
    validated_graph = _validate_attributes(expanded_graph, ctx)
    #   - for each node, validate against PER_NODE_TYPE_SCHEMA
    #   - missing required fields -> emit attribute_schema_violation
    #   - extra fields -> emit attribute_schema_extension trace
    #   - schema-passing nodes get `typed_attributes` set on the node

    # Stage 5: Topologically order nodes and edges
    ordered = _topological_order(validated_graph, ctx)
    #   - parent volumes before their attached components
    #   - source primitives before booleans that consume them
    #   - target nodes before edge decorators that reference them
    #   - cycles -> emit cycle_in_construction_graph and break
    #     deterministically by node_id

    # Stage 6: Emit base ops (one generator call per node, in order)
    base_ops: list[ShapeOp] = []
    base_trace: list[TraceEntry] = []
    for node in ordered.nodes:
        gen = REGISTRY.resolve_generator(ctx.domain, node.node_type)
        if gen is None:
            base_trace.append(_no_generator_trace(node, ctx))
            continue
        node_ops = list(gen.implementation(node, ctx))
        base_ops.extend(node_ops)
        base_trace.extend(_attribute_ops_to_node(node, node_ops, gen))

    # Stage 7: Emit relational ops (one decorator call per edge)
    op_resolver = _build_op_resolver(base_ops, ordered.nodes)
    edge_ops: list[ShapeOp] = []
    edge_trace: list[TraceEntry] = []
    for edge in ordered.edges:
        dec = REGISTRY.resolve_decorator(ctx.domain, edge.edge_type)
        if dec is None:
            edge_trace.append(_no_decorator_trace(edge, ctx))
            continue
        edge_op_iter = dec.implementation(edge, ctx, op_resolver)
        edge_ops.extend(edge_op_iter)
        edge_trace.extend(_attribute_ops_to_edge(edge, edge_op_iter, dec))

    # Stage 8: Validate emitted ops + attach trace
    all_ops = (*base_ops, *edge_ops)
    _validate_against_all_ops(all_ops)
    #   - every emitted op.op must be in shape_ir_v2.ALL_OPS
    #   - violations emit emitted_op_outside_shape_ir_v2 diagnostic
    #     AND drop the offending op (no silent degradation)

    program = ShapeProgram(
        version=SHAPE_IR_V2_VERSION,
        asset_name=ctx.asset_name,
        family=ctx.family_alias,           # metadata tag, never dispatched
        ops=all_ops,
    )
    return SynthesisResult(
        shape_program=program,
        synthesized_graph_nodes=_policy_added_nodes(ordered, normalized_graph),
        synthesizer_trace=SynthesizerTrace(
            stage_traces=(...),
            hint_resolution=base_trace + edge_trace,
            policy_applications=tuple(_policy_applied_log(ctx)),
            attempted_via="procedural_engine",
            family_dispatch_used=False,    # by construction, every run
        ),
    )
```

Eight stages, each with a single concern. Each stage's trace is
addressable and inspectable. No stage looks at the family alias for
behavior — alias appears only in trace metadata.

`program.family` carries the family id as a metadata tag, but no
code downstream dispatches on it. The pipeline guarantees this by
construction: family is consumed at Stage 1 to resolve (style,
policies) and not referenced again.

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
2. **Author the declarative knowledge files** that capture the recipe's
   decisions:
   - **StyleKnowledge JSON pack** at
     `std/procedural/knowledge/style/<style_id>.json` for parameter
     biasing (proportions, density, style band). Reused across many
     families; not family-specific by default.
   - **CompositionPolicy JSON pack(s)** at
     `std/procedural/knowledge/policy/<policy_id>.json` for the
     structural decisions the recipe currently makes. Match by
     authored-intent precondition, not family name. Reuse existing
     policies before authoring a new one.
   - **FamilyAlias JSON file** at
     `std/procedural/knowledge/aliases/<family_id>.json` mapping the
     family name to (style_id, policy_ids[]). The alias is pure
     metadata; it carries no structural decisions itself.
   All three file types are schema-validated at load time. No
   callables. No Python logic. Each value records provenance
   (which file, which field) in `synthesizer_trace`.
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

Code lives under `lathe/`. Declarative knowledge lives under `std/`.
The boundary is strict: code knows the engine, knowledge declares
the data.

### 5.1 Engine code (`lathe/asset_quality/procedural_synthesizer/`)

```
lathe/asset_quality/procedural_synthesizer/
    __init__.py                 # public API: synthesize_shape_program
    context.py                  # SynthesizerContext, _resolve_context
    pipeline.py                 # 8-stage compiler pipeline
    registry.py                 # GeneratorRegistry (domain-extensible)
    trace.py                    # SynthesizerTrace + TraceEntry schemas
    hint_resolution.py          # priority-merge logic with trace attribution
    attributes/
        __init__.py             # PER_NODE_TYPE_SCHEMA dispatch
        primary_volume.py       # PrimaryVolumeAttributes
        panel.py                # PanelAttributes
        fastener.py             # FastenerAttributes
        material_zone.py        # MaterialZoneAttributes
        ...                     # one per NODE_TYPE
    knowledge_loader/
        __init__.py
        style.py                # loads + schema-validates StyleKnowledge JSON
        policy.py               # loads + schema-validates CompositionPolicy JSON
        alias.py                # loads + schema-validates FamilyAlias JSON
        schemas/
            style.schema.json
            policy.schema.json
            alias.schema.json
    generators/
        __init__.py             # registry assembly (calls per-domain register())
        hard_surface/
            __init__.py         # registers hard-surface generators
            primary_volume.py
            panel.py
            fastener.py
            trim.py
            decal_zone.py
            guard.py
            frame.py
            inset.py
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
            wear_zone.py
            material_zone.py
        # Phase 3 additions (cycle 6 of master plan):
        vegetation/             # registers vegetation generators
            trunk.py
            branch.py
            leaf_cluster.py
            ...
        terrain/                # registers terrain generators
            heightfield_tile.py
            erosion_basin.py
            ...
        # ... future domain packages live here, never bloat each other
    decorators/
        __init__.py
        attached_to.py
        inset_into.py
        wraps_around.py
        mirrors.py
        aligned_with.py
        supports.py
        cuts.py
        # symmetric per-domain extension structure
```

### 5.2 Declarative knowledge (`std/procedural/knowledge/`)

```
std/procedural/knowledge/
    style/
        industrial_pbr_v1.json
        natural_organic_v1.json
        stylized_lowpoly_v1.json
        ...                     # one file per style, reusable across families
    policy/
        panelized_hard_surface_object.json
        radial_mechanical_assembly.json
        l_system_branching.json
        wfc_modular_layout.json
        ...                     # one file per composition policy, reusable
    aliases/
        industrial_crate.json   # { family_id, style_id, policy_ids, domain }
        mechanical_door.json
        weapon_prop.json
        ...                     # one file per family alias — METADATA ONLY
```

Every file in `std/procedural/knowledge/` is schema-validated at
load. No Python files. No callables. Adding a new family is a single
JSON file under `aliases/` that references existing style + policy
packs; no Python code change required.

The schema files in `lathe/.../knowledge_loader/schemas/` define
exactly what fields are permitted. Any file that doesn't validate
fails loudly at startup with a `knowledge_pack_invalid` error
naming the offending file and field.

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

- Declarative knowledge files exist:
  - One `StyleKnowledge` JSON at
    `std/procedural/knowledge/style/<style_id>.json` (may be shared
    with other families).
  - One or more `CompositionPolicy` JSONs at
    `std/procedural/knowledge/policy/<policy_id>.json` (may be
    shared).
  - One `FamilyAlias` JSON at
    `std/procedural/knowledge/aliases/<family_id>.json` referencing
    the style and policies.
- All knowledge files pass schema validation at startup.
- The synthesizer's output ShapeProgram passes equivalence-or-better
  diff against the original recipe's output across three test
  scenarios (default brief, varied brief, varied parts).
- The recipe function and its `_RECIPES` registration are deleted.
- The family appears in `_MIGRATED_TO_SYNTHESIZER` (during
  coexistence) or is no longer dispatched anywhere (after
  decommissioning).
- Every test in `tests/unit/test_asset_quality_grammar_lowering.py`
  that referenced the family continues to pass, updated for the new
  expected outputs where intent-driven differences are present (per
  §9.5 "structured expected outputs" policy).

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
  `attempted_via: procedural_engine` plus stage-level traces
  (`policy_applied`, `hint_resolution`, `attribute_validated`,
  `generator_resolved`, `decorator_resolved`) to every program.
  `family_dispatch_used: false` is set on every synthesized program
  by construction.

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

## 9. Resolved Decisions And Remaining Open Questions

Review iteration 1 (2026-05-11) resolved several questions that the
earlier draft had left open. They are recorded here as decisions, not
questions, so subsequent agents do not re-litigate them.

### 9.1 Resolved: Domain Extension Model

**Decision: shared synthesizer core + domain extension packs keyed
by `domain` field, never by family.**

- The `GeneratorRegistry` is keyed by `(domain, node_type)`.
- Each domain (`hard_surface`, `vegetation`, `terrain`, `wfc`,
  `cga`, `sdf_organic`, `scatter`, `animation`) lives in its own
  subpackage under `generators/<domain>/` and `decorators/<domain>/`.
- Each domain registers its generators at import time. No domain's
  registry pollutes another's.
- The `ConstructionEdge` and authored brief carry a `domain` field
  that selects the active domain. A scene with multiple domains
  (e.g., a forest with hard-surface buildings) lives in a parent
  graph whose nodes individually carry their domain.
- NODE_TYPES grow per-domain. The core set (20 hard-surface types)
  is one domain's subset, not the global universe. Vegetation has
  its own subset (`trunk`, `branch`, `leaf_cluster`, `frond`,
  `root`, `bark`); terrain has its own; etc.
- A `material_zone` type that works across domains lives in a
  pseudo-domain `core` that all domains fall back to.

### 9.2 Resolved: Knowledge Pack Source Format

**Decision: JSON files schema-validated at load time. No callables.
No Python.**

- Style, policy, and alias packs live in `std/procedural/knowledge/`
  as `.json` files.
- Schemas live in
  `lathe/asset_quality/procedural_synthesizer/knowledge_loader/schemas/`
  and are enforced at startup with `jsonschema` (or equivalent).
- Adding a new family is a single JSON file under `aliases/` that
  references existing style and policy packs. No Python code
  change required.
- A lint rule rejects any non-JSON file under
  `std/procedural/knowledge/`.

### 9.3 Resolved: First Implementation Slice Output

**Decision: the first cycle 1 commit produces real ShapeProgram
output, not a no-op skeleton.**

- The minimum viable first commit must include:
  - The full compiler pipeline (all 8 stages, with no-op
    implementations only for stages that need future work).
  - Working `primary_volume` generator with capability manifest.
  - Working `panel` generator with capability manifest.
  - Working `attached_to` edge decorator (so panels can attach
    to primary volumes).
  - Typed attribute schemas for primary_volume and panel.
  - Schema validation for those two types.
  - The hint resolution chain with trace attribution.
  - Routing of unknown families to the synthesizer.
- The acceptance proof: a test fixture authored with NO family
  alias, only a brief saying "container with 2 panels" plus a
  graph with primary_volume + 2 panel nodes attached_to it,
  produces a non-empty ShapeProgram with `family_dispatch_used:
  false` and at least 3 visible-geometry ops. The same test runs
  via the build pipeline and produces a real GLB.
- No "stub returning empty" placeholders. Every committed
  generator does its real job.

### 9.4 Resolved: Edge Decoration Ordering

**Decision: edges are topologically ordered in Stage 5 of the
compiler pipeline.**

- Decorator priority is implicit in topological order: edges whose
  source ops already exist when the decorator runs are processed
  in order of source-op emission.
- Ties broken deterministically by `edge_id` lexicographic order.
- A `decoration_order_trace` entry records the order so an
  inspector can audit deterministic behavior.

### 9.5 Remaining Open Questions

1. **Sub-asset composition** — recipes for bundle-style families
   (`world_system_assembly`, `engine_facing_runtime_bundle_system`)
   today emit references to sub-assets. Candidate: an `assembly`
   NODE_TYPE in the `core` domain that references a child
   construction graph (recursive synthesis). Resolution deferred
   to the first time we attempt to migrate a bundle recipe;
   prototype then ratify.
2. **Backward compatibility for pinned tests** — the existing
   `test_asset_quality_grammar_lowering.py` pins recipe behavior
   tightly (exact op counts, primitive types). During migration we
   need a policy: synthesizer changes that diverge from the recipe
   are acceptable if intent-driven; pure-regression divergences are
   not. The trace field provides the audit trail. Policy candidate:
   each test's pinned expectations are converted from a single
   "expected program" to a structured "expected_op_kinds (subset
   assertion) + expected_min_records + expected_node_types_covered"
   trio.
3. **Style overlay composition** — what happens when a brief
   references multiple style packs (e.g., "industrial" + "weathered")?
   Candidate: ordered overlay, later styles override earlier;
   `style_overlay_trace` records resolution. Deferred to first
   multi-style fixture.

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

Per the northstar §18 "What To Implement Next" pattern AND §9.3
resolved decision ("first slice produces real output, no no-op
skeleton"):

### First commit (single session, all-in-one slice)

1. Create the engine code tree per §5.1 with all 8 pipeline stages
   stubbed but functional (`pipeline.py`).
2. Implement `registry.py` with `GeneratorRegistry`, manifest
   inspection at registration time, `(domain, node_type)` lookup
   plus `core` domain fallback.
3. Implement `trace.py` with `SynthesizerTrace`, `TraceEntry`,
   stage-traces aggregation, and JSON-serializable output.
4. Implement `hint_resolution.py` with the §3.4 priority chain plus
   trace attribution.
5. Implement `attributes/primary_volume.py` and `attributes/panel.py`
   (typed schemas).
6. Implement `knowledge_loader/{style.py, policy.py, alias.py}` plus
   the three JSON schemas in
   `knowledge_loader/schemas/{style,policy,alias}.schema.json`.
   Load at module import time, fail loudly on schema violations.
7. Implement `generators/hard_surface/primary_volume.py` end-to-end
   with capability manifest. Same for `panel.py`.
8. Implement `decorators/attached_to.py` end-to-end with capability
   manifest.
9. Author the first declarative knowledge files:
   - `std/procedural/knowledge/style/industrial_pbr_v1.json` (minimal)
   - `std/procedural/knowledge/policy/panelized_hard_surface_object.json`
     (the panel-on-primary-volume policy that applies to many families)
   - One `aliases/<family>.json` for the simplest currently-known
     family the synthesizer can handle (likely `surface_material_sample`
     or `set_dressing_prop`).
10. Wire `evaluate_grammar_lowering` to route both unknown families
    AND the one migrated family through `synthesize_shape_program`.
11. Add `tests/unit/test_procedural_synthesizer_pipeline.py` with at
    minimum:
    - A test that authored intent (primary_volume + 2 panels +
      attached_to edges) produces a ShapeProgram with ≥ 3 ops, all
      in `shape_ir_v2.ALL_OPS`, `family_dispatch_used: false`.
    - A test that the same authored intent with a different brief
      produces a structurally-different ShapeProgram (intent
      dominance).
    - A test that a policy expansion adds an expected node type
      when its precondition matches.
    - A test that a knowledge file with invalid schema fails
      startup loudly.
12. Run the targeted verification slice (the 136+ tests). Commit.
    Push.

### Subsequent sessions

Each session adds either:

- A new generator (one of the remaining 18 hard-surface NODE_TYPES),
  or
- A new edge decorator (one of the remaining EDGE_TYPES), or
- A new recipe migration (one of the 73 families), or
- A new typed attribute schema (paired with a generator), or
- A new policy pack (composable across families).

No session ships a no-op skeleton. Every session's commit produces
something that runs end-to-end.

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
