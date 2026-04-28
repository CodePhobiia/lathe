"""Unit tests for REF-6 Phase-2 face/edge/vertex selectors.

Covers:
* grammar parse/format round-trip for face/edge/vertex tokens,
* resolution against a selector manifest that carries populated
  faces/edges/vertices arrays,
* deterministic id scheme per part,
* parent-part-not-found and sub-part-not-found error reasons,
* Phase-1 part tokens continuing to resolve through the manifest path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lathe.ref import (
    RefParseError,
    RefSelector,
    format_ref,
    parse_ref,
    resolve_ref,
)


@pytest.mark.parametrize(
    "token, kind, parent, index, sid",
    [
        ("@lathe[dist/foo#part.body.face0]", "face", "body", 0, "body.face0"),
        ("@lathe[dist/foo#part.body.face12]", "face", "body", 12, "body.face12"),
        ("@lathe[dist/foo#part.rotor_fl.edge7]", "edge", "rotor_fl", 7, "rotor_fl.edge7"),
        ("@lathe[dist/foo#part.chassis.vertex42]", "vertex", "chassis", 42, "chassis.vertex42"),
    ],
)
def test_parse_subpart_tokens(token, kind, parent, index, sid):
    node = parse_ref(token)
    assert isinstance(node.selector, RefSelector)
    assert node.selector.kind == kind
    assert node.selector.parent_part_id == parent
    assert node.selector.sub_index == index
    assert node.selector.id == sid


@pytest.mark.parametrize(
    "token",
    [
        "@lathe[dist/foo#part.body.face0]",
        "@lathe[dist/foo#part.body.edge3]",
        "@lathe[dist/foo#part.body.vertex5]",
        "@lathe[dist/foo#part.rotor_fl.face99]",
    ],
)
def test_subpart_format_roundtrip(token):
    assert format_ref(parse_ref(token)) == token


def test_parse_subpart_bad_kind_rejected():
    with pytest.raises(RefParseError) as exc:
        parse_ref("@lathe[dist/foo#part.body.weirdselector]")
    assert exc.value.code == "unknown_selector_kind"


@pytest.fixture()
def phase2_build(tmp_path: Path) -> Path:
    build_dir = tmp_path / "phase2_drone"
    build_dir.mkdir()
    (build_dir / "stages" / "shape").mkdir(parents=True)
    (build_dir / "build_report.json").write_text(
        json.dumps(
            {
                "asset": "phase2_drone",
                "kind": "mechanical_assembly",
                "certified": True,
                "stage_bundles": {"shape": {"backend_id": "x"}},
                "outputs": [],
            }
        )
    )
    manifest = {
        "schemaVersion": 1,
        "latheVersion": "0.1.0",
        "sourcePath": "examples/phase2.lth",
        "asset": "phase2_drone",
        "variant": None,
        "buildHash": "deadbeef12345678",
        "packageHash": "cafebabe12345678",
        "coordinateSystem": {"upAxis": "Y", "unit": "cm", "handedness": "right"},
        "tables": {},
        "parts": [
            {
                "id": "body",
                "ref": "@lathe[phase2_drone#part.body]",
                "bbox": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
                "faceCount": 2,
                "faces": [
                    {
                        "id": "body.face0",
                        "ref": "@lathe[phase2_drone#part.body.face0]",
                        "centroid": [0.5, 0.5, 0.0],
                        "normal": [0.0, 0.0, 1.0],
                        "area": 1.0,
                    },
                    {
                        "id": "body.face1",
                        "ref": "@lathe[phase2_drone#part.body.face1]",
                        "centroid": [0.5, 0.0, 0.5],
                        "normal": [0.0, -1.0, 0.0],
                        "area": 1.0,
                    },
                ],
                "edges": [
                    {
                        "id": "body.edge0",
                        "ref": "@lathe[phase2_drone#part.body.edge0]",
                        "endpoints": [[0, 0, 0], [1, 0, 0]],
                        "length": 1.0,
                    },
                ],
                "vertices": [
                    {
                        "id": "body.vertex0",
                        "ref": "@lathe[phase2_drone#part.body.vertex0]",
                        "position": [0.0, 0.0, 0.0],
                    },
                    {
                        "id": "body.vertex1",
                        "ref": "@lathe[phase2_drone#part.body.vertex1]",
                        "position": [1.0, 0.0, 0.0],
                    },
                ],
            },
        ],
        "sockets": [],
        "pivots": [],
        "collisions": [],
        "lods": [],
        "materials": [],
        "diagnostics": [],
        "relations": {},
    }
    (build_dir / "selector_manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def test_resolve_face_from_manifest(phase2_build: Path):
    node = parse_ref("@lathe[phase2_drone#part.body.face0]")
    result = resolve_ref(node, repo_root=phase2_build)
    assert result["ok"] is True
    assert result["facts"]["parent_part_id"] == "body"
    assert result["facts"]["sub_index"] == 0
    assert result["facts"]["centroid"] == [0.5, 0.5, 0.0]
    assert result["facts"]["normal"] == [0.0, 0.0, 1.0]


def test_resolve_edge_from_manifest(phase2_build: Path):
    node = parse_ref("@lathe[phase2_drone#part.body.edge0]")
    result = resolve_ref(node, repo_root=phase2_build)
    assert result["ok"] is True
    assert result["facts"]["endpoints"] == [[0, 0, 0], [1, 0, 0]]


def test_resolve_vertex_from_manifest(phase2_build: Path):
    node = parse_ref("@lathe[phase2_drone#part.body.vertex1]")
    result = resolve_ref(node, repo_root=phase2_build)
    assert result["ok"] is True
    assert result["facts"]["position"] == [1.0, 0.0, 0.0]


def test_resolve_face_missing_index(phase2_build: Path):
    node = parse_ref("@lathe[phase2_drone#part.body.face9999]")
    result = resolve_ref(node, repo_root=phase2_build)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "face_not_found"


def test_resolve_subpart_unknown_parent(phase2_build: Path):
    node = parse_ref("@lathe[phase2_drone#part.unknown.face0]")
    result = resolve_ref(node, repo_root=phase2_build)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "part_not_found"


def test_phase1_part_still_resolves(phase2_build: Path):
    node = parse_ref("@lathe[phase2_drone#part.body]")
    result = resolve_ref(node, repo_root=phase2_build)
    assert result["ok"] is True
    assert result["facts"]["part_id"] == "body"
    assert result["facts"]["face_count"] == 2


def test_subpart_requires_manifest(tmp_path: Path):
    build_dir = tmp_path / "no_manifest"
    build_dir.mkdir()
    (build_dir / "build_report.json").write_text(
        json.dumps(
            {
                "asset": "x",
                "kind": "mechanical_assembly",
                "certified": False,
                "stage_bundles": {"shape": {}},
                "outputs": [],
            }
        )
    )
    node = parse_ref("@lathe[no_manifest#part.body.face0]")
    result = resolve_ref(node, repo_root=tmp_path)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "selector_manifest_required"


def test_deterministic_ids_same_mesh_same_ids():
    """Running the selector-manifest sub-part extractor twice with the same
    runtime input yields identical ids and geometric facts."""
    import numpy as np
    import trimesh
    from lathe.selector_manifest import _collect_sub_parts

    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], dtype=float)
    faces = np.array([[0, 1, 2], [1, 3, 2]], dtype=int)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    class Fake:
        def __init__(self, m, fp):
            self.mesh = m
            self.face_parts = fp

    rt = Fake(mesh, ["body", "body"])
    runtime = {"topology": {"runtime_mesh": rt}}
    a = _collect_sub_parts(runtime, "body", "build")
    b = _collect_sub_parts(runtime, "body", "build")
    assert a == b
    assert [f["id"] for f in a["faces"]] == ["body.face0", "body.face1"]
    assert [v["id"] for v in a["vertices"]] == [
        "body.vertex0",
        "body.vertex1",
        "body.vertex2",
        "body.vertex3",
    ]


def test_subpart_extractor_empty_when_no_runtime_mesh():
    from lathe.selector_manifest import _collect_sub_parts

    assert _collect_sub_parts({}, "any", "build") == {"faces": [], "edges": [], "vertices": []}
