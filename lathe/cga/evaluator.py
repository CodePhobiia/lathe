"""Evaluator for CGA grammar trees.

Walks productions starting from the grammar root and an initial bounding
shape, expanding non-terminals into RHS forms until every leaf is a
:class:`Terminal`. Splits / repeats track the current shape's local frame so
each child receives its correctly sized sub-shape.

The evaluator is fully deterministic: ``chooseOne`` uses a seeded
``random.Random``, so the same grammar + seed + initial shape always yields
the same :class:`AssemblyTree`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

from .productions import (
    ChooseOne,
    Extrude,
    Grammar,
    NonTerminal,
    Production,
    Repeat,
    Rotate,
    Scale,
    Split,
    SplitItem,
    Terminal,
    Translate,
)


@dataclass
class InitialShape:
    """Initial axis-aligned bounding shape passed to :func:`evaluate_rule_tree`.

    All sizes in metres. ``position`` is the world-space origin of the shape's
    -x/-y/-z corner. ``rotation`` is degrees about ``axis`` (z if unspecified).
    """

    width: float = 1.0
    depth: float = 1.0
    height: float = 1.0
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[str, float] = ("z", 0.0)
    extruded: bool = False

    def with_axis_size(self, axis: str, size: float, offset: float) -> "InitialShape":
        x, y, z = self.position
        if axis == "x":
            return InitialShape(
                width=size,
                depth=self.depth,
                height=self.height,
                position=(x + offset, y, z),
                rotation=self.rotation,
                extruded=self.extruded,
            )
        if axis == "y":
            return InitialShape(
                width=self.width,
                depth=size,
                height=self.height,
                position=(x, y + offset, z),
                rotation=self.rotation,
                extruded=self.extruded,
            )
        return InitialShape(
            width=self.width,
            depth=self.depth,
            height=size,
            position=(x, y, z + offset),
            rotation=self.rotation,
            extruded=self.extruded,
        )

    def axis_extent(self, axis: str) -> float:
        return {"x": self.width, "y": self.depth, "z": self.height}[axis]


@dataclass
class ProductionNode:
    """One node in the evaluated assembly tree."""

    kind: str  # "rule" | "split" | "repeat" | "choose" | "extrude" | "transform" | "terminal"
    label: str
    shape: InitialShape
    children: list["ProductionNode"] = field(default_factory=list)
    terminal: Terminal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationDiagnostic:
    """A diagnostic emitted during evaluation."""

    code: str
    message: str
    severity: str = "warning"


@dataclass
class EvaluationReport:
    """Errors and warnings produced while evaluating a grammar."""

    diagnostics: list[EvaluationDiagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)


@dataclass
class AssemblyTree:
    """Root of an evaluated assembly tree."""

    root: ProductionNode
    report: EvaluationReport = field(default_factory=EvaluationReport)


def evaluate_rule_tree(
    grammar: Grammar,
    initial_shape: InitialShape | None = None,
    *,
    seed: int | None = None,
) -> AssemblyTree:
    """Expand ``grammar`` against an initial shape into an :class:`AssemblyTree`.

    Every non-terminal is expanded according to its production rule(s). When
    multiple productions share an LHS they are treated as deterministic,
    seed-driven alternatives. The recursion budget is taken from
    ``grammar.recursion_budget``.
    """
    initial = initial_shape or InitialShape()
    rng = random.Random(seed if seed is not None else grammar.seed)
    report = EvaluationReport()
    root_node = _expand_nonterminal(
        grammar=grammar,
        name=grammar.root,
        shape=initial,
        depth=0,
        rng=rng,
        report=report,
    )
    return AssemblyTree(root=root_node, report=report)


# ---------------------------------------------------------------------------
# Internal expansion
# ---------------------------------------------------------------------------


def _expand_nonterminal(
    *,
    grammar: Grammar,
    name: str,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    if depth >= grammar.recursion_budget:
        report.diagnostics.append(
            EvaluationDiagnostic(
                code="cga.recursion_budget_exceeded",
                message=f"recursion budget {grammar.recursion_budget} exceeded at {name}",
                severity="error",
            )
        )
        return ProductionNode(kind="rule", label=name, shape=shape, metadata={"truncated": True})

    productions = grammar.productions.get(name)
    if not productions:
        report.diagnostics.append(
            EvaluationDiagnostic(
                code="cga.unresolved_nonterminal",
                message=f"no production for non-terminal {name!r}; treated as terminal",
                severity="warning",
            )
        )
        return ProductionNode(
            kind="terminal",
            label=name,
            shape=shape,
            terminal=Terminal(name=name, kind="primitive"),
        )

    production, production_index = _select_production(productions, rng)
    node = ProductionNode(
        kind="rule",
        label=name,
        shape=shape,
        metadata={
            "selected_production_index": production_index,
            "production_alternative_count": len(productions),
            "selected_production_source": production.source,
        },
    )
    for rhs in production.rhs:
        node.children.append(
            _expand_rhs(
                grammar=grammar,
                rhs=rhs,
                shape=shape,
                depth=depth + 1,
                rng=rng,
                report=report,
            )
        )
    return node


def _select_production(
    productions: list[Production], rng: random.Random
) -> tuple[Production, int]:
    if len(productions) == 1:
        return productions[0], 0
    index = _select_weighted_index([1.0] * len(productions), rng)
    return productions[index], index


def _select_weighted_index(weights: list[float], rng: random.Random) -> int:
    total = sum(max(0.0, weight) for weight in weights)
    if total <= 0.0:
        return 0
    pick = rng.random() * total
    accum = 0.0
    for index, weight in enumerate(weights):
        accum += max(0.0, weight)
        if pick <= accum:
            return index
    return max(0, len(weights) - 1)


def _expand_rhs(
    *,
    grammar: Grammar,
    rhs: Any,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    if isinstance(rhs, NonTerminal):
        return _expand_nonterminal(
            grammar=grammar, name=rhs.name, shape=shape, depth=depth, rng=rng, report=report
        )
    if isinstance(rhs, Terminal):
        return ProductionNode(kind="terminal", label=rhs.name, shape=shape, terminal=rhs)
    if isinstance(rhs, Split):
        return _expand_split(grammar=grammar, split=rhs, shape=shape, depth=depth, rng=rng, report=report)
    if isinstance(rhs, Repeat):
        return _expand_repeat(grammar=grammar, repeat=rhs, shape=shape, depth=depth, rng=rng, report=report)
    if isinstance(rhs, ChooseOne):
        return _expand_choose(grammar=grammar, choose=rhs, shape=shape, depth=depth, rng=rng, report=report)
    if isinstance(rhs, Extrude):
        return _expand_extrude(grammar=grammar, extrude=rhs, shape=shape, depth=depth, rng=rng, report=report)
    if isinstance(rhs, Translate):
        return _expand_translate(grammar=grammar, op=rhs, shape=shape, depth=depth, rng=rng, report=report)
    if isinstance(rhs, Rotate):
        return _expand_rotate(grammar=grammar, op=rhs, shape=shape, depth=depth, rng=rng, report=report)
    if isinstance(rhs, Scale):
        return _expand_scale(grammar=grammar, op=rhs, shape=shape, depth=depth, rng=rng, report=report)
    report.diagnostics.append(
        EvaluationDiagnostic(
            code="cga.unknown_rhs",
            message=f"unrecognised RHS form {type(rhs).__name__}",
            severity="error",
        )
    )
    return ProductionNode(kind="terminal", label="<unknown>", shape=shape)


def _expand_split(
    *,
    grammar: Grammar,
    split: Split,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    extent = shape.axis_extent(split.axis)
    fixed = sum(item.size for item in split.items if item.unit == "m")
    ratio_total = sum(item.size for item in split.items if item.unit == "ratio")
    leftover = max(0.0, extent - fixed)
    if fixed > extent + 1e-6:
        report.diagnostics.append(
            EvaluationDiagnostic(
                code="cga.split_overflow",
                message=(
                    f"split({split.axis}) fixed sizes {fixed}m exceed shape extent "
                    f"{extent}m; clamping"
                ),
                severity="warning",
            )
        )
    node = ProductionNode(kind="split", label=f"split:{split.axis}", shape=shape)
    cursor = 0.0
    for item in split.items:
        if item.unit == "m":
            size = min(item.size, max(0.0, extent - cursor))
        else:  # ratio
            size = leftover * (item.size / ratio_total) if ratio_total > 0 else 0.0
        sub_shape = shape.with_axis_size(split.axis, size, cursor)
        sub_node = _expand_rhs(
            grammar=grammar,
            rhs=item.rhs,
            shape=sub_shape,
            depth=depth + 1,
            rng=rng,
            report=report,
        )
        sub_node.metadata.setdefault("split_axis", split.axis)
        sub_node.metadata.setdefault("split_offset", cursor)
        sub_node.metadata.setdefault("split_size", size)
        node.children.append(sub_node)
        cursor += size
    return node


def _expand_repeat(
    *,
    grammar: Grammar,
    repeat: Repeat,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    if repeat.count <= 0:
        report.diagnostics.append(
            EvaluationDiagnostic(
                code="cga.repeat_zero",
                message=f"repeat count must be > 0 (got {repeat.count})",
                severity="warning",
            )
        )
        return ProductionNode(kind="repeat", label=f"repeat:{repeat.count}", shape=shape)
    extent = shape.axis_extent(repeat.axis)
    slice_size = extent / repeat.count
    node = ProductionNode(
        kind="repeat",
        label=f"repeat:{repeat.count}",
        shape=shape,
        metadata={"axis": repeat.axis, "mirror": repeat.mirror, "rotate_deg": repeat.rotate_deg},
    )
    for i in range(repeat.count):
        sub_shape = shape.with_axis_size(repeat.axis, slice_size, slice_size * i)
        sub_node = _expand_rhs(
            grammar=grammar,
            rhs=repeat.rhs,
            shape=sub_shape,
            depth=depth + 1,
            rng=rng,
            report=report,
        )
        sub_node.metadata.setdefault("repeat_index", i)
        if repeat.mirror and i % 2 == 1:
            sub_node.metadata.setdefault("mirrored", True)
        if repeat.rotate_deg:
            sub_node.metadata.setdefault("rotate_deg", repeat.rotate_deg * i)
        node.children.append(sub_node)
    return node


def _expand_choose(
    *,
    grammar: Grammar,
    choose: ChooseOne,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    total = sum(max(0.0, weight) for weight, _ in choose.options)
    if total <= 0:
        report.diagnostics.append(
            EvaluationDiagnostic(
                code="cga.choose_zero_weight",
                message="chooseOne has zero total weight",
                severity="error",
            )
        )
        return ProductionNode(kind="choose", label="chooseOne", shape=shape)
    selected_index = _select_weighted_index([weight for weight, _ in choose.options], rng)
    chosen_rhs: Any = choose.options[selected_index][1]
    node = ProductionNode(kind="choose", label="chooseOne", shape=shape)
    node.metadata["weights"] = [w for w, _ in choose.options]
    node.metadata["selected_option_index"] = selected_index
    node.children.append(
        _expand_rhs(
            grammar=grammar,
            rhs=chosen_rhs,
            shape=shape,
            depth=depth + 1,
            rng=rng,
            report=report,
        )
    )
    return node


def _expand_extrude(
    *,
    grammar: Grammar,
    extrude: Extrude,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    new_shape = InitialShape(
        width=shape.width,
        depth=shape.depth,
        height=extrude.height if extrude.axis == "z" else shape.height,
        position=shape.position,
        rotation=shape.rotation,
        extruded=True,
    )
    if extrude.axis == "x":
        new_shape = InitialShape(
            width=extrude.height,
            depth=shape.depth,
            height=shape.height,
            position=shape.position,
            rotation=shape.rotation,
            extruded=True,
        )
    elif extrude.axis == "y":
        new_shape = InitialShape(
            width=shape.width,
            depth=extrude.height,
            height=shape.height,
            position=shape.position,
            rotation=shape.rotation,
            extruded=True,
        )
    node = ProductionNode(
        kind="extrude",
        label=f"extrude:{extrude.axis}:{extrude.height:.3f}",
        shape=new_shape,
        metadata={"axis": extrude.axis, "height": extrude.height},
    )
    if extrude.rhs is not None:
        node.children.append(
            _expand_rhs(
                grammar=grammar,
                rhs=extrude.rhs,
                shape=new_shape,
                depth=depth + 1,
                rng=rng,
                report=report,
            )
        )
    return node


def _expand_translate(
    *,
    grammar: Grammar,
    op: Translate,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    px, py, pz = shape.position
    dx, dy, dz = op.offset
    new_shape = InitialShape(
        width=shape.width,
        depth=shape.depth,
        height=shape.height,
        position=(px + dx, py + dy, pz + dz),
        rotation=shape.rotation,
        extruded=shape.extruded,
    )
    node = ProductionNode(kind="transform", label="translate", shape=new_shape, metadata={"offset": op.offset})
    if op.rhs is not None:
        node.children.append(
            _expand_rhs(grammar=grammar, rhs=op.rhs, shape=new_shape, depth=depth + 1, rng=rng, report=report)
        )
    return node


def _expand_rotate(
    *,
    grammar: Grammar,
    op: Rotate,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    new_shape = InitialShape(
        width=shape.width,
        depth=shape.depth,
        height=shape.height,
        position=shape.position,
        rotation=(op.axis, op.degrees),
        extruded=shape.extruded,
    )
    node = ProductionNode(kind="transform", label="rotate", shape=new_shape, metadata={"axis": op.axis, "degrees": op.degrees})
    if op.rhs is not None:
        node.children.append(
            _expand_rhs(grammar=grammar, rhs=op.rhs, shape=new_shape, depth=depth + 1, rng=rng, report=report)
        )
    return node


def _expand_scale(
    *,
    grammar: Grammar,
    op: Scale,
    shape: InitialShape,
    depth: int,
    rng: random.Random,
    report: EvaluationReport,
) -> ProductionNode:
    fx, fy, fz = op.factors
    new_shape = InitialShape(
        width=shape.width * fx,
        depth=shape.depth * fy,
        height=shape.height * fz,
        position=shape.position,
        rotation=shape.rotation,
        extruded=shape.extruded,
    )
    node = ProductionNode(kind="transform", label="scale", shape=new_shape, metadata={"factors": op.factors})
    if op.rhs is not None:
        node.children.append(
            _expand_rhs(grammar=grammar, rhs=op.rhs, shape=new_shape, depth=depth + 1, rng=rng, report=report)
        )
    return node
