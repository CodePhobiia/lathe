"""JSON knowledge pack loaders for the procedural synthesizer.

Three knowledge types — Style, Policy, Alias — each loaded from
``std/procedural/knowledge/<kind>/*.json``, schema-validated at load,
and exposed as frozen dataclasses.

The synthesizer never dispatches on family name. Family aliases are
metadata; their only effect is selecting a Style and a list of
Policies. Structural composition lives in Policies and is matched by
authored-intent precondition, never by family name.
"""

from __future__ import annotations

from .alias import FamilyAlias, load_alias_pack, load_all_alias_packs
from .policy import (
    CompositionPolicy,
    EdgeTemplate,
    PolicyExpansion,
    PolicyPrecondition,
    load_all_policy_packs,
    load_policy_pack,
    precondition_matches,
)
from .style import (
    KnowledgePackInvalid,
    StyleKnowledge,
    load_all_style_packs,
    load_style_pack,
)

__all__ = [
    "CompositionPolicy",
    "EdgeTemplate",
    "FamilyAlias",
    "KnowledgePackInvalid",
    "PolicyExpansion",
    "PolicyPrecondition",
    "StyleKnowledge",
    "load_alias_pack",
    "load_all_alias_packs",
    "load_all_policy_packs",
    "load_all_style_packs",
    "load_policy_pack",
    "load_style_pack",
    "precondition_matches",
]
