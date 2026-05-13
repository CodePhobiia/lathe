"""Foundry Lane I — authoring surface + stdlib modularity.

Per northstar §10 Lane I, the authoring surface needs:

  - stdlib registry (versioned kits + parts)
  - director vocabulary (style compositions)
  - field-style attr language (masks + scatter)
  - CGA-style assembly rules
  - reference-driven palette/silhouette/frequency extraction

Each module is internal-only at v0.1; public ``.lth`` syntax follows
once the execution path proves the claims.
"""

from __future__ import annotations

from .cga_assembly import (
    CGA_ASSEMBLY_VERSION,
    AssemblyRule,
    AssemblyRuleSet,
    Shape,
    SplitOp,
    apply_assembly_rules,
)
from .director_vocabulary import (
    DIRECTOR_VOCABULARY_VERSION,
    DirectorComposition,
    DirectorRegistry,
    DirectorTerm,
    director_registry_v1,
    resolve_director_term,
)
from .field_attrs import (
    FIELD_ATTRS_VERSION,
    FieldExpression,
    FieldOperator,
    evaluate_field,
    parse_field_expression,
)
from .reference_extraction import (
    REFERENCE_EXTRACTION_VERSION,
    ReferenceBoard,
    ReferencePalette,
    ReferenceSilhouette,
    extract_palette_signature,
    extract_silhouette_signature,
    extract_frequency_signature,
)
from .stdlib_registry import (
    STDLIB_REGISTRY_VERSION,
    StdlibEntry,
    StdlibRegistry,
    StdlibVersion,
    register_stdlib_kit,
    stdlib_registry_v1,
)

__all__ = [
    "CGA_ASSEMBLY_VERSION",
    "AssemblyRule",
    "AssemblyRuleSet",
    "Shape",
    "SplitOp",
    "apply_assembly_rules",
    "DIRECTOR_VOCABULARY_VERSION",
    "DirectorComposition",
    "DirectorRegistry",
    "DirectorTerm",
    "director_registry_v1",
    "resolve_director_term",
    "FIELD_ATTRS_VERSION",
    "FieldExpression",
    "FieldOperator",
    "evaluate_field",
    "parse_field_expression",
    "REFERENCE_EXTRACTION_VERSION",
    "ReferenceBoard",
    "ReferencePalette",
    "ReferenceSilhouette",
    "extract_frequency_signature",
    "extract_palette_signature",
    "extract_silhouette_signature",
    "STDLIB_REGISTRY_VERSION",
    "StdlibEntry",
    "StdlibRegistry",
    "StdlibVersion",
    "register_stdlib_kit",
    "stdlib_registry_v1",
]
