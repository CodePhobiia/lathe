"""Lathe parser package.

Turns ``.lth`` source text into the raw AST JSON consumed by
``lathe.normalizer``. This module re-exports the public parser entry
points; implementation is split across ``fast_parser``, ``grammar``,
``imports`` and the ``transformer*`` modules.
"""

from __future__ import annotations

from .grammar import (
    DuplicateFieldError,
    GRAMMAR_PATH,
    LatheParseError,
    PROGRAM_ARRAY_KEYS,
    REPO_ROOT,
)
from .imports import (
    _merge_programs,
    _parse_file_recursive,
    _resolve_import_path,
    parse_file,
    parse_text,
)
from .tokens import TOKEN_RE, _TokenStream
from .fast_parser import _FastParser
from .transformer import _LatheTransformer


__all__ = [
    "DuplicateFieldError",
    "GRAMMAR_PATH",
    "LatheParseError",
    "PROGRAM_ARRAY_KEYS",
    "REPO_ROOT",
    "TOKEN_RE",
    "parse_file",
    "parse_text",
]
