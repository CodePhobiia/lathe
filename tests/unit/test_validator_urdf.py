"""Unit tests for STAGE-11 URDF validator."""

from __future__ import annotations

from lathe.validators.urdf_validation import (
    L6401,
    L6402,
    L6403,
    L6404,
    L6405,
    L6406,
    evaluate_urdf_validation,
)


def _make_asset(robotics: bool = True, unit: str = "m") -> dict:
    asset: dict = {
        "name": "test",
        "intent": {"role": "robot arm", "robotics": robotics},
        "space": {"unit": unit},
    }
    return asset


def _make_runtime(*, sockets=None, pivots=None, physics_parts=None) -> dict:
    return {
        "interfaces": {"bundle": {"sockets": sockets or [], "pivots": pivots or []}},
        "physics": {"bundle": {"parts": physics_parts or []}},
    }


# --- Gating: non-robotics asset is a no-op ---------------------------------


def test_non_robotics_asset_skips_validator():
    asset = _make_asset(robotics=False)
    asset["intent"]["robotics"] = False
    asset.pop("kind", None)
    report = evaluate_urdf_validation(asset, _make_runtime())
    assert report["diagnostics"] == []
    assert report["metrics"]["gated_off"] is True


def test_non_robotics_asset_with_missing_everything_does_not_fire():
    """Validator MUST not fire on non-robotics assets even when every field
    that would trigger a diagnostic is missing."""
    asset = {"name": "widget", "intent": {"role": "widget"}}
    runtime = _make_runtime(
        sockets=[{"id": "missing_axis", "socket_type": "hinge"}],
        physics_parts=[{"id": "body", "movable": True}],
    )
    report = evaluate_urdf_validation(asset, runtime)
    assert report["diagnostics"] == []


def test_robot_kind_gates_validator_on():
    asset = {"name": "r", "kind": "robot", "intent": {"role": "arm"}, "space": {"unit": "m"}}
    runtime = _make_runtime(
        sockets=[{"id": "j", "socket_type": "hinge"}],  # no axis, will fire L6401
    )
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6401 in codes


# --- L6401: missing axis / limits on hinge|door ---------------------------


def test_robotics_complete_hinge_passes():
    asset = _make_asset()
    runtime = _make_runtime(
        sockets=[
            {
                "id": "shoulder",
                "socket_type": "hinge",
                "axis": [0.0, 1.0, 0.0],
                "limit_lower": -1.57,
                "limit_upper": 1.57,
                "parent_part_id": "base",
                "child_part_id": "upper_arm",
            }
        ],
        physics_parts=[{"id": "upper_arm", "movable": True, "mass": 1.0, "inertia": [0.1, 0.1, 0.1]}],
    )
    report = evaluate_urdf_validation(asset, runtime)
    assert not any(d.get("severity") == "error" for d in report["diagnostics"])
    assert report["joint_count"] == 1


def test_hinge_missing_axis_emits_l6401():
    asset = _make_asset()
    runtime = _make_runtime(
        sockets=[{"id": "shoulder", "socket_type": "hinge", "limit_lower": 0, "limit_upper": 1.0}]
    )
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6401 in codes


def test_door_socket_missing_limits_emits_l6401():
    asset = _make_asset()
    runtime = _make_runtime(sockets=[{"id": "hinge0", "socket_type": "door", "axis": [0, 1, 0]}])
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6401 in codes


# --- L6402: joint graph cycle ---------------------------------------------


def test_joint_graph_cycle_emits_l6402():
    asset = _make_asset()
    runtime = _make_runtime(
        sockets=[
            {
                "id": "j1",
                "socket_type": "hinge",
                "axis": [0.0, 1.0, 0.0],
                "limit_lower": 0.0,
                "limit_upper": 1.0,
                "parent_part_id": "A",
                "child_part_id": "B",
            },
            {
                "id": "j2",
                "socket_type": "hinge",
                "axis": [0.0, 1.0, 0.0],
                "limit_lower": 0.0,
                "limit_upper": 1.0,
                "parent_part_id": "B",
                "child_part_id": "C",
            },
            {
                "id": "j3",
                "socket_type": "hinge",
                "axis": [0.0, 1.0, 0.0],
                "limit_lower": 0.0,
                "limit_upper": 1.0,
                "parent_part_id": "C",
                "child_part_id": "A",
            },
        ],
        physics_parts=[
            {"id": p, "movable": True, "mass": 1.0, "inertia": [0.1, 0.1, 0.1]} for p in ("A", "B", "C")
        ],
    )
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6402 in codes


# --- L6403: missing mass / inertia on movable part ------------------------


def test_missing_mass_emits_l6403():
    asset = _make_asset()
    runtime = _make_runtime(
        sockets=[
            {
                "id": "j",
                "socket_type": "hinge",
                "axis": [0, 1, 0],
                "limit_lower": 0,
                "limit_upper": 1,
            }
        ],
        physics_parts=[
            {"id": "arm", "movable": True, "inertia": [0.1, 0.1, 0.1]}  # no mass
        ],
    )
    report = evaluate_urdf_validation(asset, runtime)
    errs = [d for d in report["diagnostics"] if d["code"] == L6403]
    assert errs
    assert "mass" in errs[0]["details"]["missing"]


def test_missing_inertia_emits_l6403():
    asset = _make_asset()
    runtime = _make_runtime(
        physics_parts=[{"id": "arm", "movable": True, "mass": 1.0}]  # no inertia
    )
    report = evaluate_urdf_validation(asset, runtime)
    errs = [d for d in report["diagnostics"] if d["code"] == L6403]
    assert errs
    assert "inertia" in errs[0]["details"]["missing"]


def test_immovable_part_skips_physics_checks():
    asset = _make_asset()
    runtime = _make_runtime(physics_parts=[{"id": "chassis", "movable": False}])
    report = evaluate_urdf_validation(asset, runtime)
    assert not any(d["code"] == L6403 for d in report["diagnostics"])


# --- L6405: non-unit axis -------------------------------------------------


def test_non_unit_axis_emits_l6405():
    asset = _make_asset()
    runtime = _make_runtime(
        sockets=[
            {
                "id": "bad",
                "socket_type": "hinge",
                "axis": [1.0, 1.0, 0.0],  # |axis| = sqrt(2), not unit
                "limit_lower": 0.0,
                "limit_upper": 1.0,
            }
        ]
    )
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6405 in codes


# --- L6406: degenerate limit range ----------------------------------------


def test_degenerate_limit_range_emits_l6406():
    asset = _make_asset()
    runtime = _make_runtime(
        sockets=[
            {
                "id": "bad",
                "socket_type": "hinge",
                "axis": [0.0, 1.0, 0.0],
                "limit_lower": 1.0,
                "limit_upper": 1.0,
            }
        ]
    )
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6406 in codes


# --- L6404: inconsistent units --------------------------------------------


def test_mixed_mass_units_emits_l6404():
    asset = _make_asset(unit="m")
    runtime = _make_runtime(
        physics_parts=[
            {"id": "a", "movable": True, "mass": 1.0, "inertia": [0.1, 0.1, 0.1], "mass_units": "kg"},
            {"id": "b", "movable": True, "mass": 500.0, "inertia": [0.1, 0.1, 0.1], "mass_units": "g"},
        ]
    )
    report = evaluate_urdf_validation(asset, runtime)
    codes = {d["code"] for d in report["diagnostics"]}
    assert L6404 in codes
