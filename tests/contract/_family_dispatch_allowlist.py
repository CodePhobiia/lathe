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

    # ---------------------------------------------------------------
    # NOTE: the Cycle 3a per-file allowlist entries for asset_graph.py,
    # connection_layout.py, creative_grammar.py, path_profiles.py,
    # shape_program_driver.py, structural_profiles.py, and
    # surface_grammar.py were cleared by the unblocking pass. Each
    # remaining family-keyed line in those files now carries an inline
    # ``# no-family-dispatch: <reason>`` comment documenting why the
    # dispatch is genuine + where the migration target is. New
    # family-keyed dispatch must either:
    #   - carry its own inline exempt comment, OR
    #   - be added back to this allowlist with a justified reason.
    # ---------------------------------------------------------------
)
