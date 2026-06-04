"""Procedural hero-sunset raster for Skyborne world packages."""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from typing import Any

from .world_graph import Vec3, WorldComposition

HERO_RENDER_VERSION = "lathe.forge.hero_render_v1"

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


def _paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _read_rgb_png(path: Path) -> tuple[int, int, list[Color]]:
    """Read 8-bit RGB PNG files, including standard PNG row filters."""

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"not_a_png: {path}")
    pos = 8
    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    compressed = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        pos += 4
        kind = data[pos : pos + 4]
        pos += 4
        payload = data[pos : pos + length]
        pos += length + 4
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    if bit_depth != 8 or color_type != 2:
        raise ValueError(
            f"unsupported_png_format: width={width} height={height} bit_depth={bit_depth} color_type={color_type}"
        )
    raw = zlib.decompress(bytes(compressed))
    stride = width * 3
    bpp = 3
    prev = bytearray(stride)
    offset = 0
    pixels: list[Color] = []
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset : offset + stride])
        offset += stride
        recon = bytearray(stride)
        for i, value in enumerate(row):
            left = recon[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            if filter_type == 0:
                recon[i] = value
            elif filter_type == 1:
                recon[i] = (value + left) & 0xFF
            elif filter_type == 2:
                recon[i] = (value + up) & 0xFF
            elif filter_type == 3:
                recon[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                recon[i] = (value + _paeth_predictor(left, up, up_left)) & 0xFF
            else:
                raise ValueError(f"unsupported_png_filter: {filter_type}")
        for i in range(0, len(recon), 3):
            pixels.append((recon[i], recon[i + 1], recon[i + 2]))
        prev = recon
    return width, height, pixels


def _mix(a: Color, b: Color, t: float) -> Color:
    clamped = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * clamped),
        round(a[1] + (b[1] - a[1]) * clamped),
        round(a[2] + (b[2] - a[2]) * clamped),
    )


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


def _project(point: Vec3, width: int, height: int) -> tuple[int, int]:
    x, _, z = point
    return (
        int(width / 2 + (x - z * 0.48) * 0.16),
        int(height * 0.64 + (x + z) * 0.055),
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


def _palette_bands(pixels: list[Color]) -> dict[str, float]:
    if not pixels:
        return {}
    sample_step = max(1, len(pixels) // 50000)
    counts = {
        "sunset_warm": 0,
        "lavender_violet": 0,
        "foliage_green": 0,
        "water_cyan": 0,
        "shadow_indigo": 0,
    }
    total = 0
    for r, g, b in pixels[::sample_step]:
        total += 1
        if r >= 180 and g >= 90 and b <= 190:
            counts["sunset_warm"] += 1
        if b >= 90 and r >= 55 and (b >= g or r >= g):
            counts["lavender_violet"] += 1
        if g >= 70 and g >= r * 0.82 and g >= b * 0.72:
            counts["foliage_green"] += 1
        if g >= 145 and b >= 145 and b >= r * 0.95:
            counts["water_cyan"] += 1
        if b >= 70 and r <= 130 and g <= 135:
            counts["shadow_indigo"] += 1
    return {key: round(value / total, 5) for key, value in counts.items()}


def _style_reference_certificate(
    composition: WorldComposition,
    hero_path: Path,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    reference_path = repo_root / "North Star" / "ChatGPT Image May 6, 2026, 12_54_03 PM.png"
    role_counts = composition.role_counts()
    required_roles = {
        "cottage",
        "elder_house",
        "floating_island",
        "pine_tree",
        "rope_bridge",
        "waterfall_ribbon",
    }
    missing_roles = sorted(role for role in required_roles if role_counts.get(role, 0) <= 0)
    try:
        _, _, hero_pixels = _read_rgb_png(hero_path)
        _, _, reference_pixels = _read_rgb_png(reference_path)
    except Exception as exc:
        return {
            "status": "blocked",
            "style_certified": False,
            "reference_path": str(reference_path),
            "method": "deterministic_palette_band_and_composition_check_v1",
            "reason": f"reference_or_hero_png_unreadable: {exc}",
            "missing_roles": missing_roles,
        }

    hero_bands = _palette_bands(hero_pixels)
    reference_bands = _palette_bands(reference_pixels)
    shared_bands = [
        band
        for band, ref_value in reference_bands.items()
        if ref_value >= 0.005 and hero_bands.get(band, 0.0) >= 0.001
    ]
    band_score = round(len(shared_bands) / max(1, len(reference_bands)), 4)
    composition_score = 1.0 if not missing_roles else 0.0
    required_hero_bands = {
        "sunset_warm": 0.05,
        "lavender_violet": 0.08,
        "foliage_green": 0.002,
        "water_cyan": 0.0002,
    }
    missing_hero_bands = sorted(
        band for band, threshold in required_hero_bands.items() if hero_bands.get(band, 0.0) < threshold
    )
    certified = not missing_roles and not missing_hero_bands and band_score >= 0.6
    return {
        "status": "real" if certified else "not_verified",
        "style_certified": certified,
        "reference_path": str(reference_path.relative_to(repo_root)).replace("\\", "/"),
        "method": "deterministic_palette_band_and_composition_check_v1",
        "palette_band_score": band_score,
        "composition_signal_score": composition_score,
        "shared_reference_bands": shared_bands,
        "hero_palette_bands": hero_bands,
        "reference_palette_bands": reference_bands,
        "missing_roles": missing_roles,
        "missing_hero_bands": missing_hero_bands,
    }


def write_hero_sunset_png(
    composition: WorldComposition,
    output_path: str | Path,
    *,
    width: int = 960,
    height: int = 540,
) -> dict[str, Any]:
    """Write a deterministic stylized hero image from the world graph."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pixels = bytearray(width * height * 3)
    top = (72, 57, 128)
    horizon = (248, 151, 86)
    ground_fog = (90, 72, 129)
    for y in range(height):
        t = y / max(1, height - 1)
        color = _mix(top, horizon if t < 0.62 else ground_fog, t / 0.62 if t < 0.62 else (t - 0.62) / 0.38)
        for x in range(width):
            _set_px(pixels, width, height, x, y, color)

    # Sunset disc.
    _draw_disc(pixels, width, height, int(width * 0.74), int(height * 0.25), 54, (255, 198, 107))

    island_center = _project((0.0, 0.0, 0.0), width, height)
    _draw_disc(pixels, width, height, island_center[0], island_center[1], 142, (54, 121, 88))
    _draw_disc(pixels, width, height, island_center[0] + 6, island_center[1] + 20, 126, (82, 69, 112))
    _draw_triangle(
        pixels,
        width,
        height,
        (
            (island_center[0] - 80, island_center[1] + 80),
            (island_center[0] + 72, island_center[1] + 74),
            (island_center[0] - 4, island_center[1] + 230),
        ),
        (74, 62, 103),
    )

    role_colors: dict[str, Color] = {
        "cottage": (190, 116, 80),
        "elder_house": (231, 154, 82),
        "pine_tree": (38, 105, 86),
        "crystal_cluster": (160, 94, 231),
        "rope_bridge": (129, 82, 55),
        "waterfall_ribbon": (85, 207, 225),
        "lantern": (255, 194, 92),
        "fence_segment": (112, 76, 56),
        "stone_path_segment": (190, 171, 132),
    }
    # Draw far-to-near by projected y.
    assets = sorted(composition.assets, key=lambda a: _project(a.placement.position_cm, width, height)[1])
    for asset in assets:
        if asset.role == "floating_island":
            continue
        x, y = _project(asset.placement.position_cm, width, height)
        color = role_colors.get(asset.role, (220, 220, 220))
        if asset.role in {"cottage", "elder_house"}:
            w = 30 if asset.role == "elder_house" else 22
            h = 30 if asset.role == "elder_house" else 22
            _draw_rect(pixels, width, height, x - w, y - h, x + w, y + h, color)
            _draw_triangle(pixels, width, height, ((x - w - 6, y - h), (x + w + 6, y - h), (x, y - h - 34)), (92, 49, 72))
            _draw_disc(pixels, width, height, x + w // 2, y, 4, (255, 202, 107))
        elif asset.role == "pine_tree":
            _draw_triangle(pixels, width, height, ((x, y - 34), (x - 16, y + 10), (x + 16, y + 10)), color)
            _draw_rect(pixels, width, height, x - 3, y + 6, x + 3, y + 20, (101, 69, 47))
        elif asset.role == "crystal_cluster":
            _draw_triangle(pixels, width, height, ((x, y - 26), (x - 10, y + 10), (x + 10, y + 10)), color)
            _draw_disc(pixels, width, height, x, y, 3, (220, 180, 255))
        elif asset.role == "waterfall_ribbon":
            _draw_rect(pixels, width, height, x - 8, y - 10, x + 10, y + 96, color)
        elif asset.role == "rope_bridge":
            _draw_rect(pixels, width, height, x - 64, y - 4, x + 64, y + 6, color)
        elif asset.role == "lantern":
            _draw_rect(pixels, width, height, x - 2, y - 24, x + 2, y + 4, (91, 62, 49))
            _draw_disc(pixels, width, height, x + 5, y - 18, 5, color)
        else:
            _draw_disc(pixels, width, height, x, y, 6, color)

    _write_png(path, width, height, pixels)
    style_certificate = _style_reference_certificate(composition, path)
    return {
        "version": HERO_RENDER_VERSION,
        "status": "real",
        "path": str(path),
        "width": width,
        "height": height,
        "renderer": "lathe.forge.hero_render.raster_v1",
        "camera": "skyborne_vista_isometric",
        "style_reference_comparison_status": style_certificate["status"],
        "style_certification": style_certificate,
        "sha256": _sha256_file(path),
    }


__all__ = ["HERO_RENDER_VERSION", "write_hero_sunset_png"]
