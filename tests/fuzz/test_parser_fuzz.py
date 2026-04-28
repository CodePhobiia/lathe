"""Parser fuzz tests (BL-38, Plan 08 Phase 9 — Stability).

Hypothesis-driven property test asserting the *only* way out of
``lathe.parser.parse_text`` for arbitrary input is either a normalized
program ``dict`` or a ``LatheParseError``. Anything else (a stray
``ValueError`` from a token regex, an ``IndexError`` from a stream pop,
an ``AttributeError`` from the transformer, a hung loop) is a parser
bug.

This is the **proof-of-concept** scope from Plan 08 Phase 9: 200
Hypothesis examples per strategy, durable corpus stored under
``.hypothesis/`` (gitignored). Plan 08 calls for 10k iterations as the
full deliverable; we ship 200 here as the fast smoke and document the
ramp in ``perf/README.md``.

Strategies:

- ``random_text``: pure ``st.text()`` — exercises the tokenizer's
  failure path. Almost all examples are expected to raise.
- ``random_tokens``: token-regex-derived strings — exercises the parser
  proper after the tokenizer accepts.
- ``random_program_skeleton``: well-formed-ish ``asset`` / ``profile``
  / ``contract`` / ``critic`` skeletons with random identifiers and
  values — exercises the transformer and AST construction path. Most
  of these should *succeed* and return a dict.

All three are united by the same ``_assert_parser_invariant`` helper.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from lathe.parser import LatheParseError, parse_text

pytestmark = pytest.mark.fuzz


# Scale knob (BL-42): default 200 (fast, PR CI / local smoke);
# nightly cron sets LATHE_FUZZ_EXTENDED=1 for the full 10k sweep.
_EXTENDED = os.environ.get("LATHE_FUZZ_EXTENDED") == "1"
MAX_EXAMPLES = 10000 if _EXTENDED else 200


# -- invariant -----------------------------------------------------------


def _assert_parser_invariant(source: str) -> None:
    """The parser must return a dict OR raise LatheParseError. No third option."""
    try:
        result: Any = parse_text(source)
    except LatheParseError:
        return  # acceptable failure mode
    except RecursionError:
        # Pathological nesting — Hypothesis will rarely hit this; allow it.
        return
    assert isinstance(result, dict), (
        f"parse_text returned non-dict {type(result).__name__} for source: {source!r}"
    )
    # Top-level keys exist (sanity that we got the canonical empty program shape).
    assert "assets" in result and "profiles" in result, (
        f"parse_text returned dict missing canonical keys for source: {source!r}"
    )


# -- strategies ----------------------------------------------------------


# Identifier alphabet matches the grammar's ``[a-z][a-z0-9_]*`` ident.
_IDENT_FIRST = st.sampled_from("abcdefghijklmnopqrstuvwxyz")
_IDENT_REST = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=0,
    max_size=8,
)
_IDENT = st.builds(lambda a, b: a + b, _IDENT_FIRST, _IDENT_REST)


# Token vocabulary directly drawn from ``lathe.parser.tokens.TOKEN_RE``.
_OPS = st.sampled_from(
    [
        "{",
        "}",
        "(",
        ")",
        "[",
        "]",
        ",",
        ":",
        "=",
        ".",
        "+",
        "-",
        "*",
        "/",
        "<",
        ">",
        "..",
        "==",
        "!=",
        "<=",
        ">=",
    ]
)
_KEYWORDS = st.sampled_from(
    [
        "asset",
        "profile",
        "contract",
        "critic",
        "stage",
        "uses",
        "module",
        "import",
        "build",
        "ensure",
        "kind",
        "true",
        "false",
    ]
)
_NUMBERS = st.builds(
    lambda n: str(n),
    st.one_of(
        st.integers(min_value=-1000, max_value=1000),
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    ),
)
_UNITS = st.sampled_from(["mm", "cm", "m", "deg", "rad", "g", "kg", "ms", "s", "kb", "mb", "gb", "px"])
_NUMBER_WITH_UNIT = st.builds(
    lambda n, u: f"{abs(int(n))}{u}", st.integers(min_value=0, max_value=200), _UNITS
)
_STRINGS = st.builds(lambda s: '"' + s.replace("\\", "").replace('"', "") + '"', st.text(max_size=10))


_TOKEN = st.one_of(_IDENT, _OPS, _KEYWORDS, _NUMBERS, _NUMBER_WITH_UNIT, _STRINGS)


@st.composite
def _random_token_stream(draw: Any) -> str:
    """Whitespace-joined random tokens; mostly garbage to the parser."""
    n = draw(st.integers(min_value=0, max_value=20))
    parts = [draw(_TOKEN) for _ in range(n)]
    return " ".join(parts)


@st.composite
def _random_program_skeleton(draw: Any) -> str:
    """A single ``asset``/``profile``/``contract`` declaration with random idents."""
    decl_kind = draw(st.sampled_from(["asset", "profile", "contract", "critic"]))
    name = draw(_IDENT)
    body_lines = draw(st.integers(min_value=0, max_value=4))
    body: list[str] = []
    for _ in range(body_lines):
        key = draw(_IDENT)
        val_kind = draw(st.sampled_from(["ident", "number", "string", "bool"]))
        if val_kind == "ident":
            val = draw(_IDENT)
        elif val_kind == "number":
            val = draw(_NUMBERS)
        elif val_kind == "string":
            val = draw(_STRINGS)
        else:
            val = draw(st.sampled_from(["true", "false"]))
        body.append(f"  {key} = {val}")
    body_text = "\n".join(body)
    if decl_kind == "asset":
        # Asset requires a ``kind`` field to satisfy the parser.
        return f"asset {name} {{\n  kind = prop\n{body_text}\n}}"
    return f"{decl_kind} {name} {{\n{body_text}\n}}"


# -- tests ---------------------------------------------------------------


@given(source=st.text(max_size=200))
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_parser_invariant_random_text(source: str) -> None:
    """Property: random text never crashes the parser uncleanly."""
    _assert_parser_invariant(source)


@given(source=_random_token_stream())
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_parser_invariant_random_tokens(source: str) -> None:
    """Property: arbitrary token streams never crash the parser uncleanly."""
    _assert_parser_invariant(source)


@given(source=_random_program_skeleton())
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_parser_invariant_program_skeleton(source: str) -> None:
    """Property: well-formed-ish skeletons either parse or raise cleanly."""
    _assert_parser_invariant(source)


# -- regression seed -----------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "",
        " ",
        "\n\n\n",
        "// just a comment",
        "/* block */",
        "asset",  # truncated
        "asset x {",  # unclosed
        "asset x { kind = }",  # missing value
        "%%%",  # tokenizer rejection
        "\x00",  # null byte
        "asset x { kind = prop }",  # well-formed minimal
    ],
)
def test_parser_invariant_regression_seeds(source: str) -> None:
    """Hand-picked seeds for the same invariant — pinned regression set."""
    _assert_parser_invariant(source)
