"""``lathe ref planes <build_dir>`` — list cardinal planes per part (REF-10).

Derives axis-aligned planes from each part's bounding box so downstream
consumers can say "top of part X" as a plane with a normal + origin.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FACE_AXES = (
    ("+X", (1.0, 0.0, 0.0), 3),
    ("-X", (-1.0, 0.0, 0.0), 0),
    ("+Y", (0.0, 1.0, 0.0), 4),
    ("-Y", (0.0, -1.0, 0.0), 1),
    ("+Z", (0.0, 0.0, 1.0), 5),
    ("-Z", (0.0, 0.0, -1.0), 2),
)


def _planes_for_part(part: dict) -> list[dict]:
    bbox = part.get("bbox")
    if not (isinstance(bbox, list) and len(bbox) == 6):
        return []
    mn = bbox[:3]
    mx = bbox[3:]
    center = [(mn[i] + mx[i]) / 2.0 for i in range(3)]
    planes: list[dict] = []
    for label, normal, extent_idx in _FACE_AXES:
        value = bbox[extent_idx]
        origin = list(center)
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[label[1]]
        origin[axis_idx] = value
        planes.append(
            {
                "label": f"{part.get('id')}.{label}",
                "face": label,
                "normal": list(normal),
                "origin": [round(v, 6) for v in origin],
            }
        )
    return planes


def run_ref_planes(args) -> None:
    """List cardinal planes for selector-manifest parts."""
    build_dir = Path(args.build_dir)
    manifest_path = build_dir / "selector_manifest.json"
    if not manifest_path.exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"selector_manifest.json not found under {build_dir}",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"invalid manifest JSON: {exc}"}), file=sys.stderr)
        raise SystemExit(2) from exc

    filter_part = getattr(args, "part", None)
    parts = manifest.get("parts") or []
    out_parts: list[dict] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if filter_part and part.get("id") != filter_part:
            continue
        planes = _planes_for_part(part)
        out_parts.append(
            {
                "id": part.get("id"),
                "bbox": part.get("bbox"),
                "planes": planes,
            }
        )
    if filter_part and not out_parts:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"part '{filter_part}' not found",
                    "available": [p.get("id") for p in parts if isinstance(p, dict)],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(3)
    print(
        json.dumps(
            {
                "ok": True,
                "build_dir": str(build_dir),
                "parts": out_parts,
            },
            indent=2,
        )
    )
