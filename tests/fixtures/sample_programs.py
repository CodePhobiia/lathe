"""Hero ``.lth`` sample-program factory.

Exposes a ``sample_program(name)`` fixture that returns a parsed AST for
a named hero example. This is a thin wrapper around
``lathe.parser.parse_file`` today; Wave 3 will add a caching layer so
repeated property/golden tests don't re-parse the same source.

Usage::

    def test_something(sample_program):
        ast = sample_program("courier_drone")
        ...
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

HERO_EXAMPLES = (
    "courier_drone",
    "brassbound_chest",
    "industrial_crate",
    "mechanical_door",
    "console_terminal",
    "sci_fi_wall_panel",
    "service_cabinet",
    "control_pedestal",
    "supply_container",
)


def _resolve_example_path(repo_root: Path, name: str) -> Path:
    """Return the ``.lth`` source for a hero example by name.

    The ``examples/`` directory is a flat layout, one ``.lth`` per hero.
    Raise ``FileNotFoundError`` with a clear message if the requested hero
    is not present.
    """
    candidate = repo_root / "examples" / f"{name}.lth"
    if not candidate.exists():
        raise FileNotFoundError(
            f"Hero example {name!r} not found at {candidate}. Known heroes: {', '.join(HERO_EXAMPLES)}"
        )
    return candidate


@pytest.fixture()
def sample_program(repo_root: Path) -> Callable[[str], dict[str, Any]]:
    """Return a factory that parses the named hero example on demand."""
    from lathe.parser import parse_file

    def _load(name: str) -> dict[str, Any]:
        path = _resolve_example_path(repo_root, name)
        return parse_file(path)

    return _load


@pytest.fixture(params=HERO_EXAMPLES)
def hero_sample_program(
    request: pytest.FixtureRequest, sample_program: Callable[[str], dict[str, Any]]
) -> dict[str, Any]:
    """Parametrize a test across every hero example.

    Wave 3 golden snapshot tests iterate heroes via this fixture.
    """
    return sample_program(request.param)
