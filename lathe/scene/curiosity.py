"""Curiosity anchor summaries and deterministic expansion helpers."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .diagnostics import scene_diagnostic
from .graph import SCENE_REF_COLLECTIONS, check_scene_graph
from .ids import scene_entity_id, snake_id

CURIOSITY_SUMMARY_VERSION = "lathe.curiosity_summary.v1"
CURIOSITY_EXPANSION_PHASE = "curiosity_expansion"

_ENTITY_COLLECTIONS: dict[str, str] = {
    **SCENE_REF_COLLECTIONS,
    "relationships": "relationship_id",
    "materials": "material_id",
}
_EXPANDABLE_TARGET_PREFIXES = ("obj_", "region_")
_STOP_TOKENS = {
    "and",
    "are",
    "because",
    "beyond",
    "for",
    "from",
    "has",
    "into",
    "only",
    "still",
    "that",
    "the",
    "this",
    "when",
    "with",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class CuriosityExpansionResult(Mapping[str, Any]):
    """Result returned by :func:`expand_anchor`."""

    scene_graph: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    memory_events: list[dict[str, Any]] = field(default_factory=list)
    added_ids: list[str] = field(default_factory=list)
    anchor_id: str | None = None
    option_id: str | None = None

    @property
    def ok(self) -> bool:
        """Return true when expansion completed without error diagnostics."""
        return not any(diagnostic.get("severity") == "error" for diagnostic in self.diagnostics)

    def __getitem__(self, key: str) -> Any:
        """Return a value from the updated Scene Graph."""
        return self.scene_graph[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over updated Scene Graph keys."""
        return iter(self.scene_graph)

    def __len__(self) -> int:
        """Return the number of top-level updated Scene Graph keys."""
        return len(self.scene_graph)


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diag(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostic = scene_diagnostic(code, name, path, message, severity=severity, details=dict(details or {}))
    diagnostic["phase"] = CURIOSITY_EXPANSION_PHASE
    return diagnostic


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _child_items(item: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = item.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, child in enumerate(raw):
        if isinstance(child, Mapping):
            yield index, child


def _string_field(item: Mapping[str, Any], field_name: str) -> str | None:
    value = item.get(field_name)
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _scene_refs(scene_graph: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for collection, field_name in SCENE_REF_COLLECTIONS.items():
        for _index, item in _items(scene_graph, collection):
            entity_id = _string_field(item, field_name)
            if entity_id is not None:
                refs.add(entity_id)
    return refs


def _find_entity(scene_graph: Mapping[str, Any], entity_id: str) -> tuple[str, int, Mapping[str, Any]] | None:
    for collection, field_name in _ENTITY_COLLECTIONS.items():
        for index, item in _items(scene_graph, collection):
            if item.get(field_name) == entity_id:
                return collection, index, item
    return None


def _find_anchor(scene_graph: Mapping[str, Any], anchor_id: str) -> tuple[int, Mapping[str, Any]] | None:
    for index, anchor in _items(scene_graph, "curiosity_anchors"):
        if anchor.get("anchor_id") == anchor_id:
            return index, anchor
    return None


def _find_option(anchor: Mapping[str, Any], option_id: str) -> tuple[int, Mapping[str, Any]] | None:
    for index, option in _child_items(anchor, "expansion_options"):
        if option.get("id") == option_id:
            return index, option
    return None


def _tokens(value: object) -> set[str]:
    tokens = {token for token in _TOKEN_RE.findall(str(value).lower()) if len(token) >= 3}
    return tokens - _STOP_TOKENS


def _facts_match(anchor_fact: str, hidden_fact: str) -> bool:
    anchor_tokens = _tokens(anchor_fact)
    hidden_tokens = _tokens(hidden_fact)
    if not anchor_tokens or not hidden_tokens:
        return False
    overlap = anchor_tokens & hidden_tokens
    threshold = min(3, len(anchor_tokens))
    return len(overlap) >= threshold


def _object_reveals(scene_graph: Mapping[str, Any], object_id: str | None) -> set[str]:
    if object_id is None:
        return set()
    entity = _find_entity(scene_graph, object_id)
    if entity is None or entity[0] != "objects":
        return set()
    reveals: set[str] = set()
    for _index, affordance in _child_items(entity[2], "affordances"):
        reveal_id = _string_field(affordance, "reveals")
        if reveal_id is not None:
            reveals.add(reveal_id)
    return reveals


def _linked_hidden_states(scene_graph: Mapping[str, Any], anchor: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    attached_to = _string_field(anchor, "attached_to")
    hidden_fact = _string_field(anchor, "hidden_fact") or ""
    revealed_ids = _object_reveals(scene_graph, attached_to)
    linked: list[Mapping[str, Any]] = []
    for _index, hidden in _items(scene_graph, "hidden_state"):
        hidden_id = _string_field(hidden, "hidden_id")
        if hidden_id in revealed_ids:
            linked.append(hidden)
            continue
        if hidden.get("attached_to") != attached_to:
            continue
        hidden_state_fact = _string_field(hidden, "fact") or ""
        if _facts_match(hidden_fact, hidden_state_fact):
            linked.append(hidden)
    return sorted(linked, key=lambda item: _string_field(item, "hidden_id") or "")


def _hidden_summary(hidden: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hidden_id": _string_field(hidden, "hidden_id") or "",
        "attached_to": _string_field(hidden, "attached_to") or "",
        "fact": _string_field(hidden, "fact") or "",
        "reveal_condition": _string_field(hidden, "reveal_condition") or "",
        "visible": bool(hidden.get("visible")),
    }


def _option_summary(option: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "option_id": _string_field(option, "id") or "",
        "label": _string_field(option, "label") or "",
        "target_scope": _string_field(option, "target_scope") or "",
        "required_assets": _string_list(option.get("required_assets")),
        "continuity_constraints": _string_list(option.get("continuity_constraints")),
    }


def _card_for_anchor(scene_graph: Mapping[str, Any], anchor: Mapping[str, Any]) -> dict[str, Any]:
    expansion_options = [_option_summary(option) for _index, option in _child_items(anchor, "expansion_options")]
    continuity_constraints: list[str] = []
    seen: set[str] = set()
    for option in expansion_options:
        for constraint in option["continuity_constraints"]:
            if constraint in seen:
                continue
            seen.add(constraint)
            continuity_constraints.append(constraint)

    hidden_states = [_hidden_summary(hidden) for hidden in _linked_hidden_states(scene_graph, anchor)]
    return {
        "anchor_id": _string_field(anchor, "anchor_id") or "",
        "attached_to": _string_field(anchor, "attached_to") or "",
        "visible_clue": _string_field(anchor, "visible_clue") or "",
        "hidden_fact": _string_field(anchor, "hidden_fact") or "",
        "suggested_user_actions": _string_list(anchor.get("suggested_user_actions")),
        "expansion_options": expansion_options,
        "hidden_state": hidden_states,
        "linked_hidden_ids": [hidden["hidden_id"] for hidden in hidden_states],
        "continuity_constraints": continuity_constraints,
    }


def validate_curiosity(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return diagnostics for curiosity-to-hidden-state and expansion links."""
    diagnostics: list[dict[str, Any]] = []
    refs = _scene_refs(scene_graph)
    for anchor_index, anchor in _items(scene_graph, "curiosity_anchors"):
        anchor_id = _string_field(anchor, "anchor_id")
        attached_to = _string_field(anchor, "attached_to")
        if attached_to is not None and attached_to not in refs:
            diagnostics.append(
                _diag(
                    "C2201",
                    "invalid_curiosity_attachment",
                    _json_pointer("curiosity_anchors", anchor_index, "attached_to"),
                    f"Curiosity anchor attachment {attached_to!r} does not reference a scene entity.",
                    details={"anchor_id": anchor_id, "attached_to": attached_to},
                )
            )

        hidden_fact = _string_field(anchor, "hidden_fact")
        linked_hidden = _linked_hidden_states(scene_graph, anchor)
        if hidden_fact is not None and not linked_hidden:
            diagnostics.append(
                _diag(
                    "C2202",
                    "curiosity_hidden_state_link_missing",
                    _json_pointer("curiosity_anchors", anchor_index, "hidden_fact"),
                    "Curiosity anchor hidden_fact does not link to hidden_state by attachment, affordance, or fact overlap.",
                    severity="warning",
                    details={"anchor_id": anchor_id, "attached_to": attached_to},
                )
            )

        seen_option_ids: dict[str, int] = {}
        for option_index, option in _child_items(anchor, "expansion_options"):
            option_id = _string_field(option, "id")
            if option_id is not None:
                first_index = seen_option_ids.get(option_id)
                if first_index is not None:
                    diagnostics.append(
                        _diag(
                            "C2203",
                            "duplicate_curiosity_option_id",
                            _json_pointer("curiosity_anchors", anchor_index, "expansion_options", option_index, "id"),
                            f"Curiosity expansion option {option_id!r} duplicates option index {first_index}.",
                            details={"anchor_id": anchor_id, "option_id": option_id, "first_index": first_index},
                        )
                    )
                else:
                    seen_option_ids[option_id] = option_index

            target_scope = _string_field(option, "target_scope")
            target_path = _json_pointer("curiosity_anchors", anchor_index, "expansion_options", option_index, "target_scope")
            if target_scope is None:
                continue
            if target_scope not in refs:
                diagnostics.append(
                    _diag(
                        "C2204",
                        "invalid_curiosity_expansion_target",
                        target_path,
                        f"Curiosity expansion target_scope {target_scope!r} does not reference a scene entity.",
                        details={"anchor_id": anchor_id, "option_id": option_id, "target_scope": target_scope},
                    )
                )
                continue
            if not target_scope.startswith(_EXPANDABLE_TARGET_PREFIXES):
                diagnostics.append(
                    _diag(
                        "C2205",
                        "unsupported_curiosity_expansion_target",
                        target_path,
                        "Curiosity expansion helpers can add shells only from object or region target scopes.",
                        details={
                            "anchor_id": anchor_id,
                            "option_id": option_id,
                            "target_scope": target_scope,
                            "supported_prefixes": list(_EXPANDABLE_TARGET_PREFIXES),
                        },
                    )
                )
    return diagnostics


def summarize_curiosity(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic curiosity cards plus link diagnostics."""
    anchors = sorted(
        (anchor for _index, anchor in _items(scene_graph, "curiosity_anchors")),
        key=lambda item: _string_field(item, "anchor_id") or "",
    )
    return {
        "schema_version": CURIOSITY_SUMMARY_VERSION,
        "scene_id": scene_graph.get("scene_id"),
        "scene_version": scene_graph.get("version"),
        "cards": [_card_for_anchor(scene_graph, anchor) for anchor in anchors],
        "diagnostics": validate_curiosity(scene_graph),
    }


def _has_error(diagnostics: Sequence[Mapping[str, Any]]) -> bool:
    return any(diagnostic.get("severity") == "error" for diagnostic in diagnostics)


def _title_from_id(value: str) -> str:
    return snake_id(value).replace("_", " ").title()


def _bounds_center(item: Mapping[str, Any]) -> list[float]:
    bounds = item.get("bounds")
    center = bounds.get("center") if isinstance(bounds, Mapping) else None
    if isinstance(center, list) and len(center) == 3 and all(isinstance(value, int | float) for value in center):
        return [float(value) for value in center]
    return [0.0, 0.0, 1.0]


def _bounds_size(item: Mapping[str, Any]) -> list[float]:
    bounds = item.get("bounds")
    size = bounds.get("size") if isinstance(bounds, Mapping) else None
    if isinstance(size, list) and len(size) == 3 and all(isinstance(value, int | float) for value in size):
        return [float(value) for value in size]
    return [2.0, 2.0, 2.0]


def _object_position(item: Mapping[str, Any]) -> list[float]:
    transform = item.get("transform")
    position = transform.get("position") if isinstance(transform, Mapping) else None
    if isinstance(position, list) and len(position) == 3 and all(isinstance(value, int | float) for value in position):
        return [float(value) for value in position]
    return [0.0, 0.0, 1.0]


def _new_region_bounds(target_region: Mapping[str, Any]) -> dict[str, list[float]]:
    center = _bounds_center(target_region)
    size = _bounds_size(target_region)
    branch_size = [max(2.4, size[0] * 1.35), max(2.0, size[1] * 1.8), max(2.4, size[2])]
    offset_y = max(size[1], 1.2) + (branch_size[1] / 2.0)
    return {
        "center": [round(center[0], 3), round(center[1] + offset_y, 3), round(center[2], 3)],
        "size": [round(value, 3) for value in branch_size],
    }


def _region_shell(anchor: Mapping[str, Any], option: Mapping[str, Any], target_region: Mapping[str, Any]) -> dict[str, Any]:
    anchor_id = _string_field(anchor, "anchor_id") or "curiosity_unknown"
    option_id = _string_field(option, "id") or "expansion"
    label = _string_field(option, "label") or _title_from_id(option_id)
    region_id = scene_entity_id("region", f"{anchor_id}_{option_id}")
    target_mood = _string_field(target_region, "mood") or "unrevealed"
    return {
        "region_id": region_id,
        "name": _title_from_id(option_id),
        "type": "interior",
        "purpose": f"Expansion branch for {label}",
        "mood": f"{target_mood}; newly reachable",
        "bounds": _new_region_bounds(target_region),
        "semantic_tags": ["curiosity expansion", option_id, "branch"],
    }


def _role_for_asset(asset_id: str) -> str:
    tokens = set(asset_id.split("_"))
    if tokens & {"arch", "architecture", "floor", "room", "shell", "wall"}:
        return "environment_structure"
    if tokens & {"candle", "lamp", "light", "moonbeam"}:
        return "light_fixture"
    if tokens & {"chart", "clue", "constellation", "lens", "map", "sigil"}:
        return "narrative_clue"
    return "dressing_prop"


def _object_shell(
    *,
    anchor_id: str,
    option_id: str,
    asset_name: str,
    index: int,
    region_id: str,
    target_scope: str,
    base_position: Sequence[float],
) -> dict[str, Any]:
    asset_id = snake_id(asset_name, fallback="asset")
    offset = ((index % 3) - 1) * 0.65
    row = index // 3
    position = [
        round(float(base_position[0]) + offset, 3),
        round(float(base_position[1]) + 0.45 + (row * 0.55), 3),
        round(max(0.1, float(base_position[2]) + 0.15), 3),
    ]
    return {
        "object_id": scene_entity_id("object", f"{anchor_id}_{option_id}_{asset_id}"),
        "name": _title_from_id(asset_id),
        "role": _role_for_asset(asset_id),
        "region": region_id,
        "lathe_asset": asset_id,
        "source_family": "curiosity_expansion",
        "transform": {
            "position": position,
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1],
        },
        "semantic_tags": ["curiosity expansion", option_id, asset_id],
        "state": {
            "expansion_shell": True,
            "source_anchor": anchor_id,
            "source_option": option_id,
            "target_scope": target_scope,
        },
        "affordances": [],
        "provenance": {
            "source": "deterministic_lathe",
            "commercial_use": True,
        },
    }


def _opens_to_relationship(anchor_id: str, option_id: str, target_scope: str, region_id: str) -> dict[str, Any]:
    return {
        "relationship_id": scene_entity_id("relationship", f"{anchor_id}_{option_id}_opens_to"),
        "from": target_scope,
        "to": region_id,
        "type": "opens_to",
        "description": f"Curiosity option {option_id} opens a branch region from {target_scope}.",
    }


def _same_item(existing: Mapping[str, Any], generated: Mapping[str, Any]) -> bool:
    return dict(existing) == dict(generated)


def _existing_item(scene_graph: Mapping[str, Any], collection: str, field_name: str, entity_id: str) -> Mapping[str, Any] | None:
    for _index, item in _items(scene_graph, collection):
        if item.get(field_name) == entity_id:
            return item
    return None


def _add_unique_item(
    working: dict[str, Any],
    collection: str,
    field_name: str,
    item: Mapping[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    entity_id = _string_field(item, field_name)
    if entity_id is None:
        return False, [
            _diag(
                "C2208",
                "curiosity_generated_entity_missing_id",
                f"/{collection}",
                f"Generated curiosity entity in {collection!r} is missing {field_name}.",
            )
        ]
    existing = _existing_item(working, collection, field_name, entity_id)
    if existing is not None:
        if _same_item(existing, item):
            return False, []
        return False, [
            _diag(
                "C2209",
                "curiosity_generated_id_conflict",
                f"/{collection}",
                f"Generated curiosity entity ID {entity_id!r} conflicts with an existing {collection} item.",
                details={"entity_id": entity_id, "collection": collection},
            )
        ]
    raw_collection = working.get(collection)
    if not isinstance(raw_collection, list):
        return False, [
            _diag(
                "C2210",
                "invalid_scene_graph_collection",
                f"/{collection}",
                f"Scene Graph collection {collection!r} must be an array before curiosity expansion.",
                details={"collection": collection},
            )
        ]
    raw_collection.append(copy.deepcopy(dict(item)))
    return True, []


def _object_transforms(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    transforms: dict[str, Any] = {}
    for _index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        transform = item.get("transform")
        if object_id is not None and isinstance(transform, Mapping):
            transforms[object_id] = copy.deepcopy(dict(transform))
    return transforms


def _stable_object_diagnostics(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    after_transforms = _object_transforms(after)
    for object_id, before_transform in _object_transforms(before).items():
        after_transform = after_transforms.get(object_id)
        if after_transform is None:
            diagnostics.append(
                _diag(
                    "C2211",
                    "curiosity_continuity_violation",
                    "/objects",
                    f"Curiosity expansion removed existing object {object_id!r}.",
                    details={"object_id": object_id},
                )
            )
        elif after_transform != before_transform:
            diagnostics.append(
                _diag(
                    "C2211",
                    "curiosity_continuity_violation",
                    "/objects",
                    f"Curiosity expansion altered transform for existing object {object_id!r}.",
                    details={"object_id": object_id},
                )
            )
    return diagnostics


def _memory_event(
    scene_graph: Mapping[str, Any],
    anchor: Mapping[str, Any],
    option: Mapping[str, Any],
    *,
    affected_ids: Sequence[str],
) -> dict[str, Any]:
    anchor_id = _string_field(anchor, "anchor_id") or "curiosity_unknown"
    option_id = _string_field(option, "id") or "expansion"
    label = _string_field(option, "label") or _title_from_id(option_id)
    scene_refs = _scene_refs(scene_graph)
    filtered_affected = [entity_id for entity_id in affected_ids if entity_id in scene_refs]
    return {
        "event_id": scene_entity_id("memory", f"{anchor_id}_{option_id}_expanded"),
        "type": "decision",
        "text": f"Expanded curiosity anchor {anchor_id} with option {option_id}: {label}",
        "affected_ids": _unique(filtered_affected),
        "source": f"curiosity_expansion:{anchor_id}:{option_id}",
    }


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _append_memory_event(working: dict[str, Any], event: Mapping[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    events = working.get("memory_events")
    if not isinstance(events, list):
        return False, [
            _diag(
                "C2212",
                "invalid_memory_events_container",
                "/memory_events",
                "Scene Graph memory_events must be an array before curiosity expansion records continuity.",
            )
        ]
    event_id = _string_field(event, "event_id")
    for index, existing in enumerate(events):
        if not isinstance(existing, Mapping) or existing.get("event_id") != event_id:
            continue
        if _same_item(existing, event):
            return False, []
        return False, [
            _diag(
                "C2213",
                "curiosity_memory_event_conflict",
                _json_pointer("memory_events", index, "event_id"),
                f"Scene Graph already contains a different memory event {event_id!r}.",
                details={"event_id": event_id},
            )
        ]
    events.append(copy.deepcopy(dict(event)))
    return True, []


def _selected_option_diagnostics(
    scene_graph: Mapping[str, Any],
    *,
    anchor_index: int,
    anchor: Mapping[str, Any],
    option_index: int,
    option: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    refs = _scene_refs(scene_graph)
    target_scope = _string_field(option, "target_scope")
    target_path = _json_pointer("curiosity_anchors", anchor_index, "expansion_options", option_index, "target_scope")
    if target_scope is None or target_scope not in refs:
        diagnostics.append(
            _diag(
                "C2204",
                "invalid_curiosity_expansion_target",
                target_path,
                f"Curiosity expansion target_scope {target_scope!r} does not reference a scene entity.",
                details={
                    "anchor_id": _string_field(anchor, "anchor_id"),
                    "option_id": _string_field(option, "id"),
                    "target_scope": target_scope,
                },
            )
        )
    elif not target_scope.startswith(_EXPANDABLE_TARGET_PREFIXES):
        diagnostics.append(
            _diag(
                "C2205",
                "unsupported_curiosity_expansion_target",
                target_path,
                "Curiosity expansion helpers can add shells only from object or region target scopes.",
                details={
                    "anchor_id": _string_field(anchor, "anchor_id"),
                    "option_id": _string_field(option, "id"),
                    "target_scope": target_scope,
                },
            )
        )
    if not _linked_hidden_states(scene_graph, anchor):
        diagnostics.append(
            _diag(
                "C2202",
                "curiosity_hidden_state_link_missing",
                _json_pointer("curiosity_anchors", anchor_index, "hidden_fact"),
                "Curiosity anchor hidden_fact does not link to hidden_state by attachment, affordance, or fact overlap.",
                severity="warning",
                details={"anchor_id": _string_field(anchor, "anchor_id")},
            )
        )
    return diagnostics


def _expansion_targets(
    scene_graph: Mapping[str, Any],
    anchor: Mapping[str, Any],
    option: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    anchor_id = _string_field(anchor, "anchor_id") or "curiosity_unknown"
    option_id = _string_field(option, "id") or "expansion"
    target_scope = _string_field(option, "target_scope") or ""
    target = _find_entity(scene_graph, target_scope)
    if target is None:
        return [], [], [], [], [
            _diag(
                "C2204",
                "invalid_curiosity_expansion_target",
                "/curiosity_anchors",
                f"Curiosity expansion target_scope {target_scope!r} does not reference a scene entity.",
                details={"anchor_id": anchor_id, "option_id": option_id, "target_scope": target_scope},
            )
        ]

    regions: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    affected_ids: list[str] = [anchor_id, target_scope]

    if target_scope.startswith("region_"):
        region = target[2]
        branch_region = _region_shell(anchor, option, region)
        regions.append(branch_region)
        branch_region_id = branch_region["region_id"]
        relationships.append(_opens_to_relationship(anchor_id, option_id, target_scope, branch_region_id))
        object_region = branch_region_id
        base_position = _bounds_center(branch_region)
        affected_ids.append(branch_region_id)
    else:
        target_object = target[2]
        object_region = _string_field(target_object, "region") or ""
        base_position = _object_position(target_object)

    for hidden in _linked_hidden_states(scene_graph, anchor):
        hidden_id = _string_field(hidden, "hidden_id")
        if hidden_id is not None:
            affected_ids.append(hidden_id)

    for asset_index, asset_name in enumerate(_string_list(option.get("required_assets"))):
        object_shell = _object_shell(
            anchor_id=anchor_id,
            option_id=option_id,
            asset_name=asset_name,
            index=asset_index,
            region_id=object_region,
            target_scope=target_scope,
            base_position=base_position,
        )
        objects.append(object_shell)
        affected_ids.append(object_shell["object_id"])

    return regions, objects, relationships, affected_ids, []


def expand_anchor(scene_graph: Mapping[str, Any], anchor_id: str, option_id: str) -> CuriosityExpansionResult:
    """Return a versioned Scene Graph copy expanded from a curiosity option."""
    original = copy.deepcopy(dict(scene_graph))
    anchor_record = _find_anchor(scene_graph, anchor_id)
    if anchor_record is None:
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=[
                _diag(
                    "C2206",
                    "curiosity_anchor_not_found",
                    "/curiosity_anchors",
                    f"Curiosity anchor {anchor_id!r} was not found.",
                    details={"anchor_id": anchor_id, "option_id": option_id},
                )
            ],
            anchor_id=anchor_id,
            option_id=option_id,
        )

    anchor_index, anchor = anchor_record
    option_record = _find_option(anchor, option_id)
    if option_record is None:
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=[
                _diag(
                    "C2207",
                    "curiosity_option_not_found",
                    _json_pointer("curiosity_anchors", anchor_index, "expansion_options"),
                    f"Curiosity anchor {anchor_id!r} has no expansion option {option_id!r}.",
                    details={"anchor_id": anchor_id, "option_id": option_id},
                )
            ],
            anchor_id=anchor_id,
            option_id=option_id,
        )

    option_index, option = option_record
    diagnostics = _selected_option_diagnostics(
        scene_graph,
        anchor_index=anchor_index,
        anchor=anchor,
        option_index=option_index,
        option=option,
    )
    if _has_error(diagnostics):
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=diagnostics,
            anchor_id=anchor_id,
            option_id=option_id,
        )

    regions, objects, relationships, affected_ids, target_diagnostics = _expansion_targets(scene_graph, anchor, option)
    diagnostics.extend(target_diagnostics)
    if _has_error(diagnostics):
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=diagnostics,
            anchor_id=anchor_id,
            option_id=option_id,
        )

    working = copy.deepcopy(dict(scene_graph))
    added_ids: list[str] = []
    for collection, field_name, items in (
        ("regions", "region_id", regions),
        ("objects", "object_id", objects),
        ("relationships", "relationship_id", relationships),
    ):
        for item in items:
            added, add_diagnostics = _add_unique_item(working, collection, field_name, item)
            diagnostics.extend(add_diagnostics)
            entity_id = _string_field(item, field_name)
            if entity_id is not None and (added or _existing_item(working, collection, field_name, entity_id) is not None):
                added_ids.append(entity_id)

    if _has_error(diagnostics):
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=diagnostics,
            added_ids=_unique(added_ids),
            anchor_id=anchor_id,
            option_id=option_id,
        )

    event = _memory_event(working, anchor, option, affected_ids=affected_ids)
    appended, append_diagnostics = _append_memory_event(working, event)
    diagnostics.extend(append_diagnostics)
    if _has_error(diagnostics):
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=diagnostics,
            added_ids=_unique(added_ids),
            anchor_id=anchor_id,
            option_id=option_id,
        )

    if added_ids or appended:
        version = working.get("version")
        working["version"] = version + 1 if isinstance(version, int) and version >= 1 else 1

    diagnostics.extend(_stable_object_diagnostics(scene_graph, working))
    diagnostics.extend(check_scene_graph(working))
    if _has_error(diagnostics):
        return CuriosityExpansionResult(
            scene_graph=original,
            diagnostics=diagnostics,
            added_ids=_unique(added_ids),
            anchor_id=anchor_id,
            option_id=option_id,
        )

    return CuriosityExpansionResult(
        scene_graph=working,
        diagnostics=diagnostics,
        memory_events=[dict(event)] if appended else [],
        added_ids=_unique(added_ids),
        anchor_id=anchor_id,
        option_id=option_id,
    )


__all__ = [
    "CURIOSITY_EXPANSION_PHASE",
    "CURIOSITY_SUMMARY_VERSION",
    "CuriosityExpansionResult",
    "expand_anchor",
    "summarize_curiosity",
    "validate_curiosity",
]
