"""Phase 13 experimental-syntax checks.

Validates the optional ``experimental { ... }`` block on assets and
materialized variants:
unknown sub-blocks (``L7100``), the ``art_direction`` field
whitelist (``L7101``/``L7102``), the ``references.use`` path
(``L7103``), and the ``kit.use`` part-list format/membership
(``L7104``/``L7105``/``L7106``).

Phase 13 only — the stable public surface is unchanged. A clean
``experimental`` block produces zero diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import ResolutionError
from ..paths import PathGuardError, safe_resolve
from .utils import diag

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPERIMENTAL_SUBBLOCKS: tuple[str, ...] = ("art_direction", "references", "kit")
_ART_DIRECTION_WHITELIST: tuple[str, ...] = (
    "style_tags",
    "wear",
    "material_age",
    "detail_density",
)


def check_experimental_block(checker: Any) -> None:
    """Validate the Phase 13 ``experimental`` block on every asset.

    Iterates materialized assets and variants so variant patches that
    add or mutate ``experimental`` receive the same validation as base
    assets. Resolution failures are already reported by the asset
    checker, so this pass skips them to avoid duplicate noise.
    """
    names = [asset.get("name", "") for asset in checker.program.get("assets", [])]
    names.extend(variant.get("name", "") for variant in checker.program.get("variants", []))
    for name in names:
        if not name:
            continue
        try:
            asset = checker.resolver.materialize_asset(name)
        except ResolutionError:
            continue
        experimental = asset.get("experimental")
        if not isinstance(experimental, dict) or not experimental:
            continue
        asset_name = asset.get("name", "")
        _check_unknown_subblocks(checker, asset_name, experimental)
        if "art_direction" in experimental:
            _check_art_direction(
                checker, asset_name, experimental.get("art_direction") or {}
            )
        if "references" in experimental:
            _check_references(
                checker, asset_name, experimental.get("references") or {}
            )
        if "kit" in experimental:
            _check_kit(checker, asset, experimental.get("kit") or {})


def _check_unknown_subblocks(
    checker: Any, asset_name: str, experimental: dict[str, Any]
) -> None:
    raw_unknowns = experimental.get("_unknown_subblocks") or []
    unknowns = raw_unknowns if isinstance(raw_unknowns, list) else []
    keyed_unknowns = [
        key
        for key in experimental
        if isinstance(key, str)
        and key not in _EXPERIMENTAL_SUBBLOCKS
        and key != "_unknown_subblocks"
    ]
    unknowns = [*unknowns, *keyed_unknowns]
    for entry in unknowns:
        if not isinstance(entry, str) or not entry:
            continue
        checker.diagnostics.append(
            diag(
                "L7100",
                "experimental_unknown_subblock",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental sub-block '{entry}' is "
                    f"not recognized in the Phase 13 MVP"
                ),
                asset=asset_name,
                path="experimental",
                details={"subblock": entry},
                suggested_repairs=[
                    f"Remove the '{entry}' sub-block from experimental",
                    f"Allowed sub-blocks: {', '.join(_EXPERIMENTAL_SUBBLOCKS)}",
                ],
            )
        )


def _check_art_direction(
    checker: Any, asset_name: str, art_direction: Any
) -> None:
    if not isinstance(art_direction, dict):
        checker.diagnostics.append(
            diag(
                "L7102",
                "experimental_art_direction_invalid_value",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental.art_direction must be a "
                    f"block of fields"
                ),
                asset=asset_name,
                path="experimental.art_direction",
                suggested_repairs=[
                    "Wrap art_direction overrides in `art_direction { ... }`",
                ],
            )
        )
        return
    for field, value in art_direction.items():
        if field not in _ART_DIRECTION_WHITELIST:
            checker.diagnostics.append(
                diag(
                    "L7101",
                    "experimental_art_direction_unknown_field",
                    "error",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.art_direction field "
                        f"'{field}' is not in the Phase 13 MVP whitelist"
                    ),
                    asset=asset_name,
                    path=f"experimental.art_direction.{field}",
                    details={"field": field},
                    suggested_repairs=[
                        f"Remove '{field}' from art_direction",
                        "Allowed fields: style_tags, wear, material_age, detail_density",
                    ],
                )
            )
            continue
        if field == "style_tags":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                checker.diagnostics.append(
                    diag(
                        "L7102",
                        "experimental_art_direction_invalid_value",
                        "error",
                        "typecheck",
                        (
                            f"Asset '{asset_name}' experimental.art_direction.style_tags "
                            f"must be a list of strings"
                        ),
                        asset=asset_name,
                        path="experimental.art_direction.style_tags",
                        suggested_repairs=[
                            'Use a list of strings, e.g. style_tags = ["weathered_industrial"]',
                        ],
                    )
                )
        elif not isinstance(value, str):
            checker.diagnostics.append(
                diag(
                    "L7102",
                    "experimental_art_direction_invalid_value",
                    "error",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.art_direction.{field} "
                        f"must be a string"
                    ),
                    asset=asset_name,
                    path=f"experimental.art_direction.{field}",
                    suggested_repairs=[
                        f'Use a string value, e.g. {field} = "..."',
                    ],
                )
            )


def _check_references(
    checker: Any, asset_name: str, references: Any
) -> None:
    if not isinstance(references, dict):
        checker.diagnostics.append(
            diag(
                "L7103",
                "experimental_references_invalid_path",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental.references must be a "
                    f"block with a `use` field"
                ),
                asset=asset_name,
                path="experimental.references",
                suggested_repairs=[
                    'Wrap as `references { use = "<path>" }`',
                ],
            )
        )
        return
    _check_unknown_fields(
        checker,
        asset_name,
        "experimental.references",
        references,
        {"use", "_resolved_path"},
        code="L7103",
        name="experimental_references_invalid_path",
        suggested="Remove the unsupported field from references",
    )
    use_value = references.get("use")
    if not isinstance(use_value, str) or not use_value:
        checker.diagnostics.append(
            diag(
                "L7103",
                "experimental_references_invalid_path",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental.references.use must be "
                    f"a non-empty string"
                ),
                asset=asset_name,
                path="experimental.references.use",
                suggested_repairs=[
                    'Set `use = "examples/refs/asset_quality/<name>"`',
                ],
            )
        )
        return
    resolved_path = references.get("_resolved_path")
    candidate = _resolve_path_for_check(checker, resolved_path, use_value)
    if candidate is None or not candidate.exists() or not candidate.is_dir():
        checker.diagnostics.append(
            diag(
                "L7103",
                "experimental_references_invalid_path",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental.references.use path "
                    f"'{use_value}' does not resolve to an existing directory"
                ),
                asset=asset_name,
                path="experimental.references.use",
                details={"use": use_value},
                suggested_repairs=[
                    "Confirm the path exists relative to the source .lth file",
                    "Phase 11 fixtures live under examples/refs/asset_quality/<name>",
                ],
            )
        )


def _resolve_path_for_check(
    checker: Any, resolved_path: Any, use_value: str
) -> Path | None:
    source_path = checker.program.get("_source_path") if isinstance(checker.program, dict) else None
    roots: list[Path] = []
    if source_path:
        roots.append(Path(source_path).resolve().parent)
    roots.append(_REPO_ROOT)
    if isinstance(resolved_path, str) and resolved_path:
        try:
            candidate = Path(resolved_path).resolve()
        except (OSError, RuntimeError):
            return None
        if _path_within_any_root(candidate, roots):
            return candidate
        return None
    for root in roots:
        try:
            candidate = safe_resolve(root, use_value)
        except (PathGuardError, OSError, RuntimeError):
            continue
        if candidate.exists():
            return candidate
    return None


def _path_within_any_root(candidate: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            resolved_root = root.resolve()
        except (OSError, RuntimeError):
            continue
        if candidate == resolved_root:
            return True
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            continue
        return True
    return False


def _check_kit(checker: Any, asset: dict[str, Any], kit: Any) -> None:
    asset_name = asset.get("name", "")
    if not isinstance(kit, dict):
        checker.diagnostics.append(
            diag(
                "L7105",
                "experimental_kit_invalid_format",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental.kit must be a block "
                    f"with a `use` list"
                ),
                asset=asset_name,
                path="experimental.kit",
                suggested_repairs=[
                    'Wrap as `kit { use = ["category.name", ...] }`',
                ],
            )
        )
        return
    _check_unknown_fields(
        checker,
        asset_name,
        "experimental.kit",
        kit,
        {"use"},
        code="L7105",
        name="experimental_kit_invalid_format",
        suggested="Remove the unsupported field from kit",
    )
    raw_use = kit.get("use")
    if not isinstance(raw_use, list):
        checker.diagnostics.append(
            diag(
                "L7105",
                "experimental_kit_invalid_format",
                "error",
                "typecheck",
                (
                    f"Asset '{asset_name}' experimental.kit.use must be a list "
                    f"of strings"
                ),
                asset=asset_name,
                path="experimental.kit.use",
                suggested_repairs=[
                    'Use a list, e.g. use = ["fasteners.hex_bolt_m6"]',
                ],
            )
        )
        return
    library = _safe_load_kit_library_for_check()
    known_parts: dict[str, Any] | None = (
        _kit_library_parts_by_key(library) if library is not None else None
    )
    asset_families = _asset_family_candidates(asset)
    asset_family = asset_families[0]
    for entry in raw_use:
        if not isinstance(entry, str) or not entry:
            checker.diagnostics.append(
                diag(
                    "L7105",
                    "experimental_kit_invalid_format",
                    "error",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.kit.use must contain "
                        f"only strings"
                    ),
                    asset=asset_name,
                    path="experimental.kit.use",
                    suggested_repairs=[
                        'Use category.name strings, e.g. "fasteners.hex_bolt_m6"',
                    ],
                )
            )
            continue
        if "." not in entry or entry.count(".") != 1:
            checker.diagnostics.append(
                diag(
                    "L7105",
                    "experimental_kit_invalid_format",
                    "error",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.kit.use entry "
                        f"'{entry}' must use the `<category>.<name>` format"
                    ),
                    asset=asset_name,
                    path="experimental.kit.use",
                    details={"entry": entry},
                    suggested_repairs=[
                        'Use the form "<category>.<name>", e.g. "fasteners.hex_bolt_m6"',
                    ],
                )
            )
            continue
        if known_parts is None:
            checker.diagnostics.append(
                diag(
                    "L7104",
                    "experimental_kit_unknown_part",
                    "warning",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.kit.use entry "
                        f"'{entry}' could not be validated against the kit library"
                    ),
                    asset=asset_name,
                    path="experimental.kit.use",
                    details={"entry": entry, "reason": "kit_library_unavailable"},
                    suggested_repairs=[
                        "Verify the kit library loads (std/kits/hardsurface/)",
                    ],
                )
            )
            continue
        part = known_parts.get(entry)
        if part is None:
            checker.diagnostics.append(
                diag(
                    "L7104",
                    "experimental_kit_unknown_part",
                    "error",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.kit.use entry "
                        f"'{entry}' is not present in the loaded kit library"
                    ),
                    asset=asset_name,
                    path="experimental.kit.use",
                    details={"entry": entry},
                    suggested_repairs=[
                        f"Remove '{entry}' from kit.use",
                        "Inspect available parts under std/kits/hardsurface/<category>/",
                    ],
                )
            )
            continue
        allowed_families = getattr(part, "allowed_families", ())
        if (
            isinstance(allowed_families, tuple)
            and "*" not in allowed_families
            and not any(family in allowed_families for family in asset_families)  # no-family-dispatch: per-part `allowed_families` allowlist check via generator expression — `allowed_families` is the part's own data-driven contract (mirrors kit_library.py); `for family in asset_families` binds the comprehension variable, not a dispatch lookup
        ):
            checker.diagnostics.append(
                diag(
                    "L7106",
                    "experimental_kit_disallowed_family",
                    "error",
                    "typecheck",
                    (
                        f"Asset '{asset_name}' experimental.kit.use entry "
                        f"'{entry}' is not allowed for family '{asset_family}'"
                    ),
                    asset=asset_name,
                    path="experimental.kit.use",
                    details={
                        "entry": entry,
                        "family": asset_family,
                        "family_candidates": list(asset_families),
                        "allowed_families": list(allowed_families),
                    },
                    suggested_repairs=[
                        f"Use a kit part whose allowed_families includes '{asset_family}'",
                        f"Remove '{entry}' from kit.use",
                    ],
                )
            )


def _check_unknown_fields(
    checker: Any,
    asset_name: str,
    block_path: str,
    values: dict[str, Any],
    allowed: set[str],
    *,
    code: str,
    name: str,
    suggested: str,
) -> None:
    for field in sorted(set(values) - allowed):
        checker.diagnostics.append(
            diag(
                code,
                name,
                "error",
                "typecheck",
                f"Asset '{asset_name}' {block_path} field '{field}' is not supported",
                asset=asset_name,
                path=f"{block_path}.{field}",
                details={"field": field},
                suggested_repairs=[
                    f"{suggested}: '{field}'",
                ],
            )
        )


def _safe_load_kit_library_for_check() -> Any:
    try:
        from ..asset_quality.kit_library import load_kit_library

        return load_kit_library()
    except Exception:  # pragma: no cover - defensive guard
        return None


def _kit_library_parts_by_key(library: Any) -> dict[str, Any]:
    parts_by_key: dict[str, Any] = {}
    parts = getattr(library, "parts", None)
    if parts is None:
        return parts_by_key
    for part in parts:
        category = getattr(part, "category", None)
        name = getattr(part, "name", None)
        if isinstance(category, str) and isinstance(name, str) and category and name:
            parts_by_key[f"{category}.{name}"] = part
    return parts_by_key


def _asset_family_candidates(asset: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    assembly = asset.get("assembly")
    if isinstance(assembly, dict):
        family = assembly.get("family")
        if isinstance(family, str) and family:
            candidates.extend(_family_aliases(family))
    family = asset.get("family")
    if isinstance(family, str) and family:
        candidates.extend(_family_aliases(family))
    from_family = asset.get("from")
    if isinstance(from_family, str) and from_family:
        candidates.extend(_family_aliases(from_family))
    deduped = tuple(dict.fromkeys(candidates))
    return deduped or ("generic",)


def _family_aliases(family: str) -> tuple[str, ...]:
    if family.endswith("_family"):
        canonical = family[: -len("_family")]
        return (canonical, family) if canonical else (family,)
    return (family,)
