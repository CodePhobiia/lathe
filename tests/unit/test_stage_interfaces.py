"""Unit tests for the interfaces stage (STAGE-3/4/5, V0.2 E3).

Covers typed sockets, typed pivots, AABB/transform shape, default application
with DeprecationWarning, anchor-id uniqueness enforcement in the checker, and
selector-manifest round-trip through the schema validator.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest
import trimesh

from lathe.checker.interfaces import check_interfaces, SOCKET_TYPES, PIVOT_TYPES
from lathe.core.mesh import RuntimeMesh
from lathe.core.stages.interfaces import (
    DEFAULT_PIVOT_TYPE,
    DEFAULT_SOCKET_TYPE,
    run as run_interfaces,
)
from lathe.selector_manifest import build_selector_manifest, write_selector_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "lathe.selector.schema.json"


@pytest.fixture(scope="module")
def schema_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def _make_executor(tmp_path: Path, interfaces_cfg: dict) -> SimpleNamespace:
    """Build a lightweight executor stand-in for exercising the stage."""
    # 2cm cube centred at origin.
    mesh = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    runtime_mesh = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (128, 128, 128)},
        units="cm",
    )
    stage_dir = tmp_path / "interfaces"
    stage_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        stage_dirs={"interfaces": stage_dir},
        asset={"build": {"interfaces": interfaces_cfg}},
        runtime={"topology": {"runtime_mesh": runtime_mesh}},
    )


# ---------------------------------------------------------------------------
# Stage output shape
# ---------------------------------------------------------------------------


def test_socket_with_explicit_type_is_emitted(tmp_path):
    cfg = {
        "sockets": [
            {"id": "cargo_door_hinge", "socket_type": "hinge"},
        ],
        "anchors": [],
    }
    executor = _make_executor(tmp_path, cfg)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        bundle = run_interfaces(executor, rig_bundle={})
    socket = bundle["sockets"][0]
    assert socket["id"] == "cargo_door_hinge"
    assert socket["socket_type"] == "hinge"
    assert len(socket["transform"]) == 4
    assert all(len(row) == 4 for row in socket["transform"])
    assert "aabb" in socket
    assert "min" in socket["aabb"] and "max" in socket["aabb"]


def test_socket_without_type_defaults_and_warns(tmp_path):
    cfg = {"sockets": ["battery_slot"], "anchors": []}
    executor = _make_executor(tmp_path, cfg)
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        bundle = run_interfaces(executor, rig_bundle={})
    socket = bundle["sockets"][0]
    assert socket["socket_type"] == DEFAULT_SOCKET_TYPE
    dep_warnings = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
    assert any("battery_slot" in str(w.message) for w in dep_warnings)


def test_pivot_with_type_contact_round_trips(tmp_path, schema_validator):
    cfg = {
        "sockets": [],
        "pivots": [{"id": "ground_contact", "pivot_type": "contact"}],
        "anchors": [],
    }
    executor = _make_executor(tmp_path, cfg)
    bundle = run_interfaces(executor, rig_bundle={})
    pivot = next(p for p in bundle["pivots"] if p["id"] == "ground_contact")
    assert pivot["pivot_type"] == "contact"

    # Feed through selector manifest → schema.
    manifest = build_selector_manifest(
        asset_name="a",
        variant_name=None,
        source_path="examples/a.lth",
        build_hash="0123abcd" * 4,
        runtime={"interfaces": {"bundle": bundle}},
        build_dir=tmp_path / "a",
    )
    schema_validator.validate(manifest)
    pm = next(p for p in manifest["pivots"] if p["id"] == "ground_contact")
    assert pm["pivotType"] == "contact"


def test_default_world_pivot_when_no_pivots_declared(tmp_path):
    cfg = {"sockets": [], "anchors": []}
    executor = _make_executor(tmp_path, cfg)
    bundle = run_interfaces(executor, rig_bundle={})
    assert len(bundle["pivots"]) == 1
    world_pivot = bundle["pivots"][0]
    assert world_pivot["id"] == "world"
    assert world_pivot["pivot_type"] == "world"
    # Identity transform.
    identity = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    assert world_pivot["transform"] == identity


def test_transform_is_4x4_row_major(tmp_path):
    cfg = {
        "sockets": [{"id": "port_usb", "socket_type": "port"}],
        "anchors": [],
    }
    executor = _make_executor(tmp_path, cfg)
    bundle = run_interfaces(executor, rig_bundle={})
    t = bundle["sockets"][0]["transform"]
    assert len(t) == 4
    for row in t:
        assert isinstance(row, list)
        assert len(row) == 4
        for v in row:
            assert isinstance(v, float)
    # Translation column encodes socket position (row-major).
    pos = bundle["sockets"][0]["position"]
    assert pytest.approx(t[0][3], abs=1e-6) == pos[0]
    assert pytest.approx(t[1][3], abs=1e-6) == pos[1]
    assert pytest.approx(t[2][3], abs=1e-6) == pos[2]


def test_socket_aabb_matches_position(tmp_path):
    cfg = {
        "sockets": [{"id": "hand_grip", "socket_type": "hand"}],
        "anchors": [],
    }
    executor = _make_executor(tmp_path, cfg)
    bundle = run_interfaces(executor, rig_bundle={})
    sock = bundle["sockets"][0]
    pos = sock["position"]
    aabb = sock["aabb"]
    # AABB centre must equal the socket position within 1e-6.
    cx = 0.5 * (aabb["min"][0] + aabb["max"][0])
    cy = 0.5 * (aabb["min"][1] + aabb["max"][1])
    cz = 0.5 * (aabb["min"][2] + aabb["max"][2])
    assert abs(cx - pos[0]) < 1e-6
    assert abs(cy - pos[1]) < 1e-6
    assert abs(cz - pos[2]) < 1e-6
    # AABB has positive extent in every axis.
    for a, b in zip(aabb["min"], aabb["max"]):
        assert b >= a


# ---------------------------------------------------------------------------
# Checker — unknown types + uniqueness
# ---------------------------------------------------------------------------


class _CheckerStub:
    def __init__(self) -> None:
        self.diagnostics: list[dict] = []


def test_checker_flags_unknown_socket_type():
    asset = {
        "name": "demo",
        "build": {
            "interfaces": {
                "sockets": [{"id": "gizmo", "socket_type": "no_such_type"}],
                "pivots": [],
                "anchors": [],
            }
        },
    }
    checker = _CheckerStub()
    check_interfaces(checker, asset)
    codes = [d["code"] for d in checker.diagnostics]
    assert "L4701" in codes
    msg = next(d["message"] for d in checker.diagnostics if d["code"] == "L4701")
    assert "no_such_type" in msg
    assert "attach" in msg  # lists valid types


def test_checker_flags_duplicate_anchor_id_across_socket_and_pivot():
    asset = {
        "name": "demo",
        "build": {
            "interfaces": {
                "sockets": [{"id": "shared", "socket_type": "attach"}],
                "pivots": [{"id": "shared", "pivot_type": "center"}],
                "anchors": [],
            }
        },
    }
    checker = _CheckerStub()
    check_interfaces(checker, asset)
    codes = [d["code"] for d in checker.diagnostics]
    assert "L4703" in codes
    dup_msg = next(d["message"] for d in checker.diagnostics if d["code"] == "L4703")
    assert "shared" in dup_msg
    assert "socket" in dup_msg and "pivot" in dup_msg


def test_checker_accepts_all_catalogued_types():
    asset = {
        "name": "demo",
        "build": {
            "interfaces": {
                "sockets": [
                    {"id": f"s_{t}", "socket_type": t} for t in SOCKET_TYPES
                ],
                "pivots": [
                    {"id": f"p_{t}", "pivot_type": t} for t in PIVOT_TYPES
                ],
                "anchors": [],
            }
        },
    }
    checker = _CheckerStub()
    check_interfaces(checker, asset)
    # No diagnostics for a catalogued-only asset.
    assert checker.diagnostics == []


# ---------------------------------------------------------------------------
# Selector manifest round-trip
# ---------------------------------------------------------------------------


def test_selector_manifest_includes_typed_sockets_and_pivots(
    tmp_path, schema_validator
):
    cfg = {
        "sockets": [
            {"id": "battery_slot", "socket_type": "slot"},
            {"id": "rail_top", "socket_type": "rail"},
        ],
        "pivots": [
            {"id": "mass_center", "pivot_type": "center"},
            {"id": "floor_contact", "pivot_type": "bottom"},
        ],
        "anchors": [],
    }
    executor = _make_executor(tmp_path, cfg)
    bundle = run_interfaces(executor, rig_bundle={})

    manifest = build_selector_manifest(
        asset_name="courier_demo",
        variant_name=None,
        source_path="examples/courier_demo.lth",
        build_hash="feedface" * 4,
        runtime={"interfaces": {"bundle": bundle}},
        build_dir=tmp_path / "courier_demo",
    )
    schema_validator.validate(manifest)
    socket_by_id = {s["id"]: s for s in manifest["sockets"]}
    assert socket_by_id["battery_slot"]["socketType"] == "slot"
    assert socket_by_id["rail_top"]["socketType"] == "rail"
    assert "transform" in socket_by_id["battery_slot"]
    assert "aabb" in socket_by_id["battery_slot"]
    pivot_by_id = {p["id"]: p for p in manifest["pivots"]}
    assert pivot_by_id["mass_center"]["pivotType"] == "center"
    assert pivot_by_id["floor_contact"]["pivotType"] == "bottom"
    assert "transform" in pivot_by_id["floor_contact"]

    # Full write round-trip.
    build_dir = tmp_path / "courier_demo"
    build_dir.mkdir(exist_ok=True)
    path = write_selector_manifest(manifest, build_dir)
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    schema_validator.validate(reloaded)
    assert reloaded["sockets"][0]["socketType"] in {"slot", "rail"}


def test_end_to_end_courier_drone_has_typed_manifest():
    """courier_drone must certify with at least one socket carrying a type."""
    import subprocess
    import sys

    build_out = REPO_ROOT / "tmp_stages3_e2e" / "courier_drone"
    if build_out.exists():
        import shutil

        shutil.rmtree(build_out.parent)

    cmd = [
        sys.executable,
        "-m",
        "lathe.cli",
        "build",
        "examples/courier_drone.lth",
        "courier_drone",
        "--out",
        "tmp_stages3_e2e",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"courier_drone build failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    manifest_path = build_out / "selector_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Sockets must have socketType populated (courier_drone declares two legacy
    # string-form sockets; after STAGE-3 they default to "attach").
    assert manifest["sockets"], "courier_drone must declare sockets"
    for sock in manifest["sockets"]:
        assert "socketType" in sock
        assert sock["socketType"] in set(SOCKET_TYPES)
        assert "transform" in sock
        assert "aabb" in sock
    # Pivots must be populated via legacy-anchor migration (floor_contact) plus
    # any explicit pivots; each carries a pivotType.
    assert manifest["pivots"], "courier_drone should now emit at least one pivot"
    for piv in manifest["pivots"]:
        assert "pivotType" in piv
        assert piv["pivotType"] in set(PIVOT_TYPES)
