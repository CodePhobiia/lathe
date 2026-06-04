"""Top-down minimap rasterizer for Forge world graphs."""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from typing import Any

from .world_graph import Vec3, WorldComposition

MINIMAP_VERSION = "lathe.forge.minimap_v1"

Color = tuple[int, int, int]


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
    data = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)),
            _png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(data)


def _set_px(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: Color,
) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    idx = (y * width + x) * 3
    pixels[idx : idx + 3] = bytes(color)


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


def _draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Color,
    *,
    thickness: int = 1,
) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        _draw_disc(pixels, width, height, x, y, thickness, color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _draw_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    half_w: int,
    half_h: int,
    color: Color,
) -> None:
    for yy in range(y - half_h, y + half_h + 1):
        for xx in range(x - half_w, x + half_w + 1):
            _set_px(pixels, width, height, xx, yy, color)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_minimap_png(
    composition: WorldComposition,
    output_path: str | Path,
    *,
    width: int = 512,
    height: int = 512,
) -> dict[str, Any]:
    """Rasterize a deterministic top-down minimap from the world graph."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pixels = bytearray([34, 36, 48] * (width * height))
    scale = min(width, height) / 2100.0

    def project(point: Vec3) -> tuple[int, int]:
        x, _, z = point
        return (
            int(width / 2 + x * scale),
            int(height / 2 - z * scale),
        )

    # Island base.
    center = project((0.0, 0.0, 0.0))
    _draw_disc(pixels, width, height, center[0], center[1], int(830.0 * scale), (64, 83, 80))
    _draw_disc(pixels, width, height, center[0], center[1], int(745.0 * scale), (63, 146, 91))

    # Path graph.
    node_positions = {node.node_id: project(node.position_cm) for node in composition.path_nodes}
    for edge in composition.path_edges:
        points = [project(point) for point in edge.control_points_cm]
        for a, b in zip(points, points[1:]):
            _draw_line(pixels, width, height, a[0], a[1], b[0], b[1], (207, 178, 121), thickness=2)

    # Assets.
    role_color: dict[str, Color] = {
        "cottage": (205, 132, 83),
        "elder_house": (246, 178, 84),
        "pine_tree": (31, 103, 79),
        "crystal_cluster": (157, 105, 232),
        "rope_bridge": (145, 98, 67),
        "waterfall_ribbon": (68, 194, 220),
        "lantern": (255, 194, 92),
        "fence_segment": (126, 83, 55),
        "stone_path_segment": (177, 166, 143),
    }
    for asset in composition.assets:
        if asset.role == "floating_island":
            continue
        x, y = project(asset.placement.position_cm)
        color = role_color.get(asset.role, (220, 220, 220))
        if asset.role in {"cottage", "elder_house"}:
            size = 8 if asset.role == "elder_house" else 6
            _draw_rect(pixels, width, height, x, y, size, size, color)
        elif asset.role in {"rope_bridge", "stone_path_segment", "fence_segment"}:
            _draw_rect(pixels, width, height, x, y, 8, 2, color)
        else:
            _draw_disc(pixels, width, height, x, y, 4, color)

    # Spawn and quest marker sit on top.
    for node_id, color in (("village_square", (255, 255, 255)), ("elder_house_door", (255, 238, 95))):
        if node_id in node_positions:
            x, y = node_positions[node_id]
            _draw_disc(pixels, width, height, x, y, 5, color)

    _write_png(path, width, height, pixels)
    return {
        "version": MINIMAP_VERSION,
        "status": "real",
        "path": str(path),
        "width": width,
        "height": height,
        "source": "forge_world_graph",
        "sha256": _sha256_file(path),
    }


__all__ = ["MINIMAP_VERSION", "write_minimap_png"]
