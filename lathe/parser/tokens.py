from __future__ import annotations

import re

from .grammar import LatheParseError


TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<line_comment>//[^\n]*)
  | (?P<block_comment>/\*[\s\S]*?\*/)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<unit>-?(?:\d+\.\d+|\d+)(?:mm|cm|m|deg|rad|g|kg|ms|s|kb|mb|gb|px|px_per_m|px_per_cm)\b)
  | (?P<number>-?(?:\d+\.\d+|\d+))
  | (?P<op>\.\.|==|!=|<=|>=|[{}()\[\],:=.+\-*/<>])
  | (?P<ident>[a-z][a-z0-9_]*)
    """,
    re.VERBOSE,
)


class _TokenStream:
    def __init__(self, source: str) -> None:
        self.tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(source):
            match = TOKEN_RE.match(source, pos)
            if not match:
                snippet = source[pos : pos + 40].splitlines()[0]
                raise LatheParseError(f"Unexpected token near: {snippet!r}")
            pos = match.end()
            kind = match.lastgroup or ""
            value = match.group()
            if kind in {"ws", "line_comment", "block_comment"}:
                continue
            self.tokens.append((kind, value))
        self.tokens.append(("eof", ""))
        self.index = 0

    def peek(self, value: str | None = None) -> str:
        current = self.tokens[self.index][1]
        return current if value is None else current == value

    def kind(self) -> str:
        return self.tokens[self.index][0]

    def pop(self, expected: str | None = None) -> str:
        value = self.tokens[self.index][1]
        if expected is not None and value != expected:
            raise LatheParseError(f"Expected '{expected}', got '{value or 'end of file'}'")
        self.index += 1
        return value

    def pop_ident(self) -> str:
        if self.kind() != "ident":
            raise LatheParseError(f"Expected identifier, got '{self.peek() or 'end of file'}'")
        return self.pop()

    def eof(self) -> bool:
        return self.kind() == "eof"
