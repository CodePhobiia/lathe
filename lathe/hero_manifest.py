"""Canonical hero asset manifest.

Single source of truth for the 9 hero `.lth` assets that are exercised by the
gallery + scoreboard pipeline and by any other tooling that wants to iterate
over "the heroes" without each script repeating the list.

Thresholds mirror the Wave 3 reviewer report
(`plans/reviews/wave3_tests_contract_review.md`) — the same values the
`.lth` sources themselves declare. If a hero's threshold changes in its
source, update it here too.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Hero:
    """A single hero asset entry."""

    asset_name: str
    source_path: Path
    family: str
    threshold: float


HEROES: List[Hero] = [
    Hero(
        asset_name="courier_drone",
        source_path=_REPO_ROOT / "examples" / "courier_drone.lth",
        family="vehicle",
        threshold=0.86,
    ),
    Hero(
        asset_name="brassbound_chest",
        source_path=_REPO_ROOT / "examples" / "brassbound_chest.lth",
        family="container",
        threshold=0.84,
    ),
    Hero(
        asset_name="industrial_crate",
        source_path=_REPO_ROOT / "examples" / "industrial_crate.lth",
        family="container",
        threshold=0.84,
    ),
    Hero(
        asset_name="mechanical_door",
        source_path=_REPO_ROOT / "examples" / "mechanical_door.lth",
        family="architecture",
        threshold=0.84,
    ),
    Hero(
        asset_name="console_terminal",
        source_path=_REPO_ROOT / "examples" / "console_terminal.lth",
        family="prop",
        threshold=0.85,
    ),
    Hero(
        asset_name="sci_fi_wall_panel",
        source_path=_REPO_ROOT / "examples" / "sci_fi_wall_panel.lth",
        family="architecture",
        threshold=0.84,
    ),
    Hero(
        asset_name="service_cabinet",
        source_path=_REPO_ROOT / "examples" / "service_cabinet.lth",
        family="architecture",
        threshold=0.82,
    ),
    Hero(
        asset_name="control_pedestal",
        source_path=_REPO_ROOT / "examples" / "control_pedestal.lth",
        family="prop",
        threshold=0.83,
    ),
    Hero(
        asset_name="supply_container",
        source_path=_REPO_ROOT / "examples" / "supply_container.lth",
        family="container",
        threshold=0.84,
    ),
]


def hero_by_name(name: str) -> Hero:
    """Lookup a hero by asset_name; raises KeyError if absent."""
    for hero in HEROES:
        if hero.asset_name == name:
            return hero
    raise KeyError(f"unknown hero: {name!r}")
