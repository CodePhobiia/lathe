"""Contract lint: Lathe must never dispatch on family name for behavior.

Catches every form of family-keyed dispatch the procedural synthesizer
is meant to replace. Lives in CI from Cycle 1 onward; every cycle's
verification floor includes it.

Patterns scanned in every ``lathe/**/*.py`` file:

  1. ``_RECIPES.get(family)`` or ``_RECIPES[family]``
  2. ``dict.get(family)`` / ``dict[family]`` against ``_FAMILY_*`` /
     ``_GRAMMARS`` / similar behavior maps
  3. ``family ==`` / ``family in {...}`` / ``family in (...)``

Exemptions live in ``_family_dispatch_allowlist.ALLOWLIST`` with a
reason per entry. Inline ``# no-family-dispatch: <reason>`` comments
on the offending line also exempt that line.

The procedural synthesizer
(``lathe/asset_quality/procedural_synthesizer/``) must NEVER appear in
this exemption list. Its family-dispatch-free guarantee is
structurally enforced.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import pytest

from ._family_dispatch_allowlist import ALLOWLIST


_REPO_ROOT = Path(__file__).resolve().parents[2]
_LATHE_ROOT = _REPO_ROOT / "lathe"

# Pattern 1: _RECIPES.get(family) / _RECIPES[family]
_RECIPES_PATTERN = re.compile(r"_RECIPES\s*(\.get\s*\(\s*family\b|\[\s*family\b)")

# Pattern 2: _FAMILY_*[family] / _GRAMMARS[family] / similar
_FAMILY_DICT_PATTERN = re.compile(
    r"(_FAMILY_[A-Z_]+|_GRAMMARS|_FAMILIES)\s*(\.get\s*\(\s*family\b|\[\s*family\b)"
)

# Pattern 3: family == "..." / family in {...} / family in (...) /
# family in [...]
_FAMILY_EQUALITY_PATTERN = re.compile(r"\bfamily\s*==\s*[\"']")
_FAMILY_MEMBERSHIP_PATTERN = re.compile(r"\bfamily\s+in\s+[\(\{\[]")


_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_RECIPES_PATTERN, "recipe_dict_dispatch"),
    (_FAMILY_DICT_PATTERN, "family_behavior_dict_dispatch"),
    (_FAMILY_EQUALITY_PATTERN, "family_equality_check"),
    (_FAMILY_MEMBERSHIP_PATTERN, "family_membership_check"),
)


# Pseudo-domain "core" allows family ==/in within the synthesizer's
# trace fields and reports — but only when explicitly tagged. The
# inline comment marker is the second escape hatch.
_INLINE_EXEMPT_MARKER = "no-family-dispatch:"


def _is_allowlisted(file_rel: str, line: str) -> bool:
    """Check the (file, line) against the static allowlist.

    A substring of ``"*"`` matches any line in the matched file
    (full-file allowlist — for use when a file is on the Cycle 3
    migration worklist as a whole).
    """
    for glob_pat, substring, _reason in ALLOWLIST:
        if not fnmatch.fnmatch(file_rel, glob_pat):
            continue
        if substring == "*" or substring in line:
            return True
    return False


def _is_inline_exempt(line: str) -> bool:
    return _INLINE_EXEMPT_MARKER in line


def _iter_lathe_files():
    for path in _LATHE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _scan_file(path: Path) -> list[dict[str, object]]:
    """Return a list of violations found in this file."""
    violations: list[dict[str, object]] = []
    rel = path.relative_to(_REPO_ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations
    for line_number, line in enumerate(text.splitlines(), start=1):
        # Skip comments entirely
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if _is_inline_exempt(line):
            continue
        for pattern, kind in _PATTERNS:
            if pattern.search(line):
                if _is_allowlisted(rel, line):
                    continue
                violations.append(
                    {
                        "file": rel,
                        "line_number": line_number,
                        "line": line.strip(),
                        "kind": kind,
                    }
                )
    return violations


def test_no_family_dispatch_in_lathe_codebase() -> None:
    """Every family-keyed dispatch in lathe/ must be allowlisted or absent.

    Fails fast with a clear message listing every violation. Run
    locally with::

        python -m pytest tests/contract/test_no_family_dispatch.py -q

    Add exemptions to ``_family_dispatch_allowlist.ALLOWLIST`` with a
    reason justifying why the occurrence is metadata-only / reporting.
    """
    violations: list[dict[str, object]] = []
    for path in _iter_lathe_files():
        violations.extend(_scan_file(path))

    if violations:
        lines = ["Found family-name dispatch violations in lathe/:"]
        for v in violations:
            lines.append(
                f"  {v['file']}:{v['line_number']} [{v['kind']}]  {v['line']}"
            )
        lines.append("")
        lines.append("Each violation must either:")
        lines.append(
            "  1. Be removed (preferred — Lathe is procedural, "
            "family is metadata)."
        )
        lines.append(
            "  2. Carry an inline `# no-family-dispatch: <reason>` "
            "comment justifying why it is metadata-only."
        )
        lines.append(
            "  3. Be added to tests/contract/_family_dispatch_allowlist.py "
            "ALLOWLIST with a reason."
        )
        pytest.fail("\n".join(lines))


def test_no_family_dispatch_inside_procedural_synthesizer() -> None:
    """The procedural synthesizer package must never dispatch on family.

    Stronger than the global check: even allowlisted patterns are not
    permitted inside the synthesizer. The synthesizer is structurally
    family-blind by design.
    """
    synth_root = _LATHE_ROOT / "asset_quality" / "procedural_synthesizer"
    if not synth_root.exists():
        pytest.skip("procedural_synthesizer package not present")

    violations: list[dict[str, object]] = []
    for path in synth_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pattern, kind in _PATTERNS:
                if pattern.search(line):
                    violations.append(
                        {
                            "file": rel,
                            "line_number": line_number,
                            "line": line.strip(),
                            "kind": kind,
                        }
                    )

    if violations:
        lines = [
            "The procedural synthesizer package introduced "
            "family-keyed dispatch. This is a hard architectural "
            "violation; not even the allowlist permits it here."
        ]
        for v in violations:
            lines.append(
                f"  {v['file']}:{v['line_number']} [{v['kind']}]  {v['line']}"
            )
        pytest.fail("\n".join(lines))


def test_synthesizer_family_dispatch_used_is_false_by_construction() -> None:
    """The synthesizer's trace invariant is enforced at TraceBuilder.freeze.

    Verifies that the SynthesizerTrace dataclass refuses to construct
    with family_dispatch_used != False.
    """
    from lathe.asset_quality.procedural_synthesizer import (
        SynthesizerTrace,
    )

    # Frozen trace with True is rejected
    with pytest.raises(AssertionError):
        SynthesizerTrace(
            entries=(),
            family_dispatch_used=True,
            attempted_via="procedural_engine",
        )

    # Frozen trace with False constructs cleanly
    trace = SynthesizerTrace(
        entries=(),
        family_dispatch_used=False,
        attempted_via="procedural_engine",
    )
    assert trace.family_dispatch_used is False
    assert trace.attempted_via == "procedural_engine"
