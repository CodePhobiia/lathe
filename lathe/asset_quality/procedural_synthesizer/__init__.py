"""Procedural Synthesizer — Lathe's family-free shape-program compiler.

Replaces family-name dispatch with a procedural compiler pipeline
that consumes typed construction-graph nodes, expands reusable
composition policies (matched by authored intent, never by family
name), validates typed per-NODE_TYPE attribute schemas, and emits
ShapeIR v2 ops through domain-extensible generators.

Public API:

    synthesize_procedural_program(asset, runtime) -> SynthesisResult

The result's ``shape_program`` field is a ShapeIR v2 ShapeProgram
ready for lowering to the kernel. The ``trace`` field exposes every
decision the pipeline made. ``synthesized_graph_nodes`` reports
nodes that composition policies added on top of the authored graph.

See docs/asset-quality/procedural-synthesizer-architecture-spec.md
(v2) plus docs/asset-quality/procedural-synthesizer-architecture-
correction.md for the architecture.
"""

from __future__ import annotations

# Importing the generators package triggers domain registration.
# This must happen before any synthesize_procedural_program call.
from . import generators  # noqa: F401

from .context import (
    ConstructionEdgeTyped,
    ConstructionNodeTyped,
    SynthesizerContext,
    resolve_context,
)
from .domain_extension import (
    DomainExtensionManifest,
    DomainExtensionRegistration,
)
from .knowledge_loader import (
    CompositionPolicy,
    FamilyAlias,
    KnowledgePackInvalid,
    PolicyExpansion,
    PolicyPrecondition,
    StyleKnowledge,
)
from .pipeline import SynthesisResult, synthesize_procedural_program
from .registry import (
    REGISTRY,
    EdgeDecoratorCapabilityManifest,
    EdgeTypeDecorator,
    GeneratorCapabilityManifest,
    GeneratorRegistry,
    NodeTypeGenerator,
)
from .trace import SynthesizerTrace, TraceBuilder, TraceEntry


__all__ = [
    "CompositionPolicy",
    "ConstructionEdgeTyped",
    "ConstructionNodeTyped",
    "DomainExtensionManifest",
    "DomainExtensionRegistration",
    "EdgeDecoratorCapabilityManifest",
    "EdgeTypeDecorator",
    "FamilyAlias",
    "GeneratorCapabilityManifest",
    "GeneratorRegistry",
    "KnowledgePackInvalid",
    "NodeTypeGenerator",
    "PolicyExpansion",
    "PolicyPrecondition",
    "REGISTRY",
    "StyleKnowledge",
    "SynthesizerContext",
    "SynthesizerTrace",
    "SynthesisResult",
    "TraceBuilder",
    "TraceEntry",
    "resolve_context",
    "synthesize_procedural_program",
]
