"""Create glTF validation evidence for a Skyborne `.lthworld`.

The exporter emits a proxy glTF scene: one simple cube mesh instanced at
each Forge world placement. This is honest engine-handoff evidence for
world graph transforms and package inventory, not final mesh import
evidence for every member asset.
"""

from __future__ import annotations

import argparse
import base64
import json
import struct
import subprocess
from pathlib import Path
from typing import Any

from lathe.asset_foundry.runtime.signed_package import sign_lthworld_directory


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


def write_proxy_gltf(world_dir: Path, out_path: Path) -> dict[str, Any]:
    graph = _load(world_dir / "world_graph.json")
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
            "proxy_notice": "Proxy glTF validates world graph transforms only; it is not final per-asset mesh import evidence.",
        },
    }
    _write_json(out_path, gltf)
    return {"node_count": len(nodes), "mesh_count": 1, "path": str(out_path)}


def validate_gltf(
    gltf_path: Path,
    *,
    validator_workdir: Path,
) -> dict[str, Any]:
    script = (
        "const fs=require('fs');"
        "const v=require('gltf-validator');"
        "const text=fs.readFileSync(process.argv[1],'utf8');"
        "v.validateString(text,{uri:process.argv[1]}).then(r=>{"
        "console.log(JSON.stringify(r));"
        "}).catch(e=>{console.error(e && e.stack ? e.stack : String(e)); process.exit(2);});"
    )
    proc = subprocess.run(
        ["node", "-e", script, str(gltf_path.resolve())],
        cwd=validator_workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "validator_failed",
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


def write_validation_evidence(world_dir: Path, validator_workdir: Path) -> dict[str, Any]:
    evidence_dir = world_dir / "engine_import_evidence"
    gltf_path = evidence_dir / "skyborne_proxy_scene.gltf"
    export_summary = write_proxy_gltf(world_dir, gltf_path)
    validation = validate_gltf(gltf_path, validator_workdir=validator_workdir)
    evidence = {
        "version": "lathe.skyborne.gltf_validation_evidence_v1",
        "status": validation["status"],
        "claim_level": "proxy",
        "world_id": _load(world_dir / "world_manifest.json")["world_id"],
        "gltf_path": "engine_import_evidence/skyborne_proxy_scene.gltf",
        "export_summary": export_summary,
        "validator": validation,
        "rule_of_truth": (
            "This validates a proxy glTF scene generated from the Forge world graph. "
            "It does not prove final per-member mesh import."
        ),
    }
    evidence_path = evidence_dir / "gltf_validation_evidence.json"
    _write_json(evidence_path, evidence)

    manifest_path = world_dir / "world_manifest.json"
    manifest = _load(manifest_path)
    manifest["sidecar_files"]["engine_import_evidence"] = "engine_import_evidence/gltf_validation_evidence.json"
    manifest["artifact_statuses"]["engine_import_evidence"] = {
        "status": evidence["status"],
        "path": "engine_import_evidence/gltf_validation_evidence.json",
        "claim_level": "proxy",
        "reason": "proxy_gltf_validates_world_graph_transforms_only",
    }
    _write_json(manifest_path, manifest)

    repro = _load(world_dir / "repro_evidence.json")
    envelope = sign_lthworld_directory(
        world_dir,
        world_id=manifest["world_id"],
        repro_evidence=repro,
    )
    _write_json(world_dir / "signature.json", envelope.__dict__)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("world_dir")
    parser.add_argument(
        "--validator-workdir",
        default=".tmp_tools/gltf_validator_probe",
        help="Directory whose node_modules contains the gltf-validator package.",
    )
    args = parser.parse_args()
    evidence = write_validation_evidence(Path(args.world_dir), Path(args.validator_workdir))
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
