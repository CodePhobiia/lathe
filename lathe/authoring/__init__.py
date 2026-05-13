"""Lathe authoring layer (Wave 18 / research §8).

Three layers per research §8:

  1. Declarative DSL (.lth) — the source of truth. Diffable,
     reproducible, machine-editable. Always wins on conflicts.
  2. Visual node graph — non-programmer control, exposed parameters,
     previewable nodes. Translates to/from .lth.
  3. Natural-language / sketch assistant — fast intent capture,
     edits the DSL/graph, proposes variants.

This package lands the contract surface for all three layers without
prescribing a specific UI. Each layer is a translation pass between a
typed authoring representation and the canonical construction graph
the synthesizer consumes.
"""

from .graph_ir import (
    AuthorGraphNode,
    AuthorGraphEdge,
    AuthorGraph,
    author_graph_from_construction_graph,
    construction_graph_from_author_graph,
)
from .nl_intent import (
    NLIntent,
    parse_nl_intent,
    nl_intent_to_construction_payload,
)

__all__ = [
    "AuthorGraphNode",
    "AuthorGraphEdge",
    "AuthorGraph",
    "author_graph_from_construction_graph",
    "construction_graph_from_author_graph",
    "NLIntent",
    "parse_nl_intent",
    "nl_intent_to_construction_payload",
]
