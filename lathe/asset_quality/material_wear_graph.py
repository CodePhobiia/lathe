"""Phase 8 deterministic Material/Wear Graph IR.

Adds an internal ``MaterialWearGraph`` representation that binds
authored wear masks and material zones to construction-graph nodes
(Phase 4) and edge targets, plus a uniform-noise diagnostic that
detects when the existing surface output looks like procedural noise
rather than semantically driven storytelling.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 12.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 8.
Per-mask-type / zone-type reference:
``docs/asset-quality/material-wear-graph-v1.md``.

Design summary
--------------

Phase 8 is **evidence + diagnostic only**. It does not run a real
material-authoring tool, drive Blender, produce mask textures, or drive
surface maps. The surface bundle carries additive hooks that say so.
The evaluator inspects the live runtime, consumes a resolved
``surface.material_graph`` only when it already has Material/Wear Graph
v1 shape, otherwise picks the per-family default graph
(industrial_crate is the first concrete family), validates that mask
bindings reference real construction nodes and structural edge targets,
scores how uniform the existing surface output looks, and publishes a
structured payload under ``runtime["material_wear_graph"]`` plus the
matching ``material_wear_graph`` key on the validate-stage report (the
22nd top-level key, on top of the 21 that Phases 0 through 7 publish).

Per-family default graphs ride alongside the recipe so Phase 14 golden
examples can demonstrate a non-uniform material story without any
``.lth`` syntax change. Phase 13 will add the public surface-program
syntax that lets authors override the defaults; Phase 8 is the
internal IR + diagnostic surface that future syntax lowers into.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``highlow_relation`` and before
``geometry_integrity`` (so the highlow_relation evidence is
available). Like Phases 1 through 7, the layer is informational only
and never blocks certification — it omits the top-level
``diagnostics`` field so the ``FunctionValidator`` wrapper treats the
validator as passing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

MATERIAL_WEAR_VERSION = "material_wear_v1"


WEAR_MASK_TYPES: frozenset[str] = frozenset(
    {
        "convex_edge_wear",
        "concave_grime",
        "lower_contact_scuff",
        "handle_touch_wear",
        "decal_wear",
    }
)


ZONE_TYPES: frozenset[str] = frozenset(
    {
        "base_material",
        "underlayer",
    }
)


_UNIFORM_NOISE_WARNING_THRESHOLD = 0.50

_BAKE_MAP_FULL_COUNT = 4

_ZONE_DIVERSITY_FULL_CREDIT = 3.0

_ZONE_DIVERSITY_WEIGHT = 0.4
_WEAR_BINDING_WEIGHT = 0.6


@dataclass(frozen=True)
class WearMask:
    """One authored wear mask in the material/wear graph.

    A wear mask carries an intensity in ``[0.0, 1.0]`` plus an optional
    binding to a construction-graph node and / or a structural edge
    target (e.g. ``"body_shell.outer_edges"``). At least one of
    ``bound_node_id`` or ``bound_edge_target`` is expected to be non-
    ``None``; orphan-detection in :func:`evaluate_material_wear_graph`
    inspects these fields and emits a structured diagnostic when the
    binding fails to resolve against the live construction graph.
    """

    mask_id: str
    mask_type: str
    intensity: float
    bound_node_id: str | None
    bound_edge_target: str | None
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate bindings and freeze parameter metadata."""
        _require_non_empty_string(self.mask_id, "mask_id")
        if self.mask_type not in WEAR_MASK_TYPES:
            raise ValueError(
                f"unknown material wear mask_type {self.mask_type!r}; "
                f"expected one of {sorted(WEAR_MASK_TYPES)}"
            )
        object.__setattr__(
            self, "intensity", _validate_unit_float(self.intensity, "intensity")
        )
        bound_node_id = _clean_optional_string(self.bound_node_id, "bound_node_id")
        bound_edge_target = _clean_optional_string(
            self.bound_edge_target, "bound_edge_target"
        )
        if bound_node_id is None and bound_edge_target is None:
            raise ValueError("WearMask requires bound_node_id or bound_edge_target")
        object.__setattr__(self, "bound_node_id", bound_node_id)
        object.__setattr__(self, "bound_edge_target", bound_edge_target)
        object.__setattr__(
            self, "parameters", _freeze_parameters(self.parameters, "parameters")
        )


@dataclass(frozen=True)
class MaterialZone:
    """One material zone (base material or underlayer) in the graph.

    A material zone records a base color (hex token), a roughness and
    metalness in ``[0.0, 1.0]``, an optional binding to a part name
    (matching ``asset["intent"]["parts"]``), and an open-ended
    ``parameters`` dict reserved for forward phases that may layer on
    finish hints (anisotropy, clearcoat, etc.).
    """

    zone_id: str
    zone_type: str
    base_color: str
    roughness: float
    metalness: float
    bound_part: str | None
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate material scalars and freeze parameter metadata."""
        _require_non_empty_string(self.zone_id, "zone_id")
        if self.zone_type not in ZONE_TYPES:
            raise ValueError(
                f"unknown material zone_type {self.zone_type!r}; "
                f"expected one of {sorted(ZONE_TYPES)}"
            )
        _require_non_empty_string(self.base_color, "base_color")
        object.__setattr__(
            self, "roughness", _validate_unit_float(self.roughness, "roughness")
        )
        object.__setattr__(
            self, "metalness", _validate_unit_float(self.metalness, "metalness")
        )
        object.__setattr__(
            self, "bound_part", _clean_optional_string(self.bound_part, "bound_part")
        )
        object.__setattr__(
            self, "parameters", _freeze_parameters(self.parameters, "parameters")
        )


@dataclass(frozen=True)
class MaterialWearGraph:
    """A frozen graph of material zones, underlayers, and wear masks.

    The graph is the per-family default Phase 8 publishes. Phase 13's
    public surface-program syntax lowers into the same dataclass, which
    is why each member is a tuple instead of a list — author overrides
    must produce a fully frozen graph, not mutate one in flight.
    """

    family: str
    version: str
    materials: tuple[MaterialZone, ...]
    underlayers: tuple[MaterialZone, ...]
    wear_masks: tuple[WearMask, ...]

    def __post_init__(self) -> None:
        """Validate graph identity and freeze child collections."""
        _require_non_empty_string(self.family, "family")
        _require_non_empty_string(self.version, "version")
        object.__setattr__(
            self, "materials", _freeze_typed_tuple(self.materials, MaterialZone, "materials")
        )
        object.__setattr__(
            self,
            "underlayers",
            _freeze_typed_tuple(self.underlayers, MaterialZone, "underlayers"),
        )
        object.__setattr__(
            self, "wear_masks", _freeze_typed_tuple(self.wear_masks, WearMask, "wear_masks")
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (lists in place of tuples)."""
        return {
            "family": self.family,
            "version": self.version,
            "materials": [_material_zone_to_dict(zone) for zone in self.materials],
            "underlayers": [_material_zone_to_dict(zone) for zone in self.underlayers],
            "wear_masks": [_wear_mask_to_dict(mask) for mask in self.wear_masks],
        }


def _require_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _clean_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be None or a non-empty string")
    return value


def _validate_unit_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number in [0.0, 1.0]")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
        raise ValueError(f"{field_name} must be a finite number in [0.0, 1.0]")
    return numeric


def _freeze_parameters(value: Any, field_name: str) -> MappingProxyType:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return MappingProxyType(deepcopy(dict(value)))


def _freeze_typed_tuple(value: Any, item_type: type, field_name: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence")
    frozen = tuple(value)
    for item in frozen:
        if not isinstance(item, item_type):
            raise ValueError(f"{field_name} must contain only {item_type.__name__}")
    return frozen


def _material_zone_to_dict(zone: MaterialZone) -> dict[str, Any]:
    return {
        "zone_id": zone.zone_id,
        "zone_type": zone.zone_type,
        "base_color": zone.base_color,
        "roughness": zone.roughness,
        "metalness": zone.metalness,
        "bound_part": zone.bound_part,
        "parameters": dict(zone.parameters),
    }


def _wear_mask_to_dict(mask: WearMask) -> dict[str, Any]:
    return {
        "mask_id": mask.mask_id,
        "mask_type": mask.mask_type,
        "intensity": mask.intensity,
        "bound_node_id": mask.bound_node_id,
        "bound_edge_target": mask.bound_edge_target,
        "parameters": dict(mask.parameters),
    }


def _industrial_crate_default_graph() -> MaterialWearGraph:
    """Return the canonical industrial_crate default material/wear graph.

    Mirrors the painted-steel example in spec Section 12.3:

    - One ``base_material`` zone (``painted_steel_body``) bound to the
      ``body`` part with a muted blue-grey base color and a
      semi-rough non-metallic finish.
    - One ``underlayer`` zone (``dark_bare_metal``) bound to the
      ``body`` part with a dark, metallic finish that the chip-edge
      and contact-scuff masks reveal.
    - Six wear masks (one per WEAR_MASK_TYPES member, two for the
      mirrored ``foot`` and ``handle`` pairs since each member of the
      pair gets its own bound_node_id):

      | mask_id | mask_type | binding |
      |---|---|---|
      | recipe.wear.convex_edges_body | convex_edge_wear | edge_target body.outer_edges |
      | recipe.wear.concave_grime_lid_seam | concave_grime | node recipe.lid_seam + edge_target body.top_band |
      | recipe.wear.foot_scuff_l | lower_contact_scuff | node recipe.foot_rail_front |
      | recipe.wear.foot_scuff_r | lower_contact_scuff | node recipe.foot_rail_back |
      | recipe.wear.handle_touch_l | handle_touch_wear | node recipe.handle_l |
      | recipe.wear.handle_touch_r | handle_touch_wear | node recipe.handle_r |
      | recipe.wear.warning_decal | decal_wear | node recipe.warning_decal_zone |
      | recipe.wear.corner_guard_0..7 | convex_edge_wear | node recipe.corner_guard_* + edge_target body.corners |

    Total: 1 base material + 1 underlayer + 15 wear masks. The two
    foot-scuff masks (one per mirrored foot node) keep the binding
    one-to-one with the synthesized graph nodes; the same holds for the
    two handle-touch masks and eight corner-guard masks. The single
    decal_wear binding tracks the one ``recipe.warning_decal_zone``
    synthesized by Phase 6.
    """
    materials = (
        MaterialZone(
            zone_id="painted_steel_body",
            zone_type="base_material",
            base_color="#4f5668",
            roughness=0.62,
            metalness=0.0,
            bound_part="body",
            parameters={},
        ),
    )
    underlayers = (
        MaterialZone(
            zone_id="dark_bare_metal",
            zone_type="underlayer",
            base_color="#2a2a2a",
            roughness=0.50,
            metalness=1.0,
            bound_part="body",
            parameters={},
        ),
    )
    wear_masks = (
        WearMask(
            mask_id="recipe.wear.convex_edges_body",
            mask_type="convex_edge_wear",
            intensity=0.28,
            bound_node_id=None,
            bound_edge_target="body.outer_edges",
            parameters={},
        ),
        WearMask(
            mask_id="recipe.wear.concave_grime_lid_seam",
            mask_type="concave_grime",
            intensity=0.22,
            bound_node_id="recipe.lid_seam",
            bound_edge_target="body.top_band",
            parameters={},
        ),
        WearMask(
            mask_id="recipe.wear.foot_scuff_l",
            mask_type="lower_contact_scuff",
            intensity=0.35,
            bound_node_id="recipe.foot_rail_front",
            bound_edge_target="body.bottom_front",
            parameters={},
        ),
        WearMask(
            mask_id="recipe.wear.foot_scuff_r",
            mask_type="lower_contact_scuff",
            intensity=0.35,
            bound_node_id="recipe.foot_rail_back",
            bound_edge_target="body.bottom_back",
            parameters={},
        ),
        WearMask(
            mask_id="recipe.wear.handle_touch_l",
            mask_type="handle_touch_wear",
            intensity=0.18,
            bound_node_id="recipe.handle_l",
            bound_edge_target="body.left_face",
            parameters={},
        ),
        WearMask(
            mask_id="recipe.wear.handle_touch_r",
            mask_type="handle_touch_wear",
            intensity=0.18,
            bound_node_id="recipe.handle_r",
            bound_edge_target="body.right_face",
            parameters={},
        ),
        WearMask(
            mask_id="recipe.wear.warning_decal",
            mask_type="decal_wear",
            intensity=0.20,
            bound_node_id="recipe.warning_decal_zone",
            bound_edge_target="body.front_face",
            parameters={},
        ),
        *tuple(
            WearMask(
                mask_id=f"recipe.wear.corner_guard_{index}",
                mask_type="convex_edge_wear",
                intensity=0.24,
                bound_node_id=f"recipe.corner_guard_{index}",
                bound_edge_target="body.corners",
                parameters={},
            )
            for index in range(8)
        ),
    )
    return MaterialWearGraph(
        family="industrial_crate",
        version=MATERIAL_WEAR_VERSION,
        materials=materials,
        underlayers=underlayers,
        wear_masks=wear_masks,
    )


def _generic_default_graph(family: str) -> MaterialWearGraph:
    """Return the generic empty graph for an unrecognised family.

    No materials, no underlayers, no wear masks. The uniform-noise
    score will land at the upper bound (``1.0``) and the warning will
    fire — the intended signal that an author should opt into a real
    material/wear graph. Phase 13's public surface-program syntax is
    the opt-in path; until then, generic-family assets read as
    auto-noise on purpose.
    """
    return MaterialWearGraph(
        family=family,
        version=MATERIAL_WEAR_VERSION,
        materials=(),
        underlayers=(),
        wear_masks=(),
    )


_FAMILY_DEFAULT_GRAPHS: dict[str, Any] = {
    "industrial_crate": _industrial_crate_default_graph,
}


def _select_default_graph(family: str) -> MaterialWearGraph:
    factory = _FAMILY_DEFAULT_GRAPHS.get(family)  # no-family-dispatch: per-family wear-graph factory map for the validator's default-graph fallback; migrate to a wear-graph CompositionPolicy keyed on intent tags / capability triggers
    if factory is None:
        return _generic_default_graph(family)
    return factory()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve_family(runtime: dict[str, Any]) -> str:
    """Return the family token published by Phase 2's design_brief, or ``"generic"``."""
    design_brief = _as_dict(runtime.get("design_brief"))
    brief = _as_dict(design_brief.get("brief"))
    family = brief.get("family")
    if isinstance(family, str) and family:
        return family
    return "generic"


def _resolve_construction_node_ids(runtime: dict[str, Any]) -> set[str]:
    """Return the set of construction-graph node ids published by Phase 4.

    When Phase 6's grammar lowering has run, the synthesized recipe
    nodes (``recipe.handle_l``, ``recipe.foot_rail_front``, ``recipe.warning_decal_zone``,
    ...) live under ``runtime["grammar_lowering"]["synthesized_graph_nodes"]``
    and are merged here so wear-mask bindings against recipe nodes can
    resolve. The live pipeline does not auto-merge those nodes into
    ``runtime["construction_graph"]["nodes"]``; Phase 8 reads both
    sources read-only without mutating either.
    """
    construction_graph = _as_dict(runtime.get("construction_graph"))
    grammar_lowering = _as_dict(runtime.get("grammar_lowering"))
    node_ids: set[str] = set()
    for entry in _as_list(construction_graph.get("nodes")):
        if isinstance(entry, dict):
            node_id = entry.get("node_id")
            if isinstance(node_id, str) and node_id:
                node_ids.add(node_id)
    for entry in _as_list(grammar_lowering.get("synthesized_graph_nodes")):
        if isinstance(entry, dict):
            node_id = entry.get("node_id")
            if isinstance(node_id, str) and node_id:
                node_ids.add(node_id)
    return node_ids


def _resolve_surface_bundle(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("surface")).get("bundle"))


def _surface_has_driven_map_evidence(surface_bundle: dict[str, Any]) -> bool:
    """Return True when surface zones are backed by map/control-pack evidence."""
    outputs = _as_dict(surface_bundle.get("outputs"))
    bake_outputs = _as_dict(surface_bundle.get("bake_outputs"))
    control_pack = _as_dict(surface_bundle.get("surface_control_pack"))
    hooks = _as_dict(surface_bundle.get("material_wear_graph_hooks"))
    return bool(
        outputs
        or bake_outputs
        or control_pack
        or hooks.get("surface_maps_driven_by_material_wear_graph") is True
    )


def _resolve_existing_surface_zone_count(runtime: dict[str, Any]) -> int:
    """Return the count of map-backed surface ``material_zones``.

    The surface stage publishes ``runtime["surface"]["bundle"]["material_zones"]``
    as a list of ``{"material": ..., "part": ...}`` dicts. The count
    feeds uniform-noise only when the bundle also carries map/control-pack
    evidence. This prevents metadata-only zones from suppressing a
    uniform-noise warning.
    """
    surface_bundle = _resolve_surface_bundle(runtime)
    if not _surface_has_driven_map_evidence(surface_bundle):
        return 0
    return len(_as_list(surface_bundle.get("material_zones")))


def _resolve_edge_targets(runtime: dict[str, Any]) -> set[str]:
    """Return structural edge/target tokens published by prior phases.

    Edge-bound wear masks resolve only against real construction edges
    or ShapeIR targets emitted by grammar lowering. Non-empty strings
    alone are not evidence.
    """
    construction_graph = _as_dict(runtime.get("construction_graph"))
    grammar_lowering = _as_dict(runtime.get("grammar_lowering"))
    targets: set[str] = set()

    for entry in _as_list(construction_graph.get("edges")):
        if not isinstance(entry, dict):
            continue
        source_id = entry.get("source_id")
        target_id = entry.get("target_id")
        edge_type = entry.get("edge_type")
        if isinstance(source_id, str) and isinstance(edge_type, str):
            targets.add(f"{source_id}.{edge_type}")
        if isinstance(source_id, str) and isinstance(target_id, str):
            targets.add(f"{source_id}->{target_id}")
        if (
            isinstance(source_id, str)
            and isinstance(target_id, str)
            and isinstance(edge_type, str)
        ):
            targets.add(f"{source_id}.{edge_type}.{target_id}")
        attributes = _as_dict(entry.get("attributes"))
        for key in ("edge_target", "target", "selector"):
            value = attributes.get(key)
            if isinstance(value, str) and value:
                targets.add(value)

    shape_program = _as_dict(grammar_lowering.get("shape_program"))
    for op in _as_list(shape_program.get("ops")):
        if not isinstance(op, dict):
            continue
        target = op.get("target")
        if isinstance(target, str) and target:
            targets.add(target)

    return targets


def _resolve_bake_map_count_present(runtime: dict[str, Any]) -> int:
    """Return the count of bake maps present per Phase 7's evidence.

    Reads ``runtime["highlow_relation"]["bake_maps"]`` (a list of
    ``BakeMapEvidence`` dicts) and counts those with ``present=True``.
    A missing or malformed structure collapses to ``0``.
    """
    highlow = _as_dict(runtime.get("highlow_relation"))
    raw_maps = _as_list(highlow.get("bake_maps"))
    return sum(
        1
        for entry in raw_maps
        if isinstance(entry, dict) and bool(entry.get("present"))
    )


def _quality_plan_alignment(runtime: dict[str, Any], graph: MaterialWearGraph) -> dict[str, Any]:
    """Return read-only alignment evidence when Phase 14C quality plan exists."""
    quality_plan = _as_dict(runtime.get("quality_plan"))
    if not quality_plan:
        return {"quality_plan_present": False}
    material_requirements = _as_dict(quality_plan.get("material_separation_requirements"))
    surface_story = _as_dict(quality_plan.get("surface_story"))
    return {
        "quality_plan_present": True,
        "object_family": quality_plan.get("object_family"),
        "required_material_goal_count": len(_as_list(material_requirements.get("zones"))),
        "material_zone_count": len(graph.materials),
        "surface_story_rule_count": len(_as_list(surface_story.get("wear_logic"))),
        "wear_mask_count": len(graph.wear_masks),
    }


def _validate_bindings(
    graph: MaterialWearGraph, node_ids: set[str], edge_targets: set[str]
) -> tuple[list[str], list[str], int, int, int, int, int, int]:
    """Validate wear-mask bindings against node and edge target evidence.

    Returns orphan node-mask ids, orphan edge-mask ids, resolved node
    count, resolved edge count, resolved-both count, masks with at
    least one resolved binding, declared node count, and declared edge
    count.

    - ``orphan_mask_ids`` — mask ids whose ``bound_node_id`` is not
      present in the construction-graph node set.
    - ``bound_node`` / ``bound_edge`` / ``bound_both`` — counts for the
      ``graph_summary`` payload.
    - ``bound_resolved`` — masks with at least one resolved binding
      (node binding present in the graph, or edge binding resolved).
      Feeds the uniform-noise ``wear_binding_ratio``.
    """
    orphan_node_ids: list[str] = []
    orphan_edge_ids: list[str] = []
    resolved_node = 0
    resolved_edge = 0
    resolved_both = 0
    bound_resolved = 0
    declared_node = 0
    declared_edge = 0
    for mask in graph.wear_masks:
        has_node_binding = mask.bound_node_id is not None
        has_edge_binding = (
            mask.bound_edge_target is not None and bool(mask.bound_edge_target)
        )
        node_resolved = has_node_binding and mask.bound_node_id in node_ids
        edge_resolved = has_edge_binding and mask.bound_edge_target in edge_targets
        if has_node_binding:
            declared_node += 1
            if node_resolved:
                resolved_node += 1
            else:
                orphan_node_ids.append(mask.mask_id)
        if has_edge_binding:
            declared_edge += 1
            if edge_resolved:
                resolved_edge += 1
            else:
                orphan_edge_ids.append(mask.mask_id)
        if node_resolved and edge_resolved:
            resolved_both += 1
        if node_resolved or edge_resolved:
            bound_resolved += 1
    return (
        orphan_node_ids,
        orphan_edge_ids,
        resolved_node,
        resolved_edge,
        resolved_both,
        bound_resolved,
        declared_node,
        declared_edge,
    )


def _wear_masks_by_type(graph: MaterialWearGraph) -> dict[str, int]:
    """Return a deterministic ``{mask_type: count}`` dict.

    Iteration order follows the sorted ``WEAR_MASK_TYPES`` set so the
    JSON shape is stable across Python versions and runs. Mask types
    with zero entries are omitted to keep the summary compact.
    """
    counts: dict[str, int] = {}
    for mask in graph.wear_masks:
        counts[mask.mask_type] = counts.get(mask.mask_type, 0) + 1
    return dict(sorted(counts.items()))


def _compute_uniform_noise(
    *,
    graph: MaterialWearGraph,
    existing_surface_zone_count: int,
    bound_resolved: int,
) -> tuple[float, float, float]:
    """Return ``(uniform_noise_score, zone_diversity, wear_binding_ratio)``.

    Score formula (clamped to ``[0.0, 1.0]``):

    ```
    zone_diversity      = min(1.0, max(graph.materials.count, existing_surface_zone_count) / 3.0)
    wear_binding_ratio  = bound_resolved / max(1, wear_mask_count)
    uniform_noise_score = clamp(1.0 - (0.4 * zone_diversity + 0.6 * wear_binding_ratio), 0.0, 1.0)
    ```

    A clean fixture (3+ zones, all wear masks resolved) lands at score
    ``<= 0.05``. A graph with no zones and no bindings lands at score
    ``1.0`` and fires the warning.
    """
    material_count = len(graph.materials)
    diversity_input = float(max(material_count, existing_surface_zone_count))
    zone_diversity = min(1.0, diversity_input / _ZONE_DIVERSITY_FULL_CREDIT)
    wear_mask_count = len(graph.wear_masks)
    if wear_mask_count == 0:
        wear_binding_ratio = 0.0
    else:
        wear_binding_ratio = bound_resolved / float(wear_mask_count)
    score = 1.0 - (
        _ZONE_DIVERSITY_WEIGHT * zone_diversity
        + _WEAR_BINDING_WEIGHT * wear_binding_ratio
    )
    score = max(0.0, min(1.0, score))
    return round(score, 6), round(zone_diversity, 6), round(wear_binding_ratio, 6)


def _uniform_noise_warnings(
    score: float, graph: MaterialWearGraph
) -> list[str]:
    """Return the warning strings for the uniform-noise payload.

    Specific-first; generic fallback last. Empty graph fires a
    structured "no graph" warning so reviewers see the cause; otherwise
    a generic uniform-noise warning carries the score.
    """
    if score < _UNIFORM_NOISE_WARNING_THRESHOLD:
        return []
    if not graph.materials and not graph.wear_masks:
        return [
            "material/wear graph is empty: no authored zones or wear masks; "
            "consider opting into a per-family graph (Phase 13 syntax)."
        ]
    return [
        f"material/wear graph reads as uniform noise "
        f"(uniform_noise_score={score:.3f}); "
        f"consider strengthening zone diversity or wear-mask bindings."
    ]


def _asset_surface(asset: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(asset.get("surface"))


def _material_graph_reference(surface: dict[str, Any]) -> str:
    value = surface.get("material_graph")
    return value if isinstance(value, str) else ""


def _material_graph_values(surface: dict[str, Any]) -> dict[str, Any]:
    resolved = _as_dict(surface.get("resolved_material_graph"))
    return _as_dict(resolved.get("values"))


def _material_zone_from_raw(raw: dict[str, Any], fallback_type: str) -> MaterialZone:
    zone_id = raw.get("zone_id", raw.get("id", raw.get("name")))
    return MaterialZone(
        zone_id=zone_id,
        zone_type=raw.get("zone_type", fallback_type),
        base_color=raw.get("base_color"),
        roughness=raw.get("roughness"),
        metalness=raw.get("metalness"),
        bound_part=raw.get("bound_part"),
        parameters=_as_dict(raw.get("parameters")),
    )


def _wear_mask_from_raw(raw: dict[str, Any]) -> WearMask:
    mask_id = raw.get("mask_id", raw.get("id", raw.get("name")))
    return WearMask(
        mask_id=mask_id,
        mask_type=raw.get("mask_type"),
        intensity=raw.get("intensity"),
        bound_node_id=raw.get("bound_node_id"),
        bound_edge_target=raw.get("bound_edge_target"),
        parameters=_as_dict(raw.get("parameters")),
    )


def _graph_from_material_graph_values(
    *, family: str, reference: str, values: dict[str, Any]
) -> MaterialWearGraph | None:
    del reference
    raw_graph = _as_dict(values.get("material_wear_graph")) or values
    raw_materials = _as_list(raw_graph.get("materials"))
    raw_underlayers = _as_list(raw_graph.get("underlayers"))
    raw_wear_masks = _as_list(raw_graph.get("wear_masks"))
    if not (raw_materials or raw_underlayers or raw_wear_masks):
        return None
    materials = tuple(
        _material_zone_from_raw(item, "base_material")
        for item in raw_materials
        if isinstance(item, dict)
    )
    underlayers = tuple(
        _material_zone_from_raw(item, "underlayer")
        for item in raw_underlayers
        if isinstance(item, dict)
    )
    wear_masks = tuple(
        _wear_mask_from_raw(item) for item in raw_wear_masks if isinstance(item, dict)
    )
    return MaterialWearGraph(
        family=family,
        version=str(raw_graph.get("version") or MATERIAL_WEAR_VERSION),
        materials=materials,
        underlayers=underlayers,
        wear_masks=wear_masks,
    )


def _select_graph(
    asset: dict[str, Any], runtime: dict[str, Any], family: str
) -> tuple[MaterialWearGraph, str, str, list[dict[str, str]]]:
    """Return graph plus source metadata and any material-graph skip evidence."""
    del runtime
    surface = _asset_surface(asset)
    reference = _material_graph_reference(surface)
    values = _material_graph_values(surface)
    skipped: list[dict[str, str]] = []
    if reference or values:
        try:
            authored_graph = _graph_from_material_graph_values(
                family=family, reference=reference, values=values
            )
        except (TypeError, ValueError) as exc:
            skipped.append(
                {
                    "tool": "surface.material_graph",
                    "reason": "resolved_material_graph_invalid",
                    "evidence": str(exc),
                }
            )
        else:
            if authored_graph is not None:
                return authored_graph, "surface.material_graph", reference, skipped
            skipped.append(
                {
                    "tool": "surface.material_graph",
                    "reason": "resolved_material_graph_not_lowerable_to_material_wear_graph_v1",
                    "evidence": reference or "resolved_material_graph",
                }
            )
    return _select_default_graph(family), "family_default", reference, skipped


def _material_wear_runtime_skips(
    graph: MaterialWearGraph, surface_bundle: dict[str, Any]
) -> list[dict[str, str]]:
    """Return skipped reasons for Phase 8 work the surface stage did not run."""
    if not graph.wear_masks:
        return []
    hooks = _as_dict(surface_bundle.get("material_wear_graph_hooks"))
    skipped: list[dict[str, str]] = []
    if hooks.get("mask_textures_generated") is not True:
        skipped.append(
            {
                "tool": "surface_runtime",
                "reason": "mask_texture_generation_not_implemented",
            }
        )
    if hooks.get("surface_maps_driven_by_material_wear_graph") is not True:
        skipped.append(
            {
                "tool": "surface_runtime",
                "reason": "surface_map_driving_not_implemented",
            }
        )
    return skipped


def evaluate_material_wear_graph(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive material/wear graph payload for the validate stage.

    Args:
        asset: normalized asset dict. Carried for signature parity with
            other validators; the evaluator currently reads only the
            runtime bundles.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["design_brief"]["brief"]["family"]`` (Phase 2),
            ``runtime["construction_graph"]["nodes"]`` (Phase 4),
            ``runtime["grammar_lowering"]["synthesized_graph_nodes"]``
            (Phase 6), ``runtime["highlow_relation"]["bake_maps"]``
            (Phase 7), and ``runtime["surface"]["bundle"]["material_zones"]``
            (existing surface stage).

    Returns:
        Additive payload with ``version`` (``"material_wear_v1"``),
        ``family``, ``graph`` (full :class:`MaterialWearGraph` dict),
        ``graph_summary`` (zone counts + wear-mask counts +
        binding-resolution counts), ``binding_validation``
        (``all_node_bindings_resolved``, ``orphan_node_bindings``,
        ``construction_graph_node_count``), ``uniform_noise``
        (``is_uniform_noise``, ``uniform_noise_score``,
        ``zone_diversity``, ``wear_binding_ratio``, ``warnings``),
        and ``skipped_reasons``. No top-level ``diagnostics`` key —
        Phase 8 is informational only and never blocks certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    family = _resolve_family(safe_runtime)
    graph, graph_source, material_graph_reference, material_graph_skips = _select_graph(
        safe_asset, safe_runtime, family
    )
    node_ids = _resolve_construction_node_ids(safe_runtime)
    edge_targets = _resolve_edge_targets(safe_runtime)
    surface_bundle = _resolve_surface_bundle(safe_runtime)
    existing_surface_zone_count = _resolve_existing_surface_zone_count(safe_runtime)
    bake_map_count_present = _resolve_bake_map_count_present(safe_runtime)

    (
        orphan_mask_ids,
        orphan_edge_mask_ids,
        bound_node_count,
        bound_edge_count,
        bound_both_count,
        bound_resolved_count,
        declared_node_count,
        declared_edge_count,
    ) = _validate_bindings(graph, node_ids, edge_targets)

    skipped_reasons: list[dict[str, str]] = list(material_graph_skips)
    skipped_reasons.extend(_material_wear_runtime_skips(graph, surface_bundle))
    if bake_map_count_present < _BAKE_MAP_FULL_COUNT:
        skipped_reasons.append(
            {"tool": "bake_runtime", "reason": "incomplete_bake_maps"}
        )

    uniform_noise_score, zone_diversity, wear_binding_ratio = _compute_uniform_noise(
        graph=graph,
        existing_surface_zone_count=existing_surface_zone_count,
        bound_resolved=bound_resolved_count,
    )
    is_uniform_noise = uniform_noise_score >= _UNIFORM_NOISE_WARNING_THRESHOLD
    warnings_list = _uniform_noise_warnings(uniform_noise_score, graph)

    wear_mask_count = len(graph.wear_masks)
    payload = {
        "version": MATERIAL_WEAR_VERSION,
        "family": family,
        "graph": graph.to_dict(),
        "graph_summary": {
            "graph_source": graph_source,
            "material_graph_reference": material_graph_reference,
            "material_zone_count": len(graph.materials),
            "underlayer_count": len(graph.underlayers),
            "wear_mask_count": wear_mask_count,
            "wear_masks_by_type": _wear_masks_by_type(graph),
            "bound_to_construction_nodes": bound_node_count,
            "bound_to_edge_targets": bound_edge_count,
            "bound_to_both": bound_both_count,
            "declared_node_bindings": declared_node_count,
            "declared_edge_bindings": declared_edge_count,
            "resolved_bindings": bound_resolved_count,
        },
        "binding_validation": {
            "all_node_bindings_resolved": len(orphan_mask_ids) == 0,
            "all_edge_bindings_resolved": len(orphan_edge_mask_ids) == 0,
            "orphan_node_bindings": orphan_mask_ids,
            "orphan_edge_bindings": orphan_edge_mask_ids,
            "construction_graph_node_count": len(node_ids),
            "edge_target_count": len(edge_targets),
        },
        "uniform_noise": {
            "is_uniform_noise": is_uniform_noise,
            "uniform_noise_score": uniform_noise_score,
            "zone_diversity": zone_diversity,
            "wear_binding_ratio": wear_binding_ratio,
            "warnings": warnings_list,
        },
        "skipped_reasons": skipped_reasons,
    }
    quality_plan_alignment = _quality_plan_alignment(safe_runtime, graph)
    if quality_plan_alignment["quality_plan_present"]:
        payload["quality_plan_alignment"] = quality_plan_alignment
    return payload


# Anchors the contract that every default-graph wear-mask type is in
# WEAR_MASK_TYPES and every default-graph zone type is in ZONE_TYPES.
# Imported defaults are validated once at module import time so a typo
# in the hand-authored industrial_crate factory cannot ship.
def _verify_default_graph_contracts() -> None:
    for family_factory in _FAMILY_DEFAULT_GRAPHS.values():
        graph = family_factory()
        for mask in graph.wear_masks:
            if mask.mask_type not in WEAR_MASK_TYPES:
                raise AssertionError(
                    f"material_wear_graph default uses unknown mask_type "
                    f"{mask.mask_type!r}; expected one of {sorted(WEAR_MASK_TYPES)}"
                )
        for zone in graph.materials + graph.underlayers:
            if zone.zone_type not in ZONE_TYPES:
                raise AssertionError(
                    f"material_wear_graph default uses unknown zone_type "
                    f"{zone.zone_type!r}; expected one of {sorted(ZONE_TYPES)}"
                )


_verify_default_graph_contracts()
