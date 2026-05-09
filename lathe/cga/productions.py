"""CGA production-rule parser and dataclasses.

Mini-language:

  Rule       := IDENT "-->" rhs ("," rhs)*
  rhs        := nonterminal | terminal | split | repeat | choose | transform
  nonterminal := IDENT (PascalCase)
  terminal    := IDENT param_call? | "kit:" IDENT param_call?
              | "mesh_ref:" IDENT param_call?
  param_call  := "(" IDENT ("=" | ":") value ("," IDENT ("=" | ":") value)* ")"
  split      := "split" "(" axis ")" "{" splititem ("," splititem)* "}"
  splititem  := size_or_ratio ":" rhs
  size_or_ratio := number unit?    (e.g. 3m, 2.5)
                | number "*"        (relative size, fills remainder)
  repeat     := "repeat" "(" int ")" "{" rhs "}"
              | "repeat" "(" int "," "mirror=true" ")" "{" rhs "}"
              | "repeat" "(" int "," "rotate=" Ndeg ")" "{" rhs "}"
  choose     := "chooseOne" "{" weight ":" rhs ("," weight ":" rhs)* "}"
  transform  := transform_op rhs
  transform_op := "extrude(height:" length ")"
                | "translate(...)" | "rotate(axis,deg)" | "scale(...)"

Whitespace is insignificant outside identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class NonTerminal:
    """A reference to another production rule (PascalCase identifier)."""

    name: str


@dataclass
class Terminal:
    """A leaf shape: an inline mesh primitive token, kit call, or mesh ref.

    ``kind`` is one of ``"primitive" | "kit" | "mesh_ref"``.
    """

    name: str
    kind: str = "primitive"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitItem:
    """One slice within a split."""

    size: float
    unit: str  # "m" | "ratio"
    rhs: "RHS"


@dataclass
class Split:
    """Axis-aligned subdivision of the current shape."""

    axis: str  # "x" | "y" | "z"
    items: list[SplitItem] = field(default_factory=list)


@dataclass
class Repeat:
    """N-fold repetition of a single RHS along an implicit axis (default x)."""

    count: int
    rhs: "RHS"
    axis: str = "x"
    mirror: bool = False
    rotate_deg: float = 0.0


@dataclass
class ChooseOne:
    """Deterministic-with-seed weighted choose."""

    options: list[tuple[float, "RHS"]] = field(default_factory=list)


@dataclass
class Extrude:
    """Extrude the current 2D shape into 3D along an axis."""

    height: float
    axis: str = "z"
    rhs: "RHS | None" = None


@dataclass
class Translate:
    """Offset the current shape origin."""

    offset: tuple[float, float, float]
    rhs: "RHS | None" = None


@dataclass
class Rotate:
    """Rotate the current shape around an axis."""

    axis: str
    degrees: float
    rhs: "RHS | None" = None


@dataclass
class Scale:
    """Scale the current shape along axes."""

    factors: tuple[float, float, float]
    rhs: "RHS | None" = None


# RHS is a union covering each form a production right-hand side may take.
RHS = (
    NonTerminal
    | Terminal
    | Split
    | Repeat
    | ChooseOne
    | Extrude
    | Translate
    | Rotate
    | Scale
    | list  # comma-list of RHS becomes a sibling tuple
)


@dataclass
class Production:
    """A single ``LHS --> rhs (, rhs)*`` production."""

    lhs: str
    rhs: list[Any]
    source: str = ""


@dataclass
class Grammar:
    """A parsed CGA grammar, ready to evaluate."""

    productions: dict[str, list[Production]] = field(default_factory=dict)
    root: str = "Root"
    seed: int = 0
    recursion_budget: int = 32

    def add(self, production: Production) -> None:
        """Add a production, supporting multiple alternatives per LHS."""
        self.productions.setdefault(production.lhs, []).append(production)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------


_TOKEN_PATTERNS: list[tuple[str, str]] = [
    ("WS", r"\s+"),
    ("ARROW", r"-->"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("COMMA", r","),
    ("COLON", r":"),
    ("STAR", r"\*"),
    ("EQ", r"="),
    # Numbers carry unit/star suffix detection in parser
    ("NUMBER", r"-?\d+(?:\.\d+)?"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
]
_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_PATTERNS)
)


@dataclass
class _Token:
    kind: str
    text: str
    pos: int


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    while i < len(source):
        m = _MASTER_RE.match(source, i)
        if not m:
            raise ValueError(
                f"unexpected character {source[i]!r} at position {i} in production {source!r}"
            )
        kind = m.lastgroup or "?"
        text = m.group()
        if kind != "WS":
            tokens.append(_Token(kind=kind, text=text, pos=i))
        i = m.end()
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Cursor:
    def __init__(self, tokens: list[_Token], source: str) -> None:
        self.tokens = tokens
        self.source = source
        self.i = 0

    def peek(self, kind: str | None = None, text: str | None = None) -> bool:
        if self.i >= len(self.tokens):
            return False
        tok = self.tokens[self.i]
        if kind is not None and tok.kind != kind:
            return False
        if text is not None and tok.text != text:
            return False
        return True

    def eat(self, kind: str | None = None, text: str | None = None) -> _Token:
        if self.i >= len(self.tokens):
            raise ValueError(f"unexpected end of production {self.source!r}")
        tok = self.tokens[self.i]
        if kind is not None and tok.kind != kind:
            raise ValueError(
                f"expected {kind} but got {tok.kind} ({tok.text!r}) in {self.source!r}"
            )
        if text is not None and tok.text != text:
            raise ValueError(
                f"expected {text!r} but got {tok.text!r} in {self.source!r}"
            )
        self.i += 1
        return tok

    def at_end(self) -> bool:
        return self.i >= len(self.tokens)


_LENGTH_UNITS = {"m", "cm", "mm"}
_UNIT_TO_M = {"m": 1.0, "cm": 0.01, "mm": 0.001}


def _is_pascal(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _read_length(c: _Cursor) -> tuple[float, str]:
    """Read a number with optional unit suffix or '*' ratio marker."""
    num_tok = c.eat("NUMBER")
    value = float(num_tok.text)
    if c.peek("STAR"):
        c.eat("STAR")
        return value, "ratio"
    if c.peek("IDENT"):
        ident = c.tokens[c.i].text
        if ident in _LENGTH_UNITS:
            c.eat("IDENT")
            return value * _UNIT_TO_M[ident], "m"
        if ident == "deg":
            c.eat("IDENT")
            return value, "deg"
    return value, ""


def _read_axis(c: _Cursor) -> str:
    tok = c.eat("IDENT")
    if tok.text not in {"x", "y", "z"}:
        raise ValueError(f"axis must be x|y|z, got {tok.text!r}")
    return tok.text


def _read_param_value(c: _Cursor) -> Any:
    if c.peek("NUMBER"):
        value, unit = _read_length(c)
        if unit == "deg":
            return {"value": value, "unit": "deg"}
        return value
    if c.peek("IDENT"):
        text = c.eat("IDENT").text
        if text in {"true", "True"}:
            return True
        if text in {"false", "False"}:
            return False
        return text
    raise ValueError(f"expected parameter value in {c.source!r}")


def _parse_terminal_params(c: _Cursor) -> dict[str, Any]:
    if not c.peek("LPAREN"):
        return {}
    c.eat("LPAREN")
    params: dict[str, Any] = {}
    while not c.peek("RPAREN"):
        key = c.eat("IDENT").text
        if c.peek("EQ"):
            c.eat("EQ")
        else:
            c.eat("COLON")
        params[key] = _read_param_value(c)
        if c.peek("COMMA"):
            c.eat("COMMA")
    c.eat("RPAREN")
    return params


def _parse_rhs_atom(c: _Cursor) -> Any:
    """Parse one atomic RHS form (split/repeat/choose/transform/terminal/nonterminal)."""
    if not c.peek("IDENT"):
        raise ValueError(f"expected RHS atom in {c.source!r}")
    head = c.tokens[c.i].text

    if head == "split":
        c.eat("IDENT")
        c.eat("LPAREN")
        axis_label = c.eat("IDENT").text
        if axis_label not in {"x", "y", "z"}:
            raise ValueError(f"split axis must be x|y|z, got {axis_label!r}")
        c.eat("RPAREN")
        c.eat("LBRACE")
        items: list[SplitItem] = []
        while not c.peek("RBRACE"):
            size, unit = _read_length(c)
            c.eat("COLON")
            rhs = _parse_rhs(c)
            items.append(SplitItem(size=size, unit=unit or "m", rhs=rhs))
            if c.peek("COMMA"):
                c.eat("COMMA")
        c.eat("RBRACE")
        return Split(axis=axis_label, items=items)

    if head == "repeat":
        c.eat("IDENT")
        c.eat("LPAREN")
        count = int(c.eat("NUMBER").text)
        mirror = False
        rotate_deg = 0.0
        axis = "x"
        while c.peek("COMMA"):
            c.eat("COMMA")
            opt = c.eat("IDENT").text
            c.eat("EQ")
            if opt == "mirror":
                mirror = c.eat("IDENT").text in {"true", "True"}
            elif opt == "rotate":
                rot_val, rot_unit = _read_length(c)
                rotate_deg = rot_val if rot_unit == "deg" else rot_val
            elif opt == "axis":
                axis = c.eat("IDENT").text
            else:
                raise ValueError(f"unknown repeat option {opt!r}")
        c.eat("RPAREN")
        c.eat("LBRACE")
        rhs = _parse_rhs(c)
        c.eat("RBRACE")
        return Repeat(count=count, rhs=rhs, axis=axis, mirror=mirror, rotate_deg=rotate_deg)

    if head == "chooseOne":
        c.eat("IDENT")
        c.eat("LBRACE")
        options: list[tuple[float, Any]] = []
        while not c.peek("RBRACE"):
            weight = float(c.eat("NUMBER").text)
            c.eat("COLON")
            rhs = _parse_rhs(c)
            options.append((weight, rhs))
            if c.peek("COMMA"):
                c.eat("COMMA")
        c.eat("RBRACE")
        return ChooseOne(options=options)

    if head == "extrude":
        c.eat("IDENT")
        c.eat("LPAREN")
        kw = c.eat("IDENT").text
        if kw != "height":
            raise ValueError(f"extrude expects 'height:', got {kw!r}")
        c.eat("COLON")
        h_val, h_unit = _read_length(c)
        axis = "z"
        if c.peek("COMMA"):
            c.eat("COMMA")
            c.eat("IDENT", text="axis")
            c.eat("EQ")
            axis = c.eat("IDENT").text
        c.eat("RPAREN")
        sub: Any | None = None
        if not (c.peek("COMMA") or c.peek("RBRACE") or c.at_end()):
            sub = _parse_rhs_atom(c)
        return Extrude(height=h_val if h_unit in {"m", ""} else h_val, axis=axis, rhs=sub)

    if head == "translate":
        c.eat("IDENT")
        c.eat("LPAREN")
        coords: list[float] = []
        while True:
            v, _u = _read_length(c)
            coords.append(v)
            if c.peek("COMMA"):
                c.eat("COMMA")
                continue
            break
        c.eat("RPAREN")
        while len(coords) < 3:
            coords.append(0.0)
        sub2: Any | None = None
        if not (c.peek("COMMA") or c.peek("RBRACE") or c.at_end()):
            sub2 = _parse_rhs_atom(c)
        return Translate(offset=(coords[0], coords[1], coords[2]), rhs=sub2)

    if head == "rotate":
        c.eat("IDENT")
        c.eat("LPAREN")
        axis = c.eat("IDENT").text
        c.eat("COMMA")
        deg_val, _ = _read_length(c)
        c.eat("RPAREN")
        sub3: Any | None = None
        if not (c.peek("COMMA") or c.peek("RBRACE") or c.at_end()):
            sub3 = _parse_rhs_atom(c)
        return Rotate(axis=axis, degrees=deg_val, rhs=sub3)

    if head == "scale":
        c.eat("IDENT")
        c.eat("LPAREN")
        factors: list[float] = []
        while True:
            v_tok = c.eat("NUMBER")
            factors.append(float(v_tok.text))
            if c.peek("COMMA"):
                c.eat("COMMA")
                continue
            break
        c.eat("RPAREN")
        while len(factors) < 3:
            factors.append(1.0)
        sub4: Any | None = None
        if not (c.peek("COMMA") or c.peek("RBRACE") or c.at_end()):
            sub4 = _parse_rhs_atom(c)
        return Scale(factors=(factors[0], factors[1], factors[2]), rhs=sub4)

    if head == "kit":
        c.eat("IDENT")
        c.eat("COLON")
        ref = c.eat("IDENT").text
        return Terminal(name=ref, kind="kit", params=_parse_terminal_params(c))

    if head == "mesh_ref":
        c.eat("IDENT")
        c.eat("COLON")
        ref = c.eat("IDENT").text
        return Terminal(name=ref, kind="mesh_ref", params=_parse_terminal_params(c))

    # Plain identifier — non-terminal if PascalCase, terminal otherwise.
    c.eat("IDENT")
    if _is_pascal(head):
        return NonTerminal(name=head)
    return Terminal(name=head, kind="primitive", params=_parse_terminal_params(c))


def _parse_rhs(c: _Cursor) -> Any:
    """Parse one RHS slot, which may be a single atom (siblings handled at production level)."""
    return _parse_rhs_atom(c)


def parse_production(source: str) -> Production:
    """Parse a single CGA production string into a :class:`Production`."""
    if "-->" not in source:
        raise ValueError(f"production missing '-->' arrow: {source!r}")
    tokens = _tokenize(source)
    cursor = _Cursor(tokens, source)
    lhs_tok = cursor.eat("IDENT")
    cursor.eat("ARROW")
    rhs_list: list[Any] = [_parse_rhs(cursor)]
    while cursor.peek("COMMA"):
        cursor.eat("COMMA")
        rhs_list.append(_parse_rhs(cursor))
    if not cursor.at_end():
        leftover = cursor.tokens[cursor.i].text
        raise ValueError(f"trailing tokens after production: {leftover!r} in {source!r}")
    return Production(lhs=lhs_tok.text, rhs=rhs_list, source=source)


def parse_productions(sources: list[str]) -> Grammar:
    """Parse a list of CGA production strings into a :class:`Grammar`."""
    grammar = Grammar()
    for src in sources:
        text = (src or "").strip()
        if not text or text.startswith("#"):
            continue
        production = parse_production(text)
        grammar.add(production)
    return grammar
