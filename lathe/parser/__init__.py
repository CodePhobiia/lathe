"""Lathe parser package.

Turns ``.lth`` source text into the raw AST JSON consumed by
``lathe.normalizer``. This module re-exports the public parser entry
points; implementation is split across ``fast_parser``, ``grammar``,
``imports`` and the ``transformer*`` modules.
"""

from __future__ import annotations

from .grammar import (
    GRAMMAR_PATH,
    PROGRAM_ARRAY_KEYS,
    REPO_ROOT,
    DuplicateFieldError,
    LatheParseError,
)
from .imports import parse_file, parse_text
from .prompt_injection import (
    PromptInjectionDiagnostic,
    PromptInjectionError,
    PromptInjectionScanResult,
    scan_source,
)
from .tokens import TOKEN_RE

__all__ = [
    "GRAMMAR_PATH",
    "PROGRAM_ARRAY_KEYS",
    "REPO_ROOT",
    "TOKEN_RE",
    "DuplicateFieldError",
    "LatheParseError",
    "PromptInjectionDiagnostic",
    "PromptInjectionError",
    "PromptInjectionScanResult",
    "parse_file",
    "parse_text",
    "scan_source",
]
