"""Domain extension contract.

This is the plugin contract that Phase 3 domains (vegetation, terrain,
WFC, CGA, F-Rep/SDF, scatter, animation) register against. It lands in
Cycle 1 so domain expansion in Cycle 6 becomes "add a DomainExtension"
not "redesign the synthesizer."

A DomainExtension declares a domain's contribution to the procedural
engine: which NODE_TYPEs it owns, which EDGE_TYPEs it owns, which
generators/decorators handle them, which kernel capabilities it
requires, and which ShapeIR v2 ops it can emit.

The hard-surface domain is the first DomainExtension registered. It
ships as a Cycle 1 deliverable alongside this contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import EdgeTypeDecorator, NodeTypeGenerator


@dataclass(frozen=True)
class DomainExtensionManifest:
    """Declares a domain's procedural contribution.

    Inspected at registration time so incomplete coverage surfaces as
    a diagnostic rather than a silent gap. A registry refuses to
    register a manifest whose ``node_type_schemas`` does not cover
    every NODE_TYPE its generators declare to handle.
    """

    domain_id: str
    """Unique domain identifier. Examples: "hard_surface", "vegetation",
    "terrain", "wfc", "cga", "sdf_organic", "scatter", "animation".

    The pseudo-domain ``"core"`` is reserved for NODE_TYPEs that work
    across all domains (e.g., ``material_zone``).
    """

    node_type_schemas: dict[str, type]
    """NODE_TYPE -> typed attribute schema class. Validated by Stage 4
    of the compiler pipeline before generators consume the node.
    """

    edge_type_schemas: dict[str, type]
    """EDGE_TYPE -> typed attribute schema class. Symmetric to
    node_type_schemas.
    """

    required_kernel_capabilities: tuple[str, ...]
    """Kernel capabilities the domain's generators emit ops against.
    Examples: "solid.box", "solid.rounded_box", "op.subtract", "op.bevel".
    """

    emitted_shape_ir_ops: tuple[str, ...]
    """ShapeIR v2 ops this domain's generators may emit. Subset of
    ``lathe.asset_quality.shape_ir_v2.ALL_OPS``. Used by Stage 8 of
    the pipeline to validate that emitted ops are legitimate.
    """

    style_pack_compatibility: tuple[str, ...]
    """Style pack IDs (or wildcards) this domain accepts. Empty
    tuple means "any compatible style." A specific list means "only
    these styles." Wildcards: ``"*"`` accepts all.
    """

    policy_pack_compatibility: tuple[str, ...]
    """CompositionPolicy IDs (or wildcards) this domain accepts. Same
    semantics as style_pack_compatibility.
    """

    description: str = ""
    """Human-readable summary of the domain. Lives in manifests for
    audit; ignored by the pipeline.
    """


@dataclass
class DomainExtensionRegistration:
    """A DomainExtension's registration request to the GeneratorRegistry.

    Bundles the manifest with the actual generator and decorator
    callables. The registry validates the manifest, then registers
    every generator/decorator under (domain_id, node_type) /
    (domain_id, edge_type).
    """

    manifest: DomainExtensionManifest
    generators: tuple[NodeTypeGenerator, ...]
    decorators: tuple[EdgeTypeDecorator, ...] = field(default_factory=tuple)
