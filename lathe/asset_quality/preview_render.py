"""Deterministic proxy preview generation for asset-quality fixtures.

The Phase 14B preview renderer is intentionally internal and
filesystem-local. It writes simple PNG evidence from checked-in JSON
fixtures without invoking Blender, Roblox, USD viewers, or any external
renderer. The resulting images are proxy previews suitable for strict
visual-evidence gating, not final production renders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PREVIEW_EVIDENCE_VERSION = "lathe.asset_quality.preview_evidence.v1"
PREVIEW_PRODUCER = "lathe.asset_quality.preview_render.deterministic_proxy_v1"
PREVIEW_SIZE = (640, 480)
COMPARISON_SIZE = (960, 720)

PREVIEW_ROLE_FILENAMES: dict[str, str] = {
    "final_beauty": "final_beauty.png",
    "material_ids": "material_ids.png",
    "wireframe": "wireframe.png",
    "comparison_sheet": "comparison_sheet.png",
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_Color = tuple[int, int, int, int]


@dataclass(frozen=True)
class PreviewArtifact:
    """Metadata for one generated proxy preview image."""

    role: str
    path: str
    width: int
    height: int
    sha256: str


class _Canvas:
    def __init__(self, width: int, height: int, background: _Color) -> None:
        self.width = width
        self.height = height
        self.pixels = [[background for _x in range(width)] for _y in range(height)]

    def fill_rect(self, x: int, y: int, width: int, height: int, color: _Color) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + width)
        y1 = min(self.height, y + height)
        for py in range(y0, y1):
            row = self.pixels[py]
            for px in range(x0, x1):
                row[px] = color

    def stroke_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: _Color,
        *,
        thickness: int = 1,
    ) -> None:
        for offset in range(thickness):
            self.line(x + offset, y + offset, x + width - offset, y + offset, color)
            self.line(x + offset, y + height - offset, x + width - offset, y + height - offset, color)
            self.line(x + offset, y + offset, x + offset, y + height - offset, color)
            self.line(x + width - offset, y + offset, x + width - offset, y + height - offset, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: _Color) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if 0 <= x0 < self.width and 0 <= y0 < self.height:
                self.pixels[y0][x0] = color
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def blit_scaled(self, source: _Canvas, x: int, y: int, width: int, height: int) -> None:
        for py in range(height):
            sy = min(source.height - 1, int(py * source.height / height))
            for px in range(width):
                sx = min(source.width - 1, int(px * source.width / width))
                tx = x + px
                ty = y + py
                if 0 <= tx < self.width and 0 <= ty < self.height:
                    self.pixels[ty][tx] = source.pixels[sy][sx]

    def png_bytes(self) -> bytes:
        rows = bytearray()
        for row in self.pixels:
            rows.append(0)
            for r, g, b, a in row:
                rows.extend((r, g, b, a))
        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 6, 0, 0, 0)
        return b"".join(
            [
                _PNG_SIGNATURE,
                _png_chunk(b"IHDR", ihdr),
                _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9)),
                _png_chunk(b"IEND", b""),
            ]
        )


def generate_preview_artifacts(example_dir: str | Path) -> dict[str, Any]:
    """Generate deterministic proxy previews and update preview evidence."""
    path = Path(example_dir)
    asset_id = _asset_id(path)
    render_key = _preview_render_key(path, asset_id)
    previews_dir = path / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)

    canvases = {
        "final_beauty": _render_final_beauty(render_key),
        "material_ids": _render_material_ids(render_key),
        "wireframe": _render_wireframe(render_key),
    }
    canvases["comparison_sheet"] = _render_comparison_sheet(canvases)

    artifacts: list[PreviewArtifact] = []
    for role, filename in PREVIEW_ROLE_FILENAMES.items():
        rel_path = f"previews/{filename}"
        image_bytes = canvases[role].png_bytes()
        (path / rel_path).write_bytes(image_bytes)
        artifacts.append(
            PreviewArtifact(
                role=role,
                path=rel_path,
                width=canvases[role].width,
                height=canvases[role].height,
                sha256=hashlib.sha256(image_bytes).hexdigest(),
            )
        )

    evidence = build_preview_evidence(asset_id, artifacts)
    (path / "preview_evidence.json").write_text(_canonical_json(evidence), encoding="utf-8")
    return {
        "ok": True,
        "asset_id": asset_id,
        "example_dir": str(path),
        "artifacts": [artifact.__dict__ for artifact in artifacts],
        "preview_evidence_path": str(path / "preview_evidence.json"),
    }


def build_preview_evidence(
    asset_id: str,
    artifacts: list[PreviewArtifact],
) -> dict[str, Any]:
    """Build the truthfulness payload for deterministic proxy previews."""
    by_role = {artifact.role: artifact for artifact in artifacts}
    views: dict[str, Any] = {}
    for role in PREVIEW_ROLE_FILENAMES:
        artifact = by_role[role]
        views[role] = {
            "blocking_for_strict": True,
            "blocking_for_warning": False,
            "height": artifact.height,
            "path": artifact.path,
            "producer": PREVIEW_PRODUCER,
            "reason": "Generated by Lathe's deterministic proxy preview renderer; no external renderer was executed.",
            "sha256": artifact.sha256,
            "status": "present",
            "width": artifact.width,
        }
    return {
        "asset_id": asset_id,
        "schema_version": PREVIEW_EVIDENCE_VERSION,
        "truthfulness": {
            "external_renderer_used": False,
            "producer": PREVIEW_PRODUCER,
            "real_render_output": False,
            "reason": (
                "Deterministic proxy PNGs were generated from checked-in fixture "
                "metadata. No Blender, Roblox, USD viewer, game engine, or "
                "external renderer lane was executed."
            ),
        },
        "views": views,
    }


def _asset_id(path: Path) -> str:
    brief_path = path / "design_brief.json"
    if brief_path.exists():
        try:
            payload = json.loads(brief_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return path.name
        if isinstance(payload, dict) and isinstance(payload.get("asset_id"), str):
            return payload["asset_id"]
    return path.name


def _preview_render_key(path: Path, asset_id: str) -> str:
    object_family = _preview_object_family(path)
    key = f"{asset_id}:{object_family}" if object_family else asset_id
    patch_result_path = path / "patch_result.json"
    if not patch_result_path.exists():
        return key
    try:
        payload = json.loads(patch_result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return key
    patch_sha = payload.get("patch_sha256")
    if isinstance(patch_sha, str) and patch_sha:
        return f"{key}:{patch_sha}"
    return key


def _preview_object_family(path: Path) -> str:
    quality_plan_path = path / "quality_plan.json"
    if quality_plan_path.exists():
        try:
            payload = json.loads(quality_plan_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        object_family = payload.get("object_family") if isinstance(payload, dict) else None
        if isinstance(object_family, str) and object_family:
            return object_family
    brief_path = path / "design_brief.json"
    if brief_path.exists():
        try:
            payload = json.loads(brief_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        if isinstance(payload, dict):
            family = payload.get("family")
            if isinstance(family, str) and family:
                return family
    return ""


def _render_final_beauty(asset_id: str) -> _Canvas:
    canvas = _Canvas(*PREVIEW_SIZE, (225, 231, 229, 255))
    _draw_background_grid(canvas, (206, 214, 213, 255))
    if _is_sword_asset(asset_id):
        _draw_sword(canvas, _sword_beauty_palette(asset_id), shaded=True, wire=False)
        _draw_deterministic_blade_scuffs(canvas, asset_id, (238, 244, 242, 255))
    elif _is_machine_asset(asset_id):
        _draw_machine(canvas, _beauty_palette(asset_id), shaded=True, wire=False)
        _draw_deterministic_scuffs(canvas, asset_id, (236, 210, 144, 255))
    elif _is_counter_asset(asset_id):
        _draw_counter(canvas, _beauty_palette(asset_id), shaded=True, wire=False)
        _draw_deterministic_scuffs(canvas, asset_id, (236, 210, 144, 255))
    else:
        _draw_crate(canvas, _beauty_palette(asset_id), shaded=True, wire=False)
        _draw_deterministic_scuffs(canvas, asset_id, (236, 210, 144, 255))
    return canvas


def _render_material_ids(asset_id: str) -> _Canvas:
    canvas = _Canvas(*PREVIEW_SIZE, (24, 28, 35, 255))
    _draw_background_grid(canvas, (43, 48, 58, 255), step=48)
    if _is_sword_asset(asset_id):
        _draw_sword(canvas, _sword_material_id_palette(asset_id), shaded=False, wire=False)
    elif _is_machine_asset(asset_id):
        _draw_machine(canvas, _material_id_palette(asset_id), shaded=False, wire=False)
    elif _is_counter_asset(asset_id):
        _draw_counter(canvas, _material_id_palette(asset_id), shaded=False, wire=False)
    else:
        _draw_crate(canvas, _material_id_palette(asset_id), shaded=False, wire=False)
    return canvas


def _render_wireframe(asset_id: str) -> _Canvas:
    canvas = _Canvas(*PREVIEW_SIZE, (14, 18, 22, 255))
    _draw_background_grid(canvas, (34, 43, 49, 255), step=32)
    if _is_sword_asset(asset_id):
        _draw_sword(canvas, _sword_wire_palette(asset_id), shaded=False, wire=True)
    elif _is_machine_asset(asset_id):
        _draw_machine(canvas, _wire_palette(asset_id), shaded=False, wire=True)
    elif _is_counter_asset(asset_id):
        _draw_counter(canvas, _wire_palette(asset_id), shaded=False, wire=True)
    else:
        _draw_crate(canvas, _wire_palette(asset_id), shaded=False, wire=True)
    return canvas


def _render_comparison_sheet(canvases: dict[str, _Canvas]) -> _Canvas:
    canvas = _Canvas(*COMPARISON_SIZE, (238, 240, 237, 255))
    panel_w = 420
    panel_h = 280
    margin_x = 42
    margin_y = 54
    gap_x = 72
    gap_y = 76
    slots = [
        ("final_beauty", margin_x, margin_y),
        ("material_ids", margin_x + panel_w + gap_x, margin_y),
        ("wireframe", margin_x, margin_y + panel_h + gap_y),
        ("final_beauty", margin_x + panel_w + gap_x, margin_y + panel_h + gap_y),
    ]
    for role, x, y in slots:
        canvas.fill_rect(x - 8, y - 8, panel_w + 16, panel_h + 16, (44, 49, 52, 255))
        canvas.blit_scaled(canvases[role], x, y, panel_w, panel_h)
        canvas.stroke_rect(x - 8, y - 8, panel_w + 16, panel_h + 16, (10, 12, 14, 255), thickness=2)
    return canvas


def _draw_background_grid(canvas: _Canvas, color: _Color, *, step: int = 40) -> None:
    for x in range(0, canvas.width, step):
        canvas.line(x, 0, x, canvas.height - 1, color)
    for y in range(0, canvas.height, step):
        canvas.line(0, y, canvas.width - 1, y, color)


def _draw_crate(
    canvas: _Canvas,
    palette: dict[str, _Color],
    *,
    shaded: bool,
    wire: bool,
) -> None:
    front = (150, 170, 330, 218)
    side_offset = (74, -46)
    top_offset = (60, -58)
    if not wire:
        canvas.fill_rect(front[0] + side_offset[0], front[1] + side_offset[1], front[2], front[3], palette["side"])
        canvas.fill_rect(front[0] + top_offset[0], front[1] + top_offset[1], front[2], 68, palette["top"])
        canvas.fill_rect(*front, palette["body"])
    line = palette["line"]
    canvas.stroke_rect(*front, line, thickness=3 if wire else 2)
    canvas.stroke_rect(front[0] + side_offset[0], front[1] + side_offset[1], front[2], front[3], line, thickness=2)
    canvas.stroke_rect(front[0] + top_offset[0], front[1] + top_offset[1], front[2], 68, line, thickness=2)
    for x, y in (
        (front[0] - 10, front[1] - 10),
        (front[0] + front[2] - 56, front[1] - 10),
        (front[0] - 10, front[1] + front[3] - 56),
        (front[0] + front[2] - 56, front[1] + front[3] - 56),
    ):
        if not wire:
            canvas.fill_rect(x, y, 66, 66, palette["guard"])
        canvas.stroke_rect(x, y, 66, 66, line, thickness=2)
    panel = (front[0] + 58, front[1] + 54, front[2] - 116, front[3] - 100)
    if not wire:
        canvas.fill_rect(*panel, palette["panel"])
    canvas.stroke_rect(*panel, line, thickness=2)
    canvas.line(front[0] + 28, front[1] + 44, front[0] + front[2] - 28, front[1] + 44, line)
    latch = (front[0] + 142, front[1] + 84, 46, 68)
    if not wire:
        canvas.fill_rect(*latch, palette["metal"])
    canvas.stroke_rect(*latch, line, thickness=2)
    for x in (front[0] + 34, front[0] + front[2] - 118):
        if not wire:
            canvas.fill_rect(x, front[1] + 104, 84, 34, palette["rubber"])
        canvas.stroke_rect(x, front[1] + 104, 84, 34, line, thickness=2)
    for x in (front[0] + 28, front[0] + front[2] - 120):
        if not wire:
            canvas.fill_rect(x, front[1] + front[3] + 4, 92, 28, palette["rubber"])
        canvas.stroke_rect(x, front[1] + front[3] + 4, 92, 28, line, thickness=2)
    if shaded and not wire:
        canvas.fill_rect(front[0], front[1], front[2], 14, palette["highlight"])
        canvas.fill_rect(front[0], front[1] + front[3] - 20, front[2], 20, palette["shadow"])


def _draw_sword(
    canvas: _Canvas,
    palette: dict[str, _Color],
    *,
    shaded: bool,
    wire: bool,
) -> None:
    cx = canvas.width // 2
    blade_top = 72
    blade_bottom = 322
    blade_base_width = 62
    segment_count = 7
    segment_height = (blade_bottom - blade_top) // segment_count
    line = palette["line"]

    for index in range(segment_count):
        t = index / max(1, segment_count - 1)
        width = int(blade_base_width * (0.98 - 0.25 * t))
        y = blade_top + index * segment_height
        x = cx - width // 2
        if not wire:
            canvas.fill_rect(x, y, width, segment_height + 2, palette["blade"])
            if shaded:
                canvas.fill_rect(x, y, max(2, width // 5), segment_height + 2, palette["blade_shadow"])
                canvas.fill_rect(x + width - max(2, width // 6), y, max(2, width // 6), segment_height + 2, palette["blade_highlight"])
        canvas.stroke_rect(x, y, width, segment_height + 2, line, thickness=1 if wire else 2)

    tip_y = blade_top - 44
    tip_width = 30
    if not wire:
        canvas.fill_rect(cx - tip_width // 2, tip_y + 16, tip_width, 28, palette["blade"])
        canvas.fill_rect(cx - 7, tip_y, 14, 18, palette["blade_highlight"])
    canvas.line(cx - tip_width // 2, tip_y + 44, cx, tip_y, line)
    canvas.line(cx, tip_y, cx + tip_width // 2, tip_y + 44, line)
    canvas.line(cx - tip_width // 2, tip_y + 44, cx + tip_width // 2, tip_y + 44, line)

    fuller_w = 13
    if not wire:
        canvas.fill_rect(cx - fuller_w // 2, blade_top + 32, fuller_w, 172, palette["fuller"])
    canvas.stroke_rect(cx - fuller_w // 2, blade_top + 32, fuller_w, 172, line, thickness=1)
    canvas.line(cx, blade_top + 8, cx, blade_bottom - 2, palette["ridge"])

    guard_y = blade_bottom + 16
    guard_w = 238
    guard_h = 30
    if not wire:
        canvas.fill_rect(cx - guard_w // 2, guard_y, guard_w, guard_h, palette["guard"])
        canvas.fill_rect(cx - 32, guard_y - 8, 64, guard_h + 16, palette["guard_center"])
        canvas.fill_rect(cx - guard_w // 2 - 20, guard_y + 2, 24, guard_h - 4, palette["guard_cap"])
        canvas.fill_rect(cx + guard_w // 2 - 4, guard_y + 2, 24, guard_h - 4, palette["guard_cap"])
    canvas.stroke_rect(cx - guard_w // 2, guard_y, guard_w, guard_h, line, thickness=2)
    canvas.stroke_rect(cx - 32, guard_y - 8, 64, guard_h + 16, line, thickness=2)
    canvas.stroke_rect(cx - guard_w // 2 - 20, guard_y + 2, 24, guard_h - 4, line, thickness=2)
    canvas.stroke_rect(cx + guard_w // 2 - 4, guard_y + 2, 24, guard_h - 4, line, thickness=2)

    grip_y = guard_y + guard_h + 2
    grip_h = 92
    grip_w = 34
    if not wire:
        canvas.fill_rect(cx - grip_w // 2, grip_y, grip_w, grip_h, palette["grip"])
    canvas.stroke_rect(cx - grip_w // 2, grip_y, grip_w, grip_h, line, thickness=2)
    for index in range(8):
        y = grip_y + 8 + index * 10
        if not wire:
            canvas.fill_rect(cx - grip_w // 2 - 4, y, grip_w + 8, 5, palette["wrap"])
        canvas.stroke_rect(cx - grip_w // 2 - 4, y, grip_w + 8, 5, line, thickness=1)

    pommel_y = grip_y + grip_h + 2
    if not wire:
        canvas.fill_rect(cx - 33, pommel_y, 66, 28, palette["pommel"])
        canvas.fill_rect(cx - 22, pommel_y + 25, 44, 16, palette["guard_cap"])
    canvas.stroke_rect(cx - 33, pommel_y, 66, 28, line, thickness=2)
    canvas.stroke_rect(cx - 22, pommel_y + 25, 44, 16, line, thickness=2)


def _draw_machine(
    canvas: _Canvas,
    palette: dict[str, _Color],
    *,
    shaded: bool,
    wire: bool,
) -> None:
    line = palette["line"]
    body = (190, 148, 250, 210)
    hopper = (240, 82, 150, 72)
    conveyor = (150, 362, 340, 42)
    if not wire:
        canvas.fill_rect(*body, palette["body"])
        canvas.fill_rect(*hopper, palette["top"])
        canvas.fill_rect(*conveyor, palette["rubber"])
    canvas.stroke_rect(*body, line, thickness=3 if wire else 2)
    canvas.stroke_rect(*hopper, line, thickness=2)
    canvas.stroke_rect(*conveyor, line, thickness=2)
    for index in range(4):
        x = conveyor[0] + 28 + index * 74
        if not wire:
            canvas.fill_rect(x, conveyor[1] + 6, 42, 30, palette["metal"])
        canvas.stroke_rect(x, conveyor[1] + 6, 42, 30, line, thickness=1)
    panel = (body[0] + 38, body[1] + 48, 92, 96)
    if not wire:
        canvas.fill_rect(*panel, palette["panel"])
    canvas.stroke_rect(*panel, line, thickness=2)
    for index, color_key in enumerate(("guard", "metal", "panel")):
        x = body[0] + 156 + index * 38
        if not wire:
            canvas.fill_rect(x, body[1] + 62, 24, 24, palette[color_key])
        canvas.stroke_rect(x, body[1] + 62, 24, 24, line, thickness=1)
    output = (body[0] + 92, body[1] + body[3] - 28, 70, 36)
    if not wire:
        canvas.fill_rect(*output, palette["guard"])
    canvas.stroke_rect(*output, line, thickness=2)
    if shaded and not wire:
        canvas.fill_rect(body[0], body[1], body[2], 14, palette["highlight"])
        canvas.fill_rect(body[0], body[1] + body[3] - 18, body[2], 18, palette["shadow"])


def _draw_counter(
    canvas: _Canvas,
    palette: dict[str, _Color],
    *,
    shaded: bool,
    wire: bool,
) -> None:
    line = palette["line"]
    top = (140, 156, 360, 46)
    base = (172, 202, 296, 160)
    sign = (230, 86, 180, 54)
    shelf = (196, 254, 248, 38)
    if not wire:
        canvas.fill_rect(*sign, palette["guard"])
        canvas.fill_rect(*top, palette["top"])
        canvas.fill_rect(*base, palette["body"])
        canvas.fill_rect(*shelf, palette["panel"])
    canvas.stroke_rect(*sign, line, thickness=2)
    canvas.stroke_rect(*top, line, thickness=3 if wire else 2)
    canvas.stroke_rect(*base, line, thickness=2)
    canvas.stroke_rect(*shelf, line, thickness=2)
    for x in (base[0] + 26, base[0] + base[2] - 58):
        if not wire:
            canvas.fill_rect(x, base[1] + base[3], 34, 46, palette["rubber"])
        canvas.stroke_rect(x, base[1] + base[3], 34, 46, line, thickness=2)
    display = (base[0] + 186, base[1] + 34, 72, 64)
    if not wire:
        canvas.fill_rect(*display, palette["metal"])
    canvas.stroke_rect(*display, line, thickness=2)
    for index in range(5):
        x = top[0] + 34 + index * 58
        canvas.line(x, top[1], x + 20, top[1] + top[3], line)
    if shaded and not wire:
        canvas.fill_rect(top[0], top[1], top[2], 10, palette["highlight"])
        canvas.fill_rect(base[0], base[1] + base[3] - 16, base[2], 16, palette["shadow"])


def _draw_deterministic_scuffs(canvas: _Canvas, asset_id: str, color: _Color) -> None:
    digest = hashlib.sha256(asset_id.encode()).digest()
    for idx in range(18):
        raw = digest[idx % len(digest)]
        x = 164 + (raw * 19 + idx * 41) % 296
        y = 178 + (raw * 13 + idx * 29) % 190
        length = 8 + raw % 18
        canvas.line(x, y, x + length, y + (idx % 5) - 2, color)


def _draw_deterministic_blade_scuffs(canvas: _Canvas, asset_id: str, color: _Color) -> None:
    digest = hashlib.sha256(asset_id.encode()).digest()
    for idx in range(22):
        raw = digest[idx % len(digest)]
        x = 292 + (raw * 11 + idx * 17) % 56
        y = 94 + (raw * 23 + idx * 31) % 214
        length = 6 + raw % 16
        canvas.line(x, y, x + length, y + (idx % 3) - 1, color)


def _is_sword_asset(asset_id: str) -> bool:
    lowered = asset_id.lower()
    return "sword" in lowered or "weapon" in lowered


def _is_machine_asset(asset_id: str) -> bool:
    lowered = asset_id.lower()
    return any(token in lowered for token in ("machine", "tycoon", "dropper", "dispenser"))


def _is_counter_asset(asset_id: str) -> bool:
    lowered = asset_id.lower()
    return any(token in lowered for token in ("counter", "shop", "furniture"))


def _beauty_palette(asset_id: str) -> dict[str, _Color]:
    accent = 88 + hashlib.sha256(asset_id.encode()).digest()[0] % 34
    return {
        "body": (95, 116, 113, 255),
        "guard": (150, 147, 127, 255),
        "highlight": (123, 145, 139, 255),
        "line": (38, 47, 47, 255),
        "metal": (166, 168, 158, 255),
        "panel": (78, accent, 100, 255),
        "rubber": (38, 39, 39, 255),
        "shadow": (59, 73, 72, 255),
        "side": (74, 91, 91, 255),
        "top": (128, 145, 137, 255),
    }


def _material_id_palette(asset_id: str) -> dict[str, _Color]:
    digest = hashlib.sha256(asset_id.encode()).digest()
    return {
        "body": (44, 176, 212, 255),
        "guard": (232, 109 + digest[1] % 20, 70, 255),
        "highlight": (44, 176, 212, 255),
        "line": (10, 10, 14, 255),
        "metal": (239, 214, 71, 255),
        "panel": (89, 202, 118, 255),
        "rubber": (147, 98, 218, 255),
        "shadow": (44, 176, 212, 255),
        "side": (36, 128, 210, 255),
        "top": (82, 192, 164, 255),
    }


def _wire_palette(asset_id: str) -> dict[str, _Color]:
    blue = 210 + hashlib.sha256(asset_id.encode()).digest()[2] % 32
    return {
        "body": (0, 0, 0, 0),
        "guard": (0, 0, 0, 0),
        "highlight": (0, 0, 0, 0),
        "line": (77, blue, 230, 255),
        "metal": (0, 0, 0, 0),
        "panel": (0, 0, 0, 0),
        "rubber": (0, 0, 0, 0),
        "shadow": (0, 0, 0, 0),
        "side": (0, 0, 0, 0),
        "top": (0, 0, 0, 0),
    }


def _sword_beauty_palette(asset_id: str) -> dict[str, _Color]:
    brass = 124 + hashlib.sha256(asset_id.encode()).digest()[3] % 28
    return {
        "blade": (178, 190, 195, 255),
        "blade_highlight": (224, 232, 230, 255),
        "blade_shadow": (128, 143, 150, 255),
        "fuller": (108, 123, 132, 255),
        "grip": (46, 31, 24, 255),
        "guard": (brass, 103, 48, 255),
        "guard_cap": (194, 150, 66, 255),
        "guard_center": (154, 116, 52, 255),
        "line": (34, 37, 39, 255),
        "pommel": (174, 128, 56, 255),
        "ridge": (241, 245, 242, 255),
        "wrap": (82, 55, 39, 255),
    }


def _sword_material_id_palette(asset_id: str) -> dict[str, _Color]:
    digest = hashlib.sha256(asset_id.encode()).digest()
    return {
        "blade": (64, 188, 232, 255),
        "blade_highlight": (64, 188, 232, 255),
        "blade_shadow": (64, 188, 232, 255),
        "fuller": (92, 126 + digest[4] % 38, 242, 255),
        "grip": (164, 88, 216, 255),
        "guard": (240, 184, 48, 255),
        "guard_cap": (230, 104, 80, 255),
        "guard_center": (240, 184, 48, 255),
        "line": (8, 9, 12, 255),
        "pommel": (230, 104, 80, 255),
        "ridge": (255, 255, 255, 255),
        "wrap": (68, 214, 124, 255),
    }


def _sword_wire_palette(asset_id: str) -> dict[str, _Color]:
    blue = 208 + hashlib.sha256(asset_id.encode()).digest()[5] % 30
    clear = (0, 0, 0, 0)
    return {
        "blade": clear,
        "blade_highlight": clear,
        "blade_shadow": clear,
        "fuller": clear,
        "grip": clear,
        "guard": clear,
        "guard_cap": clear,
        "guard_center": clear,
        "line": (80, blue, 236, 255),
        "pommel": clear,
        "ridge": (190, 244, 255, 255),
        "wrap": clear,
    }


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum & 0xFFFFFFFF)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic proxy preview artifacts.")
    parser.add_argument("example_dir")
    args = parser.parse_args(argv)
    payload = generate_preview_artifacts(args.example_dir)
    print(_canonical_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PREVIEW_PRODUCER",
    "PREVIEW_ROLE_FILENAMES",
    "PreviewArtifact",
    "build_preview_evidence",
    "generate_preview_artifacts",
]
