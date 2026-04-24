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


def _bbox_from_bounds(bounds_min: Any, bounds_max: Any) -> list[float] | None:
    if not isinstance(bounds_min, list) or not isinstance(bounds_max, list):
        return None
    if len(bounds_min) != 3 or len(bounds_max) != 3:
        return None
    if not all(isinstance(v, (int, float)) for v in bounds_min):
        return None
    if not all(isinstance(v, (int, float)) for v in bounds_max):
        return None
    return [
        float(bounds_min[0]), float(bounds_min[1]), float(bounds_min[2]),
        float(bounds_max[0]), float(bounds_max[1]), float(bounds_max[2]),
    ]


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
    if runtime_mesh is None:
        return empty
    try:
        import numpy as np

        mesh = getattr(runtime_mesh, "mesh", None)
        face_parts = list(getattr(runtime_mesh, "face_parts", []) or [])
        if mesh is None or len(face_parts) != len(mesh.faces):
            return empty
        face_indices = [i for i, part in enumerate(face_parts) if part == pid]
        if not face_indices:
            return empty

        faces_out: list[dict[str, Any]] = []
        centroids = mesh.triangles_center
        normals = mesh.face_normals
        areas = mesh.area_faces
        for local_idx, face_idx in enumerate(face_indices[:max_faces]):
            face_id = f"{pid}.face{local_idx}"
            c = centroids[face_idx]
            n = normals[face_idx]
            entry = {
                "id": face_id,
                "ref": _ref(token_target, f"part.{face_id}"),
                "centroid": [round(float(c[0]), 6), round(float(c[1]), 6), round(float(c[2]), 6)],
                "normal": [round(float(n[0]), 6), round(float(n[1]), 6), round(float(n[2]), 6)],
                "area": round(float(areas[face_idx]), 6),
                "meshFaceIndex": int(face_idx),
            }
            faces_out.append(entry)

        vertex_ids: dict[int, int] = {}
        for face_idx in face_indices:
            for vi in mesh.faces[face_idx]:
                vi = int(vi)
                if vi not in vertex_ids:
                    vertex_ids[vi] = len(vertex_ids)
        verts_out: list[dict[str, Any]] = []
        sorted_verts = sorted(vertex_ids.items(), key=lambda kv: kv[1])
        for vi, local_idx in sorted_verts[:max_vertices]:
            p = mesh.vertices[vi]
            vid = f"{pid}.vertex{local_idx}"
            verts_out.append({
                "id": vid,
                "ref": _ref(token_target, f"part.{vid}"),
                "position": [round(float(p[0]), 6), round(float(p[1]), 6), round(float(p[2]), 6)],
                "meshVertexIndex": int(vi),
            })

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
            edges_out.append({
                "id": eid,
                "ref": _ref(token_target, f"part.{eid}"),
                "endpoints": [
                    [round(float(pa[0]), 6), round(float(pa[1]), 6), round(float(pa[2]), 6)],
                    [round(float(pb[0]), 6), round(float(pb[1]), 6), round(float(pb[2]), 6)],
                ],
                "length": round(length, 6),
            })

        return {"faces": faces_out, "edges": edges_out, "vertices": verts_out}
    except Exception:  # noqa: BLE001 — best-effort enrichment
        return empty


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
        if isinstance(bbox, list) and len(bbox) == 6 and all(isinstance(v, (int, float)) for v in bbox):
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
    if not isinstance(value, list) or len(value) != 4:
        return None
    rows: list[list[float]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 4:
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
    if len(lo) != 3 or len(hi) != 3:
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
        if isinstance(origin, list) and len(origin) == 3 and all(isinstance(v, (int, float)) for v in origin):
            entry["origin"] = [float(v) for v in origin]
        axis = sock.get("axis")
        if isinstance(axis, list) and len(axis) == 3 and all(isinstance(v, (int, float)) for v in axis):
            entry["axis"] = [float(v) for v in axis]
        transform = _validate_transform(sock.get("transform"))
        if transform is not None:
            entry["transform"] = transform
        aabb = _validate_aabb(sock.get("aabb"))
        if aabb is not None:
            entry["aabb"] = aabb
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
        pivot_type = piv.get("pivot_type") or piv.get("pivotType") or _DEFAULT_PIVOT_TYPE
        entry: dict[str, Any] = {
            "id": str(pid),
            "ref": _ref(token_target, f"pivot.{pid}"),
            "pivotType": str(pivot_type),
        }
        if isinstance(piv.get("name"), str) and piv["name"]:
            entry["name"] = piv["name"]
        origin = piv.get("origin") or piv.get("position")
        if isinstance(origin, list) and len(origin) == 3 and all(isinstance(v, (int, float)) for v in origin):
            entry["origin"] = [float(v) for v in origin]
        axis = piv.get("axis")
        if isinstance(axis, list) and len(axis) == 3 and all(isinstance(v, (int, float)) for v in axis):
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
        lvl = entry.get("level")
        if not isinstance(lvl, int) or lvl < 0:
            continue
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
        if isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha):
            clean["sha256"] = sha
        fmt = entry.get("format")
        if isinstance(fmt, str) and fmt in {"json", "yaml"}:
            clean["format"] = fmt
        out[name] = clean
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
