"""Typed attribute schemas per NODE_TYPE.

Stage 4 of the procedural synthesizer pipeline validates each
ConstructionNode.attributes dict against the schema registered for
its node_type. Validation failures emit
``attribute_schema_violation`` trace entries and the node is dropped
from further pipeline stages.

Adding a new NODE_TYPE means adding its schema here and registering
it in ``ATTRIBUTE_SCHEMAS``. Schemas are frozen dataclasses with
``from_dict()`` classmethods that validate raw input.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .frame import FrameAttributes
from .panel import PanelAttributes
from .primary_volume import PrimaryVolumeAttributes
from .trim import TrimAttributes


# Per-NODE_TYPE schema registry. Adding a new NODE_TYPE attribute
# schema means adding it here. The pipeline consults this map in
# Stage 4. NODE_TYPEs absent from this map skip validation (their
# generators must handle raw dict attributes).
ATTRIBUTE_SCHEMAS: Mapping[str, Callable[[dict[str, Any]], Any]] = {
    "primary_volume": PrimaryVolumeAttributes.from_dict,
    "panel": PanelAttributes.from_dict,
    "frame": FrameAttributes.from_dict,
    "trim": TrimAttributes.from_dict,
}


def validate_attributes(node_type: str, raw_attributes: dict[str, Any]) -> Any:
    """Validate raw attribute dict against the schema for ``node_type``.

    Returns the typed attribute instance. Raises ValueError or TypeError
    on validation failure. NODE_TYPEs without a registered schema return
    the raw dict unchanged.
    """
    validator = ATTRIBUTE_SCHEMAS.get(node_type)
    if validator is None:
        return raw_attributes
    return validator(raw_attributes)


__all__ = [
    "ATTRIBUTE_SCHEMAS",
    "FrameAttributes",
    "PanelAttributes",
    "PrimaryVolumeAttributes",
    "TrimAttributes",
    "validate_attributes",
]
