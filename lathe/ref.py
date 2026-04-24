"""Semantic `@lathe[...]` reference grammar, parsing, and resolution.

Implements the Phase-1 (non-geometric) slice of the E1 Semantic Reference
System. Geometric selectors (``face<n>``, ``edge<n>``, ``vertex<n>``,
``socket.<id>``, ``collision.<id>``, ``pivot.<id>``, ``material.<id>``,
``lod<n>.<id>``) are parsed far enough to emit a helpful Phase-2 error and
pointed at ``docs/refs.md`` + the V0.2 roadmap; they are NOT resolved here.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from .errors import LatheError


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


SelectorKind = Literal["asset", "variant", "stage", "diagnostic", "part"]


@dataclass(frozen=True)
class RefSelector:
    """A parsed selector fragment of an `@lathe[...]` token.

    The ``kind`` discriminates the entity class; ``id`` is the matched
    identifier (asset name, variant name, stage name, diagnostic id, or
    part id). Phase 1 only parses these five kinds — geometric selectors
    are rejected up front at :func:`parse_ref` with a dedicated error code.
    """

    kind: SelectorKind
    id: str


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
    selector: Optional[RefSelector] = None


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
            "@lathe[...] target must not contain '..' path components; "
            "see docs/refs.md for path rules",
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
            "@lathe[...] target must be repo-relative (no absolute Windows "
            "drive paths); see docs/refs.md",
            token=target,
        )
    if stripped.startswith("/"):
        raise RefParseError(
            "path_traversal_rejected",
            "@lathe[...] target must be repo-relative (no absolute POSIX "
            "paths); see docs/refs.md",
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
            f"@lathe[...] selector '{raw_selector}' is missing an id "
            "(expected '<kind>.<id>')",
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
        # Sub-part suffixes (part.<id>.face<n>) mark Phase-2 geometric refs.
        if "." in rest:
            part_id, _, sub = rest.partition(".")
            if _PHASE2_SUBPART_RE.match(sub):
                raise RefParseError(
                    "phase_2_feature_not_yet_available",
                    f"Sub-part selectors ('part.{part_id}.{sub}') are a "
                    "Phase-2 feature; see docs/refs.md and "
                    "docs/next_version_roadmap.md E1 REF-6",
                    token=token,
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


_TOKEN_PREFIX = "@lathe["
_TOKEN_SUFFIX = "]"


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

    ``format_ref(parse_ref(t)) == t`` for any Phase-1 valid token ``t`` that
    has no surrounding whitespace.
    """

    if node.selector is None:
        return f"{_TOKEN_PREFIX}{node.target}{_TOKEN_SUFFIX}"
    return (
        f"{_TOKEN_PREFIX}{node.target}#{node.selector.kind}.{node.selector.id}"
        f"{_TOKEN_SUFFIX}"
    )


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


def _maybe_stale_warning(target_path: Path, selector: Optional[RefSelector]) -> None:
    """Emit a :class:`StaleRefWarning` when the build dir shows obvious drift."""

    report_path = target_path / "build_report.json"
    if not report_path.exists():
        warnings.warn(
            f"@lathe[{target_path}] has no build_report.json — ref may be stale "
            "(is the build complete?)",
            StaleRefWarning,
            stacklevel=3,
        )
        return
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
            "message": (
                f"build_report.json reports asset '{asset_name}', not "
                f"'{selector.id}'"
            ),
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
        "backend_id": stage_bundle.get("backend_id")
        or (stage_bundle.get("backend") or {}).get("id")
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


_RESOLVERS = {
    "asset": _resolve_asset,
    "variant": _resolve_variant,
    "stage": _resolve_stage,
    "diagnostic": _resolve_diagnostic,
    "part": _resolve_part,
}


def resolve_ref(node: RefNode, *, repo_root: Path | str | None = None) -> dict[str, Any]:
    """Resolve a parsed ref to a fact payload.

    Phase-1 behaviour:

    * Whole-build refs and ``asset``/``variant``/``stage``/``diagnostic``/
      ``part`` selectors resolve against ``build_report.json`` and the
      shape bundle for part lists.
    * ``source`` targets (``.lth`` files) are detected but currently only
      return a path-existence fact — selector resolution against a source
      file is a REF-5 deliverable in the next wave.
    * Stale-ref drift emits a :class:`StaleRefWarning`; it does NOT raise.

    Returns a JSON-serialisable dict with stable keys: ``ok``, ``ref``,
    ``target_path``, ``target_kind``, ``selector_kind``, ``selector_id``,
    and ``facts``.
    """

    if not isinstance(node, RefNode):
        raise TypeError("resolve_ref expects a RefNode — call parse_ref(token) first")

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    target_path = (root / node.target).resolve() if not Path(node.target).is_absolute() else Path(node.target)

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
                    "message": (
                        f"target path {target_path} does not exist on disk"
                    ),
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
    report = _build_report(target_path)
    _maybe_stale_warning(target_path, node.selector)

    if node.selector is None:
        result = _resolve_whole_build(target_path, report)
    else:
        resolver = _RESOLVERS.get(node.selector.kind)
        if resolver is None:
            # Shouldn't happen — parse_ref rejects unknown kinds — but keep
            # the API defensive rather than crash on a malformed RefNode.
            raise RefResolutionError(
                f"no resolver for selector kind '{node.selector.kind}'"
            )
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
    "RefNode",
    "RefSelector",
    "RefError",
    "RefParseError",
    "RefResolutionError",
    "StaleRefWarning",
    "parse_ref",
    "format_ref",
    "resolve_ref",
]
