"""Tests for lathe.shape.placement_binding_v1 (Wave 5)."""

from __future__ import annotations

from lathe.shape.placement import (
    Anchor,
    Frame,
    RELATION_SPECS,
    RelationResolver,
)


def _anchor(
    anchor_id: str,
    origin: tuple[float, float, float],
    z_axis: tuple[float, float, float],
    affordances: tuple[str, ...],
    host: str = "host",
) -> Anchor:
    return Anchor(
        anchor_id=anchor_id,
        role="test",
        frame=Frame(origin_cm=origin, z_axis=z_axis),
        bounds_cm=(10.0, 10.0, 10.0),
        affordances=affordances,
        capacity=1,
        host_node_id=host,
    )


def test_resolver_picks_opposed_normal_for_attached_to() -> None:
    """attached_to should pair source (down-facing) with target (up-facing)."""
    resolver = RelationResolver()
    source = _anchor("src.mount", (0, 0, 0), (0, 0, -1.0), ("attaches",), host="bracket")
    target = _anchor("tgt.face", (5, 0, 10), (0, 0, 1.0), ("receives_attachment",), host="body")
    binding = resolver.resolve(
        edge_id="e1",
        relation="attached_to",
        source_node_id="bracket",
        target_node_id="body",
        source_anchors=[source],
        target_anchors=[target],
    )
    assert binding.is_resolved()
    assert binding.chosen is not None
    assert binding.chosen.source_anchor_id == "src.mount"
    assert binding.chosen.target_anchor_id == "tgt.face"
    # Transform is target origin + clearance along target normal
    spec = RELATION_SPECS["attached_to"]
    assert binding.chosen.transform_world_cm[2] == 10 + spec.clearance_cm


def test_resolver_rejects_missing_affordance() -> None:
    """Without the right affordance, no candidate is valid."""
    resolver = RelationResolver()
    source = _anchor("src.mount", (0, 0, 0), (0, 0, -1.0), ("wraps",))
    target = _anchor("tgt.face", (0, 0, 10), (0, 0, 1.0), ("receives_attachment",))
    binding = resolver.resolve(
        edge_id="e1",
        relation="attached_to",
        source_node_id="src",
        target_node_id="tgt",
        source_anchors=[source],
        target_anchors=[target],
    )
    assert not binding.is_resolved()
    assert "missing affordance" in binding.candidates[0].rejection_reason


def test_resolver_rejects_misaligned_normals() -> None:
    """opposed normal policy rejects parallel normals."""
    resolver = RelationResolver()
    source = _anchor("src.mount", (0, 0, 0), (0, 0, 1.0), ("attaches",))  # same direction as target
    target = _anchor("tgt.face", (0, 0, 10), (0, 0, 1.0), ("receives_attachment",))
    binding = resolver.resolve(
        edge_id="e1",
        relation="attached_to",
        source_node_id="src",
        target_node_id="tgt",
        source_anchors=[source],
        target_anchors=[target],
    )
    assert not binding.is_resolved()


def test_unknown_relation_returns_unresolved_binding() -> None:
    resolver = RelationResolver()
    binding = resolver.resolve(
        edge_id="e1",
        relation="invented_relation",
        source_node_id="a",
        target_node_id="b",
        source_anchors=[],
        target_anchors=[],
    )
    assert not binding.is_resolved()
    assert "no_relation_spec" in binding.proof


def test_resolver_picks_first_valid_deterministically() -> None:
    """When multiple valid candidates exist, tie-break is deterministic."""
    resolver = RelationResolver()
    source = _anchor("src.mount", (0, 0, 0), (0, 0, -1.0), ("attaches",))
    targets = [
        _anchor(f"tgt.{i}", (i, 0, 10), (0, 0, 1.0), ("receives_attachment",))
        for i in range(3)
    ]
    b1 = resolver.resolve("e1", "attached_to", "s", "t", [source], targets)
    b2 = resolver.resolve("e1", "attached_to", "s", "t", [source], targets)
    assert b1.is_resolved() and b2.is_resolved()
    assert b1.chosen.target_anchor_id == b2.chosen.target_anchor_id
