"""Parser for the Lathe attribute mini-language.

The language is deliberately tiny — see ``ast.py`` for the supported nodes.
This module exposes :func:`parse` and :func:`parse_expression`. The parser
is a hand-written recursive-descent / Pratt parser; we avoid taking a
dependency on lark or any external library to keep the surface area small
and to guarantee deterministic behavior.

Forbidden Python-style constructs (``for``, ``while``, ``def``, ``import``,
``lambda``, ``return``, ``class``, etc.) are explicitly rejected so users
cannot smuggle in Turing-complete escapes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import ast as _ast
from .errors import ForbiddenConstructError, ParseError, SourceSpan

_FORBIDDEN_KEYWORDS = frozenset(
    {
        "for",
        "while",
        "def",
        "class",
        "import",
        "from",
        "lambda",
        "return",
        "yield",
        "global",
        "nonlocal",
        "try",
        "except",
        "finally",
        "raise",
        "with",
        "assert",
        "del",
        "if",
        "elif",
        "else",
        "pass",
        "break",
        "continue",
        "as",
        "is",
        "in",
    }
)

_NAMED_COLORS: dict[str, tuple[float, float, float, float]] = {
    "black": (0.0, 0.0, 0.0, 1.0),
    "white": (1.0, 1.0, 1.0, 1.0),
    "red": (1.0, 0.0, 0.0, 1.0),
    "green": (0.0, 1.0, 0.0, 1.0),
    "blue": (0.0, 0.0, 1.0, 1.0),
    "yellow": (1.0, 1.0, 0.0, 1.0),
    "magenta": (1.0, 0.0, 1.0, 1.0),
    "cyan": (0.0, 1.0, 1.0, 1.0),
    "gray": (0.5, 0.5, 0.5, 1.0),
    "grey": (0.5, 0.5, 0.5, 1.0),
    "transparent": (0.0, 0.0, 0.0, 0.0),
}

# ----------------------------------------------------------------------
# Tokenizer
# ----------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<WS>[ \t\r\n]+)
  | (?P<COMMENT>\#[^\n]*)
  | (?P<HEXCOLOR>\#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?)
  | (?P<FLOAT>\d+\.\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?|\d+[eE][+-]?\d+)
  | (?P<INT>\d+)
  | (?P<STRING>"([^"\\]|\\.)*"|'([^'\\]|\\.)*')
  | (?P<AT_IDENT>@[A-Za-z_][A-Za-z_0-9]*)
  | (?P<IDENT>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<OP>==|!=|<=|>=|&&|\|\||\.\.|->|[+\-*/%<>=&|~!.,()\[\]{}:])
    """,
    re.VERBOSE,
)


@dataclass
class _Token:
    kind: str
    text: str
    start: int
    end: int


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    n = len(source)
    while i < n:
        m = _TOKEN_RE.match(source, i)
        if not m:
            span = SourceSpan(source, i, min(i + 1, n))
            raise ParseError(f"unexpected character {source[i]!r}", span)
        kind = m.lastgroup or "OP"
        text = m.group()
        if kind not in ("WS", "COMMENT"):
            tokens.append(_Token(kind, text, m.start(), m.end()))
        i = m.end()
    tokens.append(_Token("EOF", "", n, n))
    return tokens


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------


class _Parser:
    """Recursive-descent / Pratt parser. Operates over a token list."""

    def __init__(self, source: str, tokens: list[_Token]) -> None:
        self.source = source
        self.tokens = tokens
        self.pos = 0

    # -- helpers --------------------------------------------------------

    @property
    def cur(self) -> _Token:
        return self.tokens[self.pos]

    def _span(self, start_tok: _Token, end_tok: _Token | None = None) -> SourceSpan:
        end = end_tok if end_tok is not None else self.tokens[max(self.pos - 1, 0)]
        return SourceSpan(self.source, start_tok.start, end.end)

    def _peek(self, k: int = 0) -> _Token:
        return self.tokens[self.pos + k]

    def _advance(self) -> _Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind: str, text: str | None = None) -> _Token:
        tok = self.cur
        if tok.kind != kind or (text is not None and tok.text != text):
            want = text or kind
            span = SourceSpan(self.source, tok.start, tok.end)
            raise ParseError(
                f"expected {want!r} but got {tok.text!r} ({tok.kind})", span
            )
        return self._advance()

    def _match(self, kind: str, text: str | None = None) -> _Token | None:
        tok = self.cur
        if tok.kind == kind and (text is None or tok.text == text):
            return self._advance()
        return None

    # -- entry points ---------------------------------------------------

    def parse_program(self) -> _ast.Program:
        start = self.cur
        statements: list[_ast.Statement] = []
        while self.cur.kind != "EOF":
            stmt = self._parse_statement()
            statements.append(stmt)
            # Optional separator: newlines are already whitespace; allow ';'.
            self._match("OP", ";")
        return _ast.Program(self._span(start), tuple(statements))

    def parse_expression(self) -> _ast.Expr:
        expr = self._parse_or()
        if self.cur.kind != "EOF":
            tok = self.cur
            raise ParseError(
                f"trailing tokens after expression: {tok.text!r}",
                SourceSpan(self.source, tok.start, tok.end),
            )
        return expr

    # -- statements -----------------------------------------------------

    def _parse_statement(self) -> _ast.Statement:
        # Reject Python-style control-flow keywords up front.
        if self.cur.kind == "IDENT" and self.cur.text in _FORBIDDEN_KEYWORDS:
            tok = self.cur
            raise ForbiddenConstructError(
                f"forbidden construct {tok.text!r} — the attribute language is "
                "declarative-leaning (no loops, recursion, conditionals, or imports)",
                SourceSpan(self.source, tok.start, tok.end),
            )

        # Assignment: '@name = expr' or 'name = expr'
        if self.cur.kind == "AT_IDENT" and self._peek(1).kind == "OP" and self._peek(1).text == "=":
            target = self._advance()
            self._advance()  # consume '='
            value = self._parse_or()
            return _ast.Assignment(
                self._span(target),
                target_name=target.text[1:],
                target_is_attr=True,
                value=value,
            )
        if self.cur.kind == "IDENT" and self._peek(1).kind == "OP" and self._peek(1).text == "=":
            # Bare-name assignment, e.g. ``mask = ...``
            target = self._advance()
            self._advance()  # consume '='
            value = self._parse_or()
            return _ast.Assignment(
                self._span(target),
                target_name=target.text,
                target_is_attr=False,
                value=value,
            )

        return self._parse_or()

    # -- expressions (precedence ladder) -------------------------------

    # || has lowest precedence, then &&, then mask | & ~, then comparisons,
    # then + -, then * / %, then unary, then power-free postfix (call/index/.)
    def _parse_or(self) -> _ast.Expr:
        left = self._parse_and()
        while True:
            tok = self.cur
            if tok.kind == "OP" and tok.text in ("||", "|"):
                op = tok.text
                self._advance()
                right = self._parse_and()
                left = _ast.BinOp(self._span(self._token_for(left)), op, left, right)
                continue
            break
        return left

    def _parse_and(self) -> _ast.Expr:
        left = self._parse_not()
        while True:
            tok = self.cur
            if tok.kind == "OP" and tok.text in ("&&", "&"):
                op = tok.text
                self._advance()
                right = self._parse_not()
                left = _ast.BinOp(self._span(self._token_for(left)), op, left, right)
                continue
            break
        return left

    def _parse_not(self) -> _ast.Expr:
        tok = self.cur
        if tok.kind == "OP" and tok.text in ("!", "~"):
            self._advance()
            operand = self._parse_not()
            return _ast.UnaryOp(self._span(tok), tok.text, operand)
        return self._parse_compare()

    def _parse_compare(self) -> _ast.Expr:
        left = self._parse_addsub()
        tok = self.cur
        if tok.kind == "OP" and tok.text in ("==", "!=", "<", ">", "<=", ">="):
            op = tok.text
            self._advance()
            right = self._parse_addsub()
            return _ast.BinOp(self._span(self._token_for(left)), op, left, right)
        return left

    def _parse_addsub(self) -> _ast.Expr:
        left = self._parse_muldiv()
        while True:
            tok = self.cur
            if tok.kind == "OP" and tok.text in ("+", "-"):
                op = tok.text
                self._advance()
                right = self._parse_muldiv()
                left = _ast.BinOp(self._span(self._token_for(left)), op, left, right)
                continue
            break
        return left

    def _parse_muldiv(self) -> _ast.Expr:
        left = self._parse_unary()
        while True:
            tok = self.cur
            if tok.kind == "OP" and tok.text in ("*", "/", "%"):
                op = tok.text
                self._advance()
                right = self._parse_unary()
                left = _ast.BinOp(self._span(self._token_for(left)), op, left, right)
                continue
            break
        return left

    def _parse_unary(self) -> _ast.Expr:
        tok = self.cur
        if tok.kind == "OP" and tok.text in ("+", "-"):
            self._advance()
            operand = self._parse_unary()
            return _ast.UnaryOp(self._span(tok), tok.text, operand)
        return self._parse_postfix()

    def _parse_postfix(self) -> _ast.Expr:
        expr = self._parse_primary()
        while True:
            tok = self.cur
            if tok.kind == "OP" and tok.text == ".":
                self._advance()
                name_tok = self._expect("IDENT")
                expr = _ast.MemberAccess(
                    self._span(self._token_for(expr), name_tok), expr, name_tok.text
                )
                continue
            if tok.kind == "OP" and tok.text == "(":
                expr = self._parse_call(expr)
                continue
            if tok.kind == "OP" and tok.text == "[":
                self._advance()
                index = self._parse_or()
                close = self._expect("OP", "]")
                expr = _ast.Index(
                    self._span(self._token_for(expr), close), expr, index
                )
                continue
            break
        return expr

    def _parse_call(self, callee: _ast.Expr) -> _ast.Call:
        self._expect("OP", "(")
        positional: list[_ast.Expr] = []
        keywords: list[_ast.KeywordArg] = []
        if not (self.cur.kind == "OP" and self.cur.text == ")"):
            while True:
                # Keyword arg detection: IDENT '=' (but not '==')
                if (
                    self.cur.kind == "IDENT"
                    and self._peek(1).kind == "OP"
                    and self._peek(1).text == "="
                ):
                    name_tok = self._advance()
                    self._advance()  # consume '='
                    value = self._parse_or()
                    keywords.append(
                        _ast.KeywordArg(self._span(name_tok), name_tok.text, value)
                    )
                else:
                    if keywords:
                        tok = self.cur
                        raise ParseError(
                            "positional argument follows keyword argument",
                            SourceSpan(self.source, tok.start, tok.end),
                        )
                    positional.append(self._parse_or())
                if not self._match("OP", ","):
                    break
        close = self._expect("OP", ")")
        return _ast.Call(
            self._span(self._token_for(callee), close),
            callee,
            tuple(positional),
            tuple(keywords),
        )

    def _parse_primary(self) -> _ast.Expr:
        tok = self.cur
        if tok.kind == "INT":
            self._advance()
            return _ast.IntLiteral(self._span(tok), int(tok.text))
        if tok.kind == "FLOAT":
            self._advance()
            return _ast.FloatLiteral(self._span(tok), float(tok.text))
        if tok.kind == "STRING":
            self._advance()
            return _ast.StringLiteral(self._span(tok), _decode_string(tok.text))
        if tok.kind == "HEXCOLOR":
            self._advance()
            return _ast.ColorLiteral(self._span(tok), _decode_hex_color(tok.text))
        if tok.kind == "AT_IDENT":
            self._advance()
            return _ast.AttrRef(self._span(tok), tok.text[1:])
        if tok.kind == "IDENT":
            if tok.text in _FORBIDDEN_KEYWORDS:
                raise ForbiddenConstructError(
                    f"forbidden keyword {tok.text!r}",
                    SourceSpan(self.source, tok.start, tok.end),
                )
            if tok.text in ("true", "false"):
                self._advance()
                return _ast.BoolLiteral(self._span(tok), tok.text == "true")
            if tok.text in _NAMED_COLORS:
                self._advance()
                return _ast.ColorLiteral(self._span(tok), _NAMED_COLORS[tok.text])
            self._advance()
            return _ast.Identifier(self._span(tok), tok.text)
        if tok.kind == "OP" and tok.text == "(":
            return self._parse_paren_or_vector()
        if tok.kind == "OP" and tok.text == "[":
            return self._parse_list()
        raise ParseError(
            f"unexpected token {tok.text!r} ({tok.kind})",
            SourceSpan(self.source, tok.start, tok.end),
        )

    def _parse_paren_or_vector(self) -> _ast.Expr:
        start = self._expect("OP", "(")
        first = self._parse_or()
        if self._match("OP", ","):
            items: list[_ast.Expr] = [first]
            items.append(self._parse_or())
            while self._match("OP", ","):
                items.append(self._parse_or())
            close = self._expect("OP", ")")
            if not 2 <= len(items) <= 4:
                raise ParseError(
                    f"vector literal must have 2-4 components, got {len(items)}",
                    self._span(start, close),
                )
            return _ast.VectorLiteral(self._span(start, close), tuple(items))
        self._expect("OP", ")")
        return first

    def _parse_list(self) -> _ast.ListLiteral:
        start = self._expect("OP", "[")
        items: list[_ast.Expr] = []
        if not (self.cur.kind == "OP" and self.cur.text == "]"):
            items.append(self._parse_or())
            while self._match("OP", ","):
                items.append(self._parse_or())
        close = self._expect("OP", "]")
        return _ast.ListLiteral(self._span(start, close), tuple(items))

    # -- span helper ----------------------------------------------------

    def _token_for(self, node: _ast.Node) -> _Token:
        """Return a synthetic token covering ``node.span`` for span chaining."""
        return _Token("SYNTH", "", node.span.start, node.span.end)


def _decode_hex_color(text: str) -> tuple[float, float, float, float]:
    body = text[1:]
    if len(body) == 6:
        r, g, b = (int(body[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        return (r, g, b, 1.0)
    if len(body) == 8:
        r, g, b, a = (int(body[i : i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
        return (r, g, b, a)
    raise ParseError(f"invalid hex color literal {text!r}")


def _decode_string(text: str) -> str:
    quote = text[0]
    inner = text[1:-1]
    # Handle the small subset of escapes we support.
    return (
        inner.replace("\\\\", "\\")
        .replace(f"\\{quote}", quote)
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def parse(source: str) -> _ast.Program:
    """Parse a full source string into a :class:`Program` AST.

    A program may contain zero or more statements (assignments and / or
    bare expressions). Use :func:`parse_expression` when the caller knows
    the source is a single expression — its error messages are tighter.
    """
    tokens = _tokenize(source)
    return _Parser(source, tokens).parse_program()


def parse_expression(source: str) -> _ast.Expr:
    """Parse a single expression. Raises :class:`ParseError` if more remains."""
    tokens = _tokenize(source)
    return _Parser(source, tokens).parse_expression()
