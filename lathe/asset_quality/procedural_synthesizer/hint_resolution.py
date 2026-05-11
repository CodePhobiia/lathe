"""Hint resolution — priority chain with trace attribution.

Generators consume parameter values through this chain so authored
intent always wins over style bias. Every resolution writes a
``hint_resolved`` trace entry recording which priority level supplied
the winning value.

Priority order (highest wins):
  1. Typed node attribute (already schema-validated by Stage 4)
  2. Authored brief field
  3. Authored parts list (presence/absence)
  4. style.parameter_priors[node_type][field]
  5. style.proportion_priors[node_type] / density_priors / silhouette_priors
  6. Generator-internal absolute default
"""

from __future__ import annotations

from typing import Any, Mapping

from .context import SynthesizerContext
from .trace import TraceBuilder


_MISSING = object()


def resolve_hint(
    *,
    field_name: str,
    node_id: str,
    node_type: str,
    typed_attr_value: Any = _MISSING,
    brief_field: str | None = None,
    style_prior_path: tuple[str, ...] | None = None,
    absolute_default: Any = None,
    context: SynthesizerContext,
    trace: TraceBuilder,
) -> Any:
    """Resolve one field value through the priority chain.

    Args:
        field_name: name of the field being resolved (for trace).
        node_id: owning node id (for trace).
        node_type: owning node type (for trace).
        typed_attr_value: priority 1 — if not _MISSING, wins.
        brief_field: priority 2 — key to read from context.brief if not
            None.
        style_prior_path: priority 4 — sequence of keys to dig into
            context.style.parameter_priors. If None, skipped.
        absolute_default: priority 6 fallback.
        context: SynthesizerContext.
        trace: TraceBuilder for attribution.

    Returns the resolved value plus emits a ``hint_resolved`` trace
    entry naming the priority that won.

    The priority-3 "parts list presence/absence" is not modeled here
    because it is a structural decision, not a parameter value.
    Parts-list presence is consulted by policy preconditions and by
    generators that handle node-existence logic — not by this
    field-resolution function.
    """
    # Priority 1: typed attribute
    if typed_attr_value is not _MISSING:
        trace.emit(
            "hint_resolved",
            stage=0,
            field=field_name,
            node_id=node_id,
            node_type=node_type,
            source="typed_attribute",
            value=_jsonable(typed_attr_value),
        )
        return typed_attr_value

    # Priority 2: brief field
    if brief_field is not None:
        if brief_field in context.brief:
            value = context.brief[brief_field]
            trace.emit(
                "hint_resolved",
                stage=0,
                field=field_name,
                node_id=node_id,
                node_type=node_type,
                source="brief_field",
                source_key=brief_field,
                value=_jsonable(value),
            )
            return value

    # Priority 4/5: style priors
    if style_prior_path is not None and context.style is not None:
        value = _walk_style(context.style, style_prior_path)
        if value is not _MISSING:
            trace.emit(
                "hint_resolved",
                stage=0,
                field=field_name,
                node_id=node_id,
                node_type=node_type,
                source="style_prior",
                source_path=list(style_prior_path),
                value=_jsonable(value),
            )
            return value

    # Priority 6: absolute default
    trace.emit(
        "hint_resolved",
        stage=0,
        field=field_name,
        node_id=node_id,
        node_type=node_type,
        source="absolute_default",
        value=_jsonable(absolute_default),
    )
    return absolute_default


def _walk_style(style: Any, path: tuple[str, ...]) -> Any:
    """Walk into style.parameter_priors / proportion_priors / etc.

    ``path`` starts with the prior bucket name (e.g.,
    ``"parameter_priors"``), then the node_type, then the field name.
    Returns ``_MISSING`` if any step is absent.
    """
    if not path:
        return _MISSING
    head, *rest = path
    current: Any = getattr(style, head, _MISSING)
    if current is _MISSING:
        return _MISSING
    for step in rest:
        if isinstance(current, Mapping):
            if step not in current:
                return _MISSING
            current = current[step]
        else:
            return _MISSING
    return current


def _jsonable(value: Any) -> Any:
    """Best-effort coerce for trace payload. Falls back to repr."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return repr(value)
