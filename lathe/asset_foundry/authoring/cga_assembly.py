"""CGA-style assembly rules.

Per northstar §10 Lane I priority task #5. CGA (Computer Generated
Architecture) grammars from CityEngine drive procedural building
generation by splitting shapes and rewriting them rule-by-rule.

This module declares a tiny CGA-style grammar:

  - ``Shape``: a typed scope with a bounding box + label.
  - ``SplitOp``: splits along an axis with size pattern (absolute /
    relative / repeat).
  - ``AssemblyRule``: ``label -> [SplitOp | ReplaceOp | Component]``.
  - ``apply_assembly_rules``: deterministically rewrites shapes until
    fixpoint.

The grammar is intentionally narrow at v0.1 — split + replace + tag.
Full CGA-Shape DSL (offset, comp, roof, occlusions) is deferred.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

CGA_ASSEMBLY_VERSION = "lathe.asset_foundry.cga_assembly_v1"


@dataclass(frozen=True)
class Shape:
    """A scoped shape in the CGA grammar."""

    shape_id: str
    label: str
    """Current rule-label (e.g. ``Building``, ``Floor``, ``Wall``)."""

    bbox_cm: tuple[tuple[float, float, float], tuple[float, float, float]]
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SplitOp:
    """Split a shape along one axis."""

    axis: str
    """``x`` | ``y`` | ``z``."""
    pattern: tuple[tuple[str, float], ...]
    """Sequence of ``(size_kind, value)`` where size_kind is:
      - ``abs``: absolute cm
      - ``rel``: fraction of parent extent (0..1)
      - ``repeat``: variable-count repetition of fixed-cm tiles
    """
    output_labels: tuple[str, ...]
    """Labels for each output shape. Length must match pattern."""


@dataclass(frozen=True)
class AssemblyRule:
    """One rule: trigger label -> output operations."""

    rule_id: str
    trigger_label: str
    ops: tuple[Any, ...]
    """Sequence of SplitOp or 'replace_label:NEW' or 'tag_component:NAME'."""

    condition: str = ""
    """Optional field-expression that must evaluate truthy for the
    rule to fire (uses lathe.asset_foundry.authoring.field_attrs)."""


@dataclass(frozen=True)
class AssemblyRuleSet:
    """Named collection of assembly rules."""

    rule_set_id: str
    rules: tuple[AssemblyRule, ...]
    max_iterations: int = 32
    """Max rewriting passes to avoid infinite recursion."""


def _axis_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}[axis.lower()]


def _apply_split(shape: Shape, op: SplitOp) -> tuple[Shape, ...]:
    """Apply a split op to a shape, returning sub-shapes."""
    if len(op.pattern) != len(op.output_labels):
        raise ValueError("SplitOp pattern length must equal output_labels length")
    axis_idx = _axis_index(op.axis)
    (mn0, mn1, mn2), (mx0, mx1, mx2) = shape.bbox_cm
    mins = [mn0, mn1, mn2]
    maxs = [mx0, mx1, mx2]
    extent = maxs[axis_idx] - mins[axis_idx]

    # Resolve sizes.
    abs_total = 0.0
    rel_total = 0.0
    repeat_indices: list[int] = []
    sizes_resolved: list[float] = [0.0] * len(op.pattern)
    for i, (size_kind, value) in enumerate(op.pattern):
        if size_kind == "abs":
            sizes_resolved[i] = float(value)
            abs_total += float(value)
        elif size_kind == "rel":
            rel_total += float(value)
        elif size_kind == "repeat":
            repeat_indices.append(i)
        else:
            raise ValueError(f"unknown size_kind: {size_kind!r}")
    leftover = max(0.0, extent - abs_total)
    if rel_total > 0:
        for i, (size_kind, value) in enumerate(op.pattern):
            if size_kind == "rel":
                sizes_resolved[i] = leftover * (float(value) / max(rel_total, 1e-9))
    if repeat_indices:
        repeat_leftover = max(0.0, extent - sum(sizes_resolved))
        # Each repeat slot takes its 'value' size as the tile width;
        # generate floor(leftover / tile_width) tiles.
        new_pattern: list[tuple[str, float]] = []
        new_labels: list[str] = []
        sizes_new: list[float] = []
        for i, (size_kind, value) in enumerate(op.pattern):
            if size_kind == "repeat":
                tile_width = float(value)
                if tile_width <= 0:
                    continue
                tiles = int(repeat_leftover // tile_width)
                for k in range(tiles):
                    new_pattern.append(("abs", tile_width))
                    new_labels.append(f"{op.output_labels[i]}_{k:02d}")
                    sizes_new.append(tile_width)
                repeat_leftover -= tiles * tile_width
            else:
                new_pattern.append((size_kind, value))
                new_labels.append(op.output_labels[i])
                sizes_new.append(sizes_resolved[i])
        sizes_resolved = sizes_new
        op_labels = tuple(new_labels)
    else:
        op_labels = op.output_labels

    out: list[Shape] = []
    cursor = mins[axis_idx]
    for i, (size, label) in enumerate(zip(sizes_resolved, op_labels)):
        new_mins = list(mins)
        new_maxs = list(maxs)
        new_mins[axis_idx] = cursor
        new_maxs[axis_idx] = cursor + size
        out.append(
            Shape(
                shape_id=f"{shape.shape_id}.{label}_{i:02d}",
                label=label,
                bbox_cm=(
                    (new_mins[0], new_mins[1], new_mins[2]),
                    (new_maxs[0], new_maxs[1], new_maxs[2]),
                ),
                attributes=shape.attributes,
            )
        )
        cursor += size
    return tuple(out)


def apply_assembly_rules(
    rule_set: AssemblyRuleSet,
    seed_shape: Shape,
) -> tuple[Shape, ...]:
    """Apply a rule set to a seed shape; return the leaf shapes."""
    rule_by_label: dict[str, AssemblyRule] = {}
    for rule in rule_set.rules:
        rule_by_label.setdefault(rule.trigger_label, rule)

    work: list[Shape] = [seed_shape]
    iterations = 0
    while iterations < rule_set.max_iterations:
        iterations += 1
        changed = False
        next_work: list[Shape] = []
        for shape in work:
            rule = rule_by_label.get(shape.label)
            if rule is None:
                next_work.append(shape)
                continue
            new_shapes: list[Shape] = [shape]
            for op in rule.ops:
                if isinstance(op, SplitOp):
                    expanded: list[Shape] = []
                    for s in new_shapes:
                        expanded.extend(_apply_split(s, op))
                    new_shapes = expanded
                elif isinstance(op, str) and op.startswith("replace_label:"):
                    new_label = op.split(":", 1)[1]
                    new_shapes = [
                        Shape(
                            shape_id=s.shape_id,
                            label=new_label,
                            bbox_cm=s.bbox_cm,
                            attributes=s.attributes,
                        )
                        for s in new_shapes
                    ]
                elif isinstance(op, str) and op.startswith("tag_component:"):
                    tag = op.split(":", 1)[1]
                    new_shapes = [
                        Shape(
                            shape_id=s.shape_id,
                            label=s.label,
                            bbox_cm=s.bbox_cm,
                            attributes={**s.attributes, "component_tag": tag},
                        )
                        for s in new_shapes
                    ]
            if new_shapes != [shape]:
                changed = True
            next_work.extend(new_shapes)
        work = next_work
        if not changed:
            break
    return tuple(work)


__all__ = [
    "CGA_ASSEMBLY_VERSION",
    "AssemblyRule",
    "AssemblyRuleSet",
    "Shape",
    "SplitOp",
    "apply_assembly_rules",
]
