from __future__ import annotations

import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.core.uv_ops import apply_box_uv


def test_box_uv_packing_report_includes_resolution() -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    runtime = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (128, 128, 128)},
        units="cm",
    )
    asset = {
        "build": {
            "uv": {
                "sets": ["base", "lightmap"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 1024,
            }
        }
    }

    _, meta = apply_box_uv(runtime, asset)

    assert meta["packing_report"]["resolution"] == 1024
    assert meta["packing_report"]["padding_normalized"] > 0
