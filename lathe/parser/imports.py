"""Import-statement handling for the Lathe parser.

Resolves ``import`` and ``uses`` references relative to the source
file, pulls in stdlib (``std/``) files, and surfaces structured
errors for missing or circular imports.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..paths import PathGuardError, safe_resolve
from .fast_parser import _FastParser
from .grammar import (
    LatheParseError,
    PROGRAM_ARRAY_KEYS,
    REPO_ROOT,
    _dedupe_keep_first,
    _empty_program,
)
from .prompt_injection import check_and_log as _scan_prompt_injection


def _merge_programs(imported: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    merged = _empty_program()
    merged["module"] = local.get("module")
    merged["imports"] = _dedupe_keep_first([*imported.get("imports", []), *local.get("imports", [])])
    for key in PROGRAM_ARRAY_KEYS:
        merged[key] = [*imported.get(key, []), *local.get(key, [])]
    return merged


def _resolve_import_path(source_path: Path, import_name: str) -> Path:
    rel = Path(*import_name.split(".")).with_suffix(".lth")
    rel_str = str(rel)
    source_dir = source_path.parent

    # Source-relative lookup is hardened (SEC-1): a crafted import name
    # can't reach disk outside the source's own directory tree.
    # REPO_ROOT is trusted stdlib — it keeps the original resolve path.
    try:
        resolved = safe_resolve(source_dir, rel_str)
        if resolved.exists() and resolved.is_file():
            return resolved
    except PathGuardError:
        pass

    repo_candidate = (REPO_ROOT / rel).resolve()
    if repo_candidate.exists() and repo_candidate.is_file():
        return repo_candidate

    raise LatheParseError(f"Could not resolve import '{import_name}' from '{source_path}'")


def parse_text(source: str) -> dict[str, Any]:
    """Parse text.

    Args:
        source: source argument.

    Returns:
        The result.
    """
    try:
        return _FastParser(source).parse()
    except LatheParseError:
        raise
    except (ValueError, KeyError, IndexError, AttributeError, TypeError, UnicodeDecodeError) as exc:
        # _FastParser raises LatheParseError explicitly for known grammar errors
        # (re-raised above). These remaining classes cover defensive cases where
        # an internal state-machine bug or a malformed token stream surfaces as
        # a stdlib exception; wrap them in LatheParseError for a stable error
        # contract to callers.
        raise LatheParseError(str(exc)) from exc


def _parse_file_recursive(path: Path, stack: list[Path], cache: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in stack:
        cycle = " -> ".join(str(item) for item in [*stack, resolved])
        raise LatheParseError(f"Import cycle detected: {cycle}")
    if resolved in cache:
        return deepcopy(cache[resolved])

    source_text = resolved.read_text(encoding="utf-8")
    # SEC-8 pre-parse scan. Warnings by default; env/CLI flag promotes to errors.
    _scan_prompt_injection(source_text, path=str(resolved))
    raw = parse_text(source_text)
    merged_imports = _empty_program()
    for import_name in raw.get("imports", []):
        import_path = _resolve_import_path(resolved, import_name)
        imported = _parse_file_recursive(import_path, [*stack, resolved], cache)
        merged_imports = _merge_programs(merged_imports, imported)

    merged = _merge_programs(merged_imports, raw)
    cache[resolved] = deepcopy(merged)
    return merged


def parse_file(path: str | Path) -> dict[str, Any]:
    """Parse file.

    Args:
        path: path argument.

    Returns:
        The result.
    """
    resolved = Path(path).resolve()
    program = _parse_file_recursive(resolved, [], {})
    program["_source_path"] = str(resolved)
    return program
