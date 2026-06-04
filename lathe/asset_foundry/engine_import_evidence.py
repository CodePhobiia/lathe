"""Engine/import evidence helpers for `.lthworld` packages."""

from __future__ import annotations

import base64
import json
import struct
import subprocess
from pathlib import Path
from typing import Any

ENGINE_IMPORT_EVIDENCE_VERSION = "lathe.asset_foundry.engine_import_evidence_v1"
PROXY_GLTF_VALIDATION_VERSION = "lathe.skyborne.gltf_validation_evidence_v1"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cube_buffer() -> tuple[str, int]:
    indices = [
        0,
        1,
        2,
        0,
        2,
        3,
        4,
        6,
        5,
        4,
        7,
        6,
        0,
        4,
        5,
        0,
        5,
        1,
        1,
        5,
        6,
        1,
        6,
        2,
        2,
        6,
        7,
        2,
        7,
        3,
        3,
        7,
        4,
        3,
        4,
        0,
    ]
    positions = [
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ]
    raw = bytearray()
    for idx in indices:
        raw.extend(struct.pack("<H", idx))
    while len(raw) % 4:
        raw.append(0)
    for point in positions:
        raw.extend(struct.pack("<fff", *point))
    return base64.b64encode(bytes(raw)).decode("ascii"), len(raw)


def write_proxy_gltf(world_dir: str | Path, out_path: str | Path) -> dict[str, Any]:
    """Write a proxy glTF scene from Forge placements.

    This validates world graph transforms and package inventory only;
    it is not final per-member mesh evidence.
    """

    root = Path(world_dir)
    target = Path(out_path)
    graph = _load(root / "world_graph.json")
    encoded, byte_length = _cube_buffer()
    nodes = []
    for asset in graph["assets"]:
        placement = asset["placement"]
        x_cm, y_cm, z_cm = placement["position_cm"]
        scale = float(placement.get("scale") or 1.0)
        nodes.append(
            {
                "name": asset["world_asset_id"],
                "mesh": 0,
                "translation": [x_cm / 100.0, z_cm / 100.0, y_cm / 100.0],
                "scale": [scale, scale, scale],
                "extras": {
                    "role": asset["role"],
                    "asset_id": asset["asset_id"],
                    "style_pack_id": asset["style_pack_id"],
                    "source": "lathe_forge_world_graph_proxy",
                },
            }
        )
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "lathe.skyborne_gltf_validation.proxy_export_v1",
        },
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "buffers": [
            {
                "uri": f"data:application/octet-stream;base64,{encoded}",
                "byteLength": byte_length,
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 72, "target": 34963},
            {"buffer": 0, "byteOffset": 72, "byteLength": 96, "target": 34962},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5123,
                "count": 36,
                "type": "SCALAR",
                "max": [7],
                "min": [0],
            },
            {
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5126,
                "count": 8,
                "type": "VEC3",
                "max": [0.5, 0.5, 0.5],
                "min": [-0.5, -0.5, -0.5],
            },
        ],
        "materials": [
            {
                "name": "Lathe proxy material",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.55, 0.44, 0.85, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8,
                },
            }
        ],
        "meshes": [
            {
                "name": "Lathe world member proxy cube",
                "primitives": [
                    {
                        "attributes": {"POSITION": 1},
                        "indices": 0,
                        "material": 0,
                    }
                ],
            }
        ],
        "extras": {
            "world_id": graph["world_id"],
            "proxy_notice": (
                "Proxy glTF validates world graph transforms only; "
                "it is not final per-asset mesh import evidence."
            ),
        },
    }
    _write_json(target, gltf)
    return {"node_count": len(nodes), "mesh_count": 1, "path": str(target)}


def validate_gltf(
    gltf_path: str | Path,
    *,
    validator_workdir: str | Path,
) -> dict[str, Any]:
    """Run the Khronos glTF validator npm package against a glTF file."""

    path = Path(gltf_path)
    script = (
        "const fs=require('fs');"
        "const v=require('gltf-validator');"
        "const text=fs.readFileSync(process.argv[1],'utf8');"
        "v.validateString(text,{uri:process.argv[1]}).then(r=>{"
        "console.log(JSON.stringify(r));"
        "}).catch(e=>{console.error(e && e.stack ? e.stack : String(e)); process.exit(2);});"
    )
    proc = subprocess.run(
        ["node", "-e", script, str(path.resolve())],
        cwd=Path(validator_workdir),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "validator_failed",
            "tool": "KhronosGroup glTF-Validator npm package",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    report = json.loads(proc.stdout)
    report.pop("validatedAt", None)
    report["uri"] = "engine_import_evidence/skyborne_proxy_scene.gltf"
    issues = report.get("issues") or {}
    num_errors = int(issues.get("numErrors") or 0)
    return {
        "status": "validated_proxy" if num_errors == 0 else "validation_failed",
        "tool": "KhronosGroup glTF-Validator npm package",
        "returncode": proc.returncode,
        "num_errors": num_errors,
        "num_warnings": int(issues.get("numWarnings") or 0),
        "num_infos": int(issues.get("numInfos") or 0),
        "num_hints": int(issues.get("numHints") or 0),
        "report": report,
    }


__all__ = [
    "ENGINE_IMPORT_EVIDENCE_VERSION",
    "PROXY_GLTF_VALIDATION_VERSION",
    "validate_gltf",
    "write_proxy_gltf",
]
