"""Prompt-injection static scanner for ``.lth`` sources (SEC-8, V0.2 P0).

Pre-parse pass invoked from :func:`lathe.parser.parse_file` that flags
suspected prompt-injection patterns in comments and string literals so
downstream learned-provider calls cannot be coerced by hostile source.

Severity is configurable — by default the scanner emits *warnings* and
parsing proceeds. Callers that pass ``strict=True`` (or set the env
variable ``LATHE_STRICT_PROMPT_INJECTION=1``) turn the warnings into
errors that abort parsing.

Diagnostic codes:

* ``L7001`` — phrase matching a known prompt-injection instruction
* ``L7002`` — Unicode bidirectional-direction override in source
* ``L7003`` — chat-template sentinel token (``<|im_start|>`` etc.)
* ``L7004`` — oversized string literal (>10k chars, probable payload)
* ``L7005`` — system-prompt impersonation (``system prompt:``, etc.)

Each diagnostic carries the 1-based line + column, the matched text
(truncated to 80 chars), and a code/severity/remediation tuple. See
``docs/security/prompt_injection.md`` for operator-facing guidance.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..logging_utils import error as log_error
from ..logging_utils import warning as log_warning

_LOG = logging.getLogger(__name__)


OVERSIZED_LITERAL_CHARS: int = 10_000
"""Maximum allowed characters in a single string literal before we flag it."""


_INJECTION_PHRASES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous_instructions",
        re.compile(
            r"ignore\s+(?:all\s+|previous\s+|prior\s+)+instructions",
            re.IGNORECASE,
        ),
    ),
    ("disregard_above", re.compile(r"disregard\s+(?:all|any|the)\s+(?:above|prior|previous)", re.IGNORECASE)),
    ("forget_everything", re.compile(r"forget\s+(?:everything|all\s+prior|all\s+previous)", re.IGNORECASE)),
    ("jailbreak", re.compile(r"\b(?:jailbreak|DAN\s+mode|developer\s+mode)\b", re.IGNORECASE)),
)

_SYSTEM_PROMPT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a[n]?\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:an?\s+)?(?:administrator|root|system)", re.IGNORECASE),
)

_CHAT_SENTINELS: tuple[str, ...] = (
    "<|im_start|>",
    "<|im_end|>",
    "<|endoftext|>",
    "<|system|>",
    "<|assistant|>",
    "<|user|>",
)

# Unicode bidirectional + invisible direction overrides that can hide
# malicious text in otherwise-innocuous string literals.
_DIRECTION_OVERRIDES: tuple[str, ...] = (
    "\u202a",  # LRE
    "\u202b",  # RLE
    "\u202c",  # PDF
    "\u202d",  # LRO
    "\u202e",  # RLO
    "\u2066",  # LRI
    "\u2067",  # RLI
    "\u2068",  # FSI
    "\u2069",  # PDI
)


Severity = str  # "warning" | "error"


@dataclass
class PromptInjectionDiagnostic:
    """One row of scanner output."""

    code: str
    name: str
    severity: Severity
    line: int
    column: int
    match: str
    message: str
    remediation: str

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready dictionary representation."""
        return {
            "code": self.code,
            "name": self.name,
            "severity": self.severity,
            "line": self.line,
            "column": self.column,
            "match": self.match,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass
class PromptInjectionScanResult:
    """Aggregated scanner output for a single source."""

    diagnostics: list[PromptInjectionDiagnostic] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """Return whether the scan found no diagnostics."""
        return not self.diagnostics

    @property
    def has_errors(self) -> bool:
        """Return whether any diagnostic is an error."""
        return any(d.severity == "error" for d in self.diagnostics)


class PromptInjectionError(Exception):
    """Raised when strict mode is enabled and any diagnostic fires."""

    def __init__(self, diagnostics: list[PromptInjectionDiagnostic]):
        """Build an exception from scanner diagnostics."""
        self.diagnostics = diagnostics
        lines = [f"{d.code} {d.name} (line {d.line}:{d.column}): {d.message}" for d in diagnostics]
        super().__init__("Prompt-injection scanner rejected source:\n  " + "\n  ".join(lines))


def _line_col(source: str, index: int) -> tuple[int, int]:
    prefix = source[:index]
    line = prefix.count("\n") + 1
    column = index + 1 if line == 1 else index - prefix.rfind("\n")
    return line, column


def _iter_string_literals(source: str) -> Iterable[tuple[int, int, str]]:
    """Yield (start_index, end_index, contents) for each string literal.

    Handles single and double-quoted literals with standard backslash
    escapes. Raw behavior is acceptable because we only read the
    bytes — we never execute the escapes.
    """
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in ('"', "'"):
            quote = ch
            start = i
            i += 1
            while i < n:
                c = source[i]
                if c == "\\" and i + 1 < n:
                    i += 2
                    continue
                if c == quote:
                    yield start, i + 1, source[start + 1 : i]
                    i += 1
                    break
                i += 1
            else:
                break
        elif ch == "#":  # comment to end-of-line
            end = source.find("\n", i)
            end = n if end == -1 else end
            yield i, end, source[i:end]
            i = end
        else:
            i += 1


def _mk(
    *,
    code: str,
    name: str,
    severity: Severity,
    source: str,
    index: int,
    match: str,
    message: str,
    remediation: str,
) -> PromptInjectionDiagnostic:
    line, col = _line_col(source, index)
    snippet = match.replace("\n", " ")
    if len(snippet) > 80:
        snippet = snippet[:77] + "..."
    return PromptInjectionDiagnostic(
        code=code,
        name=name,
        severity=severity,
        line=line,
        column=col,
        match=snippet,
        message=message,
        remediation=remediation,
    )


def scan_source(source: str, *, strict: bool = False) -> PromptInjectionScanResult:
    """Scan raw ``.lth`` source text for prompt-injection patterns.

    Args:
        source: UTF-8 decoded source text.
        strict: when True, every finding is reported as ``severity="error"``.

    Returns:
        :class:`PromptInjectionScanResult` listing zero or more diagnostics.
    """
    severity: Severity = "error" if strict else "warning"
    diags: list[PromptInjectionDiagnostic] = []

    for start, _end, content in _iter_string_literals(source):
        for name, pattern in _INJECTION_PHRASES:
            for match in pattern.finditer(content):
                diags.append(
                    _mk(
                        code="L7001",
                        name=f"prompt_injection_{name}",
                        severity=severity,
                        source=source,
                        index=start + match.start(),
                        match=match.group(0),
                        message="Suspected prompt-injection instruction in source",
                        remediation=(
                            "Remove the instruction, or mark the file as "
                            "allowlisted in docs/security/prompt_injection.md"
                        ),
                    )
                )

        for pattern in _SYSTEM_PROMPT_PATTERNS:
            for match in pattern.finditer(content):
                diags.append(
                    _mk(
                        code="L7005",
                        name="system_prompt_impersonation",
                        severity=severity,
                        source=source,
                        index=start + match.start(),
                        match=match.group(0),
                        message="Source appears to impersonate a system prompt",
                        remediation=(
                            "Rephrase the literal so it cannot be interpreted as a system instruction"
                        ),
                    )
                )

        for sentinel in _CHAT_SENTINELS:
            idx = 0
            while True:
                found = content.find(sentinel, idx)
                if found == -1:
                    break
                diags.append(
                    _mk(
                        code="L7003",
                        name="chat_template_sentinel",
                        severity=severity,
                        source=source,
                        index=start + found,
                        match=sentinel,
                        message="Source contains a chat-template sentinel token",
                        remediation="Escape or remove the sentinel token",
                    )
                )
                idx = found + len(sentinel)

        for char in _DIRECTION_OVERRIDES:
            idx = 0
            while True:
                found = content.find(char, idx)
                if found == -1:
                    break
                diags.append(
                    _mk(
                        code="L7002",
                        name="unicode_direction_override",
                        severity=severity,
                        source=source,
                        index=start + found,
                        match=repr(char),
                        message="Source contains a Unicode direction-override character",
                        remediation="Replace the directional override with its visible equivalent",
                    )
                )
                idx = found + 1

        if len(content) > OVERSIZED_LITERAL_CHARS:
            diags.append(
                _mk(
                    code="L7004",
                    name="oversized_literal",
                    severity=severity,
                    source=source,
                    index=start,
                    match=f"{len(content)} chars",
                    message=f"String literal exceeds {OVERSIZED_LITERAL_CHARS} characters",
                    remediation="Move large payloads to a separate asset file and reference by path",
                )
            )

    return PromptInjectionScanResult(diagnostics=diags)


def check_and_log(
    source: str,
    *,
    path: str | None = None,
    strict: bool | None = None,
) -> PromptInjectionScanResult:
    """Run :func:`scan_source` and emit warnings / raise on errors.

    Invoked by :func:`lathe.parser.parse_file` as a pre-parse pass.
    When ``strict`` is ``None`` the env variable
    ``LATHE_STRICT_PROMPT_INJECTION`` controls the mode.
    """
    if strict is None:
        strict = os.getenv("LATHE_STRICT_PROMPT_INJECTION", "0") in ("1", "true", "yes")
    result = scan_source(source, strict=strict)
    if result.clean:
        return result
    location = path or "<source>"
    for diag in result.diagnostics:
        if diag.severity == "error":
            log_error(
                _LOG,
                "lathe.parser.prompt_injection.diagnostic",
                "{code} {name} ({location}:{line}:{column}): {message} [{match}]",
                code=diag.code,
                name=diag.name,
                location=location,
                line=diag.line,
                column=diag.column,
                message=diag.message,
                match=diag.match,
                severity=diag.severity,
                remediation=diag.remediation,
            )
        else:
            log_warning(
                _LOG,
                "lathe.parser.prompt_injection.diagnostic",
                "{code} {name} ({location}:{line}:{column}): {message} [{match}]",
                code=diag.code,
                name=diag.name,
                location=location,
                line=diag.line,
                column=diag.column,
                message=diag.message,
                match=diag.match,
                severity=diag.severity,
                remediation=diag.remediation,
            )
    if strict and result.diagnostics:
        raise PromptInjectionError(result.diagnostics)
    return result


__all__ = [
    "OVERSIZED_LITERAL_CHARS",
    "PromptInjectionDiagnostic",
    "PromptInjectionError",
    "PromptInjectionScanResult",
    "check_and_log",
    "scan_source",
]
