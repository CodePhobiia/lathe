"""Selector manifest writer (REF-5).

Emits ``selector_manifest.json`` alongside every certified Lathe build. The
manifest is the authoritative sidecar for ``@lathe[...]`` reference resolution:
every addressable entity (part, socket, pivot, collision, LOD, material,
diagnostic) has a stable id whose canonical form is the corresponding ref
token. Face/edge/vertex lists stay empty in Phase 1 — those land with REF-6.

Schema: ``schema/lathe.selector.schema.json`` (schemaVersion=1). The writer
validates against it via ``jsonschema.Draft202012Validator`` before the file
hits disk so a broken manifest never masquerades as a valid one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from . import __version__ as _LATHE_VERSION
from .errors import LatheError


_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "lathe.selector.schema.json"
_VALIDATOR: jsonschema.Draft202012Validator | None = None


class SelectorManifestError(LatheError):
    """Raised when an assembled selector manifest fails schema validation."""


def _load_validator() -> jsonschema.Draft202012Validator:
    global _VALIDATOR
    if _VALIDATOR is None:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        _VALIDATOR = jsonschema.Draft202012Validator(schema)
    return _VALIDATOR


def _target_token(build_dir: Path, *, repo_root: Path | None = None) -> str:
    """Render the ``@lathe[...]`` target fragment for a build directory.

    Preference order:
      1. If ``build_dir`` is under ``repo_root``, use the repo-relative path
         with forward slashes.
      2. Else fall back to the directory's ``name``.
    """

    if repo_root is not None:
        try:
            rel = Path(build_dir).resolve().relative_to(Path(repo_root).resolve())
            return rel.as_posix()
        except ValueError:
            pass
    return Path(build_dir).name


def _ref(token_target: str, selector: str) -> str:
    return f"@lathe[{token_target}#{selector}]"


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _coerce_hash(value: str | None, *, field: str) -> str:
    """Normalise hash-shaped strings to the ``[0-9a-f]{8,}`` pattern.

    Falls back to a deterministic sha256 of the field name so the manifest
    always satisfies the schema pattern even when upstream produced a
    non-hex ``build_id`` placeholder.
    """

    if isinstance(value, str) and len(value) >= 8:
        lowered = value.lower()
        if all(c in "0123456789abcdef" for c in lowered):
            return lowered
    return hashlib.sha256((field + ":" + str(value)).encode("utf-8")).hexdigest()


def _infer_package_hash(runtime: dict[str, Any], build_dir: Path) -> str:
    """Derive ``packageHash`` from whichever source is available.

    Order of preference:
      1. ``runtime["package"]["bundle"]["package_hash"]`` if already present.
      2. sha256 of the main ``.glb`` output listed in the package bundle.
      3. sha256 of the first output's uri if present on disk.
      4. sha256 of the bundle dict (always available).
    """

    pkg_bundle = (runtime.get("package") or {}).get("bundle") or {}
    explicit = pkg_bundle.get("package_hash")
    if isinstance(explicit, str) and explicit:
        return _coerce_hash(explicit, field="packageHash")
    outputs = pkg_bundle.get("outputs") or []
    if isinstance(outputs, list):
        # Prefer glb, fall back to first entry with a sha256.
        for entry in outputs:
            if isinstance(entry, dict) and entry.get("format") == "glb" and entry.get("sha256"):
                return _coerce_hash(entry["sha256"], field="packageHash")
        for entry in outputs:
            if isinstance(entry, dict) and entry.get("sha256"):
                return _coerce_hash(entry["sha256"], field="packageHash")
            if isinstance(entry, dict) and entry.get("uri"):
                candidate = build_dir / str(entry["uri"])
                if candidate.exists() and candidate.is_file():
                    return _sha256_of_file(candidate)
    # Last resort: hash the bundle itself.
    payload = json.dumps(pkg_bundle, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _coordinate_system(asset: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve the manifest ``coordinateSystem`` block.

    Pulls ``upAxis`` and ``unit`` from the asset's ``space`` block if present;
    otherwise returns defaults (Y-up, cm, right-handed — matching the Lathe
    reference stack).
    """

    default = {"upAxis": "Y", "unit": "cm", "handedness": "right"}
    if not isinstance(asset, dict):
        return default
    space = asset.get("space") or {}
    result: dict[str, Any] = dict(default)
    up = space.get("up_axis") or space.get("upAxis")
    if isinstance(up, str) and up in {"Y", "Z", "-Y", "-Z"}:
        result["upAxis"] = up
    unit = space.get("unit") or space.get("units")
    if isinstance(unit, str) and unit in {"m", "cm", "mm", "in"}:
        result["unit"] = unit
    handedness = space.get("handedness")
    if isinstance(handedness, str) and handedness in {"right", "left"}:
        result["handedness"] = handedness
    return result


def _collect_parts(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    """Build the ``parts`` array from the topology bundle's ``part_groups``."""

    topology = (runtime.get("topology") or {}).get("bundle") or {}
    part_groups = topology.get("part_groups") or []
    parts: list[dict[str, Any]] = []
    if not isinstance(part_groups, list):
        return parts
    for group in part_groups:
        if not isinstance(group, dict):
            continue
        pid = group.get("name") or group.get("id")
        if not pid:
            continue
        entry: dict[str, Any] = {
            "id": str(pid),
            "ref": _ref(token_target, f"part.{pid}"),
        }
        if "name" in group and isinstance(group["name"], str):
            entry["name"] = group["name"]
        if "material_id" in group and isinstance(group["material_id"], str):
            entry["materialId"] = group["material_id"]
        bbox = group.get("bbox") or group.get("aabb")
        if isinstance(bbox, list) and len(bbox) == 6 and all(isinstance(v, (int, float)) for v in bbox):
            entry["bbox"] = [float(v) for v in bbox]
        face_count = group.get("face_count") or group.get("faceCount") or group.get("tri_count")
        if isinstance(face_count, int) and face_count >= 0:
            entry["faceCount"] = face_count
        # Phase 2 slots stay empty arrays.
        entry["faces"] = []
        entry["edges"] = []
        entry["vertices"] = []
        parts.append(entry)
    return parts


def _collect_sockets(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    interfaces = (runtime.get("interfaces") or {}).get("bundle") or {}
    sockets = interfaces.get("sockets") or []
    out: list[dict[str, Any]] = []
    if not isinstance(sockets, list):
        return out
    for sock in sockets:
        if not isinstance(sock, dict):
            continue
        sid = sock.get("id") or sock.get("name")
        if not sid:
            continue
        entry: dict[str, Any] = {
            "id": str(sid),
            "ref": _ref(token_target, f"socket.{sid}"),
        }
        origin = sock.get("origin") or sock.get("position")
        if isinstance(origin, list) and len(origin) == 3 and all(isinstance(v, (int, float)) for v in origin):
            entry["origin"] = [float(v) for v in origin]
        axis = sock.get("axis")
        if isinstance(axis, list) and len(axis) == 3 and all(isinstance(v, (int, float)) for v in axis):
            entry["axis"] = [float(v) for v in axis]
        for key_src, key_dst in (("kind", "kind"), ("compat_kind", "compatKind"), ("parent_part_id", "parentPartId")):
            val = sock.get(key_src)
            if isinstance(val, str) and val:
                entry[key_dst] = val
        out.append(entry)
    return out


def _collect_pivots(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    interfaces = (runtime.get("interfaces") or {}).get("bundle") or {}
    pivots = interfaces.get("pivots") or []
    out: list[dict[str, Any]] = []
    if not isinstance(pivots, list):
        return out
    for piv in pivots:
        if not isinstance(piv, dict):
            continue
        pid = piv.get("id") or piv.get("name")
        if not pid:
            continue
        entry: dict[str, Any] = {
            "id": str(pid),
            "ref": _ref(token_target, f"pivot.{pid}"),
        }
        origin = piv.get("origin") or piv.get("position")
        if isinstance(origin, list) and len(origin) == 3 and all(isinstance(v, (int, float)) for v in origin):
            entry["origin"] = [float(v) for v in origin]
        axis = piv.get("axis")
        if isinstance(axis, list) and len(axis) == 3 and all(isinstance(v, (int, float)) for v in axis):
            entry["axis"] = [float(v) for v in axis]
        for key_src, key_dst in (("kind", "kind"), ("parent_part_id", "parentPartId")):
            val = piv.get(key_src)
            if isinstance(val, str) and val:
                entry[key_dst] = val
        out.append(entry)
    return out


def _collect_collisions(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    optimize = (runtime.get("optimize") or {}).get("bundle") or {}
    manifest = optimize.get("collision_manifest") or []
    out: list[dict[str, Any]] = []
    if not isinstance(manifest, list):
        return out
    valid_kinds = {"box", "sphere", "capsule", "hull", "mesh"}
    for entry in manifest:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id") or entry.get("name")
        if not cid:
            continue
        item: dict[str, Any] = {
            "id": str(cid),
            "ref": _ref(token_target, f"collision.{cid}"),
        }
        kind = entry.get("kind") or entry.get("shape")
        if isinstance(kind, str) and kind in valid_kinds:
            item["kind"] = kind
        parent = entry.get("parent_part_id") or entry.get("parentPartId")
        if isinstance(parent, str) and parent:
            item["parentPartId"] = parent
        hulls = entry.get("hull_count") or entry.get("hullCount")
        if isinstance(hulls, int) and hulls >= 0:
            item["hullCount"] = hulls
        volume = entry.get("volume")
        if isinstance(volume, (int, float)):
            item["volume"] = float(volume)
        out.append(item)
    return out


def _collect_lods(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    optimize = (runtime.get("optimize") or {}).get("bundle") or {}
    # Prefer an explicit "lod_manifest" key (STAGE-1 addition); fall back to the
    # legacy "lods" list so Phase-1 builds that predate STAGE-1 still produce a
    # valid manifest.
    manifest = optimize.get("lod_manifest")
    out: list[dict[str, Any]] = []
    if isinstance(manifest, list) and manifest:
        for entry in manifest:
            if not isinstance(entry, dict):
                continue
            level = entry.get("level")
            part_id = entry.get("part_id") or entry.get("partId") or entry.get("part") or "mesh"
            if not isinstance(level, int) or level < 0:
                continue
            item: dict[str, Any] = {
                "level": level,
                "ref": _ref(token_target, f"lod{level}.{part_id}"),
            }
            if isinstance(part_id, str) and part_id:
                item["partId"] = part_id
            tri = entry.get("triangle_count") or entry.get("triangleCount") or entry.get("tri_count")
            if isinstance(tri, int) and tri >= 0:
                item["triangleCount"] = tri
            screen = entry.get("screen_size") or entry.get("screenSize")
            if isinstance(screen, (int, float)) and 0.0 <= float(screen) <= 1.0:
                item["screenSize"] = float(screen)
            out.append(item)
        return out
    # Legacy: optimize bundle just has a `lods` list of {name, mesh_uri, ...}.
    lods = optimize.get("lods") or []
    if not isinstance(lods, list):
        return out
    for idx, entry in enumerate(lods):
        if not isinstance(entry, dict):
            continue
        # Name is "lod<n>"; the schema wants level as an int and a partId string.
        name = str(entry.get("name") or f"lod{idx}")
        part_id = "mesh"
        item: dict[str, Any] = {
            "level": idx,
            "ref": _ref(token_target, f"lod{idx}.{part_id}"),
            "partId": part_id,
        }
        tri = entry.get("triangle_count") or entry.get("triangleCount")
        if isinstance(tri, int) and tri >= 0:
            item["triangleCount"] = tri
        out.append(item)
    return out


def _collect_materials(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    surface = (runtime.get("surface") or {}).get("bundle") or {}
    materials = surface.get("materials")
    out: list[dict[str, Any]] = []
    if isinstance(materials, list) and materials:
        for mat in materials:
            if not isinstance(mat, dict):
                continue
            mid = mat.get("id") or mat.get("name")
            if not mid:
                continue
            item: dict[str, Any] = {
                "id": str(mid),
                "ref": _ref(token_target, f"material.{mid}"),
            }
            if isinstance(mat.get("display_name") or mat.get("displayName"), str):
                item["displayName"] = mat.get("display_name") or mat.get("displayName")
            mem = mat.get("texture_memory_mb") or mat.get("textureMemoryMB")
            if isinstance(mem, (int, float)) and mem >= 0:
                item["textureMemoryMB"] = float(mem)
            ts = mat.get("texture_set") or mat.get("textureSet")
            if isinstance(ts, list) and all(isinstance(t, str) for t in ts):
                item["textureSet"] = list(ts)
            out.append(item)
        return out
    # Fall back to material_zones (the semantic-material list the surface
    # pipeline produces). One manifest entry per unique material name.
    zones = surface.get("material_zones") or []
    if not isinstance(zones, list):
        return out
    seen: set[str] = set()
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        name = zone.get("material") or zone.get("name")
        if not isinstance(name, str) or not name or name in seen:
            continue
        seen.add(name)
        out.append({
            "id": name,
            "ref": _ref(token_target, f"material.{name}"),
        })
    return out


def _collect_diagnostics(
    validate_report: dict[str, Any] | None,
    token_target: str,
) -> list[dict[str, Any]]:
    if not isinstance(validate_report, dict):
        return []
    diags = validate_report.get("diagnostics") or []
    out: list[dict[str, Any]] = []
    valid_sev = {"error", "warning", "info"}
    for diag in diags:
        if not isinstance(diag, dict):
            continue
        did = diag.get("id") or diag.get("code") or diag.get("name")
        if not did:
            continue
        sev = diag.get("severity") or "info"
        if sev not in valid_sev:
            sev = "info"
        item: dict[str, Any] = {
            "id": str(did),
            "ref": _ref(token_target, f"diagnostic.{did}"),
            "severity": sev,
        }
        for key_src, key_dst in (("stage", "stage"), ("message", "message"), ("code", "code")):
            val = diag.get(key_src)
            if isinstance(val, str) and val:
                item[key_dst] = val
        refs = diag.get("refs")
        if isinstance(refs, list) and all(isinstance(r, str) and r.startswith("@lathe[") for r in refs):
            item["refs"] = list(refs)
        cmds = diag.get("suggested_commands") or diag.get("suggestedCommands")
        if isinstance(cmds, list) and all(isinstance(c, str) for c in cmds):
            item["suggestedCommands"] = list(cmds)
        out.append(item)
    return out


def build_selector_manifest(
    *,
    asset_name: str,
    variant_name: str | None,
    source_path: str | Path,
    lathe_version: str | None = None,
    build_hash: str,
    package_hash: str | None = None,
    runtime: dict[str, Any],
    validate_report: dict[str, Any] | None = None,
    asset: dict[str, Any] | None = None,
    build_dir: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Assemble a dict matching ``schema/lathe.selector.schema.json``.

    Arguments:
        asset_name: Asset declaration name.
        variant_name: Variant name if the build is a materialized variant, else ``None``.
        source_path: Path to the originating ``.lth`` source.
        lathe_version: Override the emitted ``latheVersion``. Defaults to ``lathe.__version__``.
        build_hash: Deterministic hash of build inputs (executor's ``cache_key``).
        package_hash: Pre-computed package hash. Inferred from ``runtime`` if omitted.
        runtime: Executor ``runtime`` dict (contains each stage's bundle).
        validate_report: Validator report dict; ``diagnostics`` key is consumed.
        asset: Materialized asset dict (used for coordinate system resolution).
        build_dir: Output directory of the build (used when inferring package hash).
        repo_root: Repo root for resolving ``token_target``. Defaults to ``build_dir.parent.parent``.
    """

    resolved_build_dir = Path(build_dir) if build_dir is not None else Path.cwd()
    resolved_repo_root = Path(repo_root) if repo_root is not None else None

    token_target = _target_token(resolved_build_dir, repo_root=resolved_repo_root)
    version = lathe_version or _LATHE_VERSION

    pkg_hash = package_hash
    if not isinstance(pkg_hash, str) or not pkg_hash:
        pkg_hash = _infer_package_hash(runtime or {}, resolved_build_dir)
    pkg_hash = _coerce_hash(pkg_hash, field="packageHash")
    build_hash_norm = _coerce_hash(build_hash, field="buildHash")

    source_str = str(source_path) if source_path is not None else ""

    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "latheVersion": version,
        "sourcePath": source_str,
        "asset": asset_name,
        "variant": variant_name,
        "buildHash": build_hash_norm,
        "packageHash": pkg_hash,
        "coordinateSystem": _coordinate_system(asset),
        "tables": {},
        "parts": _collect_parts(runtime or {}, token_target),
        "sockets": _collect_sockets(runtime or {}, token_target),
        "pivots": _collect_pivots(runtime or {}, token_target),
        "collisions": _collect_collisions(runtime or {}, token_target),
        "lods": _collect_lods(runtime or {}, token_target),
        "materials": _collect_materials(runtime or {}, token_target),
        "diagnostics": _collect_diagnostics(validate_report, token_target),
        "relations": {},
    }
    return manifest


def write_selector_manifest(manifest: dict[str, Any], build_dir: Path) -> Path:
    """Validate ``manifest`` against the schema and write it to ``build_dir``.

    Returns the absolute :class:`Path` of the written ``selector_manifest.json``.
    Raises :class:`SelectorManifestError` on schema failure so a broken
    manifest never reaches disk.
    """

    validator = _load_validator()
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        pointer = "/" + "/".join(str(p) for p in first.absolute_path) if first.absolute_path else "/"
        raise SelectorManifestError(
            f"selector_manifest.json failed schema validation at {pointer}: {first.message}"
        )
    out_path = Path(build_dir) / "selector_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_path


__all__ = [
    "SelectorManifestError",
    "build_selector_manifest",
    "write_selector_manifest",
]
