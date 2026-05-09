"""Selector manifest writer (REF-5 + REF-6).

Emits ``selector_manifest.json`` alongside every certified Lathe build. The
manifest is the authoritative sidecar for ``@lathe[...]`` reference resolution:
every addressable entity (part, socket, pivot, collision, LOD, material,
diagnostic, face/edge/vertex) has a stable id whose canonical form is the
corresponding ref token. REF-6 populates the faces/edges/vertices arrays
from the authoritative topology mesh with deterministic per-part ids
(``<part>.face<n>`` etc) and minimal geometric facts.

Schema: ``schema/lathe.selector.schema.json`` (schemaVersion=1). The writer
validates against it via ``jsonschema.Draft202012Validator`` before the file
hits disk so a broken manifest never masquerades as a valid one.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional mesh enrichment dependency
    np = None  # type: ignore[assignment]

from . import __version__
from .errors import LatheError

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "lathe.selector.schema.json"
SELECTOR_SCHEMA_VERSION = 1
SUPPORTED_SELECTOR_SCHEMA_VERSIONS = frozenset({SELECTOR_SCHEMA_VERSION})
_MIN_HASH_HEX_CHARS = 8
_VECTOR_DIMENSIONS = 3
_BBOX_COORDINATE_COUNT = 6
_TRANSFORM_ROWS = 4
_TRANSFORM_COLUMNS = 4
_SHA256_HEX_CHARS = 64


class SelectorManifestError(LatheError):
    """Raised when an assembled selector manifest fails schema validation."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "selector_manifest_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Create a selector-manifest error with a stable diagnostic code."""
        super().__init__(message)
        self.code = code
        self.details = details or {}


@lru_cache(maxsize=1)
def _load_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def _selector_schema_version_issue(version: Any) -> str | None:
    version_text = "<missing>" if version in (None, "") else str(version)
    supported = {str(item) for item in SUPPORTED_SELECTOR_SCHEMA_VERSIONS}
    if version_text in supported:
        return None
    supported_text = ", ".join(sorted(supported))
    return f"selector_manifest.json unsupported schemaVersion '{version_text}' (supported: {supported_text})"


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


def _normalize_explicit_hash(value: object, *, field: str) -> str:
    """Return a canonical lowercase hash or reject invalid explicit provenance."""
    if isinstance(value, str):
        lowered = value.lower()
        if len(lowered) >= _MIN_HASH_HEX_CHARS and all(c in "0123456789abcdef" for c in lowered):
            return lowered
    message = f"{field} must be a hexadecimal digest with at least 8 characters; got {value!r}"
    raise SelectorManifestError(message)


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
        return _normalize_explicit_hash(explicit, field="runtime.package.bundle.package_hash")
    outputs = pkg_bundle.get("outputs") or []
    if isinstance(outputs, list):
        # Prefer glb, fall back to first entry with a sha256.
        for entry in outputs:
            if isinstance(entry, dict) and entry.get("format") == "glb" and entry.get("sha256"):
                return _normalize_explicit_hash(
                    entry["sha256"], field="runtime.package.bundle.outputs[].sha256"
                )
        for entry in outputs:
            if isinstance(entry, dict) and entry.get("sha256"):
                return _normalize_explicit_hash(
                    entry["sha256"], field="runtime.package.bundle.outputs[].sha256"
                )
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


def _bbox_from_bounds(bounds_min: Any, bounds_max: Any) -> list[float] | None:
    if not isinstance(bounds_min, list) or not isinstance(bounds_max, list):
        return None
    if len(bounds_min) != _VECTOR_DIMENSIONS or len(bounds_max) != _VECTOR_DIMENSIONS:
        return None
    if not all(isinstance(v, (int, float)) for v in bounds_min):
        return None
    if not all(isinstance(v, (int, float)) for v in bounds_max):
        return None
    return [
        float(bounds_min[0]),
        float(bounds_min[1]),
        float(bounds_min[2]),
        float(bounds_max[0]),
        float(bounds_max[1]),
        float(bounds_max[2]),
    ]


def _part_face_indices(runtime_mesh: Any, pid: str) -> tuple[Any, list[int]] | None:
    try:
        mesh = getattr(runtime_mesh, "mesh", None)
        face_parts = list(getattr(runtime_mesh, "face_parts", []) or [])
        if mesh is None or len(face_parts) != len(mesh.faces):
            return None
        face_indices = [i for i, part in enumerate(face_parts) if part == pid]
    except (AttributeError, TypeError):
        return None
    if not face_indices:
        return None
    return mesh, face_indices


def _collect_mesh_faces(
    mesh: Any,
    face_indices: list[int],
    pid: str,
    token_target: str,
    max_faces: int,
) -> list[dict[str, Any]]:
    faces_out: list[dict[str, Any]] = []
    centroids = mesh.triangles_center
    normals = mesh.face_normals
    areas = mesh.area_faces
    for local_idx, face_idx in enumerate(face_indices[:max_faces]):
        face_id = f"{pid}.face{local_idx}"
        c = centroids[face_idx]
        n = normals[face_idx]
        faces_out.append(
            {
                "id": face_id,
                "ref": _ref(token_target, f"part.{face_id}"),
                "centroid": [round(float(c[0]), 6), round(float(c[1]), 6), round(float(c[2]), 6)],
                "normal": [round(float(n[0]), 6), round(float(n[1]), 6), round(float(n[2]), 6)],
                "area": round(float(areas[face_idx]), 6),
                "meshFaceIndex": int(face_idx),
            }
        )
    return faces_out


def _collect_mesh_vertices(
    mesh: Any,
    face_indices: list[int],
    pid: str,
    token_target: str,
    max_vertices: int,
) -> list[dict[str, Any]]:
    vertex_ids: dict[int, int] = {}
    for face_idx in face_indices:
        for raw_vi in mesh.faces[face_idx]:
            vertex_index = int(raw_vi)
            if vertex_index not in vertex_ids:
                vertex_ids[vertex_index] = len(vertex_ids)

    verts_out: list[dict[str, Any]] = []
    sorted_verts = sorted(vertex_ids.items(), key=lambda kv: kv[1])
    for vi, local_idx in sorted_verts[:max_vertices]:
        p = mesh.vertices[vi]
        vid = f"{pid}.vertex{local_idx}"
        verts_out.append(
            {
                "id": vid,
                "ref": _ref(token_target, f"part.{vid}"),
                "position": [round(float(p[0]), 6), round(float(p[1]), 6), round(float(p[2]), 6)],
                "meshVertexIndex": int(vi),
            }
        )
    return verts_out


def _collect_mesh_edges(
    mesh: Any,
    face_indices: list[int],
    pid: str,
    token_target: str,
    max_edges: int,
) -> list[dict[str, Any]]:
    edge_set: dict[tuple[int, int], int] = {}
    for face_idx in face_indices:
        face = mesh.faces[face_idx]
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            key = (int(min(a, b)), int(max(a, b)))
            if key not in edge_set:
                edge_set[key] = len(edge_set)

    edges_out: list[dict[str, Any]] = []
    sorted_edges = sorted(edge_set.items(), key=lambda kv: kv[1])
    for (a, b), local_idx in sorted_edges[:max_edges]:
        pa = mesh.vertices[a]
        pb = mesh.vertices[b]
        length = float(np.linalg.norm(pa - pb))
        eid = f"{pid}.edge{local_idx}"
        edges_out.append(
            {
                "id": eid,
                "ref": _ref(token_target, f"part.{eid}"),
                "endpoints": [
                    [round(float(pa[0]), 6), round(float(pa[1]), 6), round(float(pa[2]), 6)],
                    [round(float(pb[0]), 6), round(float(pb[1]), 6), round(float(pb[2]), 6)],
                ],
                "length": round(length, 6),
            }
        )
    return edges_out


def _collect_mesh_sub_parts(
    mesh: Any,
    face_indices: list[int],
    pid: str,
    token_target: str,
    *,
    max_faces: int,
    max_edges: int,
    max_vertices: int,
) -> dict[str, list[dict[str, Any]]]:
    empty = {"faces": [], "edges": [], "vertices": []}
    try:
        collected = {
            "faces": _collect_mesh_faces(mesh, face_indices, pid, token_target, max_faces),
            "edges": _collect_mesh_edges(mesh, face_indices, pid, token_target, max_edges),
            "vertices": _collect_mesh_vertices(mesh, face_indices, pid, token_target, max_vertices),
        }
    except (AttributeError, IndexError, TypeError, ValueError):
        return empty
    return collected


def _collect_sub_parts(
    runtime: dict[str, Any],
    pid: str,
    token_target: str,
    *,
    max_faces: int = 256,
    max_edges: int = 512,
    max_vertices: int = 512,
) -> dict[str, list[dict[str, Any]]]:
    """Extract per-part faces/edges/vertices from the topology runtime mesh.

    Returns a dict with ``faces``, ``edges``, and ``vertices`` lists.
    Each entry has a deterministic id (``<pid>.face<n>`` etc) and minimal
    geometric facts. Caps are applied to keep the sidecar bounded on large
    meshes — consumers that need full enumeration should pull from the
    underlying GLB. Deterministic: same runtime_mesh input -> same output.
    """
    empty = {"faces": [], "edges": [], "vertices": []}
    topology = runtime.get("topology") or {}
    runtime_mesh = topology.get("runtime_mesh")
    if runtime_mesh is None or np is None:
        return empty
    part_faces = _part_face_indices(runtime_mesh, pid)
    if part_faces is None:
        return empty
    mesh, face_indices = part_faces
    return _collect_mesh_sub_parts(
        mesh,
        face_indices,
        pid,
        token_target,
        max_faces=max_faces,
        max_edges=max_edges,
        max_vertices=max_vertices,
    )


def _collect_parts(
    runtime: dict[str, Any],
    token_target: str,
) -> list[dict[str, Any]]:
    """Build the ``parts`` array from the topology bundle's ``part_groups``.

    REF-6: the ``faces``/``edges``/``vertices`` lists are populated from the
    topology runtime mesh when it's present in ``runtime["topology"]["runtime_mesh"]``.
    """
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
        if (
            isinstance(bbox, list)
            and len(bbox) == _BBOX_COORDINATE_COUNT
            and all(isinstance(v, (int, float)) for v in bbox)
        ):
            entry["bbox"] = [float(v) for v in bbox]
        else:
            flat = _bbox_from_bounds(group.get("bounds_min"), group.get("bounds_max"))
            if flat is not None:
                entry["bbox"] = flat
        face_count = group.get("face_count") or group.get("faceCount") or group.get("tri_count")
        if isinstance(face_count, int) and face_count >= 0:
            entry["faceCount"] = face_count
        sub = _collect_sub_parts(runtime, str(pid), token_target)
        entry["faces"] = sub["faces"]
        entry["edges"] = sub["edges"]
        entry["vertices"] = sub["vertices"]
        parts.append(entry)
    return parts


_DEFAULT_SOCKET_TYPE = "attach"
_DEFAULT_PIVOT_TYPE = "center"


def _validate_transform(value: Any) -> list[list[float]] | None:
    """Return a 4x4 row-major list-of-lists of floats, or ``None`` if invalid."""
    if not isinstance(value, list) or len(value) != _TRANSFORM_ROWS:
        return None
    rows: list[list[float]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != _TRANSFORM_COLUMNS:
            return None
        if not all(isinstance(v, (int, float)) for v in row):
            return None
        rows.append([float(v) for v in row])
    return rows


def _validate_aabb(value: Any) -> dict[str, list[float]] | None:
    if not isinstance(value, dict):
        return None
    lo = value.get("min")
    hi = value.get("max")
    if not isinstance(lo, list) or not isinstance(hi, list):
        return None
    if len(lo) != _VECTOR_DIMENSIONS or len(hi) != _VECTOR_DIMENSIONS:
        return None
    if not all(isinstance(v, (int, float)) for v in lo):
        return None
    if not all(isinstance(v, (int, float)) for v in hi):
        return None
    return {"min": [float(v) for v in lo], "max": [float(v) for v in hi]}


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
        socket_type = sock.get("socket_type") or sock.get("socketType") or _DEFAULT_SOCKET_TYPE
        entry: dict[str, Any] = {
            "id": str(sid),
            "ref": _ref(token_target, f"socket.{sid}"),
            "socketType": str(socket_type),
        }
        if isinstance(sock.get("name"), str) and sock["name"]:
            entry["name"] = sock["name"]
        origin = sock.get("origin") or sock.get("position")
        if (
            isinstance(origin, list)
            and len(origin) == _VECTOR_DIMENSIONS
            and all(isinstance(v, (int, float)) for v in origin)
        ):
            entry["origin"] = [float(v) for v in origin]
        axis = sock.get("axis")
        if (
            isinstance(axis, list)
            and len(axis) == _VECTOR_DIMENSIONS
            and all(isinstance(v, (int, float)) for v in axis)
        ):
            entry["axis"] = [float(v) for v in axis]
        transform = _validate_transform(sock.get("transform"))
        if transform is not None:
            entry["transform"] = transform
        aabb = _validate_aabb(sock.get("aabb"))
        if aabb is not None:
            entry["aabb"] = aabb
        for key_src, key_dst in (
            ("kind", "kind"),
            ("compat_kind", "compatKind"),
            ("parent_part_id", "parentPartId"),
        ):
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
        pivot_type = piv.get("pivot_type") or piv.get("pivotType") or _DEFAULT_PIVOT_TYPE
        entry: dict[str, Any] = {
            "id": str(pid),
            "ref": _ref(token_target, f"pivot.{pid}"),
            "pivotType": str(pivot_type),
        }
        if isinstance(piv.get("name"), str) and piv["name"]:
            entry["name"] = piv["name"]
        origin = piv.get("origin") or piv.get("position")
        if (
            isinstance(origin, list)
            and len(origin) == _VECTOR_DIMENSIONS
            and all(isinstance(v, (int, float)) for v in origin)
        ):
            entry["origin"] = [float(v) for v in origin]
        axis = piv.get("axis")
        if (
            isinstance(axis, list)
            and len(axis) == _VECTOR_DIMENSIONS
            and all(isinstance(v, (int, float)) for v in axis)
        ):
            entry["axis"] = [float(v) for v in axis]
        transform = _validate_transform(piv.get("transform"))
        if transform is not None:
            entry["transform"] = transform
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
        return _collect_declared_lods(manifest, token_target)
    # Legacy: optimize bundle just has a `lods` list of {name, mesh_uri, ...}.
    lods = optimize.get("lods") or []
    if not isinstance(lods, list):
        return out
    return _collect_legacy_lods(lods, token_target)


def _apply_lod_metrics(
    item: dict[str, Any],
    entry: dict[str, Any],
    *,
    include_screen_size: bool,
) -> None:
    tri = entry.get("triangle_count") or entry.get("triangleCount") or entry.get("tri_count")
    if isinstance(tri, int) and tri >= 0:
        item["triangleCount"] = tri
    if include_screen_size:
        screen = entry.get("screen_size") or entry.get("screenSize")
        if isinstance(screen, (int, float)) and 0.0 <= float(screen) <= 1.0:
            item["screenSize"] = float(screen)
    dist_min = entry.get("distance_min")
    if isinstance(dist_min, (int, float)) and float(dist_min) >= 0.0:
        item["distanceMin"] = float(dist_min)
    if "distance_max" in entry:
        dist_max = entry["distance_max"]
        if dist_max is None:
            item["distanceMax"] = None
        elif isinstance(dist_max, (int, float)):
            item["distanceMax"] = float(dist_max)
    coverage = entry.get("screen_coverage")
    if isinstance(coverage, (int, float)) and 0.0 <= float(coverage) <= 1.0:
        item["screenCoverage"] = float(coverage)


def _collect_declared_lods(
    manifest: list[Any],
    token_target: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
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
        _apply_lod_metrics(item, entry, include_screen_size=True)
        out.append(item)
    return out


def _collect_legacy_lods(
    lods: list[Any],
    token_target: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, entry in enumerate(lods):
        if not isinstance(entry, dict):
            continue
        # Legacy entries are positional; the schema wants level as an int and a partId string.
        part_id = "mesh"
        item: dict[str, Any] = {
            "level": idx,
            "ref": _ref(token_target, f"lod{idx}.{part_id}"),
            "partId": part_id,
        }
        _apply_lod_metrics(item, entry, include_screen_size=False)
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
        out.append(
            {
                "id": name,
                "ref": _ref(token_target, f"material.{name}"),
            }
        )
    return out


# STAGE-12: Gameplay-tag controlled vocabulary. Keep in sync with
# ``docs/gameplay_tags.md``. The checker validates tags against this set.
GAMEPLAY_TAG_CATALOG: frozenset[str] = frozenset(
    {
        "kinematic",
        "static",
        "interactable",
        "weapon",
        "vehicle",
        "door",
        "trigger",
        "spawn_point",
        "decoration",
        "destructible",
        "consumable",
        "collectible",
        "hazard",
        "cover",
        "waypoint",
        "vfx_anchor",
        "mechanical",
        "airlock",
    }
)


def _collect_gameplay_tags(asset: dict[str, Any] | None) -> list[str]:
    """Return asset-declared gameplay tags filtered to the catalog.

    Tags live in ``asset.publish.tags`` (existing free-form field); we surface
    only the ones that appear in ``GAMEPLAY_TAG_CATALOG`` so the manifest stays
    strictly a game-engine signal. Unknown tags are dropped here (and rejected
    upstream by the checker).
    """
    if not isinstance(asset, dict):
        return []
    publish = asset.get("publish")
    if not isinstance(publish, dict):
        return []
    raw = publish.get("tags") or []
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for tag in raw:
        if not isinstance(tag, str):
            continue
        if tag not in GAMEPLAY_TAG_CATALOG or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def _clean_lod_config_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    lvl = entry.get("level")
    if not isinstance(lvl, int) or lvl < 0:
        return None
    clean: dict[str, Any] = {"level": int(lvl)}
    ratio = entry.get("ratio")
    if isinstance(ratio, (int, float)):
        clean["ratio"] = float(ratio)
    dist_min = entry.get("distance_min")
    if isinstance(dist_min, (int, float)):
        clean["distance_min"] = float(dist_min)
    if "distance_max" in entry:
        dm = entry["distance_max"]
        if dm is None:
            clean["distance_max"] = None
        elif isinstance(dm, (int, float)):
            clean["distance_max"] = float(dm)
    cov = entry.get("screen_coverage")
    if isinstance(cov, (int, float)):
        clean["screen_coverage"] = float(cov)
    return clean


def _collect_lod_config(asset: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Echo the STAGE-9 ``lod_config`` block from the asset build config."""
    if not isinstance(asset, dict):
        return []
    build = asset.get("build") or {}
    optimize = build.get("optimize") if isinstance(build, dict) else None
    if not isinstance(optimize, dict):
        return []
    raw = optimize.get("lod_config")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        clean = _clean_lod_config_entry(entry)
        if clean is not None:
            out.append(clean)
    return out


def _collect_engine_manifests(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return the STAGE-10 ``engine_manifests`` block from the package bundle."""
    pkg = (runtime.get("package") or {}).get("bundle") or {}
    raw = pkg.get("engine_manifests")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for name, entry in raw.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            continue
        clean: dict[str, Any] = {"path": path}
        sha = entry.get("sha256")
        if (
            isinstance(sha, str)
            and len(sha) == _SHA256_HEX_CHARS
            and all(c in "0123456789abcdef" for c in sha)
        ):
            clean["sha256"] = sha
        fmt = entry.get("format")
        if isinstance(fmt, str) and fmt in {"json", "yaml"}:
            clean["format"] = fmt
        out[name] = clean
    return out


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _record_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _selected_shape_candidate(shape_bundle: dict[str, Any]) -> dict[str, Any]:
    selected_id = str(shape_bundle.get("selected_candidate_id") or "")
    candidates = shape_bundle.get("candidates") or []
    if not isinstance(candidates, list):
        return {}
    for candidate in candidates:
        if isinstance(candidate, dict) and str(candidate.get("candidate_id") or "") == selected_id:
            return dict(candidate)
    return {}


def _kernel_manifest_key(manifest: dict[str, Any]) -> tuple[str, str, str, int, int]:
    return (
        str(manifest.get("program_kind") or ""),
        str(manifest.get("route") or ""),
        str(manifest.get("backend") or ""),
        int(manifest.get("operand_count", 0) or 0),
        int(manifest.get("operation_count", 0) or 0),
    )


def _kernel_manifest_from_payload(value: Any) -> dict[str, Any]:
    payload = _dict_payload(value)
    if payload.get("schema") == "lathe.geometry.kernel_program_manifest.v1":
        return payload
    direct = _dict_payload(payload.get("kernel_program_manifest"))
    if direct.get("schema") == "lathe.geometry.kernel_program_manifest.v1":
        return direct
    for key in ("details", "kernel_program", "kernel_program_details"):
        nested = _dict_payload(payload.get(key))
        direct = _dict_payload(nested.get("kernel_program_manifest"))
        if direct.get("schema") == "lathe.geometry.kernel_program_manifest.v1":
            return direct
    return {}


def _shape_ir_kernel_manifests(shape_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    selected_shape_ir = shape_bundle.get("selected_shape_ir")
    shape_irs = [selected_shape_ir] if isinstance(selected_shape_ir, dict) else (
        shape_bundle.get("shape_ir") or shape_bundle.get("shape_irs") or []
    )
    if isinstance(shape_irs, dict):
        shape_irs = [shape_irs]
    if not isinstance(shape_irs, list):
        return []
    manifests: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for shape_ir in shape_irs:
        if not isinstance(shape_ir, dict):
            continue
        primitives = shape_ir.get("primitives")
        if not isinstance(primitives, list):
            continue
        for primitive in primitives:
            if not isinstance(primitive, dict):
                continue
            semantic_metadata = _dict_payload(primitive.get("semantic_metadata"))
            v2_metadata = _dict_payload(semantic_metadata.get("shape_ir_v2"))
            for modifier_source in (primitive, semantic_metadata, v2_metadata):
                for modifier_name in (
                    "v2_hull_modifier",
                    "v2_minkowski_modifier",
                    "v2_transform_modifier",
                    "v2_copy_to_points_modifier",
                    "v2_surface_scatter_modifier",
                    "v2_distribution_modifier",
                    "v2_mirror_modifier",
                    "v2_repeat_modifier",
                    "v2_fastener_grid_modifier",
                    "v2_vent_slats_modifier",
                    "v2_corner_guard_set_modifier",
                    "v2_trim_band_modifier",
                    "v2_panel_frame_modifier",
                    "v2_socket_modifier",
                    "v2_bracket_modifier",
                    "v2_mount_plate_modifier",
                    "v2_cut_panel_line_modifier",
                    "v2_countersunk_hole_modifier",
                    "v2_rounded_slot_modifier",
                    "v2_weld_seam_modifier",
                    "v2_boolean_modifier",
                    "v2_sop_boolean_modifier",
                    "v2_inset_modifier",
                    "v2_extrude_modifier",
                    "v2_shell_modifier",
                    "v2_sweep_modifier",
                    "v2_polyextrude_modifier",
                    "v2_loft_modifier",
                    "v2_carve_modifier",
                    "v2_polywire_modifier",
                    "v2_helical_sweep_modifier",
                    "v2_deform_modifier",
                    "v2_subdivision_modifier",
                    "v2_remesh_modifier",
                    "v2_polybevel_modifier",
                    "v2_mark_hard_edge_modifier",
                    "v2_weighted_normals_modifier",
                    "v2_scratch_mask_modifier",
                    "v2_dent_mask_modifier",
                    "v2_chip_edges_modifier",
                    "v2_grime_mask_modifier",
                    "v2_prism_modifier",
                    "v2_rail_modifier",
                    "v2_structural_beam_modifier",
                    "v2_ladder_frame_modifier",
                    "v2_truss_frame_modifier",
                    "v2_panel_modifier",
                    "v2_perforated_panel_modifier",
                    "v2_ribbed_panel_modifier",
                    "v2_louver_panel_modifier",
                    "v2_terrain_patch_modifier",
                    "v2_branching_tree_modifier",
                    "v2_sdf_metaball_cluster_modifier",
                    "v2_wfc_modular_assembly_modifier",
                    "v2_cga_facade_modifier",
                    "v2_tube_modifier",
                    "v2_gear_modifier",
                    "v2_capsule_modifier",
                    "v2_flange_modifier",
                    "v2_hinge_modifier",
                    "v2_handle_modifier",
                    "v2_spring_modifier",
                    "v2_curved_tube_modifier",
                    "v2_threaded_cylinder_modifier",
                    "v2_curve_profile_modifier",
                    "v2_curve_sweep_modifier",
                    "v2_curve_loft_modifier",
                ):
                    manifest = _kernel_manifest_from_payload(modifier_source.get(modifier_name))
                    if not manifest:
                        continue
                    key = _kernel_manifest_key(manifest)
                    if key in seen:
                        continue
                    seen.add(key)
                    manifests.append(manifest)
    return manifests


def _compact_kernel_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    required = manifest.get("required_capabilities")
    diagnostics = manifest.get("diagnostics")
    clean: dict[str, Any] = {
        "programKind": str(manifest.get("program_kind") or ""),
        "route": str(manifest.get("route") or ""),
        "backend": str(manifest.get("backend") or ""),
        "operandCount": int(manifest.get("operand_count", 0) or 0),
        "operationCount": int(manifest.get("operation_count", 0) or 0),
        "semanticOperationRecordCount": int(
            manifest.get("semantic_operation_record_count", 0) or 0
        ),
        "requiredCapabilities": [
            str(item)
            for item in (required if isinstance(required, list) else [])
            if str(item)
        ],
    }
    if isinstance(diagnostics, list):
        clean["diagnosticCount"] = len([item for item in diagnostics if isinstance(item, dict)])
    return clean


def _compact_operation_record(record: dict[str, Any]) -> dict[str, Any] | None:
    operation = record.get("operation") or record.get("repair_action")
    if not operation:
        return None
    out: dict[str, Any] = {"operation": str(operation)}
    for key_src, key_dst in (
        ("operation_id", "operationId"),
        ("operand_id", "operandId"),
        ("part", "part"),
        ("primitive_type", "primitiveType"),
        ("blend_mode", "blendMode"),
        ("source", "source"),
    ):
        value = record.get(key_src)
        if value not in (None, "", [], {}):
            out[key_dst] = str(value)
    operand_index = record.get("operand_index")
    if isinstance(operand_index, int):
        out["operandIndex"] = operand_index
    semantic_count = record.get("semantic_equivalent_operation_count")
    if isinstance(semantic_count, int):
        out["semanticEquivalentOperationCount"] = semantic_count
    surface_scatter = _dict_payload(record.get("surface_scatter"))
    if surface_scatter:
        target = surface_scatter.get("target")
        if target not in (None, "", [], {}):
            out["target"] = str(target)
        mesh_face_index = surface_scatter.get("mesh_face_index")
        if isinstance(mesh_face_index, int):
            out["meshFaceIndex"] = mesh_face_index
        sample_index = surface_scatter.get("sample_index")
        if isinstance(sample_index, int):
            out["sampleIndex"] = sample_index
        emitted_count = surface_scatter.get("emitted_count")
        if isinstance(emitted_count, int):
            out["instanceCount"] = emitted_count
    point_scatter = _dict_payload(record.get("point_scatter"))
    if point_scatter:
        points = point_scatter.get("points")
        if points not in (None, "", [], {}):
            out["pointSet"] = str(points)
        point_index = point_scatter.get("point_index")
        if isinstance(point_index, int):
            out["pointIndex"] = point_index
        point_count = point_scatter.get("point_count")
        if isinstance(point_count, int):
            out["instanceCount"] = point_count
    return out


def _dedupe_selector_operation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        compact = _compact_operation_record(record)
        if compact is None:
            continue
        key = (
            str(compact.get("operationId") or ""),
            str(compact.get("operation") or ""),
            str(compact.get("operandId") or ""),
            str(compact.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(compact)
    return out


def _operation_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        operation = str(record.get("operation") or "")
        if not operation:
            continue
        counts[operation] = counts.get(operation, 0) + 1
    return dict(sorted(counts.items()))


def _first_record_list(*values: Any) -> list[dict[str, Any]]:
    for value in values:
        records = _record_list(value)
        if records:
            return records
    return []


def _compact_kernel_detail_record(
    record: dict[str, Any],
    *,
    kind_key: str,
    count_key: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "operation": str(record.get("operation") or record.get("semantic_operation") or ""),
    }
    kind = record.get(kind_key)
    if kind not in (None, "", [], {}):
        out["kind"] = str(kind)
    source_part = record.get("source_part")
    if source_part not in (None, "", [], {}):
        out["sourcePart"] = str(source_part)
    method = record.get("method")
    if method not in (None, "", [], {}):
        out["method"] = str(method)
    if count_key in record:
        out["count"] = int(record.get(count_key) or 0)
    return out


def _compact_kernel_detail_records(
    records: list[dict[str, Any]],
    *,
    kind_key: str,
    count_key: str,
) -> list[dict[str, Any]]:
    return [
        _compact_kernel_detail_record(record, kind_key=kind_key, count_key=count_key)
        for record in records
        if isinstance(record, dict)
    ]


def _collect_construction_provenance(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return a compact selector-safe construction provenance block."""
    shape_bundle = _dict_payload((runtime.get("shape") or {}).get("bundle"))
    topology_bundle = _dict_payload((runtime.get("topology") or {}).get("bundle"))
    uv_bundle = _dict_payload((runtime.get("uv") or {}).get("bundle"))
    surface_bundle = _dict_payload((runtime.get("surface") or {}).get("bundle"))
    selected_candidate = _selected_shape_candidate(shape_bundle)
    shape_integration = _dict_payload(selected_candidate.get("integration_report"))
    exact_report = _dict_payload(shape_integration.get("exact_report"))
    mesh_ir_metadata = _dict_payload(_dict_payload(selected_candidate.get("mesh_ir")).get("metadata"))

    manifests: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for manifest in [
        _kernel_manifest_from_payload(shape_integration),
        _kernel_manifest_from_payload(exact_report),
        *_shape_ir_kernel_manifests(shape_bundle),
    ]:
        if not manifest:
            continue
        key = _kernel_manifest_key(manifest)
        if key in seen:
            continue
        seen.add(key)
        manifests.append(manifest)

    operation_records = _record_list(shape_integration.get("operation_records"))
    operation_records.extend(_record_list(shape_integration.get("kernel_program_semantic_operation_records")))
    for manifest in manifests:
        operation_records.extend(_record_list(manifest.get("semantic_operation_records")))
    compact_records = _dedupe_selector_operation_records(operation_records)
    kernel_feature_details = _first_record_list(
        surface_bundle.get("kernel_feature_details"),
        uv_bundle.get("kernel_feature_details"),
        topology_bundle.get("kernel_feature_details"),
        mesh_ir_metadata.get("kernel_feature_details"),
    )
    kernel_edge_treatments = _first_record_list(
        surface_bundle.get("kernel_edge_treatments"),
        uv_bundle.get("kernel_edge_treatments"),
        topology_bundle.get("kernel_edge_treatments"),
        mesh_ir_metadata.get("kernel_edge_treatments"),
    )
    kernel_pattern_instances = _first_record_list(
        surface_bundle.get("kernel_pattern_instances"),
        uv_bundle.get("kernel_pattern_instances"),
        topology_bundle.get("kernel_pattern_instances"),
        mesh_ir_metadata.get("kernel_pattern_instances"),
    )
    kernel_deforms = _first_record_list(
        surface_bundle.get("kernel_deforms"),
        uv_bundle.get("kernel_deforms"),
        topology_bundle.get("kernel_deforms"),
        mesh_ir_metadata.get("kernel_deforms"),
    )
    kernel_profile_paths = _first_record_list(
        surface_bundle.get("kernel_profile_paths"),
        uv_bundle.get("kernel_profile_paths"),
        topology_bundle.get("kernel_profile_paths"),
        mesh_ir_metadata.get("kernel_profile_paths"),
    )
    kernel_edge_controls = _first_record_list(
        surface_bundle.get("kernel_edge_controls"),
        uv_bundle.get("kernel_edge_controls"),
        topology_bundle.get("kernel_edge_controls"),
        mesh_ir_metadata.get("kernel_edge_controls"),
    )
    kernel_component_assemblies = _first_record_list(
        surface_bundle.get("kernel_component_assemblies"),
        uv_bundle.get("kernel_component_assemblies"),
        topology_bundle.get("kernel_component_assemblies"),
        mesh_ir_metadata.get("kernel_component_assemblies"),
    )
    kernel_sdf_fields = _first_record_list(
        surface_bundle.get("kernel_sdf_fields"),
        uv_bundle.get("kernel_sdf_fields"),
        topology_bundle.get("kernel_sdf_fields"),
        mesh_ir_metadata.get("kernel_sdf_fields"),
    )
    kernel_terrain_fields = _first_record_list(
        surface_bundle.get("kernel_terrain_fields"),
        uv_bundle.get("kernel_terrain_fields"),
        topology_bundle.get("kernel_terrain_fields"),
        mesh_ir_metadata.get("kernel_terrain_fields"),
    )
    kernel_scatters = _first_record_list(
        surface_bundle.get("kernel_scatters"),
        uv_bundle.get("kernel_scatters"),
        topology_bundle.get("kernel_scatters"),
        mesh_ir_metadata.get("kernel_scatters"),
    )
    kernel_surface_damage = _first_record_list(
        surface_bundle.get("kernel_surface_damage"),
        uv_bundle.get("kernel_surface_damage"),
        topology_bundle.get("kernel_surface_damage"),
        mesh_ir_metadata.get("kernel_surface_damage"),
    )

    selected_id = str(shape_bundle.get("selected_candidate_id") or "")
    if not any(
        (
            selected_id,
            shape_integration,
            manifests,
            compact_records,
            kernel_feature_details,
            kernel_edge_treatments,
            kernel_pattern_instances,
            kernel_deforms,
            kernel_profile_paths,
            kernel_edge_controls,
            kernel_component_assemblies,
            kernel_sdf_fields,
            kernel_terrain_fields,
            kernel_scatters,
            kernel_surface_damage,
        )
    ):
        return {}

    fallback_reason = (
        shape_integration.get("boolean_fallback_reason")
        or shape_integration.get("kernel_program_failure_reason")
        or shape_integration.get("reason")
    )
    out: dict[str, Any] = {
        "schema": "lathe.selector.construction_provenance.v1",
        "selectedCandidateId": selected_id,
        "shapeMode": str(shape_integration.get("mode") or ""),
        "geometryKernel": str(
            shape_integration.get("geometry_kernel")
            or shape_integration.get("boolean_kernel")
            or shape_integration.get("kernel_program_kernel")
            or ""
        ),
        "kernelProgramSucceeded": bool(shape_integration.get("kernel_program_succeeded", False)),
        "kernelProgramPrimary": bool(shape_integration.get("kernel_program_primary", False)),
        "kernelProgramBooleanFallbackCount": int(
            shape_integration.get("kernel_program_boolean_fallback_count", 0) or 0
        ),
        "kernelProgramManifestCount": len(manifests),
        "kernelProgramManifests": [_compact_kernel_manifest(manifest) for manifest in manifests],
        "operationRecordCount": len(compact_records),
        "operationCounts": _operation_counts(compact_records),
        "operationRecords": compact_records,
        "kernelFeatureDetailCount": len(kernel_feature_details),
        "kernelFeatureDetails": _compact_kernel_detail_records(
            kernel_feature_details,
            kind_key="feature_kind",
            count_key="feature_count",
        ),
        "kernelEdgeTreatmentCount": len(kernel_edge_treatments),
        "kernelEdgeTreatments": _compact_kernel_detail_records(
            kernel_edge_treatments,
            kind_key="treatment_kind",
            count_key="treatment_count",
        ),
        "kernelPatternInstanceCount": len(kernel_pattern_instances),
        "kernelPatternInstances": _compact_kernel_detail_records(
            kernel_pattern_instances,
            kind_key="pattern_kind",
            count_key="instance_count",
        ),
        "kernelDeformCount": len(kernel_deforms),
        "kernelDeforms": _compact_kernel_detail_records(
            kernel_deforms,
            kind_key="operation",
            count_key="result_face_count",
        ),
        "kernelProfilePathCount": len(kernel_profile_paths),
        "kernelProfilePaths": _compact_kernel_detail_records(
            kernel_profile_paths,
            kind_key="profile_kind",
            count_key="result_face_count",
        ),
        "kernelEdgeControlCount": len(kernel_edge_controls),
        "kernelEdgeControls": _compact_kernel_detail_records(
            kernel_edge_controls,
            kind_key="edge_control_kind",
            count_key="result_face_count",
        ),
        "kernelComponentAssemblyCount": len(kernel_component_assemblies),
        "kernelComponentAssemblies": _compact_kernel_detail_records(
            kernel_component_assemblies,
            kind_key="assembly_kind",
            count_key="result_face_count",
        ),
        "kernelSdfFieldCount": len(kernel_sdf_fields),
        "kernelSdfFields": _compact_kernel_detail_records(
            kernel_sdf_fields,
            kind_key="field_kind",
            count_key="result_face_count",
        ),
        "kernelTerrainFieldCount": len(kernel_terrain_fields),
        "kernelTerrainFields": _compact_kernel_detail_records(
            kernel_terrain_fields,
            kind_key="terrain_kind",
            count_key="result_face_count",
        ),
        "kernelScatterCount": len(kernel_scatters),
        "kernelScatters": _compact_kernel_detail_records(
            kernel_scatters,
            kind_key="scatter_kind",
            count_key="instance_count",
        ),
        "kernelSurfaceDamageCount": len(kernel_surface_damage),
        "kernelSurfaceDamage": _compact_kernel_detail_records(
            kernel_surface_damage,
            kind_key="damage_kind",
            count_key="damage_count",
        ),
    }
    kernel_operations = _record_list(shape_integration.get("kernel_program_operations"))
    exact_boolean_records = [
        record
        for record in kernel_operations
        if isinstance(record.get("kernel_exact_boolean"), dict)
    ]
    decomposition_records = [
        record
        for record in kernel_operations
        if isinstance(record.get("kernel_boolean_decomposition"), dict)
    ]
    if exact_boolean_records:
        out["kernelProgramExactBooleanCount"] = len(exact_boolean_records)
        out["kernelProgramExactBooleanRecords"] = exact_boolean_records
    if decomposition_records:
        out["kernelProgramBooleanDecompositionCount"] = len(decomposition_records)
        out["kernelProgramBooleanDecompositionRecords"] = decomposition_records
    if fallback_reason:
        out["fallbackReason"] = str(fallback_reason)
    return out


def _collect_budgets(runtime: dict[str, Any]) -> dict[str, Any] | None:
    """Return the STAGE-7/8 ``budget_report`` from the optimize bundle, if any.

    The report has already been validated against
    ``schema/budget_manifest.schema.json`` when it was emitted; we just
    propagate it verbatim so the selector manifest shares a single source of
    truth with ``stages/optimize/budget_report.json``.
    """
    optimize = (runtime.get("optimize") or {}).get("bundle") or {}
    report = optimize.get("budget_report")
    if not isinstance(report, dict):
        return None
    required = {"schemaVersion", "texture_memory", "materials", "draw_calls", "overall_status"}
    if not required.issubset(report.keys()):
        return None
    return report


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
    version = lathe_version or __version__

    pkg_hash = package_hash
    if not isinstance(pkg_hash, str) or not pkg_hash:
        pkg_hash = _infer_package_hash(runtime or {}, resolved_build_dir)
    pkg_hash = _normalize_explicit_hash(pkg_hash, field="packageHash")
    build_hash_norm = _normalize_explicit_hash(build_hash, field="buildHash")

    source_str = str(source_path) if source_path is not None else ""

    manifest: dict[str, Any] = {
        "schemaVersion": SELECTOR_SCHEMA_VERSION,
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
    budgets = _collect_budgets(runtime or {})
    if budgets is not None:
        manifest["budgets"] = budgets
    gameplay_tags = _collect_gameplay_tags(asset)
    if gameplay_tags:
        manifest["gameplayTags"] = gameplay_tags
    lod_config = _collect_lod_config(asset)
    if lod_config:
        manifest["lodConfig"] = lod_config
    engine_manifests = _collect_engine_manifests(runtime or {})
    if engine_manifests:
        manifest["engineManifests"] = engine_manifests
    construction_provenance = _collect_construction_provenance(runtime or {})
    if construction_provenance:
        manifest["constructionProvenance"] = construction_provenance
    return manifest


def write_selector_manifest(manifest: dict[str, Any], build_dir: Path) -> Path:
    """Validate ``manifest`` against the schema and write it to ``build_dir``.

    Returns the absolute :class:`Path` of the written ``selector_manifest.json``.
    Raises :class:`SelectorManifestError` on schema failure so a broken
    manifest never reaches disk.
    """
    version_issue = _selector_schema_version_issue(manifest.get("schemaVersion"))
    if version_issue is not None:
        message = f"L7201 unsupported_selector_manifest_version: {version_issue}"
        raise SelectorManifestError(
            message,
            code="L7201",
            details={
                "schemaVersion": manifest.get("schemaVersion"),
                "supported": sorted(SUPPORTED_SELECTOR_SCHEMA_VERSIONS),
            },
        )
    validator = _load_validator()
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        pointer = "/" + "/".join(str(p) for p in first.absolute_path) if first.absolute_path else "/"
        message = f"selector_manifest.json failed schema validation at {pointer}: {first.message}"
        raise SelectorManifestError(message)
    out_path = Path(build_dir) / "selector_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_path


__all__ = [
    "SELECTOR_SCHEMA_VERSION",
    "SUPPORTED_SELECTOR_SCHEMA_VERSIONS",
    "SelectorManifestError",
    "build_selector_manifest",
    "write_selector_manifest",
]
