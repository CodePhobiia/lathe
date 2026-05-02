"""Phase 9 deterministic preview-evidence layer.

Categorizes the previews requested by ``asset.package.previews``,
records expected per-preview paths, attaches bake-map evidence
sourced from the surface bundle, and emits structured skipped
reasons whenever a category is intentionally absent. The result is
the additive ``preview_evidence`` payload published on the
validate-stage report so reviewers can tell the *final beauty*
preview apart from the *material-ID*, *wireframe*, *UV layout*,
*collision*, *LOD sheet*, *normal / AO / curvature / id* bake-map
imagery, and the optional *before / after* comparison sheet.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 11.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 9 (§9.1 - §9.3).
Per-category reference: ``docs/asset-quality/preview-evidence-v1.md``.

Design summary
--------------

Phase 9 is **evidence + diagnostic only**. It does not run a
renderer, drive Blender, or produce a comparison sheet — those
producers belong to the package stage (which runs *after* validate
in :data:`lathe.executor.STAGE_ORDER`) and to forward phases that
add a real before / after pipeline.

Because validate runs before package, the evaluator cannot inspect
the previews on disk. Instead it reads the **declared** preview
list from ``executor.asset["build"]["package"]["previews"]`` and
emits the deterministic per-name paths the package stage will
later write under ``stages/package/previews/<name>.png`` (relative
to the asset's ``out_dir``). The build is deterministic, so a
declared path is truthful — the package stage cannot deviate from
it.

Bake-map evidence comes from ``runtime["surface"]["bundle"]``
(``maps`` + ``outputs``) which IS populated by the surface stage
before validate runs. Per ``AGENTS.md``, every absent map records
a structured ``skipped_reason`` instead of a fabricated path.

Preview categories
------------------

The evaluator maps the six standard preview names declared in
``lathe/core/stages/package.py`` (``"turntable"``, ``"wireframe"``,
``"material_ids"``, ``"uv_layout"``, ``"collision"``, ``"lod_sheet"``)
to the six top-level categories the report exposes:

- ``final_beauty`` — the ``"turntable"`` preview rendered in mode
  ``"shaded"``. The category that actually shows final art quality.
- ``material_ids`` — the ``"material_ids"`` debug preview rendered
  in mode ``"material_ids"``. Useful for material zone review,
  *not* a substitute for the final beauty preview.
- ``wireframe`` — the ``"wireframe"`` topology preview rendered in
  mode ``"wireframe"``.
- ``uv_layout`` — the ``"uv_layout"`` preview produced by
  :func:`lathe.core.rendering.render_uv_layout`.
- ``collision`` — the ``"collision"`` preview rendered in mode
  ``"wireframe"`` over the collision mesh.
- ``lod_sheet`` — the ``"lod_sheet"`` 2x2 grid produced by
  :func:`lathe.core.rendering.render_lod_sheet`.

Two additional categories live alongside the renderable previews:

- ``bake_maps`` — per-map evidence (``normal``, ``ao``,
  ``curvature``, ``id``) sourced from the surface bundle.
- ``comparison_sheet`` — the optional before / after sheet. Phase 9
  intentionally does not ship a renderer for this category since
  the rendering layer does not yet have a before / after
  pipeline; the category is always emitted with a structured
  skipped reason.

Final beauty distinction
------------------------

The ``distinct_final_from_material_ids`` flag is the single
truthful signal that a build's evidence carries an art-quality
preview that is not just a debug material-ID render. It is True
iff:

1. the final beauty preview is requested (``"turntable"``), AND
2. the material-ID preview is requested (``"material_ids"``), AND
3. the two paths are distinct.

If only ``"material_ids"`` is requested without ``"turntable"``,
the flag is False *and* a warning fires so reviewers know the
package config is missing the final beauty preview.

Skipped-evidence contract
-------------------------

Every skipped category emits a single structured record under
``skipped_reasons`` with a known ``reason`` token:

- ``preview_not_requested_by_package_config`` — the preview is not
  declared in ``package.previews``.
- ``preview_role_not_recognized`` — an unknown preview name was
  declared. The category is recorded as ``unknown_preview_<name>``
  so reviewers can spot the typo.
- ``bake_map_not_produced`` — the surface bundle did not publish a
  URI for the canonical bake map.
- ``comparison_sheet_not_requested`` — the optional comparison
  sheet was not requested.
- ``comparison_sheet_renderer_unavailable`` — the comparison sheet
  was requested but Phase 9 does not yet ship a renderer for it.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``material_wear_graph`` and before
``geometry_integrity``. Output additively appears under the
top-level ``preview_evidence`` key of the validate-stage report
(the 23rd top-level key, on top of the 22 that Phases 0 through 8
publish).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PREVIEW_EVIDENCE_VERSION = "preview_evidence_v1"


# Preview-name -> (category, mode) mapping. Mirrors the canonical
# render dispatch in ``lathe/core/stages/package.py`` lines ~167-200.
# Iteration order is fixed so emitted entries land in declaration
# order regardless of how a `.lth` file orders the preview names.
_STANDARD_PREVIEW_ROUTES: tuple[tuple[str, str, str], ...] = (
    ("turntable", "final_beauty", "shaded"),
    ("wireframe", "wireframe", "wireframe"),
    ("material_ids", "material_ids", "material_ids"),
    ("uv_layout", "uv_layout", "uv_layout"),
    ("collision", "collision", "wireframe"),
    ("lod_sheet", "lod_sheet", "lod_sheet"),
)


# Fixed emission order for the ``previews`` dict so the JSON shape
# is stable across Python versions and runs.
_PREVIEW_CATEGORY_ORDER: tuple[str, ...] = (
    "final_beauty",
    "material_ids",
    "wireframe",
    "uv_layout",
    "collision",
    "lod_sheet",
    "bake_maps",
    "comparison_sheet",
)


# Categories that are declared by ``package.previews`` (i.e. the
# six categories the package stage actually renders).
_RENDERABLE_CATEGORIES: frozenset[str] = frozenset(
    {
        "final_beauty",
        "material_ids",
        "wireframe",
        "uv_layout",
        "collision",
        "lod_sheet",
    }
)


# Bake-map roles the evaluator recognises. Order is the canonical
# emission order — same as Phase 7's ``_EXPECTED_BAKE_MAPS``.
_EXPECTED_BAKE_MAPS: tuple[tuple[str, str], ...] = (
    ("normal", "normal_map"),
    ("ao", "ao_map"),
    ("curvature", "curvature_map"),
    ("id", "id_map"),
)


_PREVIEW_DIR_RELPATH = "stages/package/previews"


@dataclass(frozen=True)
class PreviewEntry:
    """One declared preview entry under a renderable category.

    The ``status`` field is always ``"declared"`` — Phase 9 does not
    touch the filesystem, so the evaluator cannot promote the entry
    to ``"present"`` or ``"missing"``. A future phase that runs the
    package stage before validate could flip the status by inspecting
    the on-disk file.
    """

    role: str
    mode: str
    name: str
    path: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "mode": self.mode,
            "name": self.name,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True)
class BakeMapEntry:
    """One bake-map evidence entry sourced from the surface bundle.

    ``uri`` is ``None`` when the map name is declared in
    ``surface.bundle.maps`` but no URI is published under
    ``surface.bundle.outputs``. The evaluator never invents a path
    in that case — the entry is recorded with ``status="declared"``
    and the absence is captured in ``skipped_reasons`` instead.
    """

    role: str
    uri: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "uri": self.uri, "status": self.status}


@dataclass(frozen=True)
class SkippedReason:
    """One structured skipped-evidence record.

    Exactly two fields per record: ``category`` (the category that
    was skipped, or ``unknown_preview_<name>`` for unrecognised
    declared names) and ``reason`` (a token from the fixed
    skipped-reason vocabulary documented in the module docstring).
    """

    category: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"category": self.category, "reason": self.reason}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_str_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _is_external_or_absolute_uri(uri: str) -> bool:
    normalized = uri.replace("\\", "/")
    return (
        "://" in normalized
        or normalized.startswith("/")
        or (len(normalized) >= 2 and normalized[1] == ":")
    )


def _asset_root_surface_map_uri(uri: str, map_name: str) -> str | None:
    """Return an asset-root-resolvable surface-map URI.

    The surface stage writes its bundle from ``stages/surface`` and often
    records map-local URIs such as ``maps/normal.png``. The validate report is
    consumed from the asset root, so Phase 9 lifts those links to
    ``stages/surface/maps/<name>.png``. Absolute or external URIs are rejected
    because they are not asset-root-resolvable report links.
    """
    normalized = uri.replace("\\", "/").strip()
    if not normalized or _is_external_or_absolute_uri(normalized):
        return None
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("stages/surface/maps/"):
        return normalized
    if normalized.startswith("surface/maps/"):
        return f"stages/{normalized}"
    if normalized.startswith("maps/"):
        return f"stages/surface/{normalized}"
    if "/" not in normalized:
        return f"stages/surface/maps/{normalized}"
    if normalized.startswith("stages/"):
        return normalized
    # Unknown relative paths may still be asset-root-resolvable, but surface
    # bake maps are expected under stages/surface/maps. Keep the evidence
    # conservative instead of publishing a misleading link.
    extension = normalized.rsplit(".", 1)[-1] if "." in normalized else "png"
    return f"stages/surface/maps/{map_name}.{extension}"


def _resolve_asset_name(asset: dict[str, Any]) -> str:
    name = asset.get("name")
    if isinstance(name, str) and name:
        return name
    return "unnamed_asset"


def _package_config(asset: dict[str, Any]) -> dict[str, Any]:
    """Return the asset's normalized package config dict.

    Reads ``asset["build"]["package"]`` first (the post-resolver shape)
    and falls back to ``asset["package"]`` for parity with how other
    validators treat the asset dict. Both pathways are tolerated for
    fixture portability — the runtime executor uses the
    ``asset["package"]`` shape.
    """
    package_cfg = _as_dict(_as_dict(asset.get("build")).get("package"))
    if not package_cfg:
        package_cfg = _as_dict(asset.get("package"))
    return package_cfg


def _requested_preview_names(asset: dict[str, Any]) -> list[str]:
    """Return the list of declared preview names, preserving order."""
    package_cfg = _package_config(asset)
    raw = package_cfg.get("previews")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, str)]


def _comparison_sheet_requested(asset: dict[str, Any]) -> bool:
    package_cfg = _package_config(asset)
    return bool(package_cfg.get("comparison_sheet", False))


def _surface_bundle(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("surface")).get("bundle"))


def _resolve_bake_map_uri(outputs: dict[str, Any], map_name: str) -> str | None:
    """Return the URI string for ``map_name`` or ``None`` if not present.

    Mirrors :func:`lathe.asset_quality.highlow_relation._resolve_bake_map_uri`:
    outputs may store either a flat string URI or a nested entry dict
    with a ``uri`` field (the surface stage uses the dict shape). Both
    are tolerated.
    """
    entry = outputs.get(map_name)
    if isinstance(entry, str) and entry:
        return _asset_root_surface_map_uri(entry, map_name)
    if isinstance(entry, dict):
        uri = _as_str_or_none(entry.get("uri"))
        if uri is None:
            return None
        return _asset_root_surface_map_uri(uri, map_name)
    return None


def _bake_outputs(surface_bundle: dict[str, Any]) -> dict[str, Any]:
    """Return the merged bake outputs dict.

    Mirrors :func:`lathe.asset_quality.highlow_relation._bake_map_outputs`:
    ``bake_outputs`` (when present) is the canonical map-name -> URI
    short-form. ``outputs`` carries the full per-map record. Either
    is tolerated; the canonical short-form takes precedence.
    """
    bake_outputs = _as_dict(surface_bundle.get("bake_outputs"))
    outputs = _as_dict(surface_bundle.get("outputs"))
    merged: dict[str, Any] = dict(outputs)
    for map_name, value in bake_outputs.items():
        if value:
            merged[map_name] = value
    return merged


def _surface_map_names(surface_bundle: dict[str, Any]) -> set[str]:
    """Return the set of bake-map names declared on the surface bundle."""
    raw = surface_bundle.get("maps")
    if not isinstance(raw, list):
        return set()
    return {entry for entry in raw if isinstance(entry, str)}


def _preview_path(name: str) -> str:
    """Return the deterministic relpath the package stage writes."""
    return f"{_PREVIEW_DIR_RELPATH}/{name}.png"


def _categorize_previews(
    requested_names: list[str],
) -> tuple[
    dict[str, list[PreviewEntry]],
    list[SkippedReason],
]:
    """Categorize requested preview names into the six renderable buckets.

    Walks the standard preview routes in declaration order and emits
    a :class:`PreviewEntry` for each requested name that maps to a
    renderable category. Unknown names land in
    :class:`SkippedReason` with category
    ``unknown_preview_<name>`` and reason
    ``preview_role_not_recognized``. Renderable categories that are
    not declared in ``package.previews`` emit a single skipped entry
    with reason ``preview_not_requested_by_package_config``.

    Returns:
        A pair ``(categories, skipped)`` where ``categories`` maps
        each renderable category name to the list of declared
        :class:`PreviewEntry` records (possibly empty) and
        ``skipped`` carries the structured skipped reasons.
    """
    requested_set = set(requested_names)
    categories: dict[str, list[PreviewEntry]] = {
        category: [] for category in _RENDERABLE_CATEGORIES
    }
    skipped: list[SkippedReason] = []
    valid_route_names = {name for name, _, _ in _STANDARD_PREVIEW_ROUTES}

    for name, role, mode in _STANDARD_PREVIEW_ROUTES:
        if name not in requested_set:
            skipped.append(
                SkippedReason(
                    category=role,
                    reason="preview_not_requested_by_package_config",
                )
            )
            continue
        categories[role].append(
            PreviewEntry(
                role=role,
                mode=mode,
                name=name,
                path=_preview_path(name),
                status="declared",
            )
        )

    for name in requested_names:
        if name in valid_route_names:
            continue
        skipped.append(
            SkippedReason(
                category=f"unknown_preview_{name}",
                reason="preview_role_not_recognized",
            )
        )

    return categories, skipped


def _categorize_bake_maps(
    surface_bundle: dict[str, Any],
) -> tuple[list[BakeMapEntry], list[SkippedReason]]:
    """Resolve the four canonical bake maps from the surface bundle.

    Records a :class:`BakeMapEntry` for every canonical map either
    declared in ``surface.bundle.maps`` or published via
    ``surface.bundle.outputs`` / ``surface.bundle.bake_outputs``. Per
    ``AGENTS.md``, missing maps emit a structured skipped reason and
    never fabricate a path. When a map name is declared on the
    bundle but no URI is published, the entry carries
    ``uri=None`` and a ``bake_map_not_produced`` skipped reason is
    recorded so reviewers see the gap explicitly.

    Returns:
        ``(entries, skipped)`` where ``entries`` is the per-role
        :class:`BakeMapEntry` list (empty when the surface stage
        published no bake-map intent at all) and ``skipped`` carries
        one :class:`SkippedReason` per absent map.
    """
    outputs = _bake_outputs(surface_bundle)
    declared_maps = _surface_map_names(surface_bundle)
    entries: list[BakeMapEntry] = []
    skipped: list[SkippedReason] = []
    for map_name, role in _EXPECTED_BAKE_MAPS:
        uri = _resolve_bake_map_uri(outputs, map_name)
        declared = map_name in declared_maps or uri is not None
        if uri is not None:
            entries.append(BakeMapEntry(role=role, uri=uri, status="declared"))
            continue
        if declared:
            entries.append(BakeMapEntry(role=role, uri=None, status="declared"))
            skipped.append(
                SkippedReason(category=role, reason="bake_map_not_produced")
            )
            continue
        skipped.append(SkippedReason(category=role, reason="bake_map_not_produced"))
    return entries, skipped


def _comparison_sheet_skipped(
    requested: bool,
) -> SkippedReason:
    """Return the comparison-sheet skipped reason.

    Phase 9 intentionally does not ship a comparison-sheet
    renderer. When the package config does not request a
    comparison sheet, the ``comparison_sheet_not_requested`` token
    fires. When the config does request one, the
    ``comparison_sheet_renderer_unavailable`` token fires — Phase 9
    is intentionally truthful that the rendering layer does not
    yet have a before / after pipeline.
    """
    if not requested:
        return SkippedReason(
            category="comparison_sheet",
            reason="comparison_sheet_not_requested",
        )
    return SkippedReason(
        category="comparison_sheet",
        reason="comparison_sheet_renderer_unavailable",
    )


def _build_preview_summary(
    categories: dict[str, list[PreviewEntry]],
    bake_maps: list[BakeMapEntry],
    comparison_sheet_present: bool,
    total_preview_count: int,
) -> dict[str, Any]:
    """Compute the flat summary block consumed by humans + Phase 10.

    All ``*_present`` flags are truthful rendered-presence flags. Validate runs
    before package, so renderable previews are only declared/expected here and
    are not marked present. The companion ``*_declared`` flags carry the
    package-config intent Phase 10 can safely reason over.
    Bake-map count is the number of entries with a non-None URI (an
    entry with ``uri=None`` reflects an incomplete surface bundle and
    is recorded but not counted as present).
    """
    final_entries = categories.get("final_beauty", [])
    material_id_entries = categories.get("material_ids", [])
    wireframe_entries = categories.get("wireframe", [])
    final_beauty_declared = bool(final_entries)
    material_ids_declared = bool(material_id_entries)
    wireframe_declared = bool(wireframe_entries)
    final_beauty_present = False
    material_ids_present = False
    wireframe_present = False
    distinct_final_from_material_ids = False
    if final_beauty_declared and material_ids_declared:
        final_paths = {entry.path for entry in final_entries}
        material_id_paths = {entry.path for entry in material_id_entries}
        final_modes = {entry.mode for entry in final_entries}
        material_id_modes = {entry.mode for entry in material_id_entries}
        final_names = {entry.name for entry in final_entries}
        material_id_names = {entry.name for entry in material_id_entries}
        distinct_final_from_material_ids = bool(
            final_paths.isdisjoint(material_id_paths)
            and final_names.isdisjoint(material_id_names)
            and final_modes == {"shaded"}
            and material_id_modes == {"material_ids"}
        )
    bake_map_count = sum(1 for entry in bake_maps if entry.uri is not None)
    return {
        "final_beauty_present": final_beauty_present,
        "material_ids_present": material_ids_present,
        "wireframe_present": wireframe_present,
        "final_beauty_declared": final_beauty_declared,
        "material_ids_declared": material_ids_declared,
        "wireframe_declared": wireframe_declared,
        "bake_map_count": bake_map_count,
        "comparison_sheet_present": comparison_sheet_present,
        "comparison_sheet_requested": False,
        "comparison_sheet_renderer_available": False,
        "distinct_final_from_material_ids": distinct_final_from_material_ids,
        "total_preview_count": total_preview_count,
    }


def _build_report_links(
    categories: dict[str, list[PreviewEntry]],
    bake_maps: list[BakeMapEntry],
) -> list[str]:
    """Return the additive flat list of every declared preview path.

    Sort order: renderable categories in fixed emission order, then
    each entry within a category in declaration order, then bake-map
    URIs in canonical role order. Bake-map entries with ``uri=None``
    are skipped — only published URIs land in the link list.
    """
    links: list[str] = []
    for category in _PREVIEW_CATEGORY_ORDER:
        if category in _RENDERABLE_CATEGORIES:
            for entry in categories.get(category, []):
                if entry.path and entry.path not in links:
                    links.append(entry.path)
    for entry in bake_maps:
        if entry.uri and entry.uri not in links:
            links.append(entry.uri)
    return links


def _build_previews_payload(
    categories: dict[str, list[PreviewEntry]],
    bake_maps: list[BakeMapEntry],
) -> dict[str, list[dict[str, Any]]]:
    """Return the per-category preview entries in fixed emission order.

    The ``comparison_sheet`` bucket is always emitted as an empty
    list — Phase 9 does not yet produce a sheet, and the absence is
    captured in ``skipped_reasons`` instead.
    """
    payload: dict[str, list[dict[str, Any]]] = {}
    for category in _PREVIEW_CATEGORY_ORDER:
        if category == "bake_maps":
            payload[category] = [entry.to_dict() for entry in bake_maps]
        elif category == "comparison_sheet":
            payload[category] = []
        else:
            payload[category] = [
                entry.to_dict() for entry in categories.get(category, [])
            ]
    return payload


def _build_warnings(summary: dict[str, Any]) -> list[str]:
    """Return the warning list for the preview-evidence payload.

    Today the only warning fires when ``material_ids`` is requested
    without ``turntable``: that is the explicit failure mode the
    spec calls out — ``material_ids`` is a debug preview, not a
    final beauty preview, and a build that ships only debug imagery
    is not certifiably ready. Strict-mode behaviour is reserved for
    a forward phase.
    """
    warnings_list: list[str] = []
    if (
        not summary.get("final_beauty_declared", False)
        and summary.get("material_ids_declared", False)
    ):
        warnings_list.append(
            "package.previews requests 'material_ids' but not 'turntable' — "
            "final beauty preview is missing."
        )
    return warnings_list


def evaluate_preview_evidence(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive Phase 9 preview-evidence payload.

    Args:
        asset: normalized asset dict. Reads
            ``asset["build"]["package"]["previews"]`` (the preview
            declaration list) and ``asset["build"]["package"].get("comparison_sheet", False)``
            (the optional comparison-sheet flag).
        runtime: stage-bundle runtime dict. Reads
            ``runtime["surface"]["bundle"]["maps"]`` and
            ``runtime["surface"]["bundle"]["outputs"]`` /
            ``runtime["surface"]["bundle"]["bake_outputs"]`` for
            bake-map evidence.

    Returns:
        Additive payload with ``version`` (``"preview_evidence_v1"``),
        ``asset_name``, ``previews`` (per-category entries in fixed
        emission order), ``preview_summary`` (flat boolean / count
        block), ``report_links`` (additive flat list of declared
        preview paths and published bake-map URIs),
        ``skipped_reasons`` (structured skipped tokens, sorted by
        category), ``warnings`` (string list — non-empty when the
        package config requests material-ID without final beauty),
        and ``diagnostics`` (empty by default; reserved for forward
        phases).
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    asset_name = _resolve_asset_name(safe_asset)
    requested_names = _requested_preview_names(safe_asset)
    surface_bundle = _surface_bundle(safe_runtime)
    comparison_sheet_requested = _comparison_sheet_requested(safe_asset)

    categories, preview_skipped = _categorize_previews(requested_names)
    bake_maps, bake_skipped = _categorize_bake_maps(surface_bundle)

    comparison_sheet_skipped = _comparison_sheet_skipped(comparison_sheet_requested)

    skipped_records: list[SkippedReason] = []
    skipped_records.extend(preview_skipped)
    skipped_records.extend(bake_skipped)
    skipped_records.append(comparison_sheet_skipped)
    skipped_records.sort(key=lambda record: (record.category, record.reason))
    seen_skipped: set[tuple[str, str]] = set()
    deduped_skipped: list[SkippedReason] = []
    for record in skipped_records:
        key = (record.category, record.reason)
        if key in seen_skipped:
            continue
        seen_skipped.add(key)
        deduped_skipped.append(record)
    skipped_records = deduped_skipped

    total_preview_count = sum(
        len(categories.get(category, []))
        for category in _RENDERABLE_CATEGORIES
    )
    summary = _build_preview_summary(
        categories=categories,
        bake_maps=bake_maps,
        comparison_sheet_present=False,
        total_preview_count=total_preview_count,
    )
    summary["comparison_sheet_requested"] = comparison_sheet_requested
    warnings_list = _build_warnings(summary)
    previews_payload = _build_previews_payload(categories, bake_maps)
    report_links = _build_report_links(categories, bake_maps)

    return {
        "version": PREVIEW_EVIDENCE_VERSION,
        "asset_name": asset_name,
        "previews": previews_payload,
        "preview_summary": summary,
        "report_links": report_links,
        "skipped_reasons": [record.to_dict() for record in skipped_records],
        "warnings": warnings_list,
        "diagnostics": [],
    }
