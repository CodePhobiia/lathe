"""Semantic `@lathe[...]` reference grammar, parsing, and resolution.

Phase-1 (non-geometric) + Phase-2 face/edge/vertex selectors (REF-6). The
remaining Phase-2 kinds (``socket``, ``collision``, ``pivot``, ``material``,
``lod<n>``) are parsed far enough to emit a helpful
``phase_2_feature_not_yet_available`` error pointing at ``docs/refs.md`` +
the V0.2 roadmap; they resolve via the REF-5 selector manifest when the
manifest is present on disk.

Public surface (stable):

- :class:`RefNode`, :class:`RefSelector` — parsed token shape.
- :class:`RefError`, :class:`RefParseError`, :class:`RefResolutionError`
  — exception hierarchy rooted at :class:`~lathe.errors.LatheError`.
- :class:`StaleRefWarning` — warning category for refs that resolve but
  whose target build on disk appears to be out of sync with the caller's
  expectations.
- :func:`parse_ref`, :func:`format_ref`, :func:`resolve_ref`.

See ``docs/refs.md`` for the public reference doc and
``docs/next_version_roadmap.md`` section E1 for the roadmap.
"""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .errors import LatheError
from .paths import PathGuardError, safe_resolve

# ---------------------------------------------------------------------------
# Exceptions and warning categories
# ---------------------------------------------------------------------------


class RefError(LatheError):
    """Base class for Phase-1 ``@lathe[...]`` ref failures."""


class RefParseError(RefError):
    """Raised when an ``@lathe[...]`` token does not match the Phase-1 grammar.

    Carries a short machine-readable ``code`` and a human-readable message.
    Phase-2 selector shapes raise with ``code="phase_2_feature_not_yet_available"``
    so callers can distinguish "invalid forever" from "coming later".
    """

    def __init__(self, code: str, message: str, *, token: str | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.token = token


class RefResolutionError(RefError):
    """Raised when a ref is well-formed but its target cannot be resolved."""


class StaleRefWarning(UserWarning):
    """Emitted when a ref resolves but the build on disk looks out of sync."""


# ---------------------------------------------------------------------------
# Parsed ref dataclasses
# ---------------------------------------------------------------------------


SelectorKind = Literal[
    "asset",
    "variant",
    "stage",
    "diagnostic",
    "part",
    "face",
    "edge",
    "vertex",
]


@dataclass(frozen=True)
class RefSelector:
    """A parsed selector fragment of an `@lathe[...]` token.

    ``kind`` discriminates the entity class; ``id`` is the matched identifier.
    For sub-part geometric selectors (``face``, ``edge``, ``vertex``) the
    ``id`` field carries the canonical stable id ``<part_id>.face<n>`` (or
    ``.edge<n>`` / ``.vertex<n>``), ``parent_part_id`` carries the owning
    part id, and ``sub_index`` is the integer suffix. For non-geometric
    selectors both ``parent_part_id`` and ``sub_index`` are ``None``.
    """

    kind: SelectorKind
    id: str
    parent_part_id: str | None = None
    sub_index: int | None = None


@dataclass(frozen=True)
class RefNode:
    """A parsed ``@lathe[...]`` reference token.

    ``raw`` is the original input string for round-trip formatting.
    ``target`` is the build-or-source path portion (everything before
    the optional ``#selector``). ``selector`` is ``None`` when the token
    addresses a whole build (e.g. ``@lathe[dist/courier_drone]``).
    """

    raw: str
    target: str
    selector: RefSelector | None = None


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


# Identifier grammar — letters/digits/underscore/hyphen/dot. Dots are allowed
# inside identifiers (e.g. diagnostic ids of the form "shape.candidate_score")
# but the first split on '.' after ``part`` is still reserved for sub-entity
# selectors in Phase 2.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

_PHASE2_SELECTOR_KINDS = {
    "socket",
    "collision",
    "pivot",
    "material",
}

_PHASE2_SUBPART_RE = re.compile(r"^(face|edge|vertex)(\d+)$")
_LOD_KIND_RE = re.compile(r"^lod(\d+)$")

_VALID_SELECTOR_KINDS = {"asset", "variant", "stage", "diagnostic", "part"}
_PHASE2_SUBPART_KINDS = {"face", "edge", "vertex"}


def _reject_path_traversal(target: str) -> None:
    """Reject obviously unsafe or absolute Windows paths in the ref target.

    Callers are expected to feed repo-relative paths (``dist/foo``,
    ``examples/courier_drone.lth``) — we don't try to canonicalize here,
    we only reject tokens that *look* traversal-shaped so the downstream
    resolver never has to reason about them.
    """
    stripped = target.strip()
    if not stripped:
        raise RefParseError(
            "empty_target",
            "@lathe[...] target path is empty",
            token=target,
        )
    if ".." in stripped.split("/") or ".." in stripped.split("\\"):
        raise RefParseError(
            "path_traversal_rejected",
            "@lathe[...] target must not contain '..' path components; see docs/refs.md for path rules",
            token=target,
        )
    if stripped.startswith("\\\\?\\") or stripped.startswith("\\\\"):
        raise RefParseError(
            "path_traversal_rejected",
            "@lathe[...] target must not be a UNC or \\\\?\\ path",
            token=target,
        )
    if re.match(r"^[A-Za-z]:[\\/]", stripped):
        raise RefParseError(
            "path_traversal_rejected",
            "@lathe[...] target must be repo-relative (no absolute Windows drive paths); see docs/refs.md",
            token=target,
        )
    if stripped.startswith("/"):
        raise RefParseError(
            "path_traversal_rejected",
            "@lathe[...] target must be repo-relative (no absolute POSIX paths); see docs/refs.md",
            token=target,
        )


def _classify_selector(raw_selector: str, *, token: str) -> RefSelector:
    """Dispatch the part after ``#`` into a :class:`RefSelector` or Phase-2 error.

    Handles:

    * ``asset.<name>``, ``variant.<name>``, ``stage.<name>``,
      ``diagnostic.<id>``, ``part.<id>`` → :class:`RefSelector`.
    * ``part.<id>.face<n>``/``.edge<n>``/``.vertex<n>`` → Phase-2 error.
    * ``socket.<id>``, ``collision.<id>``, ``pivot.<id>``, ``material.<id>``,
      ``lod<n>.<id>`` → Phase-2 error.
    """
    if not raw_selector:
        raise RefParseError(
            "empty_selector",
            "@lathe[...] selector after '#' is empty",
            token=token,
        )

    if "." not in raw_selector:
        # Bare kinds (``lod<n>`` w/o id, or unknown single-word selectors).
        lod_match = _LOD_KIND_RE.match(raw_selector)
        if lod_match:
            raise RefParseError(
                "phase_2_feature_not_yet_available",
                f"LOD selectors ('lod{lod_match.group(1)}.<part-id>') are a "
                "Phase-2 feature; see docs/refs.md and "
                "docs/next_version_roadmap.md E1 REF-5/REF-6",
                token=token,
            )
        raise RefParseError(
            "unknown_selector_kind",
            f"@lathe[...] selector '{raw_selector}' is missing an id (expected '<kind>.<id>')",
            token=token,
        )

    kind, _, rest = raw_selector.partition(".")

    if kind in _PHASE2_SELECTOR_KINDS:
        raise RefParseError(
            "phase_2_feature_not_yet_available",
            f"'{kind}.<id>' selectors are a Phase-2 feature in the V0.2 refs "
            "rollout; see docs/refs.md and docs/next_version_roadmap.md E1 "
            "REF-5/REF-6",
            token=token,
        )

    if _LOD_KIND_RE.match(kind):
        raise RefParseError(
            "phase_2_feature_not_yet_available",
            "LOD selectors ('lod<n>.<part-id>') are a Phase-2 feature; "
            "see docs/refs.md and docs/next_version_roadmap.md E1 REF-5/REF-6",
            token=token,
        )

    if kind == "part":
        # Sub-part suffixes (part.<id>.face<n>) are the REF-6 geometric refs.
        if "." in rest:
            part_id, _, sub = rest.partition(".")
            if not _IDENT_RE.match(part_id):
                raise RefParseError(
                    "invalid_identifier",
                    f"part id '{part_id}' is not a valid Lathe identifier",
                    token=token,
                )
            sub_match = _PHASE2_SUBPART_RE.match(sub)
            if sub_match:
                sub_kind = sub_match.group(1)
                sub_index = int(sub_match.group(2))
                return RefSelector(
                    kind=sub_kind,  # type: ignore[arg-type]
                    id=f"{part_id}.{sub}",
                    parent_part_id=part_id,
                    sub_index=sub_index,
                )
            raise RefParseError(
                "unknown_selector_kind",
                f"Unsupported part sub-selector '{sub}' in '{raw_selector}'",
                token=token,
            )
        if not _IDENT_RE.match(rest):
            raise RefParseError(
                "invalid_identifier",
                f"part id '{rest}' is not a valid Lathe identifier",
                token=token,
            )
        return RefSelector(kind="part", id=rest)

    if kind not in _VALID_SELECTOR_KINDS:
        raise RefParseError(
            "unknown_selector_kind",
            f"@lathe[...] selector kind '{kind}' is not one of "
            f"{sorted(_VALID_SELECTOR_KINDS | _PHASE2_SELECTOR_KINDS)} or "
            "'lod<n>'; see docs/refs.md",
            token=token,
        )

    if not _IDENT_RE.match(rest):
        raise RefParseError(
            "invalid_identifier",
            f"selector id '{rest}' is not a valid Lathe identifier",
            token=token,
        )

    return RefSelector(kind=kind, id=rest)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Public parse / format
# ---------------------------------------------------------------------------


# Lathe ref syntax markers, not secrets.
_TOKEN_PREFIX = "@lathe["  # noqa: S105  # nosec B105
_TOKEN_SUFFIX = "]"  # noqa: S105  # nosec B105


def parse_ref(token: str) -> RefNode:
    """Parse an ``@lathe[...]`` reference token.

    Accepts any of the Phase-1 grammar forms listed in ``docs/refs.md``.
    Raises :class:`RefParseError` with a stable ``code`` on invalid tokens
    and on Phase-2 (geometric) selector shapes.
    """
    if not isinstance(token, str):  # defensive: surfacing happens in tests
        raise RefParseError("not_a_string", "ref token must be a string", token=str(token))

    raw = token.strip()
    if not raw.startswith(_TOKEN_PREFIX):
        raise RefParseError(
            "missing_prefix",
            f"ref tokens must start with '{_TOKEN_PREFIX}'; see docs/refs.md",
            token=token,
        )
    if not raw.endswith(_TOKEN_SUFFIX):
        raise RefParseError(
            "missing_suffix",
            f"ref tokens must end with '{_TOKEN_SUFFIX}'; see docs/refs.md",
            token=token,
        )

    inner = raw[len(_TOKEN_PREFIX) : -len(_TOKEN_SUFFIX)]
    if not inner:
        raise RefParseError(
            "empty_ref",
            "@lathe[] is empty; expected a build or source path",
            token=token,
        )

    target, sep, selector_text = inner.partition("#")
    _reject_path_traversal(target)

    if not sep:
        return RefNode(raw=raw, target=target, selector=None)

    selector = _classify_selector(selector_text, token=token)
    return RefNode(raw=raw, target=target, selector=selector)


def format_ref(node: RefNode) -> str:
    """Render a :class:`RefNode` back to its canonical ``@lathe[...]`` form.

    ``format_ref(parse_ref(t)) == t`` for any valid token ``t`` that has no
    surrounding whitespace, including Phase-2 sub-part selectors which
    render as ``part.<parent>.<face|edge|vertex><n>``.
    """
    if node.selector is None:
        return f"{_TOKEN_PREFIX}{node.target}{_TOKEN_SUFFIX}"
    sel = node.selector
    if sel.kind in _PHASE2_SUBPART_KINDS:
        return f"{_TOKEN_PREFIX}{node.target}#part.{sel.id}{_TOKEN_SUFFIX}"
    return f"{_TOKEN_PREFIX}{node.target}#{sel.kind}.{sel.id}{_TOKEN_SUFFIX}"


# ---------------------------------------------------------------------------
# Resolution (Phase 1: non-geometric only)
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _classify_target(target_path: Path) -> Literal["build", "source", "missing"]:
    if not target_path.exists():
        return "missing"
    if target_path.is_dir():
        return "build"
    if target_path.suffix == ".lth":
        return "source"
    return "source"


def _build_report(target_path: Path) -> dict[str, Any] | None:
    report_path = target_path / "build_report.json"
    if not report_path.exists():
        return None
    return _load_json(report_path)


def _selector_manifest(target_path: Path) -> dict[str, Any] | None:
    """Load ``selector_manifest.json`` from ``target_path`` if present.

    Returns the parsed dict when the sidecar exists and is valid JSON, else
    ``None``. The manifest is the authoritative REF-5 source; callers prefer
    it over ``build_report.json`` for selector lookup.
    """
    manifest_path = target_path / "selector_manifest.json"
    if not manifest_path.exists():
        return None
    payload = _load_json(manifest_path)
    return payload if isinstance(payload, dict) else None


def _collect_stage_bundles(report: dict[str, Any]) -> dict[str, Any]:
    bundles = report.get("stage_bundles")
    return bundles if isinstance(bundles, dict) else {}


def _collect_diagnostics(report: dict[str, Any]) -> list[dict[str, Any]]:
    diags = report.get("diagnostics") or []
    if not isinstance(diags, list):
        return []
    # Some builds attach diagnostics inside stage bundles — merge those too.
    merged: list[dict[str, Any]] = [d for d in diags if isinstance(d, dict)]
    for stage_name, stage_bundle in _collect_stage_bundles(report).items():
        if not isinstance(stage_bundle, dict):
            continue
        stage_diags = stage_bundle.get("diagnostics") or []
        if isinstance(stage_diags, list):
            for item in stage_diags:
                if isinstance(item, dict):
                    merged.append({**item, "stage": item.get("stage") or stage_name})
    return merged


def _part_ids_from_shape_bundle(target_path: Path) -> list[str]:
    bundle_path = target_path / "stages" / "shape" / "bundle.json"
    bundle = _load_json(bundle_path)
    if not isinstance(bundle, dict):
        return []
    candidates = bundle.get("candidates") or []
    if not isinstance(candidates, list):
        return []
    selected_id = bundle.get("selected_candidate_id")
    selected = None
    for cand in candidates:
        if isinstance(cand, dict) and cand.get("candidate_id") == selected_id:
            selected = cand
            break
    if selected is None and candidates:
        selected = candidates[0] if isinstance(candidates[0], dict) else None
    if not isinstance(selected, dict):
        return []
    labels = selected.get("part_labels") or []
    return [str(p) for p in labels if isinstance(p, (str, int))]


def _maybe_stale_warning(
    target_path: Path,
    selector: RefSelector | None,
    *,
    manifest: dict[str, Any] | None = None,
    expected_build_hash: str | None = None,
) -> None:
    """Emit a :class:`StaleRefWarning` when the build dir shows obvious drift.

    Three drift modes are detected:

    1. Neither ``selector_manifest.json`` nor ``build_report.json`` exists at
       ``target_path``. (The build is incomplete or the dir is mislabelled.)
    2. The caller supplied ``expected_build_hash`` and it does not match the
       ``buildHash`` recorded in ``selector_manifest.json``.
    3. The ref's ``asset.<id>`` / ``variant.<id>`` selector does not match the
       asset/variant name recorded in the manifest (preferred) or
       ``build_report.json`` (fallback).
    """
    manifest_path = target_path / "selector_manifest.json"
    report_path = target_path / "build_report.json"
    if not manifest_path.exists() and not report_path.exists():
        warnings.warn(
            f"@lathe[{target_path}] has no selector_manifest.json or "
            "build_report.json — ref may be stale (is the build complete?)",
            StaleRefWarning,
            stacklevel=3,
        )
        return

    # Manifest-based drift checks (REF-7: authoritative source).
    if manifest is not None:
        if expected_build_hash is not None:
            actual = manifest.get("buildHash")
            if isinstance(actual, str) and actual != expected_build_hash:
                warnings.warn(
                    f"@lathe[{target_path}] buildHash '{actual}' does not "
                    f"match expected '{expected_build_hash}' — ref may be stale",
                    StaleRefWarning,
                    stacklevel=3,
                )
        if selector is not None and selector.kind == "asset":
            asset_in_manifest = manifest.get("asset")
            if asset_in_manifest and asset_in_manifest != selector.id:
                warnings.warn(
                    f"@lathe[{target_path}#asset.{selector.id}] does not match "
                    f"selector_manifest.json asset '{asset_in_manifest}' — ref "
                    "may be stale",
                    StaleRefWarning,
                    stacklevel=3,
                )
        if selector is not None and selector.kind == "variant":
            variant_in_manifest = manifest.get("variant")
            if variant_in_manifest and variant_in_manifest != selector.id:
                warnings.warn(
                    f"@lathe[{target_path}#variant.{selector.id}] does not "
                    f"match selector_manifest.json variant "
                    f"'{variant_in_manifest}' — ref may be stale",
                    StaleRefWarning,
                    stacklevel=3,
                )
        return

    # Fallback: only build_report.json is available (pre-REF-5 builds).
    if selector is None or selector.kind != "asset":
        return
    report = _load_json(report_path)
    if not isinstance(report, dict):
        return
    asset_in_report = report.get("asset")
    if asset_in_report and asset_in_report != selector.id:
        warnings.warn(
            f"@lathe[{target_path}#asset.{selector.id}] does not match "
            f"build_report.json asset '{asset_in_report}' — ref may be stale",
            StaleRefWarning,
            stacklevel=3,
        )


def _resolve_whole_build(target_path: Path, report: dict[str, Any] | None) -> dict[str, Any]:
    if report is None:
        return {
            "ok": False,
            "reason": "no_build_report",
            "message": (
                "build_report.json not found; the target directory does not "
                "look like a completed Lathe build."
            ),
        }
    facts = {
        "asset": report.get("asset"),
        "kind": report.get("kind"),
        "certified": report.get("certified"),
        "backend_stack_id": (report.get("backend_stack") or {}).get("id"),
        "stage_ids": sorted(_collect_stage_bundles(report).keys()),
        "diagnostic_count": len(_collect_diagnostics(report)),
        "outputs": [
            {k: o.get(k) for k in ("format", "uri", "sha256", "size_bytes")}
            for o in (report.get("outputs") or [])
            if isinstance(o, dict)
        ],
    }
    return {"ok": True, "facts": facts}


def _resolve_asset(
    target_path: Path,
    report: dict[str, Any] | None,
    selector: RefSelector,
) -> dict[str, Any]:
    if report is None:
        return {
            "ok": False,
            "reason": "no_build_report",
            "message": "build_report.json not found for target build",
        }
    asset_name = report.get("asset")
    if asset_name != selector.id:
        return {
            "ok": False,
            "reason": "asset_not_in_build",
            "message": (f"build_report.json reports asset '{asset_name}', not '{selector.id}'"),
            "facts": {"build_asset": asset_name, "requested": selector.id},
        }
    return {
        "ok": True,
        "facts": {
            "asset": selector.id,
            "kind": report.get("kind"),
            "certified": report.get("certified"),
            "backend_stack_id": (report.get("backend_stack") or {}).get("id"),
        },
    }


def _resolve_variant(
    target_path: Path,
    report: dict[str, Any] | None,
    selector: RefSelector,
) -> dict[str, Any]:
    if report is None:
        return {
            "ok": False,
            "reason": "no_build_report",
            "message": "build_report.json not found for target build",
        }
    # Variants are addressed directly as an asset in the current scaffold —
    # the variant name becomes the built asset name. We report both views.
    asset_name = report.get("asset")
    matches = asset_name == selector.id
    return {
        "ok": bool(matches),
        "reason": None if matches else "variant_not_in_build",
        "facts": {
            "variant": selector.id,
            "build_asset": asset_name,
            "kind": report.get("kind"),
        },
        "message": None
        if matches
        else (
            f"build_report.json reports asset '{asset_name}', which does not "
            f"match variant '{selector.id}' — run `lathe materialize "
            f"<file> {selector.id}` to materialize this variant"
        ),
    }


def _resolve_stage(
    target_path: Path,
    report: dict[str, Any] | None,
    selector: RefSelector,
) -> dict[str, Any]:
    if report is None:
        return {
            "ok": False,
            "reason": "no_build_report",
            "message": "build_report.json not found for target build",
        }
    bundles = _collect_stage_bundles(report)
    if selector.id not in bundles:
        return {
            "ok": False,
            "reason": "stage_not_in_build",
            "facts": {"available_stages": sorted(bundles.keys())},
            "message": (
                f"stage '{selector.id}' is not present in build_report.json; "
                f"available: {sorted(bundles.keys())}"
            ),
        }
    stage_bundle = bundles.get(selector.id) or {}
    stage_dir = target_path / "stages" / selector.id
    facts = {
        "stage": selector.id,
        "stage_dir": str(stage_dir) if stage_dir.exists() else None,
        "backend_id": stage_bundle.get("backend_id") or (stage_bundle.get("backend") or {}).get("id")
        if isinstance(stage_bundle, dict)
        else None,
    }
    return {"ok": True, "facts": facts}


def _resolve_diagnostic(
    target_path: Path,
    report: dict[str, Any] | None,
    selector: RefSelector,
) -> dict[str, Any]:
    if report is None:
        return {
            "ok": False,
            "reason": "no_build_report",
            "message": "build_report.json not found for target build",
        }
    diagnostics = _collect_diagnostics(report)
    for diag in diagnostics:
        if diag.get("id") == selector.id or diag.get("code") == selector.id:
            return {
                "ok": True,
                "facts": {
                    "id": diag.get("id") or diag.get("code"),
                    "severity": diag.get("severity"),
                    "stage": diag.get("stage"),
                    "message": diag.get("message"),
                },
            }
    return {
        "ok": False,
        "reason": "diagnostic_not_found",
        "facts": {"available_diagnostic_ids": [d.get("id") or d.get("code") for d in diagnostics]},
        "message": (
            f"diagnostic '{selector.id}' not found in build_report.json; "
            "if the build has not been re-run since the diagnostic fired, "
            "re-run `lathe build` to refresh"
        ),
    }


def _resolve_part(
    target_path: Path,
    report: dict[str, Any] | None,
    selector: RefSelector,
) -> dict[str, Any]:
    if report is None:
        return {
            "ok": False,
            "reason": "no_build_report",
            "message": "build_report.json not found for target build",
        }
    part_ids = _part_ids_from_shape_bundle(target_path)
    if selector.id in part_ids:
        return {
            "ok": True,
            "facts": {
                "part_id": selector.id,
                "source": "stages/shape/bundle.json:part_labels",
                "sibling_parts": [p for p in part_ids if p != selector.id],
            },
        }
    return {
        "ok": False,
        "reason": "part_not_found",
        "facts": {"available_part_ids": part_ids},
        "message": (
            f"part '{selector.id}' not found in the shape bundle's part_labels; "
            f"known parts: {part_ids}. Phase-2 refs (face/edge/vertex) land "
            "with REF-6 — see docs/next_version_roadmap.md"
        ),
    }


def _resolve_sub_part_no_manifest(
    target_path: Path,
    report: dict[str, Any] | None,
    selector: RefSelector,
) -> dict[str, Any]:
    return {
        "ok": False,
        "reason": "selector_manifest_required",
        "facts": {
            "requested": selector.id,
            "parent_part_id": selector.parent_part_id,
            "sub_kind": selector.kind,
            "message": (
                "face/edge/vertex refs require selector_manifest.json; "
                "the target build has no manifest (pre-REF-5 build?)"
            ),
        },
        "message": (
            f"selector_manifest.json required to resolve "
            f"part.{selector.parent_part_id}.{selector.kind}"
            f"{selector.sub_index} — re-run `lathe build`"
        ),
    }


_RESOLVERS = {
    "asset": _resolve_asset,
    "variant": _resolve_variant,
    "stage": _resolve_stage,
    "diagnostic": _resolve_diagnostic,
    "part": _resolve_part,
    "face": _resolve_sub_part_no_manifest,
    "edge": _resolve_sub_part_no_manifest,
    "vertex": _resolve_sub_part_no_manifest,
}


def _find_part(manifest: dict[str, Any], part_id: str) -> dict[str, Any] | None:
    parts = manifest.get("parts") or []
    if not isinstance(parts, list):
        return None
    for part in parts:
        if isinstance(part, dict) and part.get("id") == part_id:
            return part
    return None


_SUBPART_FIELD = {"face": "faces", "edge": "edges", "vertex": "vertices"}


def _resolve_sub_part_from_manifest(
    manifest: dict[str, Any],
    selector: RefSelector,
) -> dict[str, Any]:
    parent_id = selector.parent_part_id or ""
    sub_kind = selector.kind
    field_name = _SUBPART_FIELD[sub_kind]
    part = _find_part(manifest, parent_id)
    if part is None:
        return {
            "ok": False,
            "reason": "part_not_found",
            "facts": {
                "requested_part": parent_id,
                "available_part_ids": [
                    p.get("id") for p in (manifest.get("parts") or []) if isinstance(p, dict)
                ],
                "source": "selector_manifest.json:parts",
            },
            "message": (
                f"parent part '{parent_id}' not found in selector_manifest.json "
                f"for sub-part selector '{selector.id}'"
            ),
        }
    entries = part.get(field_name) or []
    if not isinstance(entries, list):
        entries = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == selector.id:
            facts = {
                "id": selector.id,
                "parent_part_id": parent_id,
                "sub_index": selector.sub_index,
                "source": f"selector_manifest.json:parts.{field_name}",
                "ref": entry.get("ref"),
            }
            for key in ("centroid", "normal", "endpoints", "position", "area", "length"):
                if key in entry:
                    facts[key] = entry[key]
            return {"ok": True, "facts": facts}
    return {
        "ok": False,
        "reason": f"{sub_kind}_not_found",
        "facts": {
            "requested": selector.id,
            "parent_part_id": parent_id,
            f"available_{field_name}": [e.get("id") for e in entries if isinstance(e, dict)][:20],
            "source": f"selector_manifest.json:parts.{field_name}",
        },
        "message": (
            f"{sub_kind} '{selector.id}' not found on part '{parent_id}' "
            f"(part has {len(entries)} {field_name})"
        ),
    }


def _resolve_from_manifest(
    manifest: dict[str, Any],
    selector: RefSelector | None,
) -> dict[str, Any] | None:
    """Resolve a selector directly against the REF-5 selector manifest.

    Returns ``None`` when the manifest does not yet know how to resolve this
    selector kind (falls back to the legacy ``build_report.json`` path).
    """
    if selector is None:
        return {
            "ok": True,
            "facts": {
                "asset": manifest.get("asset"),
                "variant": manifest.get("variant"),
                "build_hash": manifest.get("buildHash"),
                "package_hash": manifest.get("packageHash"),
                "schema_version": manifest.get("schemaVersion"),
                "source": "selector_manifest.json",
            },
        }

    if selector.kind == "asset":
        asset_name = manifest.get("asset")
        if asset_name == selector.id:
            return {
                "ok": True,
                "facts": {
                    "asset": selector.id,
                    "variant": manifest.get("variant"),
                    "build_hash": manifest.get("buildHash"),
                    "source": "selector_manifest.json",
                },
            }
        return {
            "ok": False,
            "reason": "asset_not_in_build",
            "facts": {
                "build_asset": asset_name,
                "requested": selector.id,
                "source": "selector_manifest.json",
            },
            "message": (f"selector_manifest.json reports asset '{asset_name}', not '{selector.id}'"),
        }

    if selector.kind == "variant":
        variant_name = manifest.get("variant")
        matches = variant_name == selector.id or manifest.get("asset") == selector.id
        return {
            "ok": bool(matches),
            "reason": None if matches else "variant_not_in_build",
            "facts": {
                "variant": selector.id,
                "manifest_variant": variant_name,
                "build_asset": manifest.get("asset"),
                "source": "selector_manifest.json",
            },
            "message": None
            if matches
            else (
                f"selector_manifest.json reports variant "
                f"'{variant_name}' / asset '{manifest.get('asset')}', which "
                f"does not match '{selector.id}'"
            ),
        }

    if selector.kind == "part":
        parts = manifest.get("parts") or []
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and part.get("id") == selector.id:
                    return {
                        "ok": True,
                        "facts": {
                            "part_id": selector.id,
                            "source": "selector_manifest.json:parts",
                            "sibling_parts": [
                                p.get("id")
                                for p in parts
                                if isinstance(p, dict) and p.get("id") != selector.id
                            ],
                            "ref": part.get("ref"),
                            "bbox": part.get("bbox"),
                            "face_count": part.get("faceCount"),
                            "material_id": part.get("materialId"),
                        },
                    }
            return {
                "ok": False,
                "reason": "part_not_found",
                "facts": {
                    "available_part_ids": [p.get("id") for p in parts if isinstance(p, dict)],
                    "source": "selector_manifest.json:parts",
                },
                "message": (
                    f"part '{selector.id}' not found in selector_manifest.json; "
                    f"known parts: {[p.get('id') for p in parts if isinstance(p, dict)]}"
                ),
            }

    if selector.kind in _PHASE2_SUBPART_KINDS:
        return _resolve_sub_part_from_manifest(manifest, selector)

    if selector.kind == "diagnostic":
        diagnostics = manifest.get("diagnostics") or []
        if isinstance(diagnostics, list):
            for diag in diagnostics:
                if isinstance(diag, dict) and diag.get("id") == selector.id:
                    return {
                        "ok": True,
                        "facts": {
                            "id": diag.get("id"),
                            "severity": diag.get("severity"),
                            "stage": diag.get("stage"),
                            "message": diag.get("message"),
                            "source": "selector_manifest.json:diagnostics",
                        },
                    }
            return {
                "ok": False,
                "reason": "diagnostic_not_found",
                "facts": {
                    "available_diagnostic_ids": [d.get("id") for d in diagnostics if isinstance(d, dict)],
                    "source": "selector_manifest.json:diagnostics",
                },
                "message": (f"diagnostic '{selector.id}' not found in selector_manifest.json"),
            }

    # Stage selectors still resolve against build_report.json in Phase 1.
    return None


def resolve_ref(
    node: RefNode,
    *,
    repo_root: Path | str | None = None,
    expected_build_hash: str | None = None,
) -> dict[str, Any]:
    """Resolve a parsed ref to a fact payload.

    Phase-1 behaviour:

    * If ``selector_manifest.json`` is present it is the authoritative source
      for ``asset``/``variant``/``part``/``diagnostic`` lookups (REF-5).
    * ``stage`` selectors still read ``build_report.json`` (stages are not
      serialised into the manifest's top level).
    * ``source`` targets (``.lth`` files) are detected but currently only
      return a path-existence fact — selector resolution against a source
      file is a REF-5 deliverable in the next wave.
    * Stale-ref drift emits a :class:`StaleRefWarning`; it does NOT raise.
      Callers may pass ``expected_build_hash`` to trigger a ``buildHash``
      mismatch warning.

    Returns a JSON-serialisable dict with stable keys: ``ok``, ``ref``,
    ``target_path``, ``target_kind``, ``selector_kind``, ``selector_id``,
    and ``facts``.
    """
    if not isinstance(node, RefNode):
        raise TypeError("resolve_ref expects a RefNode — call parse_ref(token) first")

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    # SEC: refs name a target relative to ``root`` and must stay within it.
    # ``parse_ref`` already rejects absolute targets, but ``resolve_ref``
    # accepts arbitrary :class:`RefNode` instances so we re-enforce the
    # constraint and route through :func:`safe_resolve` to catch symlink
    # traversal even on hand-built nodes.
    target_kind: str
    target_path: Path
    if Path(node.target).is_absolute():
        target_kind = "missing"
        target_path = Path(node.target)
    else:
        try:
            target_path = safe_resolve(root, node.target)
        except PathGuardError:
            # Surface a path-rejection as a structured "missing" target so
            # callers handle it via the existing stale-ref path rather than
            # a hard exception.
            target_kind = "missing"
            target_path = (root / node.target).resolve(strict=False)
        else:
            target_kind = _classify_target(target_path)

    base: dict[str, Any] = {
        "ok": False,
        "ref": format_ref(node),
        "target_path": str(target_path),
        "target_kind": target_kind,
        "selector_kind": node.selector.kind if node.selector else None,
        "selector_id": node.selector.id if node.selector else None,
        "facts": {},
    }

    if target_kind == "missing":
        base.update(
            {
                "ok": False,
                "facts": {
                    "reason": "target_not_found",
                    "message": (f"target path {target_path} does not exist on disk"),
                },
            }
        )
        return base

    if target_kind == "source":
        base["facts"] = {
            "reason": "source_ref_not_yet_resolved",
            "message": (
                "source (.lth) ref resolution lands with REF-5 selector "
                "manifests; Phase 1 only resolves against completed builds"
            ),
        }
        base["ok"] = node.selector is None  # whole-source path still useful
        return base

    # target_kind == "build"
    manifest = _selector_manifest(target_path)
    report = _build_report(target_path)
    _maybe_stale_warning(
        target_path,
        node.selector,
        manifest=manifest,
        expected_build_hash=expected_build_hash,
    )

    # Prefer the selector manifest for selectors it can resolve.
    result: dict[str, Any] | None = None
    if manifest is not None:
        result = _resolve_from_manifest(manifest, node.selector)

    if result is None:
        if node.selector is None:
            result = _resolve_whole_build(target_path, report)
        else:
            resolver = _RESOLVERS.get(node.selector.kind)
            if resolver is None:
                # Shouldn't happen — parse_ref rejects unknown kinds — but keep
                # the API defensive rather than crash on a malformed RefNode.
                raise RefResolutionError(f"no resolver for selector kind '{node.selector.kind}'")
            result = resolver(target_path, report, node.selector)

    base["ok"] = bool(result.get("ok"))
    facts = result.get("facts") or {}
    if result.get("reason") and "reason" not in facts:
        facts = {**facts, "reason": result["reason"]}
    if result.get("message") and "message" not in facts:
        facts = {**facts, "message": result["message"]}
    base["facts"] = facts
    return base


__all__ = [
    "RefError",
    "RefNode",
    "RefParseError",
    "RefResolutionError",
    "RefSelector",
    "StaleRefWarning",
    "format_ref",
    "parse_ref",
    "resolve_ref",
]
