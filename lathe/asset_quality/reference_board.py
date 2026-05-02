"""Phase 11 deterministic reference / moodboard ingestion.

Carries reference intent (mood / silhouette / materials / negatives)
through generation and reporting via an additive evidence layer.
Phase 11 is **evidence + diagnostic only** — it does not run a
renderer, drive Blender, or fetch external imagery. References are
loaded from a small filesystem convention by the executor and
published to ``runtime["_reference_board"]``; the validator
:func:`evaluate_reference_board` is a pure function that reads only
that runtime slot.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md``
Section 11.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 11
(Sections 11.1-11.5).
Per-feature reference: ``docs/asset-quality/reference-board-v1.md``.

Public-syntax constraint
------------------------

Phase 11 does NOT add any public ``.lth`` syntax. There is no
``references { ... }`` block in the grammar/parser/normalizer/
resolver/checker — reference loading is INTERNAL: the executor calls
:func:`load_reference_board` (a separately-tested disk loader) and
publishes the raw dict to ``runtime["_reference_board"]`` before the
validate stage runs. This mirrors the Phase 10 pattern that publishes
``runtime["_runtime_config"]`` for the vision-critique provider hook.
Phase 13 is the only phase allowed to expose this surface to
``.lth``.

Filesystem convention
---------------------

The default disk layout is::

    examples/refs/asset_quality/<asset_name>/
        mood.json          # optional palette / lighting / era / descriptors
        silhouette.json    # optional list of silhouette intents
        materials.json     # optional list of PBR target descriptors
        negative.json      # optional list of negative constraints

All four sub-files are optional. A missing directory yields no
reference board (the loader returns ``None``). A directory that
exists but is missing one or more sub-files emits structured
``reference_missing`` skipped reasons for each absent category — the
loader never fabricates a fixture. Malformed JSON emits
``reference_malformed`` and never crashes.

Loader / validator separation
-----------------------------

Two entry points keep filesystem reads and validator logic separate:

- :func:`load_reference_board` — disk loader. Returns a JSON-
  serialisable raw dict (NOT a dataclass) so the executor can carry
  it cleanly through ``runtime["_reference_board"]``. Returns
  ``None`` when no fixture exists at the convention path.
- :func:`evaluate_reference_board` — pure validator. Reads
  ``runtime["_reference_board"]`` only. Builds the frozen-dataclass
  view and the additive evidence payload.

Returned evidence shape
-----------------------

The validator emits the additive ``reference_board`` payload::

    {
        "version": "reference_board_v1",
        "asset_name": str,
        "family": str,
        "board": {
            "mood": {...} | None,
            "silhouettes": [...],
            "materials": [...],
            "negatives": [...],
        },
        "summary": {
            "has_mood": bool,
            "silhouette_count": int,
            "material_count": int,
            "negative_count": int,
            "all_required_present": bool,
        },
        "skipped_reasons": [
            {"category": ..., "reason": ...},
            ...
        ],
        "warnings": [],
        "diagnostics": [],
    }

``all_required_present`` is True iff a mood reference is present AND
at least one silhouette is present AND at least one material is
present. Negatives are optional for the flag but still merged into
the design brief when present.

Skipped-evidence contract
-------------------------

Per ``AGENTS.md``, every skipped category emits a single structured
record with one of the fixed reason tokens:

- ``reference_board_not_loaded`` — ``runtime["_reference_board"]``
  is absent (no fixture directory or executor never called the
  loader). The validator returns a well-formed empty payload.
- ``reference_missing`` — the fixture directory exists but the
  sub-file for the named category is absent.
- ``reference_malformed`` — the sub-file exists but is not valid
  JSON or its top-level shape is unparseable.

Skipped reasons are deduplicated and sorted by ``(category, reason)``
for determinism.

Negative-constraint integration
-------------------------------

The reference board's negatives are mirrored into the Phase 2
:func:`lathe.asset_quality.design_brief.evaluate_design_brief`
output. The design brief's existing ``negative_constraints`` field
(a tuple of strings) is extended with the reference negatives,
deduplicating while preserving order — existing brief values come
first, then the reference values. This is the ONLY edit Phase 11
makes to ``design_brief.py``.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``vision_critique`` and before
``geometry_integrity``. Output additively appears under the
top-level ``reference_board`` key of the validate-stage report
(the 25th top-level key, on top of the 24 that Phases 0 through 10
publish).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REFERENCE_BOARD_VERSION = "reference_board_v1"

_DEFAULT_BASE_PATH = Path("examples/refs/asset_quality")

_MOOD_FILENAME = "mood.json"
_SILHOUETTE_FILENAME = "silhouette.json"
_MATERIALS_FILENAME = "materials.json"
_NEGATIVE_FILENAME = "negative.json"

_CATEGORY_MOOD = "mood"
_CATEGORY_SILHOUETTE = "silhouette"
_CATEGORY_MATERIALS = "materials"
_CATEGORY_NEGATIVE = "negative"
_CATEGORY_REFERENCE_BOARD = "reference_board"

_REASON_MISSING = "reference_missing"
_REASON_MALFORMED = "reference_malformed"
_REASON_NOT_LOADED = "reference_board_not_loaded"
_REASON_LOADER_ERROR = "reference_loader_error"

_STATUS_LOADED = "loaded"
_STATUS_MISSING = "missing"
_STATUS_MALFORMED = "malformed"
_STATUS_ERROR = "error"

_CATEGORY_FILENAMES = {
    _CATEGORY_MOOD: _MOOD_FILENAME,
    _CATEGORY_SILHOUETTE: _SILHOUETTE_FILENAME,
    _CATEGORY_MATERIALS: _MATERIALS_FILENAME,
    _CATEGORY_NEGATIVE: _NEGATIVE_FILENAME,
}


@dataclass(frozen=True)
class MoodReference:
    """Immutable mood reference: palette / lighting / era / tags."""

    palette: tuple[str, ...]
    lighting: str
    era: str
    descriptors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "palette": list(self.palette),
            "lighting": self.lighting,
            "era": self.era,
            "descriptors": list(self.descriptors),
        }


@dataclass(frozen=True)
class SilhouetteReference:
    """Immutable silhouette intent: shape language + proportions."""

    intent: str
    proportions: dict[str, float]
    descriptors: tuple[str, ...]
    image_uri: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "proportions": dict(self.proportions),
            "descriptors": list(self.descriptors),
            "image_uri": self.image_uri,
        }


@dataclass(frozen=True)
class MaterialReference:
    """Immutable PBR material target reference."""

    target: str
    pbr_hints: dict[str, Any]
    descriptors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "pbr_hints": dict(self.pbr_hints),
            "descriptors": list(self.descriptors),
        }


@dataclass(frozen=True)
class NegativeReference:
    """Immutable negative constraint with rationale."""

    constraint: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint": self.constraint,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class SkippedReason:
    """Structured skipped-evidence record (category + reason token)."""

    category: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "reason": self.reason}


@dataclass(frozen=True)
class ReferenceBoard:
    """Aggregated view of all four reference categories for one asset."""

    asset_name: str
    family: str
    mood: MoodReference | None
    silhouettes: tuple[SilhouetteReference, ...]
    materials: tuple[MaterialReference, ...]
    negatives: tuple[NegativeReference, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mood": self.mood.to_dict() if self.mood is not None else None,
            "silhouettes": [entry.to_dict() for entry in self.silhouettes],
            "materials": [entry.to_dict() for entry in self.materials],
            "negatives": [entry.to_dict() for entry in self.negatives],
        }


# ---------------------------------------------------------------------------
# Disk loader
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_metadata(path: Path, *, status: str, reason: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "local_path": str(path),
        "status": status,
    }
    if reason:
        metadata["reason"] = reason
    if status == _STATUS_LOADED:
        try:
            metadata["sha256"] = _sha256_file(path)
            metadata["size_bytes"] = path.stat().st_size
        except OSError as exc:
            metadata["status"] = _STATUS_ERROR
            metadata["reason"] = str(exc)
    return metadata


def _issue(
    *,
    category: str,
    reason: str,
    message: str,
    path: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "category": category,
        "reason": reason,
        "message": message,
    }
    if path is not None:
        payload["path"] = path
    if index is not None:
        payload["index"] = index
    return payload


def _append_issue(
    skipped: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    *,
    category: str,
    reason: str,
    message: str,
    path: str | None = None,
    index: int | None = None,
) -> None:
    issue = _issue(category=category, reason=reason, message=message, path=path, index=index)
    skipped.append(issue)
    warnings.append(issue)
    diagnostics.append(
        {
            "code": "RB1001" if reason == _REASON_MISSING else "RB1002",
            "severity": "warning",
            "category": category,
            "reason": reason,
            "message": message,
            **({"path": path} if path is not None else {}),
            **({"index": index} if index is not None else {}),
        }
    )


def _resolve_base_path(base_path: Path | None) -> Path:
    if base_path is None:
        return _DEFAULT_BASE_PATH
    return base_path if isinstance(base_path, Path) else Path(str(base_path))


def _read_json(path: Path) -> tuple[Any, str | None, str | None]:
    """Return ``(parsed, error_token, error_message)`` for ``path``.

    ``error_token`` is ``None`` on success; ``"reference_malformed"``
    on parse failure or unreadable file. The loader never raises —
    every read goes through this helper so a corrupt fixture yields
    a structured skipped reason instead of a crash.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, _REASON_MALFORMED, str(exc)
    try:
        return json.loads(text), None, None
    except (json.JSONDecodeError, ValueError) as exc:
        return None, _REASON_MALFORMED, str(exc)


def _list_payload(payload: Any, key: str) -> list[Any] | None:
    """Extract the canonical list from a list-bearing JSON file.

    Tolerates two shapes for silhouette/materials/negative files:
    object-form ``{"<key>": [...]}`` (canonical) and direct-list-form
    ``[...]``. Returns ``None`` when neither shape applies so callers
    can emit a malformed skipped reason.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return None


def load_reference_board(
    asset_name: str, base_path: Path | None = None
) -> dict[str, Any] | None:
    """Load the per-asset reference board from disk.

    Args:
        asset_name: the asset identifier whose fixtures live under
            ``<base_path>/<asset_name>/``.
        base_path: filesystem root for asset-quality fixtures.
            Defaults to ``examples/refs/asset_quality`` (relative to
            the current working directory).

    Returns:
        A JSON-serialisable raw dict carrying the four sub-fixture
        payloads plus a structured ``skipped`` list, or ``None`` when
        the per-asset directory does not exist. The returned dict is
        intentionally raw (no dataclasses) so the executor can publish
        it to ``runtime["_reference_board"]`` cleanly. The validator
        :func:`evaluate_reference_board` parses the dict into the
        frozen-dataclass view.

    Behavior:
        - Missing per-asset directory -> return ``None``.
        - Directory exists but a sub-file is missing -> include the
          category in ``skipped`` with ``reason="reference_missing"``.
        - Sub-file exists but cannot be parsed -> include the category
          in ``skipped`` with ``reason="reference_malformed"``.
        - Extra unknown fields in any sub-file are tolerated.
    """
    if not isinstance(asset_name, str) or not asset_name:
        return None
    root = _resolve_base_path(base_path) / asset_name
    if not root.exists() or not root.is_dir():
        return None

    skipped: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {
        "root_path": str(root),
        "status": _STATUS_LOADED,
        "files": {},
    }

    mood = _load_mood(root, skipped, warnings, diagnostics, provenance)
    silhouettes = _load_list_file(
        root,
        _SILHOUETTE_FILENAME,
        _CATEGORY_SILHOUETTE,
        "silhouettes",
        skipped,
        warnings,
        diagnostics,
        provenance,
    )
    materials = _load_list_file(
        root,
        _MATERIALS_FILENAME,
        _CATEGORY_MATERIALS,
        "materials",
        skipped,
        warnings,
        diagnostics,
        provenance,
    )
    negatives = _load_list_file(
        root,
        _NEGATIVE_FILENAME,
        _CATEGORY_NEGATIVE,
        "negatives",
        skipped,
        warnings,
        diagnostics,
        provenance,
    )
    if skipped:
        provenance["status"] = "partial"

    return {
        "asset_name": asset_name,
        "family": None,
        "mood": mood,
        "silhouettes": silhouettes,
        "materials": materials,
        "negatives": negatives,
        "skipped": skipped,
        "warnings": warnings,
        "diagnostics": diagnostics,
        "provenance": provenance,
    }


def _load_mood(
    root: Path,
    skipped: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any] | None:
    path = root / _MOOD_FILENAME
    files = provenance.setdefault("files", {})
    if not path.exists() or not path.is_file():
        files[_CATEGORY_MOOD] = _path_metadata(path, status=_STATUS_MISSING, reason=_REASON_MISSING)
        _append_issue(
            skipped,
            warnings,
            diagnostics,
            category=_CATEGORY_MOOD,
            reason=_REASON_MISSING,
            message=f"Reference mood fixture is missing: {path}",
            path=str(path),
        )
        return None
    payload, error, error_message = _read_json(path)
    if error is not None:
        files[_CATEGORY_MOOD] = _path_metadata(path, status=_STATUS_MALFORMED, reason=error)
        _append_issue(
            skipped,
            warnings,
            diagnostics,
            category=_CATEGORY_MOOD,
            reason=error,
            message=f"Reference mood fixture could not be parsed: {error_message or path}",
            path=str(path),
        )
        return None
    if not isinstance(payload, dict):
        files[_CATEGORY_MOOD] = _path_metadata(path, status=_STATUS_MALFORMED, reason=_REASON_MALFORMED)
        _append_issue(
            skipped,
            warnings,
            diagnostics,
            category=_CATEGORY_MOOD,
            reason=_REASON_MALFORMED,
            message="Reference mood fixture must be a JSON object",
            path=str(path),
        )
        return None
    files[_CATEGORY_MOOD] = _path_metadata(path, status=_STATUS_LOADED)
    return payload


def _load_list_file(
    root: Path,
    filename: str,
    category: str,
    list_key: str,
    skipped: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> list[Any]:
    path = root / filename
    files = provenance.setdefault("files", {})
    if not path.exists() or not path.is_file():
        files[category] = _path_metadata(path, status=_STATUS_MISSING, reason=_REASON_MISSING)
        _append_issue(
            skipped,
            warnings,
            diagnostics,
            category=category,
            reason=_REASON_MISSING,
            message=f"Reference {category} fixture is missing: {path}",
            path=str(path),
        )
        return []
    payload, error, error_message = _read_json(path)
    if error is not None:
        files[category] = _path_metadata(path, status=_STATUS_MALFORMED, reason=error)
        _append_issue(
            skipped,
            warnings,
            diagnostics,
            category=category,
            reason=error,
            message=f"Reference {category} fixture could not be parsed: {error_message or path}",
            path=str(path),
        )
        return []
    items = _list_payload(payload, list_key)
    if items is None:
        files[category] = _path_metadata(path, status=_STATUS_MALFORMED, reason=_REASON_MALFORMED)
        _append_issue(
            skipped,
            warnings,
            diagnostics,
            category=category,
            reason=_REASON_MALFORMED,
            message=f"Reference {category} fixture must be a JSON list or object with '{list_key}'",
            path=str(path),
        )
        return []
    files[category] = {
        **_path_metadata(path, status=_STATUS_LOADED),
        "entry_count": len(items),
        "entries": [
            {
                "index": index,
                "status": _STATUS_LOADED if isinstance(entry, dict) else _STATUS_MALFORMED,
            }
            for index, entry in enumerate(items)
        ],
    }
    return items


def make_reference_board_error(
    asset_name: str,
    *,
    message: str,
    reason: str = _REASON_LOADER_ERROR,
    path: str | None = None,
) -> dict[str, Any]:
    """Return structured loader-failure evidence for executor publication."""
    issue = _issue(
        category=_CATEGORY_REFERENCE_BOARD,
        reason=reason,
        message=message,
        path=path,
    )
    return {
        "asset_name": asset_name,
        "family": None,
        "mood": None,
        "silhouettes": [],
        "materials": [],
        "negatives": [],
        "skipped": [issue],
        "warnings": [issue],
        "diagnostics": [
            {
                "code": "RB1003",
                "severity": "warning",
                "category": _CATEGORY_REFERENCE_BOARD,
                "reason": reason,
                "message": message,
                **({"path": path} if path is not None else {}),
            }
        ],
        "provenance": {
            "root_path": path,
            "status": _STATUS_ERROR,
            "reason": reason,
        },
    }


def reference_board_fingerprint(
    asset_name: str,
    base_path: Path | None = None,
) -> dict[str, Any]:
    """Return a stable content fingerprint for reference fixture inputs."""
    fingerprint: dict[str, Any] = {
        "asset_name": asset_name,
        "status": _STATUS_MISSING,
        "files": {},
    }
    if not isinstance(asset_name, str) or not asset_name:
        fingerprint["status"] = _STATUS_ERROR
        fingerprint["reason"] = "invalid_asset_name"
        return fingerprint
    root = _resolve_base_path(base_path) / asset_name
    if not root.exists() or not root.is_dir():
        return fingerprint
    fingerprint["status"] = _STATUS_LOADED
    files: dict[str, Any] = {}
    for category, filename in sorted(_CATEGORY_FILENAMES.items()):
        path = root / filename
        if not path.exists() or not path.is_file():
            files[category] = {"status": _STATUS_MISSING, "reason": _REASON_MISSING}
            continue
        metadata = _path_metadata(path, status=_STATUS_LOADED)
        files[category] = {
            "status": metadata.get("status"),
            "sha256": metadata.get("sha256"),
            "size_bytes": metadata.get("size_bytes"),
        }
        if metadata.get("status") != _STATUS_LOADED:
            files[category]["reason"] = metadata.get("reason")
            fingerprint["status"] = _STATUS_ERROR
    fingerprint["files"] = files
    return fingerprint


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


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


def _str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(entry for entry in value if isinstance(entry, str))
    return ()


def _float_dict(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        try:
            out[key] = float(raw)
        except (TypeError, ValueError):
            continue
    return out


def _resolve_asset_name(asset: dict[str, Any], raw: dict[str, Any]) -> str:
    name = raw.get("asset_name")
    if isinstance(name, str) and name:
        return name
    asset_name = asset.get("name")
    if isinstance(asset_name, str) and asset_name:
        return asset_name
    return "unnamed_asset"


def _resolve_family(
    asset: dict[str, Any],
    raw: dict[str, Any],
    runtime: dict[str, Any],
) -> str:
    family = raw.get("family")
    if isinstance(family, str) and family:
        return family
    design_brief = runtime.get("design_brief")
    if isinstance(design_brief, dict):
        inference = design_brief.get("family_inference")
        if isinstance(inference, dict):
            matched = inference.get("matched_family")
            if isinstance(matched, str) and matched:
                return matched
    asset_family = asset.get("family")
    if isinstance(asset_family, str) and asset_family:
        return asset_family
    return "generic"


def _build_mood(payload: dict[str, Any] | None) -> MoodReference | None:
    if not isinstance(payload, dict):
        return None
    return MoodReference(
        palette=_str_tuple(payload.get("palette")),
        lighting=_as_str(payload.get("lighting")),
        era=_as_str(payload.get("era")),
        descriptors=_str_tuple(payload.get("descriptors")),
    )


def _build_silhouettes(
    entries: list[Any],
) -> tuple[SilhouetteReference, ...]:
    out: list[SilhouetteReference] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        intent = _as_str(entry.get("intent"))
        if not intent:
            continue
        out.append(
            SilhouetteReference(
                intent=intent,
                proportions=_float_dict(entry.get("proportions")),
                descriptors=_str_tuple(entry.get("descriptors")),
                image_uri=_as_str_or_none(entry.get("image_uri")),
            )
        )
    return tuple(out)


def _build_materials(
    entries: list[Any],
) -> tuple[MaterialReference, ...]:
    out: list[MaterialReference] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        target = _as_str(entry.get("target"))
        if not target:
            continue
        hints_raw = entry.get("pbr_hints")
        pbr_hints: dict[str, Any] = {}
        if isinstance(hints_raw, dict):
            for key, raw in hints_raw.items():
                if isinstance(key, str):
                    pbr_hints[key] = raw
        out.append(
            MaterialReference(
                target=target,
                pbr_hints=pbr_hints,
                descriptors=_str_tuple(entry.get("descriptors")),
            )
        )
    return tuple(out)


def _build_negatives(
    entries: list[Any],
) -> tuple[NegativeReference, ...]:
    out: list[NegativeReference] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        constraint = _as_str(entry.get("constraint"))
        if not constraint:
            continue
        out.append(
            NegativeReference(
                constraint=constraint,
                rationale=_as_str(entry.get("rationale")),
            )
        )
    return tuple(out)


def _build_summary(board: ReferenceBoard) -> dict[str, Any]:
    has_mood = board.mood is not None
    silhouette_count = len(board.silhouettes)
    material_count = len(board.materials)
    negative_count = len(board.negatives)
    all_required_present = (
        has_mood and silhouette_count >= 1 and material_count >= 1
    )
    return {
        "has_mood": has_mood,
        "silhouette_count": silhouette_count,
        "material_count": material_count,
        "negative_count": negative_count,
        "all_required_present": all_required_present,
    }


def _normalize_skipped(raw: list[Any]) -> list[SkippedReason]:
    records: list[SkippedReason] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        category = _as_str(entry.get("category"))
        reason = _as_str(entry.get("reason"))
        if not category or not reason:
            continue
        key = (category, reason)
        if key in seen:
            continue
        seen.add(key)
        records.append(SkippedReason(category=category, reason=reason))
    records.sort(key=lambda record: (record.category, record.reason))
    return records


def _json_object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _normalize_issue_list(value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _json_object_list(value):
        stable = json.dumps(entry, sort_keys=True, default=str)
        if stable in seen:
            continue
        seen.add(stable)
        normalized.append(entry)
    return normalized


def _entry_malformed_issue(
    category: str,
    path: str,
    index: int,
    message: str,
) -> dict[str, Any]:
    return _issue(
        category=category,
        reason=_REASON_MALFORMED,
        message=message,
        path=path,
        index=index,
    )


def _entry_quality_issues(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    list_specs = (
        ("silhouettes", _CATEGORY_SILHOUETTE, "intent"),
        ("materials", _CATEGORY_MATERIALS, "target"),
        ("negatives", _CATEGORY_NEGATIVE, "constraint"),
    )
    for key, category, required_field in list_specs:
        entries = raw.get(key)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            path = f"{key}[{index}]"
            if not isinstance(entry, dict):
                issues.append(
                    _entry_malformed_issue(
                        category,
                        path,
                        index,
                        f"Reference {category} entry {index} must be a JSON object",
                    )
                )
                continue
            if not isinstance(entry.get(required_field), str) or not entry.get(required_field):
                issues.append(
                    _entry_malformed_issue(
                        category,
                        path,
                        index,
                        (
                            f"Reference {category} entry {index} must include "
                            f"a non-empty '{required_field}' string"
                        ),
                    )
                )
    mood = raw.get("mood")
    if mood is not None and not isinstance(mood, dict):
        issues.append(
            _issue(
                category=_CATEGORY_MOOD,
                reason=_REASON_MALFORMED,
                message="Reference mood payload must be a JSON object",
                path="mood",
            )
        )
    return issues


def _issues_to_diagnostics(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for issue in issues:
        diagnostics.append(
            {
                "code": "RB1002",
                "severity": "warning",
                "category": issue.get("category"),
                "reason": issue.get("reason"),
                "message": issue.get("message"),
                **({"path": issue["path"]} if isinstance(issue.get("path"), str) else {}),
                **({"index": issue["index"]} if isinstance(issue.get("index"), int) else {}),
            }
        )
    return diagnostics


def evaluate_reference_board(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive Phase 11 reference-board payload.

    Args:
        asset: normalized asset dict. Reads ``asset["name"]`` for the
            payload header and ``asset.get("family")`` as a defensive
            fallback for the family slot. The validator never reads
            ``asset["build"]`` or other stage payloads — Phase 11 is
            independent of stage runtime evidence.
        runtime: stage-bundle runtime dict. Reads
            ``runtime["_reference_board"]`` only — the executor
            publishes this slot before the validate stage runs by
            calling :func:`load_reference_board`. No other runtime
            view is consumed.

    Returns:
        Additive payload with ``version``
        (``"reference_board_v1"``), ``asset_name``, ``family``,
        ``board`` (per-category reference dataclasses serialised),
        ``summary`` (boolean + count block including
        ``all_required_present``), ``skipped_reasons`` (deduplicated
        and sorted), ``warnings`` (always empty in Phase 11), and
        ``diagnostics`` (always empty — Phase 11 is informational
        only and never blocks certification).
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}

    user_provided_via_experimental = bool(
        safe_runtime.get("_reference_board_user_provided_via_experimental")
    )
    raw = safe_runtime.get("_reference_board")
    if raw is None:
        asset_name = _resolve_asset_name(safe_asset, {})
        family = _resolve_family(safe_asset, {}, safe_runtime)
        empty_board = ReferenceBoard(
            asset_name=asset_name,
            family=family,
            mood=None,
            silhouettes=(),
            materials=(),
            negatives=(),
        )
        not_loaded = SkippedReason(
            category=_CATEGORY_REFERENCE_BOARD,
            reason=_REASON_NOT_LOADED,
        )
        return {
            "version": REFERENCE_BOARD_VERSION,
            "asset_name": asset_name,
            "family": family,
            "board": empty_board.to_dict(),
            "summary": _build_summary(empty_board),
            "provenance": {},
            "skipped_reasons": [not_loaded.to_dict()],
            "warnings": [],
            "diagnostics": [],
            "user_provided_via_experimental": user_provided_via_experimental,
        }

    raw_dict = _as_dict(raw)
    asset_name = _resolve_asset_name(safe_asset, raw_dict)
    family = _resolve_family(safe_asset, raw_dict, safe_runtime)

    board = ReferenceBoard(
        asset_name=asset_name,
        family=family,
        mood=_build_mood(raw_dict.get("mood")),
        silhouettes=_build_silhouettes(_as_list(raw_dict.get("silhouettes"))),
        materials=_build_materials(_as_list(raw_dict.get("materials"))),
        negatives=_build_negatives(_as_list(raw_dict.get("negatives"))),
    )
    entry_issues = _entry_quality_issues(raw_dict)
    skipped_records = _normalize_skipped([*_as_list(raw_dict.get("skipped")), *entry_issues])
    warnings = _normalize_issue_list([*_as_list(raw_dict.get("warnings")), *entry_issues])
    diagnostics = _normalize_issue_list(
        [*_as_list(raw_dict.get("diagnostics")), *_issues_to_diagnostics(entry_issues)]
    )

    return {
        "version": REFERENCE_BOARD_VERSION,
        "asset_name": asset_name,
        "family": family,
        "board": board.to_dict(),
        "summary": _build_summary(board),
        "provenance": _as_dict(raw_dict.get("provenance")),
        "skipped_reasons": [record.to_dict() for record in skipped_records],
        "warnings": warnings,
        "diagnostics": diagnostics,
        "user_provided_via_experimental": user_provided_via_experimental,
    }
