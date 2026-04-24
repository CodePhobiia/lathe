"""Path-hardening utilities (SEC-1).

``safe_resolve`` canonicalizes a user-supplied path under an explicit
workspace root and rejects hostile inputs: absolute paths, ``..``
traversal escaping root, symlinks (unless opted-in), NUL bytes, Windows
reserved device names, 8.3 short names, trailing dots/spaces, alternate
data streams, ``\\\\?\\`` extended-length prefixes, and reparse points.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from .errors import LatheError


class PathGuardError(LatheError):
    """Raised when ``safe_resolve`` rejects a user-supplied path."""


_WIN_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# 8.3 short-name pattern: component stem contains ``~<digits>``.
_SHORT_NAME_RE = re.compile(r"~\d+")

# Prefixes that reference device namespace or extended-length paths.
_DEVICE_PREFIXES = ("\\\\?\\", "\\\\.\\", "//?/", "//./")


def _reject(msg: str, user: object) -> PathGuardError:
    return PathGuardError(f"{msg}: {user!r}")


def _check_raw_string(user_str: str) -> None:
    if "\x00" in user_str:
        raise _reject("NUL byte in path", user_str)
    for prefix in _DEVICE_PREFIXES:
        if user_str.startswith(prefix):
            raise _reject("device/extended-length prefix not allowed", user_str)


def _is_absolute_user_path(user_str: str) -> bool:
    """True if the raw user string looks absolute on any platform.

    We check both POSIX and Windows interpretations so a cross-platform
    hostile input (e.g. ``/etc/passwd`` supplied on Windows) is still
    refused regardless of host OS.
    """
    if not user_str:
        return False
    if PurePosixPath(user_str).is_absolute():
        return True
    if PureWindowsPath(user_str).is_absolute():
        return True
    # Drive-relative paths like ``C:foo`` (no separator) are still
    # suspicious — treat as absolute for rejection purposes.
    if len(user_str) >= 2 and user_str[1] == ":" and user_str[0].isalpha():
        return True
    return False


def _split_components(user_str: str) -> list[str]:
    """Split a user path on both POSIX and Windows separators."""
    normalized = user_str.replace("\\", "/")
    return [part for part in normalized.split("/") if part not in ("", ".")]


def _check_component(component: str, user_str: str) -> None:
    if ":" in component:
        raise _reject("alternate data stream / drive designator in component", user_str)
    if component.endswith(".") or component.endswith(" "):
        raise _reject("trailing dot or space in component", user_str)
    if _SHORT_NAME_RE.search(component):
        raise _reject("8.3 short-name pattern in component", user_str)
    stem = component.split(".", 1)[0].upper()
    if stem in _WIN_RESERVED_NAMES:
        raise _reject("Windows reserved device name in component", user_str)


def _is_reparse_point(path: Path) -> bool:
    """Best-effort reparse-point / symlink detection.

    On Windows, ``st_file_attributes`` (when available) gives us the
    authoritative answer via ``FILE_ATTRIBUTE_REPARSE_POINT``. We fall
    back to ``os.lstat`` + ``S_ISLNK`` which also catches POSIX symlinks.
    """
    try:
        lst = os.lstat(path)
    except (OSError, ValueError):
        return False
    if stat.S_ISLNK(lst.st_mode):
        return True
    if sys.platform == "win32":
        attrs = getattr(lst, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if attrs & reparse:
            return True
    return False


def _walk_for_reparse(
    root_resolved: Path,
    candidate: Path,
    target_resolved: Path,
) -> None:
    """Walk from candidate (pre-realpath) up to root, rejecting reparse points.

    ``realpath`` dereferences symlinks before returning, so we lose the
    information needed to spot link-in-path. Instead we walk the non-
    realpath composed path — each ``lstat`` along the way answers the
    "is this a symlink/reparse point?" question faithfully. We also
    double-check the final resolved target for completeness.
    """
    for current in (candidate, *candidate.parents):
        if _is_reparse_point(current):
            raise PathGuardError(f"symlink/reparse point in path: {current!s}")
        # Stop once we hit the workspace root (or above it).
        try:
            resolved_current = Path(os.path.realpath(current))
        except (OSError, ValueError):
            break
        if resolved_current == root_resolved:
            break
    if _is_reparse_point(target_resolved):
        raise PathGuardError(f"symlink/reparse point in path: {target_resolved!s}")


def _is_within(child: Path, root: Path) -> bool:
    try:
        child.relative_to(root)
        return True
    except ValueError:
        return False


def safe_resolve(
    root: Path | str,
    user: str | Path,
    *,
    allow_symlinks: bool = False,
) -> Path:
    """Canonicalize ``user`` under ``root``, rejecting hostile inputs.

    Args:
        root: Workspace root. Must be an existing directory; it is
            resolved via ``realpath`` before comparison.
        user: User-supplied relative path. May be ``str`` or ``Path``.
        allow_symlinks: If False (default), reject any symlink or
            Windows reparse point in the resolved chain.

    Returns:
        The resolved, canonical :class:`Path`, guaranteed to be a
        descendant (or equal to) ``root``.

    Raises:
        PathGuardError: On any rejection condition.
    """
    user_str = os.fspath(user)
    _check_raw_string(user_str)

    if _is_absolute_user_path(user_str):
        raise _reject("absolute path not allowed", user_str)

    components = _split_components(user_str)
    for component in components:
        if component == "..":
            # Traversal components are allowed syntactically; the final
            # realpath check will catch any escape attempts.
            continue
        _check_component(component, user_str)

    root_path = Path(root)
    root_resolved = Path(os.path.realpath(root_path))

    candidate = root_path / user_str
    resolved = Path(os.path.realpath(candidate))

    if not _is_within(resolved, root_resolved) and resolved != root_resolved:
        raise _reject(f"path escapes root {root_resolved!s}", user_str)

    if not allow_symlinks:
        _walk_for_reparse(root_resolved, candidate, resolved)

    return resolved


__all__ = ["PathGuardError", "safe_resolve"]
