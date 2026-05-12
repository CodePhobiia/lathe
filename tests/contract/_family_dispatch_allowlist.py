"""Allowlist for ``test_no_family_dispatch`` contract test.

Each entry names a (file_glob, line_substring, reason) tuple where
family-keyed code is permitted because it is metadata / reporting /
audit, OR because it is on the Cycle 3 migration worklist.

The Cycle 1 baseline includes every existing family-keyed dispatch in
the codebase at the time the procedural synthesizer foundation
landed. Each entry's reason names the migration target. As Cycle 3
migrates each family-aware code path to capability/tag/role dispatch
through the synthesizer, the corresponding allowlist entry is
removed.

A new family-keyed dispatch (not in this allowlist, not carrying an
inline ``# no-family-dispatch: <reason>`` comment) fails the lint.
This is how Cycle 1 protects the procedural direction from
regression while Cycle 3 chips away at the legacy surface.

The procedural synthesizer (``lathe/asset_quality/procedural_synthesizer/``)
must NEVER appear in this allowlist. Its family-dispatch-free
guarantee is structurally enforced, not allowlisted.
"""

from __future__ import annotations

# (file_path_glob, line_substring, reason)
# file_path_glob: relative to repo root; supports * wildcards via fnmatch
# line_substring: substring uniquely identifying the line within the file.
#                 "*" matches any line in the file (full-file allowlist).
# reason: why this is metadata-only OR which cycle migrates it
ALLOWLIST: tuple[tuple[str, str, str], ...] = (
    # ---------------------------------------------------------------
    # Cycle 1 baseline — established when the procedural synthesizer
    # foundation landed. Every entry below is a Cycle 3 migration
    # target. Remove the entry when its code path moves to
    # capability/tag/role dispatch through the synthesizer.
    # ---------------------------------------------------------------

    # ---------------------------------------------------------------
    # NOTE: ``_RECIPES.get(family)`` in grammar_lowering.py was
    # decommissioned in Cycle 3 Round 6. The dispatch site now routes
    # through ``synthesize_procedural_program(asset, runtime)`` — no
    # family-keyed branching. No allowlist entry required.
    # ---------------------------------------------------------------

    # Build-driving paths (Cycle 3a migration targets).
    # asset_graph.py — family-aware blueprint routing during AssetGraph
    # construction. Replace with tag/capability dispatch.
    (
        "lathe/asset_graph.py",
        "*",
        "CYCLE 3a: family-aware AssetGraph blueprint routing. "
        "Replace with tag/capability/role dispatch."
    ),

    # connection_layout.py — family-aware procedural-environment layout.
    # Each family case becomes a CompositionPolicy.
    (
        "lathe/connection_layout.py",
        "*",
        "CYCLE 3a: family-aware procedural-environment connection layout. "
        "Each family case becomes a CompositionPolicy."
    ),

    # creative_grammar.py — family-aware grammar templates. Each becomes
    # a StyleKnowledge + CompositionPolicy pair.
    (
        "lathe/creative_grammar.py",
        "*",
        "CYCLE 3a: family-aware creative grammar templates. "
        "Becomes Style + Policy packs."
    ),

    # feature_fusion.py — single family check for courier_drone bevel.
    # Replace with capability/role dispatch.
    (
        "lathe/feature_fusion.py",
        'family == "courier_drone"',
        "CYCLE 3a: single courier_drone bevel guard. "
        "Replace with capability/role dispatch."
    ),

    # object_grammar.py — procedural_setpiece-specific matching path.
    (
        "lathe/object_grammar.py",
        'family == "procedural_setpiece"',
        "CYCLE 3a: procedural_setpiece object grammar path. "
        "Replace with intent-tag dispatch."
    ),

    # path_profiles.py — family-aware path defaults for bridge/access.
    (
        "lathe/path_profiles.py",
        "*",
        "CYCLE 3a: family-aware path profile defaults. "
        "Becomes a StyleKnowledge subset."
    ),

    # shape_program_driver.py — family-name dispatch + alias map.
    (
        "lathe/shape_program_driver.py",
        "*",
        "CYCLE 3a: family-aware shape-program dispatch + alias map. "
        "Replaced by the procedural synthesizer's domain routing."
    ),

    # structural_profiles.py — family-aware structural defaults.
    (
        "lathe/structural_profiles.py",
        "*",
        "CYCLE 3a: family-aware structural profile defaults. "
        "Becomes a StyleKnowledge subset."
    ),

    # surface_grammar.py — family-aware surface grammar with _FAMILY_PRESETS.
    (
        "lathe/surface_grammar.py",
        "*",
        "CYCLE 3a: family-aware surface grammar + _FAMILY_PRESETS map. "
        "Migrate to Style + Policy packs per family."
    ),

    # asset_quality/design_brief.py — _FAMILY_DEFAULTS lookup.
    (
        "lathe/asset_quality/design_brief.py",
        "_FAMILY_DEFAULTS.get(family",
        "CYCLE 3a: family-keyed brief defaults. "
        "Migrate values to StyleKnowledge packs."
    ),

    # asset_quality/family_grammar.py — _GRAMMARS lookup.
    (
        "lathe/asset_quality/family_grammar.py",
        "_GRAMMARS.get(family",
        "CYCLE 3a: family-keyed grammar lookup. "
        "Migrate per-family rules to CompositionPolicy packs."
    ),

    # asset_quality/material_wear_graph.py — _FAMILY_DEFAULT_GRAPHS lookup.
    (
        "lathe/asset_quality/material_wear_graph.py",
        "_FAMILY_DEFAULT_GRAPHS.get(family)",
        "CYCLE 3a: family-keyed material/wear default factory. "
        "Migrate to a wear-graph CompositionPolicy."
    ),

    # blueprints/procedural.py — _FAMILY_LOADOUT_ALIASES lookup.
    (
        "lathe/blueprints/procedural.py",
        "_FAMILY_LOADOUT_ALIASES.get(family",
        "CYCLE 3a: family-keyed loadout alias map. "
        "Migrate to declarative FamilyAlias JSON."
    ),
)
