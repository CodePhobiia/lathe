"""Canonical formatter for Lathe ``.lth`` source files.

Operates at the token level. The source is tokenized (preserving
comments and newlines), then re-emitted with canonical whitespace:

* 2-space indentation, driven by ``{`` / ``}`` depth
* one statement per line; single blank line allowed between groups
* trailing commas on multi-line list / call-argument literals
* consistent inline spacing around operators and punctuation
* no trailing whitespace on any line
* single trailing newline at EOF
* ``//`` and ``/* */`` comments preserved in place

Public API:

* ``format_source(text)`` — raw source -> canonical source
* ``format_file(path, in_place=True)`` — rewrite a file; returns True
  if a change was applied
* ``check_formatted(text)`` — ``(is_canonical, canonical_form)``

The formatter is idempotent: ``format_source(format_source(x)) ==
format_source(x)`` for any parseable ``x``.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import LatheParseError

# Token regex mirrors ``lathe.parser.tokens.TOKEN_RE`` but additionally
# surfaces horizontal whitespace and newlines so we can re-emit
# canonical whitespace.
_TOKEN_RE = re.compile(
    r"""
    (?P<newline>\n)
  | (?P<hspace>[ \t\r]+)
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


_OPEN_BRACES = {"{", "[", "("}
_CLOSE_BRACES = {"}", "]", ")"}
_CLOSE_FOR = {"{": "}", "[": "]", "(": ")"}
_ATOM_KINDS = {"ident", "string", "number", "unit"}
_BLANK_LINE_NEWLINE_COUNT = 2

_SPACED_BINARY_OPS = {
    "=",
    "==",
    "!=",
    "<",
    "<=",
    ">",
    ">=",
    "+",
    "*",
    "/",
}


class _Token:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: str) -> None:
        self.kind = kind
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"_Token({self.kind!r}, {self.value!r})"


class _UnexpectedTokenError(LatheParseError):
    def __init__(self, snippet: str) -> None:
        super().__init__(f"Unexpected token near: {snippet!r}")


class _UnmatchedClosingError(LatheParseError):
    def __init__(self, token: str) -> None:
        super().__init__(f"Unmatched closing {token!r} in source")


class _UnclosedBraceError(LatheParseError):
    def __init__(self, opener: str) -> None:
        super().__init__(f"Unclosed {opener!r} in source")


class _MismatchedBraceError(LatheParseError):
    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(f"Mismatched brace: expected {expected!r}, got {actual!r}")


class _UnclosedTokenIndexError(LatheParseError):
    def __init__(self, opener: str, token_index: int) -> None:
        super().__init__(f"Unclosed {opener!r} at token index {token_index}")


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(source):
        match = _TOKEN_RE.match(source, pos)
        if not match:
            snippet = source[pos : pos + 40].splitlines()[0] if source[pos:] else ""
            raise _UnexpectedTokenError(snippet)
        kind = match.lastgroup or ""
        value = match.group()
        tokens.append(_Token(kind, value))
        pos = match.end()
    return tokens


def _code_tokens(tokens: list[_Token]) -> list[_Token]:
    """Return tokens with horizontal whitespace dropped.

    Runs of newlines collapse to at most two (= one blank line).
    """
    out: list[_Token] = []
    newline_run = 0
    for tok in tokens:
        if tok.kind == "hspace":
            continue
        if tok.kind == "newline":
            newline_run += 1
            continue
        if newline_run > 0:
            out.append(_Token("newline", "\n" if newline_run == 1 else "\n\n"))
            newline_run = 0
        out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Brace validation (fail fast on obviously malformed input)
# ---------------------------------------------------------------------------


def _check_brace_balance(tokens: list[_Token]) -> None:
    stack: list[tuple[str, int]] = []
    for idx, tok in enumerate(tokens):
        if tok.kind in {"line_comment", "block_comment", "string"}:
            continue
        if tok.value in _OPEN_BRACES:
            stack.append((tok.value, idx))
        elif tok.value in _CLOSE_BRACES:
            if not stack or _CLOSE_FOR[stack[-1][0]] != tok.value:
                raise _UnmatchedClosingError(tok.value)
            stack.pop()
    if stack:
        raise _UnclosedBraceError(stack[-1][0])


# ---------------------------------------------------------------------------
# Unary-minus detection
# ---------------------------------------------------------------------------


def _is_unary_minus(tokens: list[_Token], idx: int) -> bool:
    if tokens[idx].value != "-":
        return False
    for j in range(idx - 1, -1, -1):
        prev = tokens[j]
        if prev.kind == "newline":
            # In most cases a leading '-' at the start of a logical
            # line is a unary (e.g., assignment right-hand-side).
            return True
        if prev.kind in {"line_comment", "block_comment"}:
            continue
        pv = prev.value
        if pv in _OPEN_BRACES or pv in {",", ":", "="}:
            return True
        if pv in _SPACED_BINARY_OPS:
            return True
        return pv in {"and", "or", "not", "in", "-", "+", "*", "/"}
    return True


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class _Emitter:
    def __init__(self, indent_unit: str = "  ") -> None:
        self.indent_unit = indent_unit
        self._indent_level = 0
        # Buffer of logical lines produced so far.
        self._lines: list[str] = []
        # Pieces of the in-progress line.
        self._pieces: list[str] = []
        self._blank_pending = False

    def _current_text(self) -> str:
        return "".join(self._pieces)

    def _ensure_indented(self) -> None:
        if not self._pieces:
            self._pieces.append(self.indent_unit * self._indent_level)

    def write(self, text: str) -> None:
        if not text:
            return
        self._ensure_indented()
        self._pieces.append(text)

    def last_char(self) -> str:
        for chunk in reversed(self._pieces):
            if chunk:
                return chunk[-1]
        return ""

    def line_has_content(self) -> bool:
        return any(chunk.strip() for chunk in self._pieces)

    def newline(self) -> None:
        text = self._current_text().rstrip()
        self._pieces = []
        if text:
            if self._blank_pending and self._lines:
                self._lines.append("")
            self._lines.append(text)
            self._blank_pending = False
        # Empty-line requests are ignored here; use blank_line().

    def blank_line(self) -> None:
        self.newline()
        self._blank_pending = True

    def indent(self) -> None:
        self._indent_level += 1

    def dedent(self) -> None:
        if self._indent_level > 0:
            self._indent_level -= 1

    def result(self) -> str:
        # Flush any in-progress line without re-triggering blank handling.
        text = self._current_text().rstrip()
        self._pieces = []
        if text:
            if self._blank_pending and self._lines:
                self._lines.append("")
            self._lines.append(text)
            self._blank_pending = False
        if not self._lines:
            return ""
        return "\n".join(self._lines) + "\n"


def _render_inline(tokens: list[_Token], emitter: _Emitter) -> None:
    """Render a flat list of tokens on the current line.

    The list must not contain newlines; any nested multi-line brackets
    should already have been expanded into sub-renders.
    """
    for idx, _tok in enumerate(tokens):
        _emit_one_token(tokens, idx, emitter)


def _emit_one_token(tokens: list[_Token], idx: int, emitter: _Emitter) -> None:
    tok = tokens[idx]
    # Strip internal newlines when they sneak in; caller should have
    # filtered them out.
    if tok.kind in {"newline", "hspace"}:
        return
    # Skip comments here — they are handled by the structural layer.
    if tok.kind in {"line_comment", "block_comment"}:
        # Standalone comment inside an inline stream: emit with spacing.
        _space_before(tokens, idx, emitter)
        emitter.write(tok.value)
        return

    value = tok.value

    # Unary minus: attach to next atom (handled by suppressing the
    # leading space of the *next* token via _space_before).
    if value == "-" and _is_unary_minus(tokens, idx):
        _space_before(tokens, idx, emitter)
        emitter.write("-")
        return

    _space_before(tokens, idx, emitter)
    emitter.write(value)


def _prev_real(tokens: list[_Token], idx: int) -> _Token | None:
    for j in range(idx - 1, -1, -1):
        t = tokens[j]
        if t.kind in {"newline", "hspace"}:
            continue
        return t
    return None


def _adjacent_atoms_need_space(prev: _Token, tok: _Token) -> bool:
    return (prev.kind in _ATOM_KINDS or prev.value in _CLOSE_BRACES) and (
        tok.kind in _ATOM_KINDS or tok.value in _OPEN_BRACES
    )


def _space_before(tokens: list[_Token], idx: int, emitter: _Emitter) -> None:
    tok = tokens[idx]
    prev = _prev_real(tokens, idx)
    if prev is None:
        return
    if not emitter.line_has_content():
        # Start-of-line: no leading space.
        return
    last = emitter.last_char()
    if last == "" or last.isspace():
        return

    pv, pk = prev.value, prev.kind
    tv = tok.value

    no_space_tokens = {".", "..", ","}
    if (
        pv in _OPEN_BRACES
        or tv in _CLOSE_BRACES
        or pv in no_space_tokens
        or tv in no_space_tokens
        or tv == ":"
        or (tv == "(" and pk == "ident")
        or (pv == "-" and _is_unary_minus(tokens, _idx_of(tokens, prev)))
    ):
        return
    if (
        pv in {",", ":"}
        or tv in _SPACED_BINARY_OPS
        or pv in _SPACED_BINARY_OPS
        or tv == "-"
        or pv == "-"
        or _adjacent_atoms_need_space(prev, tok)
    ):
        emitter.write(" ")


def _idx_of(tokens: list[_Token], target: _Token) -> int:
    for i, t in enumerate(tokens):
        if t is target:
            return i
    return -1


# ---------------------------------------------------------------------------
# Structural rendering
# ---------------------------------------------------------------------------


def _find_matching(tokens: list[_Token], open_idx: int) -> int:
    depth = 0
    opener = tokens[open_idx].value
    closer = _CLOSE_FOR[opener]
    for i in range(open_idx, len(tokens)):
        tok = tokens[i]
        if tok.kind in {"line_comment", "block_comment", "string"}:
            continue
        v = tok.value
        if v in _OPEN_BRACES:
            depth += 1
        elif v in _CLOSE_BRACES:
            depth -= 1
            if depth == 0:
                if v != closer:
                    raise _MismatchedBraceError(closer, v)
                return i
    raise _UnclosedTokenIndexError(opener, open_idx)


def _scan_logical_line(tokens: list[_Token], start: int, end: int) -> tuple[int, bool]:
    """Scan for the end of one logical line in a ``{ ... }`` body.

    Inside ``(...)`` / ``[...]``, newlines are ignored. A line ends at
    a top-level newline or the block's closing ``}``. A ``{`` at
    top-level signals the start of a nested block; in that case the
    returned index is one past the ``{`` and the second element is
    True.
    """
    depth = 0
    i = start
    while i < end:
        tok = tokens[i]
        if tok.kind == "newline" and depth == 0:
            return i, False
        if tok.kind in {"line_comment", "block_comment"}:
            i += 1
            continue
        v = tok.value
        if v in {"(", "["}:
            depth += 1
        elif v in {")", "]"}:
            depth -= 1
        elif v == "{":
            if depth == 0:
                return i + 1, True
            depth += 1
        elif v == "}":
            if depth == 0:
                return i, False
            depth -= 1
        i += 1
    return end, False


def _render_block_body(
    tokens: list[_Token],
    start: int,
    end: int,
    emitter: _Emitter,
) -> None:
    """Render ``tokens[start:end]`` as the body of a block.

    ``start`` points just past the opening ``{`` (or at the file
    start for the top-level program). ``end`` points at the matching
    ``}`` (or the end of tokens).
    """
    i = start
    first_line = True
    while i < end:
        # Consume leading newlines for this line. Two or more = blank line.
        newline_count = 0
        while i < end and tokens[i].kind == "newline":
            # Collapsed-newline markers from _code_tokens are either "\n"
            # (one newline) or "\n\n" (one blank line).
            newline_count += 2 if tokens[i].value == "\n\n" else 1
            i += 1
        if i >= end:
            break
        if newline_count >= _BLANK_LINE_NEWLINE_COUNT and not first_line:
            emitter.blank_line()

        # Skip further over any token we've already processed; also skip
        # any horizontal-space tokens that might have snuck through (they
        # shouldn't — _code_tokens drops them).
        # Standalone comment on its own line: emit at current indent.
        if tokens[i].kind in {"line_comment", "block_comment"}:
            _emit_standalone_comment(tokens[i], emitter)
            i += 1
            first_line = False
            continue

        line_end, opens_subblock = _scan_logical_line(tokens, i, end)
        if opens_subblock:
            # tokens[i:line_end-1] is the prefix; tokens[line_end-1] is `{`.
            prefix = tokens[i : line_end - 1]
            _render_header(prefix, emitter)
            # Attach `{` to the current line with a single leading space.
            if emitter.line_has_content() and not emitter.last_char().isspace():
                emitter.write(" ")
            emitter.write("{")
            emitter.newline()
            close_idx = _find_matching(tokens, line_end - 1)
            emitter.indent()
            _render_block_body(tokens, line_end, close_idx, emitter)
            emitter.dedent()
            emitter.write("}")
            emitter.newline()
            i = close_idx + 1
            first_line = False
            continue

        # Plain logical line.
        line_toks = tokens[i:line_end]
        # Trim leading/trailing trivia.
        line_toks = _trim_trivia(line_toks)
        if not line_toks:
            i = line_end
            first_line = False
            continue
        _render_logical_line(line_toks, emitter)
        emitter.newline()
        i = line_end
        first_line = False


def _trim_trivia(tokens: list[_Token]) -> list[_Token]:
    start = 0
    end = len(tokens)
    while start < end and tokens[start].kind in {"newline", "hspace"}:
        start += 1
    while end > start and tokens[end - 1].kind in {"newline", "hspace"}:
        end -= 1
    return tokens[start:end]


def _render_header(tokens: list[_Token], emitter: _Emitter) -> None:
    """Render the tokens that precede an opening ``{`` of a block.

    Handles nested ``[]`` / ``()`` inline.
    """
    _render_logical_line(tokens, emitter)


def _render_logical_line(tokens: list[_Token], emitter: _Emitter) -> None:
    """Render a single logical line.

    Any ``[...]`` / ``(...)`` region that contains source newlines is
    emitted multi-line with canonical indentation and trailing commas.
    """
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.kind in {"newline", "hspace"}:
            i += 1
            continue
        if tok.value in {"[", "("}:
            close = _find_matching(tokens, i)
            inner = tokens[i + 1 : close]
            multi = any(t.kind == "newline" for t in inner)
            _space_before_opener(tokens, i, emitter)
            if multi:
                _render_multiline_bracket(tok.value, inner, emitter)
            else:
                _render_inline_bracket(tok.value, inner, emitter)
            i = close + 1
            continue
        if tok.kind in {"line_comment", "block_comment"}:
            # Inline / trailing comment.
            if emitter.line_has_content() and not emitter.last_char().isspace():
                emitter.write("  ")
            emitter.write(tok.value.rstrip())
            i += 1
            continue
        _emit_structured_token(tokens, i, emitter)
        i += 1


def _space_before_opener(tokens: list[_Token], idx: int, emitter: _Emitter) -> None:
    tok = tokens[idx]
    prev = _prev_real(tokens, idx)
    if prev is None or not emitter.line_has_content():
        return
    if emitter.last_char().isspace():
        return
    pv, pk = prev.value, prev.kind

    no_space = (
        (tok.value == "(" and pk == "ident")
        or pv in _OPEN_BRACES
        or pv == ","
        or (pv == "-" and _is_unary_minus(tokens, _idx_of(tokens, prev)))
    )
    needs_space = (
        pv in {":", "="} or pv in _SPACED_BINARY_OPS or pv == "-" or pv in _CLOSE_BRACES or pk in _ATOM_KINDS
    )
    if needs_space and not no_space:
        emitter.write(" ")


def _structured_token_needs_space(
    tokens: list[_Token],
    prev: _Token,
    tok: _Token,
) -> bool:
    pv, pk = prev.value, prev.kind
    tv = tok.value
    no_space_tokens = {".", ".."}
    if (
        pv in _OPEN_BRACES
        or tv in _CLOSE_BRACES
        or pv in no_space_tokens
        or tv in no_space_tokens
        or tv in {",", ":"}
        or (tv == "(" and pk == "ident")
        or (pv == "-" and _is_unary_minus(tokens, _idx_of(tokens, prev)))
    ):
        return False
    return (
        pv in {",", ":"}
        or tv in _SPACED_BINARY_OPS
        or pv in _SPACED_BINARY_OPS
        or tv == "-"
        or pv == "-"
        or _adjacent_atoms_need_space(prev, tok)
    )


def _emit_structured_token(tokens: list[_Token], idx: int, emitter: _Emitter) -> None:
    """Emit a single non-bracket, non-comment token with proper spacing."""
    tok = tokens[idx]
    prev = _prev_real(tokens, idx)
    value = tok.value

    # Handle unary minus: attach to the following atom.
    if value == "-" and _is_unary_minus(tokens, idx):
        if prev is not None and emitter.line_has_content() and not emitter.last_char().isspace():
            pv = prev.value
            if pv not in _OPEN_BRACES and pv not in {",", ":", "="}:
                emitter.write(" ")
        emitter.write("-")
        return

    need_space = (
        prev is not None
        and emitter.line_has_content()
        and not emitter.last_char().isspace()
        and _structured_token_needs_space(tokens, prev, tok)
    )

    if need_space:
        emitter.write(" ")
    emitter.write(value)


def _render_inline_bracket(
    opener: str,
    inner: list[_Token],
    emitter: _Emitter,
) -> None:
    closer = _CLOSE_FOR[opener]
    emitter.write(opener)
    items = _split_items_top_level(inner)
    for i, item in enumerate(items):
        if i > 0:
            emitter.write(", ")
        _render_logical_line(item, emitter)
    emitter.write(closer)


def _render_multiline_bracket(
    opener: str,
    inner: list[_Token],
    emitter: _Emitter,
) -> None:
    closer = _CLOSE_FOR[opener]
    emitter.write(opener)
    emitter.newline()
    emitter.indent()
    items = _split_items_top_level(inner, keep_trailing_comments=True)
    for item in items:
        line_tokens, trailing_comment = _extract_trailing_comment(item)
        _render_logical_line(line_tokens, emitter)
        emitter.write(",")
        if trailing_comment is not None:
            emitter.write("  ")
            emitter.write(trailing_comment.value.rstrip())
        emitter.newline()
    emitter.dedent()
    emitter.write(closer)


def _extract_trailing_comment(
    tokens: list[_Token],
) -> tuple[list[_Token], _Token | None]:
    """If the item ends with a comment, peel it off as a trailing comment."""
    if not tokens:
        return tokens, None
    j = len(tokens) - 1
    while j >= 0 and tokens[j].kind in {"newline", "hspace"}:
        j -= 1
    if j < 0:
        return tokens, None
    if tokens[j].kind in {"line_comment", "block_comment"}:
        head = tokens[:j]
        while head and head[-1].kind in {"newline", "hspace"}:
            head = head[:-1]
        return head, tokens[j]
    return tokens, None


def _split_items_top_level(
    inner: list[_Token],
    *,
    keep_trailing_comments: bool = False,
) -> list[list[_Token]]:
    """Split ``inner`` at commas at this level's top."""
    items: list[list[_Token]] = []
    current: list[_Token] = []
    depth = 0
    for tok in inner:
        if tok.kind == "hspace":
            continue
        if tok.kind == "newline":
            if depth > 0:
                # Preserve inner newlines so nested multi-line brackets
                # can detect their own multi-line-ness.
                current.append(tok)
            continue
        v = tok.value
        if v in {"(", "[", "{"}:
            depth += 1
            current.append(tok)
            continue
        if v in {")", "]", "}"}:
            depth -= 1
            current.append(tok)
            continue
        if v == "," and depth == 0:
            if _non_trivia(current):
                items.append(current)
            current = []
            continue
        current.append(tok)
    if _non_trivia(current):
        items.append(current)
    return items


def _non_trivia(tokens: list[_Token]) -> bool:
    return any(t.kind not in {"newline", "hspace"} for t in tokens)


def _emit_standalone_comment(tok: _Token, emitter: _Emitter) -> None:
    if tok.kind == "line_comment":
        emitter.write(tok.value.rstrip())
        emitter.newline()
        return
    # Block comment: keep internal line breaks; each line stripped of
    # trailing whitespace.
    lines = tok.value.split("\n")
    for idx, line in enumerate(lines):
        if idx == 0:
            emitter.write(line.rstrip())
        else:
            # Preserve the author's leading whitespace inside a multi-line
            # block comment — but strip all indentation; we re-indent to
            # the current block level and left-align the continuation.
            emitter.write(line.lstrip().rstrip())
        emitter.newline()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_source(text: str) -> str:
    """Return the canonical formatted form of ``text``.

    Raises ``LatheParseError`` on unparseable input (malformed tokens,
    unmatched braces).
    """
    if not text or not text.strip():
        return ""
    raw = _tokenize(text)
    _check_brace_balance(raw)
    tokens = _code_tokens(raw)
    emitter = _Emitter()
    _render_block_body(tokens, 0, len(tokens), emitter)
    return emitter.result()


def format_file(path: Path, *, in_place: bool = True) -> bool:
    """Format the file at ``path``.

    When ``in_place`` is True and the formatted form differs, the file
    is rewritten. Returns True if the file would change (or did).
    """
    text = path.read_text(encoding="utf-8")
    formatted = format_source(text)
    if formatted == text:
        return False
    if in_place:
        path.write_text(formatted, encoding="utf-8")
    return True


def check_formatted(text: str) -> tuple[bool, str]:
    """Return ``(is_canonical, canonical_form)`` for ``text``."""
    formatted = format_source(text)
    return formatted == text, formatted
