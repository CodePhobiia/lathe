"""Variation discipline at scale (Wave 24 / P13).

Verifies that N seeds × 1 prompt produce N visibly-distinct assets
rather than near-duplicates. The harness:

  1. Generates N AuthorGraphs from one base + N seeds.
  2. Computes a structural signature per graph (node_id list, edge
     counts, attribute hashes).
  3. Reports duplication rate + diversity score.

Without this, scaling to 100 crates from one .lth produces 100
near-identical outputs because morphology + visual language fully
constrain the generation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..determinism.seeds import derive_subseed

CONTRACT_VERSION = "lathe.authoring.variation_v1"


@dataclass(frozen=True)
class VariationReport:
    """Diversity report for N variations of one base."""

    seed_count: int
    unique_signature_count: int
    duplicate_count: int
    diversity_ratio: float  # unique / total
    most_common_signatures: tuple[tuple[str, int], ...]
    passes_diversity_threshold: bool


def _signature_for_graph(
    nodes: Iterable[Mapping[str, Any]], edges: Iterable[Mapping[str, Any]]
) -> str:
    """Compute a deterministic structural signature for a graph."""
    h = hashlib.sha256()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        h.update(str(node.get("node_id") or "").encode())
        h.update(b"|")
        h.update(str(node.get("node_type") or "").encode())
        h.update(b"|")
        attrs = node.get("attributes") or {}
        if isinstance(attrs, Mapping):
            for k in sorted(attrs):
                h.update(str(k).encode())
                h.update(b"=")
                h.update(str(attrs[k]).encode())
                h.update(b";")
        h.update(b"\n")
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        h.update(str(edge.get("source_id") or "").encode())
        h.update(b"-")
        h.update(str(edge.get("edge_type") or "").encode())
        h.update(b"->")
        h.update(str(edge.get("target_id") or "").encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


def analyze_variation(
    graph_signatures: Iterable[str],
    diversity_threshold: float = 0.7,
) -> VariationReport:
    """Compute a variation report from N graph signatures.

    ``diversity_threshold``: minimum unique_count / total_count for
    the report to pass. 0.7 means ≥70% of seeds must produce
    visibly-distinct outputs.
    """
    sigs = list(graph_signatures)
    total = len(sigs)
    counts: dict[str, int] = {}
    for s in sigs:
        counts[s] = counts.get(s, 0) + 1
    unique_count = len(counts)
    duplicate_count = total - unique_count
    ratio = unique_count / max(1, total)
    most_common = tuple(sorted(counts.items(), key=lambda kv: -kv[1])[:5])
    return VariationReport(
        seed_count=total,
        unique_signature_count=unique_count,
        duplicate_count=duplicate_count,
        diversity_ratio=ratio,
        most_common_signatures=most_common,
        passes_diversity_threshold=ratio >= diversity_threshold,
    )


def signature_for_construction_graph(construction_graph: Mapping[str, Any]) -> str:
    """Convenience: signature from a construction_graph dict."""
    return _signature_for_graph(
        construction_graph.get("nodes") or [],
        construction_graph.get("edges") or [],
    )


__all__ = [
    "CONTRACT_VERSION",
    "VariationReport",
    "analyze_variation",
    "signature_for_construction_graph",
]
