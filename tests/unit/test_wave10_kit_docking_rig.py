"""Wave 10 tests: KitGraph + docking + rig contract."""

from __future__ import annotations

import json
from pathlib import Path

from lathe.rig.rig_contract import rig_from_construction_edges
from lathe.runtime.asset_contract import InterfacePort
from lathe.scene.docking import (
    attempt_dock,
    best_docking,
    dimensions_compatible,
    kinds_compatible,
    load_compatible,
    texel_density_score,
)
from lathe.scene.kit_graph import KitGraph, kit_graph_from_dict


def test_kit_graph_loads_industrial_loading_bay() -> None:
    path = Path("std/kits/industrial_loading_bay_v1.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    kit = kit_graph_from_dict(payload)
    assert kit.kit_id == "industrial_loading_bay_v1"
    assert kit.visual_language_id == "utility_industrial_v1"
    assert kit.archetype_count() == 2
    crate_arch = kit.archetypes[0]
    assert crate_arch.role == "crate"
    assert crate_arch.repetition_limit == 3


def test_kinds_compatibility_table() -> None:
    assert kinds_compatible("support_footprint", "stack_receive")
    assert kinds_compatible("hinge_attach", "hinge_target")
    assert not kinds_compatible("support_footprint", "hinge_target")
    assert not kinds_compatible("invented_kind", "stack_receive")


def test_dimensions_compatible_within_tolerance() -> None:
    source = InterfacePort(interface_id="a", kind="support_footprint", bounds_cm=(100.0, 80.0, 5.0))
    target = InterfacePort(interface_id="b", kind="stack_receive", bounds_cm=(102.0, 79.0, 6.0))
    assert dimensions_compatible(source, target, tolerance_cm=5.0)
    target_huge = InterfacePort(interface_id="c", kind="stack_receive", bounds_cm=(200.0, 80.0, 5.0))
    assert not dimensions_compatible(source, target_huge, tolerance_cm=5.0)


def test_load_compatible() -> None:
    source = InterfacePort(interface_id="a", kind="support_footprint", load_capacity_kg=20.0)
    light_target = InterfacePort(interface_id="b", kind="stack_receive", load_capacity_kg=10.0)
    heavy_target = InterfacePort(interface_id="c", kind="stack_receive", load_capacity_kg=100.0)
    assert load_compatible(source, heavy_target)
    assert not load_compatible(source, light_target)


def test_attempt_dock_valid_path() -> None:
    source = InterfacePort(
        interface_id="crate.bottom",
        kind="support_footprint",
        bounds_cm=(100.0, 80.0, 5.0),
        load_capacity_kg=20.0,
        texel_density=512.0,
    )
    target = InterfacePort(
        interface_id="pallet.top",
        kind="stack_receive",
        bounds_cm=(102.0, 80.0, 6.0),
        load_capacity_kg=200.0,
        texel_density=512.0,
    )
    result = attempt_dock(source, target)
    assert result.valid
    assert result.style_compatibility_score == 1.0


def test_best_docking_picks_highest_score() -> None:
    source = InterfacePort(
        interface_id="crate.bottom", kind="support_footprint",
        bounds_cm=(100.0, 80.0, 5.0), load_capacity_kg=20.0, texel_density=512.0,
    )
    a = InterfacePort(interface_id="a", kind="stack_receive",
                     bounds_cm=(100.0, 80.0, 5.0), load_capacity_kg=100.0, texel_density=512.0)
    b = InterfacePort(interface_id="b", kind="stack_receive",
                     bounds_cm=(101.0, 80.0, 5.0), load_capacity_kg=100.0, texel_density=1024.0)
    best = best_docking(source, [a, b])
    assert best is not None
    # ``a`` has texel match, ``b`` has 2x mismatch — a should win.
    assert best.target_port_id == "a"


def test_rig_from_construction_edges_emits_hinge() -> None:
    edges = [
        {
            "source_id": "door_leaf",
            "target_id": "door_frame",
            "edge_type": "attached_to",
            "metadata": {
                "joint": "hinge",
                "axis": "Z",
                "limits_deg": [-5, 105],
                "default_angle_deg": 0,
                "motorized": False,
            },
        }
    ]
    rig = rig_from_construction_edges(
        asset_name="door_42",
        edges=edges,
        body_node_ids=["door_frame", "door_leaf"],
    )
    assert rig.rig_type == "rigid_constraint"
    assert len(rig.bodies) == 2
    assert len(rig.joints) == 1
    joint = rig.joints[0]
    assert joint.type == "hinge"
    assert joint.axis_world == (0.0, 0.0, 1.0)
    assert joint.limits_deg == (-5.0, 105.0)


def test_rig_skips_non_joint_edges() -> None:
    edges = [
        {
            "source_id": "bracket_01",
            "target_id": "body",
            "edge_type": "attached_to",
            "metadata": {},
        }
    ]
    rig = rig_from_construction_edges(
        asset_name="crate",
        edges=edges,
        body_node_ids=["body", "bracket_01"],
    )
    assert len(rig.joints) == 0
