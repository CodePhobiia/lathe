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
from ..security import InputClass, TrustLevel, boundary_policy, ingress_boundary
from .fast_parser import _FastParser
from .grammar import (
    PROGRAM_ARRAY_KEYS,
    REPO_ROOT,
    LatheParseError,
    _dedupe_keep_first,
    _empty_program,
)
from .prompt_injection import check_and_log as _scan_prompt_injection

_LATHE_SOURCE_BOUNDARY = boundary_policy(
    name="lathe_source_parse",
    input_class=InputClass.LATHE_SOURCE,
    trust_level=TrustLevel.UNTRUSTED,
    controls=(
        "utf8_decode",
        "prompt_injection_scan",
        "grammar_parse_only",
        "safe_import_path_resolution",
        "source_byte_budget",
        "import_depth_count_budget",
    ),
)
_MAX_SOURCE_BYTES = 1024 * 1024
_MAX_IMPORT_DEPTH = 32
_MAX_IMPORT_COUNT = 256


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


@ingress_boundary(_LATHE_SOURCE_BOUNDARY)
def parse_text(source: str) -> dict[str, Any]:
    """Parse text.

    Args:
        source: source argument.

    Returns:
        The result.
    """
    if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
        raise LatheParseError(f"Lathe source exceeds {_MAX_SOURCE_BYTES} byte parse budget")
    try:
        return _FastParser(source).parse()
    except LatheParseError:
        raise
    except (
        RecursionError,
        ValueError,
        KeyError,
        IndexError,
        AttributeError,
        TypeError,
        UnicodeDecodeError,
    ) as exc:
        # _FastParser raises LatheParseError explicitly for known grammar errors
        # (re-raised above). These remaining classes cover defensive cases where
        # an internal state-machine bug or a malformed token stream surfaces as
        # a stdlib exception; wrap them in LatheParseError for a stable error
        # contract to callers.
        raise LatheParseError(str(exc)) from exc


def _parse_file_recursive(
    path: Path,
    stack: list[Path],
    cache: dict[Path, dict[str, Any]],
    import_counter: list[int],
) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in stack:
        cycle = " -> ".join(str(item) for item in [*stack, resolved])
        raise LatheParseError(f"Import cycle detected: {cycle}")
    # ``stack`` describes the ancestor chain *above* this entry; the new
    # depth, including this file, is ``len(stack) + 1``. The previous
    # check used ``> _MAX_IMPORT_DEPTH`` and so allowed one extra level.
    depth = len(stack) + 1
    if depth > _MAX_IMPORT_DEPTH:
        raise LatheParseError(f"Import depth exceeded {_MAX_IMPORT_DEPTH} files")
    if resolved in cache:
        return deepcopy(cache[resolved])

    import_counter[0] += 1
    if import_counter[0] > _MAX_IMPORT_COUNT:
        raise LatheParseError(f"Import count exceeded {_MAX_IMPORT_COUNT} files")
    try:
        if resolved.stat().st_size > _MAX_SOURCE_BYTES:
            raise LatheParseError(f"Lathe source exceeds {_MAX_SOURCE_BYTES} byte parse budget: {resolved}")
    except (FileNotFoundError, PermissionError):
        raise
    except OSError as exc:
        raise LatheParseError(f"Could not stat source file '{resolved}': {exc}") from exc
    try:
        source_text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LatheParseError(f"Could not read source file '{resolved}': {exc}") from exc
    # SEC-8 pre-parse scan. Warnings by default; env/CLI flag promotes to errors.
    _scan_prompt_injection(source_text, path=str(resolved))
    raw = parse_text(source_text)
    merged_imports = _empty_program()
    for import_name in raw.get("imports", []):
        import_path = _resolve_import_path(resolved, import_name)
        imported = _parse_file_recursive(import_path, [*stack, resolved], cache, import_counter)
        merged_imports = _merge_programs(merged_imports, imported)

    merged = _merge_programs(merged_imports, raw)
    cache[resolved] = deepcopy(merged)
    return merged


@ingress_boundary(_LATHE_SOURCE_BOUNDARY)
def parse_file(path: str | Path) -> dict[str, Any]:
    """Parse file.

    Args:
        path: path argument.

    Returns:
        The result.
    """
    resolved = Path(path).resolve()
    program = _parse_file_recursive(resolved, [], {}, [0])
    program["_source_path"] = str(resolved)
    return program
