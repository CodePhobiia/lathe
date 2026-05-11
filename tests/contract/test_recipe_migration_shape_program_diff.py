"""Contract test: per-family ShapeProgram diff between recipe and synthesizer paths.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §6.4:

> For each family migrated: a side-by-side ShapeProgram diff test
> exists, comparing the pre-migration recipe output to the
> post-migration synthesizer output. Differences must be documented
> as intent-driven (e.g., brief now respected) or reduced.

This is the parametrized harness. Each family that has migrated
ships a fixture entry under ``_MIGRATED_FAMILY_FIXTURES`` with:

  - ``family``: the family name (matches ``_RECIPES`` key + the
    ``family`` field in the resulting ShapeProgram).
  - ``brief``: design-brief dict the recipe receives.
  - ``parts``: parts tuple the recipe receives.
  - ``graph_nodes``: pre-existing graph nodes the recipe receives.
  - ``synthesizer_asset``: the ``asset`` dict the synthesizer
    receives. Must populate ``build.shape.procedural.construction_graph``
    or ``intent.construction_graph`` for ``synthesizer_eligible`` to
    return True.
  - ``synthesizer_runtime``: the ``runtime`` dict the synthesizer
    receives. Carries ``design_brief`` and ``construction_graph``.
  - ``allowed_op_diff``: optional list of explicit diff entries the
    test tolerates (each with a documented ``reason`` per migration
    notes JSON sidecar).

Unmigrated families are not in ``_MIGRATED_FAMILY_FIXTURES``; they
fail nothing (no parametrize entry). As each Round 2/3/5 family
migrates, its fixture is added here and to the build-artifact diff
harness simultaneously.

Diff semantics: ops must be equivalent or better. "Better" is defined
by the migration notes — typically "intent-driven (e.g., brief now
respected)" or "reduced op count without losing visible structure."
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from lathe.asset_quality.grammar_lowering import _RECIPES
from lathe.asset_quality.procedural_synthesizer import synthesize_procedural_program
from lathe.asset_quality.shape_ir_v2 import ShapeOp, ShapeProgram


# --- Fixture catalog ----------------------------------------------------
#
# Each entry is a dict with the keys documented in the module
# docstring. The catalog is empty until a family migrates; each
# migration PR appends its fixture.
#
# To add a family migration:
#   1. Author its StyleKnowledge / CompositionPolicy / FamilyAlias.
#   2. Update its .lth fixture to populate construction_graph.
#   3. Append an entry below + a corresponding entry in
#      tests/integration/test_recipe_migration_build_artifact_diff.py.
#   4. Run this test — the diff against the recipe baseline must pass.
#   5. Delete _RECIPES[family].

_MIGRATED_FAMILY_FIXTURES: tuple[dict[str, Any], ...] = (
    # First migration goes here, e.g.:
    # {
    #     "family": "inventory_economy_object",
    #     "brief": {},
    #     "parts": (),
    #     "graph_nodes": (),
    #     "synthesizer_asset": {...},
    #     "synthesizer_runtime": {...},
    #     "allowed_op_diff": [],
    # },
)


def _normalize_op_for_diff(op: ShapeOp) -> tuple[str, str, frozenset[str]]:
    """Reduce a ShapeOp to its (op, target, parameter-keys) shape for diffing.

    Compares semantic structure rather than literal parameter values
    (which legitimately vary as brief inputs flow through the
    synthesizer). The migration is judged by whether the *set of
    operations* (and their targets and parameter surfaces) matches
    the recipe baseline, not by exact float equality on dimensions.
    """
    return (
        op.op,
        str(op.target or ""),
        frozenset(op.parameters.keys()),
    )


def _shape_program_signature(program: ShapeProgram) -> tuple[tuple[str, str, frozenset[str]], ...]:
    """Reduce a ShapeProgram to the ordered tuple of normalized op signatures."""
    return tuple(_normalize_op_for_diff(op) for op in program.ops)


def _run_recipe_path(
    family: str,
    brief: Mapping[str, Any],
    parts: tuple[str, ...],
    graph_nodes: tuple[dict[str, Any], ...],
) -> ShapeProgram:
    """Invoke ``_RECIPES[family]`` directly and return its ShapeProgram."""
    recipe = _RECIPES.get(family)
    if recipe is None:
        raise pytest.UsageError(
            f"family {family!r} is not in _RECIPES; cannot diff against the "
            "recipe baseline. Either the migration is already complete "
            "(in which case this fixture should be removed) or the family "
            "name is misspelled."
        )
    result = recipe(dict(brief), tuple(parts), tuple(graph_nodes))
    return result.shape_program


def _run_synthesizer_path(
    asset: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> ShapeProgram:
    """Invoke ``synthesize_procedural_program`` and return its ShapeProgram."""
    synth_result = synthesize_procedural_program(asset, runtime)
    return synth_result.shape_program


@pytest.mark.skipif(
    not _MIGRATED_FAMILY_FIXTURES,
    reason="no families have migrated yet; harness exercised by tests added per-family",
)
@pytest.mark.parametrize(
    "fixture",
    _MIGRATED_FAMILY_FIXTURES,
    ids=[f["family"] for f in _MIGRATED_FAMILY_FIXTURES] if _MIGRATED_FAMILY_FIXTURES else [],
)
def test_migrated_family_shape_program_diff(fixture: dict[str, Any]) -> None:
    """Recipe vs synthesizer ShapeProgram are equivalent (or documented difference).

    Per plan v2 §6.4: differences must be documented as intent-driven
    (e.g., brief now respected) or reduced. The fixture's
    ``allowed_op_diff`` field lists explicit accepted differences;
    any other divergence is a regression.
    """
    family = fixture["family"]
    recipe_program = _run_recipe_path(
        family,
        fixture["brief"],
        fixture["parts"],
        fixture["graph_nodes"],
    )
    synth_program = _run_synthesizer_path(
        fixture["synthesizer_asset"],
        fixture["synthesizer_runtime"],
    )

    assert recipe_program.family == family, (
        f"recipe ShapeProgram.family={recipe_program.family!r} did not match "
        f"fixture family={family!r}"
    )
    assert synth_program.family == family, (
        f"synthesizer ShapeProgram.family={synth_program.family!r} did not "
        f"match fixture family={family!r}; the FamilyAlias resolution may "
        "be misconfigured."
    )

    recipe_sig = _shape_program_signature(recipe_program)
    synth_sig = _shape_program_signature(synth_program)

    allowed_diff = fixture.get("allowed_op_diff") or []
    allowed_diff_set = {
        (entry["op"], entry["target"], frozenset(entry.get("parameter_keys", [])))
        for entry in allowed_diff
    }

    # Compute the symmetric difference between op signatures.
    recipe_only = [sig for sig in recipe_sig if sig not in synth_sig and sig not in allowed_diff_set]
    synth_only = [sig for sig in synth_sig if sig not in recipe_sig and sig not in allowed_diff_set]

    if recipe_only or synth_only:
        pytest.fail(
            f"family {family!r} ShapeProgram diff found undocumented differences:\n"
            f"  recipe-only ops: {recipe_only!r}\n"
            f"  synthesizer-only ops: {synth_only!r}\n"
            f"  allowed_op_diff entries: {allowed_diff!r}\n"
            "If these are intent-driven (brief now respected) or reductions, "
            "add them to the fixture's allowed_op_diff list with a reason "
            "in the per-family migration notes."
        )


def test_migrated_family_fixtures_match_recipe_registry() -> None:
    """Every fixture entry must reference a family currently in _RECIPES.

    A fixture for a family that has already been deleted from
    _RECIPES is dead — either the deletion was premature or the
    fixture was forgotten in the cleanup pass.
    """
    for fixture in _MIGRATED_FAMILY_FIXTURES:
        family = fixture["family"]
        assert family in _RECIPES, (
            f"fixture family={family!r} not present in _RECIPES; either "
            "remove the fixture (if the recipe was deleted intentionally) "
            "or restore the recipe (if it was deleted prematurely)."
        )


def test_migrated_family_fixtures_have_required_keys() -> None:
    """Each fixture entry must define the documented contract keys."""
    required_keys = {
        "family",
        "brief",
        "parts",
        "graph_nodes",
        "synthesizer_asset",
        "synthesizer_runtime",
    }
    for fixture in _MIGRATED_FAMILY_FIXTURES:
        missing = required_keys - set(fixture.keys())
        assert not missing, (
            f"fixture for family={fixture.get('family')!r} missing required "
            f"keys: {sorted(missing)!r}. See module docstring for the "
            "fixture contract."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
