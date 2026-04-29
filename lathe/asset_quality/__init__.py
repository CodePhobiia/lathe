"""Asset-quality upgrade package.

Hosts the design-brief, family-grammar, semantic-construction-graph,
ShapeIR v2 adapter, material/wear graph, and quality-diagnostics layers
introduced by ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md``.

Phase 0 (baseline) leaves this package empty. Phases 1+ add modules here
without modifying ``lathe/validators/*`` or the existing certification
report contract; they integrate via additive ``FunctionValidator``
registrations in ``lathe/core/stages/validate.py``.
"""

from __future__ import annotations

__all__: list[str] = []
