"""Phase 12 deterministic standard hard-surface kit library.

Carries kit-part metadata (fasteners, corner_guards, handles, rails,
warning_labels) through the validate stage as additive evidence so
later phases can compose reusable hard-surface details onto generated
assets without re-authoring their geometry. Phase 12 is **evidence
+ informational only** — it does not run a renderer, drive Blender,
mutate Phase 6 ``grammar_lowering.py``, or extend any public ``.lth``
syntax. Kit parts are loaded from the internal filesystem convention
``std/kits/hardsurface/`` by the executor and published to
``runtime["_kit_library"]``; the validator
:func:`evaluate_kit_library` is a pure function that reads only that
runtime slot.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md``
Section 12.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 12.
Per-feature reference:
``docs/asset-quality/hardsurface-kit-library-v1.md``.

Public-syntax constraint
------------------------

Phase 12 does NOT add any public ``.lth`` syntax. There is no
``kit { ... }`` or ``library { ... }`` block in the grammar/parser/
normalizer/resolver/checker. Kit-part loading is INTERNAL: the
executor calls :func:`load_kit_library` (a separately-tested disk
loader) and publishes the parsed result to
``runtime["_kit_library"]`` before the validate stage runs. This
mirrors the Phase 11 ``runtime["_reference_board"]`` pattern. Phase
13 is the only phase allowed to expose this surface to ``.lth``.

Filesystem convention
---------------------

The default disk layout is::

    std/kits/hardsurface/
        fasteners/
            *.json
        corner_guards/
            *.json
        handles/
            *.json
        rails/
            *.json
        warning_labels/
            *.json

Each ``*.json`` file is validated against
``schema/kit_part.schema.json``. Missing categories, missing files,
malformed JSON, or schema violations all yield structured
``skipped_reason`` records — the loader never fabricates a part.

Loader / validator separation
-----------------------------

Two entry points keep filesystem reads and validator logic separate:

- :func:`load_kit_library` — disk loader. Returns a populated
  :class:`KitLibrary`. Extra lookup helpers
  (:func:`lookup_kit_part`, :func:`kit_parts_by_category`,
  :func:`kit_parts_for_family`) operate on the loaded library.
- :func:`evaluate_kit_library` — pure validator. Reads
  ``runtime["_kit_library"]`` only. Builds the additive evidence
  payload that lands under the ``kit_library`` key of the validate
  stage report.

Returned evidence shape
-----------------------

The validator emits the additive ``kit_library`` payload::

    {
        "version": "kit_library_v1",
        "asset_name": str,
        "family": str,
        "library": {
            "base_path": str,
            "parts": [...],          # sorted by (category, name)
            "skipped": [...],
        },
        "summary": {
            "part_count": int,
            "parts_by_category": {
                "fasteners": int,
                "corner_guards": int,
                "handles": int,
                "rails": int,
                "warning_labels": int,
            },
            "categories_covered": int,            # 0..5
            "all_required_categories_present": bool,
            "parts_for_family_count": int,
        },
        "skipped_reasons": [...],   # deduplicated and sorted
        "warnings": [],
        "diagnostics": [],
    }

Skipped-evidence contract
-------------------------

Per ``AGENTS.md``, every skipped category emits a single structured
record with one of the fixed reason tokens:

- ``kit_library_not_loaded`` — ``runtime["_kit_library"]`` is absent.
- ``kit_library_directory_missing`` — the base directory does not
  exist on disk.
- ``category_directory_missing`` — a category subdirectory is absent.
- ``kit_part_unreadable`` — a candidate JSON file cannot be read.
- ``kit_part_malformed`` — a candidate JSON file fails parse.
- ``kit_part_schema_violation:<detail>`` — a candidate JSON file
  parses but fails schema validation. ``<detail>`` carries the first
  failing field so future authors can debug from evidence alone.
- ``kit_part_duplicate_name:<name>`` — two valid kit-part files use
  the same globally unique part name; the later file is skipped.

Skipped reasons are deduplicated and sorted by ``(category, reason)``
for determinism.

Crate grammar integration note
-------------------------------

Phase 12 does NOT mutate
``lathe/asset_quality/grammar_lowering.py`` or change Phase 6
industrial_crate recipe behaviour. Integration with the industrial
crate recipe is reserved for Phase 14 (golden examples). This module
only supplies a deterministic lookup surface so future phases can
annotate which kit parts COULD satisfy a recipe step.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``reference_board`` and before
``geometry_integrity``. Output additively appears under the
top-level ``kit_library`` key of the validate-stage report (the 26th
top-level key, on top of the 25 that Phases 0 through 11 publish).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KIT_LIBRARY_VERSION = "kit_library_v1"

REQUIRED_CATEGORIES: tuple[str, ...] = (
    "fasteners",
    "corner_guards",
    "handles",
    "rails",
    "warning_labels",
)

_ALLOWED_KINDS: frozenset[str] = frozenset({"procedural", "mesh_stub"})
_ALLOWED_AXES: frozenset[str] = frozenset({"+x", "-x", "+y", "-y", "+z", "-z"})
_ALLOWED_NORMAL_AXES: frozenset[str] = frozenset({"+x", "-x", "+y", "-y", "+z", "-z", "any"})
_ALLOWED_FACES: frozenset[str] = frozenset(
    {"any", "top", "bottom", "front", "back", "left", "right"}
)
_ALLOWED_LOD_STRATEGIES: frozenset[str] = frozenset(
    {"always_present", "drop_at_lod1", "drop_at_lod2", "drop_at_lod3"}
)
_ALLOWED_LICENSES: frozenset[str] = frozenset({"internal", "CC0", "MIT"})

_CATEGORY_KIT_LIBRARY = "kit_library"

_REASON_NOT_LOADED = "kit_library_not_loaded"
_REASON_DIRECTORY_MISSING = "kit_library_directory_missing"
_REASON_CATEGORY_DIRECTORY_MISSING = "category_directory_missing"
_REASON_KIT_PART_UNREADABLE = "kit_part_unreadable"
_REASON_KIT_PART_MALFORMED = "kit_part_malformed"
_REASON_SCHEMA_VIOLATION_PREFIX = "kit_part_schema_violation"
_REASON_DUPLICATE_NAME_PREFIX = "kit_part_duplicate_name"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_base_path() -> Path:
    return _repo_root() / "std" / "kits" / "hardsurface"


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KitSocket:
    """Immutable kit-part attachment socket."""

    name: str
    anchor_axis: str
    default_position: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "anchor_axis": self.anchor_axis,
            "default_position": list(self.default_position),
        }


@dataclass(frozen=True)
class PlacementConstraint:
    """Immutable placement constraints for the part on a host surface."""

    face: str
    normal_axis: str
    requires_flat_surface: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "face": self.face,
            "normal_axis": self.normal_axis,
            "requires_flat_surface": self.requires_flat_surface,
        }


@dataclass(frozen=True)
class ScaleRange:
    """Immutable scale range with non-negative bounds (max >= min)."""

    min_scale: float
    max_scale: float

    def to_dict(self) -> dict[str, Any]:
        return {"min": self.min_scale, "max": self.max_scale}


@dataclass(frozen=True)
class LODBehavior:
    """Immutable LOD-chain participation policy."""

    strategy: str
    retained_for_collision: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "retained_for_collision": self.retained_for_collision,
        }


@dataclass(frozen=True)
class Provenance:
    """Immutable provenance record (source + version + license)."""

    source: str
    version: str
    license: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "version": self.version,
            "license": self.license,
        }


@dataclass(frozen=True)
class KitPart:
    """Immutable single kit-part metadata record."""

    name: str
    category: str
    kind: str
    procedural_recipe: dict[str, Any] | None
    mesh_stub_uri: str | None
    material_zones: tuple[str, ...]
    sockets: tuple[KitSocket, ...]
    placement_constraints: PlacementConstraint
    scale_range: ScaleRange
    allowed_families: tuple[str, ...]
    lod_behavior: LODBehavior
    bake_group: str
    provenance: Provenance
    preview_thumbnail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "kind": self.kind,
            "procedural_recipe": (
                dict(self.procedural_recipe)
                if self.procedural_recipe is not None
                else None
            ),
            "mesh_stub_uri": self.mesh_stub_uri,
            "material_zones": list(self.material_zones),
            "sockets": [socket.to_dict() for socket in self.sockets],
            "placement_constraints": self.placement_constraints.to_dict(),
            "scale_range": self.scale_range.to_dict(),
            "allowed_families": list(self.allowed_families),
            "lod_behavior": self.lod_behavior.to_dict(),
            "bake_group": self.bake_group,
            "provenance": self.provenance.to_dict(),
            "preview_thumbnail": self.preview_thumbnail
            or _default_preview_thumbnail(self.category, self.name),
        }


@dataclass(frozen=True)
class SkippedReason:
    """Structured skipped-evidence record (category + reason token)."""

    category: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "reason": self.reason}


@dataclass(frozen=True)
class KitLibrary:
    """Aggregated view of all loaded kit parts."""

    base_path: str
    parts: tuple[KitPart, ...]
    skipped: tuple[SkippedReason, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_path": self.base_path,
            "parts": [part.to_dict() for part in self.parts],
            "skipped": [entry.to_dict() for entry in self.skipped],
        }


# ---------------------------------------------------------------------------
# Internal validator (hand-rolled — does not require ``jsonschema`` to keep
# this layer dependency-free; the JSON schema file is the source of truth).
# ---------------------------------------------------------------------------


def _validate_part_payload(payload: Any) -> tuple[KitPart | None, str | None]:
    """Validate a single parsed kit-part payload.

    Returns ``(part, None)`` on success or ``(None, "<schema_violation_detail>")``
    on failure. The detail is a short token (e.g.
    ``"missing_field_name"``) suitable for appending to the
    ``kit_part_schema_violation`` skipped-reason token so authors can
    debug from evidence alone.
    """
    if not isinstance(payload, dict):
        return None, "not_object"

    required_top_level = (
        "name",
        "category",
        "kind",
        "material_zones",
        "sockets",
        "placement_constraints",
        "scale_range",
        "allowed_families",
        "lod_behavior",
        "bake_group",
        "provenance",
    )
    allowed_top_level = (
        *required_top_level,
        "procedural_recipe",
        "mesh_stub_uri",
        "preview_thumbnail",
    )
    for field in required_top_level:
        if field not in payload:
            return None, f"missing_field_{field}"
    extra_fields = sorted(set(payload) - set(allowed_top_level))
    if extra_fields:
        return None, f"unexpected_field_{extra_fields[0]}"

    name = payload["name"]
    if not isinstance(name, str) or not name:
        return None, "invalid_field_name"

    category = payload["category"]
    if category not in REQUIRED_CATEGORIES:
        return None, "invalid_field_category"

    kind = payload["kind"]
    if kind not in _ALLOWED_KINDS:
        return None, "invalid_field_kind"

    procedural_recipe_raw = payload.get("procedural_recipe")
    procedural_recipe: dict[str, Any] | None
    if kind == "procedural":
        if not isinstance(procedural_recipe_raw, dict):
            return None, "missing_field_procedural_recipe"
        procedural_recipe = dict(procedural_recipe_raw)
    else:
        procedural_recipe = None

    mesh_stub_uri_raw = payload.get("mesh_stub_uri")
    mesh_stub_uri: str | None
    if kind == "mesh_stub":
        if not isinstance(mesh_stub_uri_raw, str) or not mesh_stub_uri_raw:
            return None, "missing_field_mesh_stub_uri"
        mesh_stub_uri = mesh_stub_uri_raw
    else:
        mesh_stub_uri = None

    zones_raw = payload["material_zones"]
    if not isinstance(zones_raw, list) or not all(
        isinstance(item, str) and item for item in zones_raw
    ):
        return None, "invalid_field_material_zones"
    material_zones = tuple(zones_raw)

    sockets_raw = payload["sockets"]
    if not isinstance(sockets_raw, list):
        return None, "invalid_field_sockets"
    sockets: list[KitSocket] = []
    for raw in sockets_raw:
        if not isinstance(raw, dict):
            return None, "invalid_field_sockets"
        socket_name = raw.get("name")
        anchor_axis = raw.get("anchor_axis")
        position = raw.get("default_position")
        if not isinstance(socket_name, str) or not socket_name:
            return None, "invalid_field_sockets_name"
        if anchor_axis not in _ALLOWED_AXES:
            return None, "invalid_field_sockets_anchor_axis"
        if (
            not isinstance(position, list)
            or len(position) != 3
            or not all(isinstance(coord, (int, float)) for coord in position)
        ):
            return None, "invalid_field_sockets_default_position"
        sockets.append(
            KitSocket(
                name=socket_name,
                anchor_axis=anchor_axis,
                default_position=(float(position[0]), float(position[1]), float(position[2])),
            )
        )

    placement_raw = payload["placement_constraints"]
    if not isinstance(placement_raw, dict):
        return None, "invalid_field_placement_constraints"
    face = placement_raw.get("face")
    normal_axis = placement_raw.get("normal_axis")
    requires_flat_surface = placement_raw.get("requires_flat_surface")
    if face not in _ALLOWED_FACES:
        return None, "invalid_field_placement_constraints_face"
    if normal_axis not in _ALLOWED_NORMAL_AXES:
        return None, "invalid_field_placement_constraints_normal_axis"
    if not isinstance(requires_flat_surface, bool):
        return None, "invalid_field_placement_constraints_requires_flat_surface"
    placement = PlacementConstraint(
        face=face,
        normal_axis=normal_axis,
        requires_flat_surface=requires_flat_surface,
    )

    scale_raw = payload["scale_range"]
    if not isinstance(scale_raw, dict):
        return None, "invalid_field_scale_range"
    min_scale = scale_raw.get("min")
    max_scale = scale_raw.get("max")
    if not isinstance(min_scale, (int, float)) or min_scale <= 0:
        return None, "invalid_field_scale_range_min"
    if not isinstance(max_scale, (int, float)) or max_scale <= 0:
        return None, "invalid_field_scale_range_max"
    if max_scale < min_scale:
        return None, "invalid_field_scale_range_order"
    scale_range = ScaleRange(min_scale=float(min_scale), max_scale=float(max_scale))

    families_raw = payload["allowed_families"]
    if (
        not isinstance(families_raw, list)
        or not families_raw
        or not all(isinstance(item, str) and item for item in families_raw)
    ):
        return None, "invalid_field_allowed_families"
    allowed_families = tuple(families_raw)

    lod_raw = payload["lod_behavior"]
    if not isinstance(lod_raw, dict):
        return None, "invalid_field_lod_behavior"
    strategy = lod_raw.get("strategy")
    retained_for_collision = lod_raw.get("retained_for_collision")
    if strategy not in _ALLOWED_LOD_STRATEGIES:
        return None, "invalid_field_lod_behavior_strategy"
    if not isinstance(retained_for_collision, bool):
        return None, "invalid_field_lod_behavior_retained_for_collision"
    lod_behavior = LODBehavior(
        strategy=strategy, retained_for_collision=retained_for_collision
    )

    bake_group = payload["bake_group"]
    if not isinstance(bake_group, str) or not bake_group:
        return None, "invalid_field_bake_group"

    provenance_raw = payload["provenance"]
    if not isinstance(provenance_raw, dict):
        return None, "invalid_field_provenance"
    source = provenance_raw.get("source")
    version = provenance_raw.get("version")
    license_value = provenance_raw.get("license")
    if not isinstance(source, str) or not source:
        return None, "invalid_field_provenance_source"
    if not isinstance(version, str) or not version:
        return None, "invalid_field_provenance_version"
    if license_value not in _ALLOWED_LICENSES:
        return None, "invalid_field_provenance_license"
    provenance = Provenance(source=source, version=version, license=license_value)
    preview_thumbnail_raw = payload.get("preview_thumbnail")
    if preview_thumbnail_raw is None:
        preview_thumbnail = _default_preview_thumbnail(category, name)
    elif isinstance(preview_thumbnail_raw, str) and preview_thumbnail_raw:
        preview_thumbnail = preview_thumbnail_raw
    else:
        return None, "invalid_field_preview_thumbnail"

    return (
        KitPart(
            name=name,
            category=category,
            kind=kind,
            procedural_recipe=procedural_recipe,
            mesh_stub_uri=mesh_stub_uri,
            material_zones=material_zones,
            sockets=tuple(sockets),
            placement_constraints=placement,
            scale_range=scale_range,
            allowed_families=allowed_families,
            lod_behavior=lod_behavior,
            bake_group=bake_group,
            provenance=provenance,
            preview_thumbnail=preview_thumbnail,
        ),
        None,
    )


def _default_preview_thumbnail(category: str, name: str) -> str:
    return f"kit://hardsurface/{category}/{name}/preview_thumbnail"


# ---------------------------------------------------------------------------
# Disk loader
# ---------------------------------------------------------------------------


def _resolve_base_path(base_path: Path | None) -> Path:
    if base_path is None:
        return _default_base_path()
    return base_path if isinstance(base_path, Path) else Path(str(base_path))


def _read_json(path: Path) -> tuple[Any, str | None]:
    """Return ``(parsed, error_token)`` for a JSON file at ``path``.

    ``error_token`` is ``None`` on success, ``_REASON_KIT_PART_UNREADABLE``
    when the file cannot be read, or ``_REASON_KIT_PART_MALFORMED`` when
    the bytes are not valid JSON. The loader never raises.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, _REASON_KIT_PART_UNREADABLE
    try:
        return json.loads(text), None
    except (json.JSONDecodeError, ValueError):
        return None, _REASON_KIT_PART_MALFORMED


def load_kit_library(base_path: Path | None = None) -> KitLibrary:
    """Load the standard hard-surface kit library from disk.

    Args:
        base_path: filesystem root that contains the five MVP category
            subdirectories. Defaults to the repository's
            ``std/kits/hardsurface/`` directory.

    Returns:
        A :class:`KitLibrary` populated with every kit part that
        parsed and validated successfully. Files that fail produce
        structured :class:`SkippedReason` entries instead of raising.
        A missing ``base_path`` directory yields an empty library
        with a single ``("kit_library", "kit_library_directory_missing")``
        skipped record so the validator can surface the gap as
        evidence.

    Behavior:
        - Missing base directory -> empty library + ``kit_library_directory_missing``.
        - Missing category subdirectory -> ``("category_<name>", "category_directory_missing")``.
        - Unreadable JSON file -> ``("kit_part_<filename>", "kit_part_unreadable")``.
        - Invalid JSON -> ``("kit_part_<filename>", "kit_part_malformed")``.
        - Schema violation -> ``("kit_part_<filename>", "kit_part_schema_violation:<detail>")``.
        - Duplicate name -> ``("kit_part_<filename>", "kit_part_duplicate_name:<name>")``.
    """
    root = _resolve_base_path(base_path)
    base_path_str = str(root)

    if not root.exists() or not root.is_dir():
        return KitLibrary(
            base_path=base_path_str,
            parts=(),
            skipped=(
                SkippedReason(
                    category=_CATEGORY_KIT_LIBRARY,
                    reason=_REASON_DIRECTORY_MISSING,
                ),
            ),
        )

    parts: list[KitPart] = []
    skipped: list[SkippedReason] = []
    seen_part_names: set[str] = set()

    for category in REQUIRED_CATEGORIES:
        category_dir = root / category
        if not category_dir.exists() or not category_dir.is_dir():
            skipped.append(
                SkippedReason(
                    category=f"category_{category}",
                    reason=_REASON_CATEGORY_DIRECTORY_MISSING,
                )
            )
            continue

        try:
            entries = sorted(entry.name for entry in category_dir.iterdir())
        except OSError:
            skipped.append(
                SkippedReason(
                    category=f"category_{category}",
                    reason=_REASON_CATEGORY_DIRECTORY_MISSING,
                )
            )
            continue

        for entry in entries:
            if not entry.endswith(".json"):
                continue
            file_path = category_dir / entry
            if not file_path.is_file():
                continue
            payload, error = _read_json(file_path)
            file_token = f"kit_part_{entry}"
            if error is not None:
                skipped.append(SkippedReason(category=file_token, reason=error))
                continue
            part, violation = _validate_part_payload(payload)
            if violation is not None:
                skipped.append(
                    SkippedReason(
                        category=file_token,
                        reason=f"{_REASON_SCHEMA_VIOLATION_PREFIX}:{violation}",
                    )
                )
                continue
            if part is not None and part.category != category:
                skipped.append(
                    SkippedReason(
                        category=file_token,
                        reason=f"{_REASON_SCHEMA_VIOLATION_PREFIX}:invalid_field_category",
                    )
                )
                continue
            if part is not None:
                if part.name in seen_part_names:
                    skipped.append(
                        SkippedReason(
                            category=file_token,
                            reason=f"{_REASON_DUPLICATE_NAME_PREFIX}:{part.name}",
                        )
                    )
                    continue
                seen_part_names.add(part.name)
                parts.append(part)

    parts.sort(key=lambda candidate: (candidate.category, candidate.name))
    skipped.sort(key=lambda record: (record.category, record.reason))

    return KitLibrary(
        base_path=base_path_str,
        parts=tuple(parts),
        skipped=tuple(skipped),
    )


def lookup_kit_part(library: KitLibrary, name: str) -> KitPart | None:
    """Return the kit part with ``name`` or ``None`` if missing."""
    if not isinstance(name, str) or not name:
        return None
    for part in library.parts:
        if part.name == name:
            return part
    return None


def kit_parts_by_category(library: KitLibrary, category: str) -> tuple[KitPart, ...]:
    """Return all parts with ``category``. Sorted by name."""
    if not isinstance(category, str) or not category:
        return ()
    matched = [part for part in library.parts if part.category == category]
    matched.sort(key=lambda candidate: candidate.name)
    return tuple(matched)


def kit_parts_for_family(library: KitLibrary, family: str) -> tuple[KitPart, ...]:
    """Return all parts whose ``allowed_families`` matches ``family``.

    Parts that include ``"*"`` in ``allowed_families`` always match.
    Sorted by ``(category, name)`` so consumers see a stable order.
    """
    if not isinstance(family, str) or not family:
        return ()
    matched: list[KitPart] = []
    for part in library.parts:
        families = part.allowed_families
        if "*" in families or family in families:
            matched.append(part)
    matched.sort(key=lambda candidate: (candidate.category, candidate.name))
    return tuple(matched)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def _resolve_asset_name(asset: dict[str, Any]) -> str:
    name = asset.get("name") if isinstance(asset, dict) else None
    if isinstance(name, str) and name:
        return name
    return "unnamed_asset"


def _resolve_family(asset: dict[str, Any], runtime: dict[str, Any]) -> str:
    if isinstance(runtime, dict):
        design_brief = runtime.get("design_brief")
        if isinstance(design_brief, dict):
            inference = design_brief.get("family_inference")
            if isinstance(inference, dict):
                matched = inference.get("matched_family")
                if isinstance(matched, str) and matched:
                    return matched
    if isinstance(asset, dict):
        family = asset.get("family")
        if isinstance(family, str) and family:
            return family
    return "generic"


def _coerce_kit_library(raw: Any) -> KitLibrary | None:
    """Accept either a :class:`KitLibrary` directly or a JSON-shaped dict.

    The executor publishes the dataclass; defensive callers (and tests)
    may publish a raw dict. Both shapes are coerced into the dataclass
    view so the validator's logic is uniform downstream.
    """
    if isinstance(raw, KitLibrary):
        return raw
    if not isinstance(raw, dict):
        return None
    parts: list[KitPart] = []
    raw_parts = raw.get("parts")
    if isinstance(raw_parts, list):
        for entry in raw_parts:
            part, violation = _validate_part_payload(entry)
            if violation is None and part is not None:
                parts.append(part)
    skipped: list[SkippedReason] = []
    raw_skipped = raw.get("skipped")
    if isinstance(raw_skipped, list):
        for entry in raw_skipped:
            if not isinstance(entry, dict):
                continue
            category = entry.get("category")
            reason = entry.get("reason")
            if isinstance(category, str) and isinstance(reason, str) and category and reason:
                skipped.append(SkippedReason(category=category, reason=reason))
    base_path = raw.get("base_path")
    base_path_str = base_path if isinstance(base_path, str) else ""
    parts.sort(key=lambda candidate: (candidate.category, candidate.name))
    skipped.sort(key=lambda record: (record.category, record.reason))
    return KitLibrary(
        base_path=base_path_str,
        parts=tuple(parts),
        skipped=tuple(skipped),
    )


def _build_summary(
    library: KitLibrary, family: str
) -> dict[str, Any]:
    parts_by_category: dict[str, int] = {category: 0 for category in REQUIRED_CATEGORIES}
    for part in library.parts:
        if part.category in parts_by_category:
            parts_by_category[part.category] += 1
    categories_covered = sum(1 for count in parts_by_category.values() if count >= 1)
    all_required_categories_present = categories_covered == len(REQUIRED_CATEGORIES)
    parts_for_family = kit_parts_for_family(library, family)
    return {
        "part_count": len(library.parts),
        "parts_by_category": parts_by_category,
        "categories_covered": categories_covered,
        "all_required_categories_present": all_required_categories_present,
        "parts_for_family_count": len(parts_for_family),
    }


def _normalize_skipped(records: tuple[SkippedReason, ...]) -> list[SkippedReason]:
    seen: set[tuple[str, str]] = set()
    out: list[SkippedReason] = []
    for record in records:
        key = (record.category, record.reason)
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    out.sort(key=lambda record: (record.category, record.reason))
    return out


def _experimental_kit_declared_parts(asset: dict[str, Any]) -> list[str]:
    """Return the user-declared kit part list from ``experimental.kit.use``.

    Phase 13: returns the deduplicated list of strings the author
    declared inside ``experimental.kit.use``. Tolerates absence and
    non-string entries by skipping them; returns ``[]`` when the
    block is missing entirely. Surfaced in the kit-library evidence
    payload as ``user_provided_via_experimental.declared_parts`` —
    Phase 13 does NOT filter the loaded library by this list, the
    declaration is informational evidence only.
    """
    if not isinstance(asset, dict):
        return []
    experimental = asset.get("experimental")
    if not isinstance(experimental, dict):
        return []
    kit_block = experimental.get("kit")
    if not isinstance(kit_block, dict):
        return []
    raw_use = kit_block.get("use")
    if not isinstance(raw_use, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in raw_use:
        if not isinstance(entry, str):
            continue
        if entry in seen:
            continue
        seen.add(entry)
        out.append(entry)
    return out


def _empty_library_payload(
    asset_name: str, family: str, declared_parts: list[str]
) -> dict[str, Any]:
    library = KitLibrary(base_path="", parts=(), skipped=())
    return {
        "version": KIT_LIBRARY_VERSION,
        "asset_name": asset_name,
        "family": family,
        "library": library.to_dict(),
        "summary": _build_summary(library, family),
        "skipped_reasons": [
            SkippedReason(
                category=_CATEGORY_KIT_LIBRARY, reason=_REASON_NOT_LOADED
            ).to_dict()
        ],
        "warnings": [],
        "diagnostics": [],
        "user_provided_via_experimental": {"declared_parts": list(declared_parts)},
    }


def evaluate_kit_library(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive Phase 12 kit-library payload.

    Args:
        asset: normalized asset dict. Reads ``asset["name"]`` for the
            payload header and ``asset.get("family")`` as a defensive
            fallback for the family slot.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["_kit_library"]`` only — the executor publishes
            this slot before the validate stage runs by calling
            :func:`load_kit_library`. No other runtime view is
            consumed.

    Returns:
        Additive payload with ``version`` (``"kit_library_v1"``),
        ``asset_name``, ``family``, ``library`` (kit metadata
        serialised), ``summary`` (counts + ``all_required_categories_present``
        flag), ``skipped_reasons`` (deduplicated and sorted),
        ``warnings`` (always empty in Phase 12), and ``diagnostics``
        (always empty — Phase 12 is informational only and never
        blocks certification).
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    asset_name = _resolve_asset_name(safe_asset)
    family = _resolve_family(safe_asset, safe_runtime)
    declared_parts = _experimental_kit_declared_parts(safe_asset)

    raw = safe_runtime.get("_kit_library")
    if raw is None:
        return _empty_library_payload(asset_name, family, declared_parts)

    library = _coerce_kit_library(raw)
    if library is None:
        return _empty_library_payload(asset_name, family, declared_parts)

    skipped_records = _normalize_skipped(library.skipped)

    return {
        "version": KIT_LIBRARY_VERSION,
        "asset_name": asset_name,
        "family": family,
        "library": library.to_dict(),
        "summary": _build_summary(library, family),
        "skipped_reasons": [record.to_dict() for record in skipped_records],
        "warnings": [],
        "diagnostics": [],
        "user_provided_via_experimental": {"declared_parts": list(declared_parts)},
    }
