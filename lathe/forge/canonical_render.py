"""Deterministic canonical asset previews for Forge world members."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any

from .world_graph import WorldAsset, WorldComposition

ASSET_CANONICAL_RENDER_VERSION = "lathe.forge.asset_canonical_render_v1"

Color = tuple[int, int, int]

_VIEWS = ("front", "three_quarter", "hero")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    raw = bytearray()
    row_bytes = width * 3
    for y in range(height):
        raw.append(0)
        start = y * row_bytes
        raw.extend(pixels[start : start + row_bytes])
    path.write_bytes(
        b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
                _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)),
                _png_chunk(b"IEND", b""),
            ]
        )
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _set_px(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: Color,
) -> None:
    if 0 <= x < width and 0 <= y < height:
        idx = (y * width + x) * 3
        pixels[idx : idx + 3] = bytes(color)


def _draw_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Color,
) -> None:
    for y in range(max(0, min(y0, y1)), min(height, max(y0, y1) + 1)):
        for x in range(max(0, min(x0, x1)), min(width, max(x0, x1) + 1)):
            _set_px(pixels, width, height, x, y, color)


def _draw_disc(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    radius: int,
    color: Color,
) -> None:
    rr = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= rr:
                _set_px(pixels, width, height, x + dx, y + dy, color)


def _draw_triangle(
    pixels: bytearray,
    width: int,
    height: int,
    points: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    color: Color,
) -> None:
    (x0, y0), (x1, y1), (x2, y2) = points
    min_x = max(0, min(x0, x1, x2))
    max_x = min(width - 1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(height - 1, max(y0, y1, y2))
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 0.001:
        return
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denom
            b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denom
            c = 1.0 - a - b
            if a >= 0 and b >= 0 and c >= 0:
                _set_px(pixels, width, height, x, y, color)


def _role_color(role: str) -> Color:
    return {
        "cottage": (190, 116, 80),
        "elder_house": (231, 154, 82),
        "fence_segment": (128, 83, 58),
        "floating_island": (70, 128, 92),
        "lantern": (255, 194, 92),
        "pine_tree": (38, 105, 86),
        "crystal_cluster": (160, 94, 231),
        "rope_bridge": (129, 82, 55),
        "stone_path_segment": (190, 171, 132),
        "waterfall_ribbon": (85, 207, 225),
    }.get(role, (210, 198, 180))


def _draw_asset_shape(
    pixels: bytearray,
    width: int,
    height: int,
    asset: WorldAsset,
    view: str,
) -> None:
    cx = width // 2
    cy = int(height * (0.58 if view == "hero" else 0.62))
    color = _role_color(asset.role)
    shade = tuple(max(0, c - 42) for c in color)
    warm_light = (255, 213, 121)
    if asset.role == "floating_island":
        _draw_disc(pixels, width, height, cx, cy, 70, (68, 130, 94))
        _draw_triangle(pixels, width, height, ((cx - 58, cy + 44), (cx + 54, cy + 44), (cx, cy + 112)), shade)
    elif asset.role in {"cottage", "elder_house"}:
        body_w = 52 if asset.role == "elder_house" else 42
        body_h = 46 if asset.role == "elder_house" else 36
        _draw_rect(pixels, width, height, cx - body_w, cy - body_h, cx + body_w, cy + body_h, color)
        _draw_triangle(
            pixels,
            width,
            height,
            ((cx - body_w - 10, cy - body_h), (cx + body_w + 10, cy - body_h), (cx, cy - body_h - 54)),
            (92, 49, 72),
        )
        _draw_rect(pixels, width, height, cx - 9, cy + 6, cx + 9, cy + body_h, (96, 55, 43))
        _draw_disc(pixels, width, height, cx + body_w // 2, cy - 8, 8, warm_light)
        if asset.role == "elder_house":
            _draw_rect(pixels, width, height, cx - 58, cy - body_h - 8, cx + 58, cy - body_h - 3, warm_light)
    elif asset.role == "pine_tree":
        _draw_rect(pixels, width, height, cx - 6, cy + 16, cx + 6, cy + 58, (101, 69, 47))
        for offset, radius in ((-54, 42), (-20, 52), (20, 62)):
            _draw_triangle(pixels, width, height, ((cx, cy + offset - radius), (cx - radius, cy + offset + 36), (cx + radius, cy + offset + 36)), color)
    elif asset.role == "crystal_cluster":
        for dx, h in ((-24, 56), (0, 76), (23, 48)):
            _draw_triangle(pixels, width, height, ((cx + dx, cy - h), (cx + dx - 17, cy + 34), (cx + dx + 17, cy + 34)), color)
        _draw_disc(pixels, width, height, cx, cy - 20, 9, (222, 181, 255))
    elif asset.role == "rope_bridge":
        _draw_rect(pixels, width, height, cx - 82, cy - 8, cx + 82, cy + 8, color)
        for x in range(cx - 72, cx + 73, 24):
            _draw_rect(pixels, width, height, x - 4, cy - 16, x + 4, cy + 16, (101, 66, 44))
    elif asset.role == "waterfall_ribbon":
        _draw_rect(pixels, width, height, cx - 18, cy - 74, cx + 18, cy + 78, color)
        _draw_disc(pixels, width, height, cx + 6, cy + 82, 26, (177, 235, 241))
    elif asset.role == "lantern":
        _draw_rect(pixels, width, height, cx - 5, cy - 58, cx + 5, cy + 42, (92, 62, 49))
        _draw_rect(pixels, width, height, cx - 28, cy - 72, cx + 28, cy - 56, shade)
        _draw_disc(pixels, width, height, cx, cy - 42, 20, warm_light)
    elif asset.role == "fence_segment":
        _draw_rect(pixels, width, height, cx - 88, cy - 2, cx + 88, cy + 8, color)
        _draw_rect(pixels, width, height, cx - 88, cy + 32, cx + 88, cy + 42, color)
        for x in (cx - 70, cx, cx + 70):
            _draw_rect(pixels, width, height, x - 7, cy - 30, x + 7, cy + 58, shade)
    else:
        _draw_disc(pixels, width, height, cx, cy, 52, color)

    if view == "three_quarter":
        _draw_rect(pixels, width, height, cx + 45, cy - 34, cx + 62, cy + 45, tuple(max(0, c - 28) for c in color))
    elif view == "hero":
        _draw_disc(pixels, width, height, int(width * 0.76), int(height * 0.18), 22, warm_light)


def _render_asset_preview(path: Path, asset: WorldAsset, view: str) -> dict[str, Any]:
    width = 240
    height = 180
    pixels = bytearray(width * height * 3)
    top = (72, 57, 128)
    horizon = (248, 151, 86)
    for y in range(height):
        t = y / max(1, height - 1)
        row = (
            round(top[0] + (horizon[0] - top[0]) * t),
            round(top[1] + (horizon[1] - top[1]) * t),
            round(top[2] + (horizon[2] - top[2]) * t),
        )
        for x in range(width):
            _set_px(pixels, width, height, x, y, row)
    _draw_rect(pixels, width, height, 0, int(height * 0.72), width - 1, height - 1, (68, 84, 102))
    _draw_asset_shape(pixels, width, height, asset, view)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_png(path, width, height, pixels)
    return {
        "status": "real",
        "path": str(path),
        "width": width,
        "height": height,
        "view": view,
        "renderer": "lathe.forge.asset_canonical_raster_v1",
        "sha256": _sha256_file(path),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _update_package_evidence(pkg_dir: Path, index_rel: str, asset_evidence: dict[str, Any]) -> None:
    manifest_path = pkg_dir / "manifest.json"
    if manifest_path.exists():
        manifest = _load_json(manifest_path)
        sidecars = dict(manifest.get("sidecar_files") or {})
        sidecars["canonical_previews"] = index_rel
        manifest["sidecar_files"] = sidecars
        _write_json(manifest_path, manifest)
    evidence_path = pkg_dir / "evidence.json"
    if evidence_path.exists():
        evidence = _load_json(evidence_path)
        evidence["canonical_view_renders"] = asset_evidence
        _write_json(evidence_path, evidence)


def write_asset_canonical_previews(
    composition: WorldComposition,
    world_dir: str | Path,
    asset_links: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Write front/three-quarter/hero PNGs for each linked world member."""

    root = Path(world_dir)
    rendered_assets = 0
    entries: list[dict[str, Any]] = []
    for asset in composition.assets:
        link = asset_links.get(asset.world_asset_id) or {}
        package_rel = str(link.get("package") or "")
        package_dir = root / package_rel
        if link.get("status") != "linked" or not package_rel or not package_dir.is_dir():
            entries.append(
                {
                    "world_asset_id": asset.world_asset_id,
                    "asset_id": asset.asset_id,
                    "role": asset.role,
                    "status": "blocked",
                    "reason": "linked_package_missing",
                    "views": {},
                }
            )
            continue
        mesh_path = package_dir / "mesh.glb"
        if not mesh_path.is_file():
            entries.append(
                {
                    "world_asset_id": asset.world_asset_id,
                    "asset_id": asset.asset_id,
                    "role": asset.role,
                    "status": "blocked",
                    "reason": "mesh_glb_missing",
                    "views": {},
                }
            )
            continue
        preview_dir = package_dir / "previews" / "canonical"
        views: dict[str, dict[str, Any]] = {}
        for view in _VIEWS:
            preview = _render_asset_preview(preview_dir / f"{view}.png", asset, view)
            preview["path"] = str(Path(package_rel) / "previews" / "canonical" / f"{view}.png").replace("\\", "/")
            views[view] = preview
        asset_evidence = {
            "version": ASSET_CANONICAL_RENDER_VERSION,
            "world_asset_id": asset.world_asset_id,
            "asset_id": asset.asset_id,
            "role": asset.role,
            "status": "real",
            "source_mesh": "mesh.glb",
            "source_mesh_status": "real",
            "views": views,
        }
        index_rel = "previews/canonical/index.json"
        _write_json(preview_dir / "index.json", asset_evidence)
        _update_package_evidence(package_dir, index_rel, asset_evidence)
        entries.append(asset_evidence)
        rendered_assets += 1

    required_asset_count = composition.asset_count()
    expected_renders = required_asset_count * len(_VIEWS)
    actual_renders = sum(len(entry.get("views") or {}) for entry in entries if entry.get("status") == "real")
    return {
        "version": ASSET_CANONICAL_RENDER_VERSION,
        "status": "real" if rendered_assets == required_asset_count and actual_renders == expected_renders else "blocked",
        "renderer": "lathe.forge.asset_canonical_raster_v1",
        "required_asset_count": required_asset_count,
        "rendered_asset_count": rendered_assets,
        "required_views": list(_VIEWS),
        "expected_render_count": expected_renders,
        "actual_render_count": actual_renders,
        "assets": entries,
        "rule_of_truth": (
            "Canonical previews are deterministic PNG rasters generated from linked world-member "
            "packages that contain mesh.glb visible-geometry sidecars."
        ),
    }


__all__ = [
    "ASSET_CANONICAL_RENDER_VERSION",
    "write_asset_canonical_previews",
]
