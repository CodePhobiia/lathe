"""Plugin-extensible generator/decorator registry.

The registry is keyed by ``(domain, node_type)`` for generators and
``(domain, edge_type)`` for decorators. Domains register their
contributions at import time via ``register_domain_extension(...)``.

The registry refuses to register a manifest whose declared
``node_type_schemas`` does not cover every NODE_TYPE its generators
handle — that gap surfaces as a registration-time error rather than a
silent gap.

The hard-surface domain is the first DomainExtension registered (in
``generators/hard_surface/__init__.py``). Phase 3 domains (vegetation,
terrain, WFC, CGA, etc.) register against the same contract without
touching the hard-surface tree.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Protocol

from .domain_extension import DomainExtensionManifest, DomainExtensionRegistration


if TYPE_CHECKING:
    from .context import ConstructionEdgeTyped, ConstructionNodeTyped, SynthesizerContext


# Op resolver protocol — passed to edge decorators so they can reference
# ops emitted by earlier nodes in the topological order.
class OpResolver(Protocol):
    """Looks up ops by their owning node_id. Provided to edge decorators."""

    def ops_for_node(self, node_id: str) -> tuple[Any, ...]:
        """Return ops emitted for the given node (in emission order)."""
        ...


@dataclass(frozen=True)
class GeneratorCapabilityManifest:
    """Declares what a generator does. Inspectable at registration time."""

    node_type: str
    domain: str
    consumed_attribute_fields: tuple[str, ...]
    consumed_style_fields: tuple[str, ...]
    emitted_op_kinds: tuple[str, ...]
    required_kernel_capabilities: tuple[str, ...]
    fallback_diagnostics: tuple[str, ...]
    output_kind: str  # "visible_geometry" | "material_mask" | "metadata_only"


@dataclass(frozen=True)
class EdgeDecoratorCapabilityManifest:
    """Declares what an edge decorator does. Symmetric to generator manifest."""

    edge_type: str
    domain: str
    consumed_attribute_fields: tuple[str, ...]
    consumed_style_fields: tuple[str, ...]
    emitted_op_kinds: tuple[str, ...]
    required_kernel_capabilities: tuple[str, ...]
    fallback_diagnostics: tuple[str, ...]
    output_kind: str


@dataclass(frozen=True)
class NodeTypeGenerator:
    """A generator: manifest + implementation."""

    manifest: GeneratorCapabilityManifest
    implementation: Callable[
        ["ConstructionNodeTyped", "SynthesizerContext"],
        Iterable[Any],  # iterable of ShapeOp
    ]


@dataclass(frozen=True)
class EdgeTypeDecorator:
    """An edge decorator: manifest + implementation."""

    manifest: EdgeDecoratorCapabilityManifest
    implementation: Callable[
        ["ConstructionEdgeTyped", "SynthesizerContext", OpResolver],
        Iterable[Any],  # iterable of ShapeOp
    ]


class GeneratorRegistry:
    """Plugin-extensible registry.

    Thread-safe registration. Reads are lock-free (the maps are
    immutable mappings, swapped via the lock).

    Registration is idempotent in the sense that re-registering the
    same (domain, node_type) replaces the prior registration but
    emits no silent log; callers should not rely on accidental
    re-registration.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generators: dict[tuple[str, str], NodeTypeGenerator] = {}
        self._decorators: dict[tuple[str, str], EdgeTypeDecorator] = {}
        self._domains: dict[str, DomainExtensionManifest] = {}

    def register_domain_extension(
        self, registration: DomainExtensionRegistration
    ) -> None:
        """Register an entire domain at once. Validates manifest coverage."""
        manifest = registration.manifest
        self._validate_registration_coverage(registration)
        with self._lock:
            self._domains[manifest.domain_id] = manifest
            for gen in registration.generators:
                self._generators[(gen.manifest.domain, gen.manifest.node_type)] = gen
            for dec in registration.decorators:
                self._decorators[(dec.manifest.domain, dec.manifest.edge_type)] = dec

    def register_generator(self, gen: NodeTypeGenerator) -> None:
        """Register a single generator. The domain must already be registered."""
        if gen.manifest.domain not in self._domains:
            raise RuntimeError(
                f"cannot register generator for unregistered domain "
                f"{gen.manifest.domain!r}; register the DomainExtension first"
            )
        with self._lock:
            self._generators[(gen.manifest.domain, gen.manifest.node_type)] = gen

    def register_decorator(self, dec: EdgeTypeDecorator) -> None:
        """Register a single decorator."""
        if dec.manifest.domain not in self._domains:
            raise RuntimeError(
                f"cannot register decorator for unregistered domain "
                f"{dec.manifest.domain!r}; register the DomainExtension first"
            )
        with self._lock:
            self._decorators[(dec.manifest.domain, dec.manifest.edge_type)] = dec

    def resolve_generator(
        self, domain: str, node_type: str
    ) -> NodeTypeGenerator | None:
        """Look up generator by (domain, node_type), falling back to 'core'.

        The 'core' pseudo-domain covers NODE_TYPEs that work across all
        domains (e.g., material_zone). When a domain-specific generator
        is not registered, the synthesizer tries the core domain.
        """
        gen = self._generators.get((domain, node_type))
        if gen is not None:
            return gen
        return self._generators.get(("core", node_type))

    def resolve_decorator(
        self, domain: str, edge_type: str
    ) -> EdgeTypeDecorator | None:
        dec = self._decorators.get((domain, edge_type))
        if dec is not None:
            return dec
        return self._decorators.get(("core", edge_type))

    def registered_domains(self) -> tuple[str, ...]:
        return tuple(sorted(self._domains))

    def domain_manifest(self, domain_id: str) -> DomainExtensionManifest | None:
        return self._domains.get(domain_id)

    def covered_node_types(self, domain: str) -> tuple[str, ...]:
        """Return node types this domain has generators for. Includes 'core'."""
        domain_types = {
            node_type for (dom, node_type) in self._generators if dom == domain
        }
        core_types = {
            node_type for (dom, node_type) in self._generators if dom == "core"
        }
        return tuple(sorted(domain_types | core_types))

    def covered_edge_types(self, domain: str) -> tuple[str, ...]:
        domain_types = {
            edge_type for (dom, edge_type) in self._decorators if dom == domain
        }
        core_types = {
            edge_type for (dom, edge_type) in self._decorators if dom == "core"
        }
        return tuple(sorted(domain_types | core_types))

    def _validate_registration_coverage(
        self, registration: DomainExtensionRegistration
    ) -> None:
        manifest = registration.manifest
        # Every generator's declared node_type must be backed by a schema
        # in the manifest, AND the generator's declared domain must
        # match the manifest's domain.
        for gen in registration.generators:
            if gen.manifest.domain != manifest.domain_id and gen.manifest.domain != "core":
                raise RuntimeError(
                    f"generator domain {gen.manifest.domain!r} does not "
                    f"match registration domain {manifest.domain_id!r}"
                )
            if gen.manifest.node_type not in manifest.node_type_schemas:
                raise RuntimeError(
                    f"generator for node_type {gen.manifest.node_type!r} "
                    f"has no schema in DomainExtensionManifest "
                    f"{manifest.domain_id!r}.node_type_schemas"
                )
        for dec in registration.decorators:
            if dec.manifest.domain != manifest.domain_id and dec.manifest.domain != "core":
                raise RuntimeError(
                    f"decorator domain {dec.manifest.domain!r} does not "
                    f"match registration domain {manifest.domain_id!r}"
                )
            if dec.manifest.edge_type not in manifest.edge_type_schemas:
                raise RuntimeError(
                    f"decorator for edge_type {dec.manifest.edge_type!r} "
                    f"has no schema in DomainExtensionManifest "
                    f"{manifest.domain_id!r}.edge_type_schemas"
                )


# Module-level singleton. Hard-surface and future domains register here.
REGISTRY = GeneratorRegistry()
