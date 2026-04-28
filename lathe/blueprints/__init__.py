"""Family-specific assembly blueprint resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from ..assembly_kernel import AssemblyBlueprint
from ..asset_graph import AssetGraph
from .containers import _chest_blueprint, _crate_blueprint, _supply_container_blueprint
from .generic import _generic_blueprint
from .mechanical import _door_blueprint, _drone_blueprint
from .panels import (
    _console_blueprint,
    _control_pedestal_blueprint,
    _service_cabinet_blueprint,
    _wall_panel_blueprint,
)

BlueprintBuilder = Callable[[AssetGraph, np.random.Generator, int], AssemblyBlueprint]

_BLUEPRINT_BUILDERS: dict[str, BlueprintBuilder] = {
    "brassbound_chest": _chest_blueprint,
    "console_terminal": _console_blueprint,
    "control_pedestal": _control_pedestal_blueprint,
    "courier_drone": _drone_blueprint,
    "industrial_crate": _crate_blueprint,
    "mechanical_door": _door_blueprint,
    "sci_fi_wall_panel": _wall_panel_blueprint,
    "service_cabinet": _service_cabinet_blueprint,
    "supply_container": _supply_container_blueprint,
}


def resolve_blueprint(
    asset_graph: AssetGraph,
    conditioning: dict[str, Any],
    rng: np.random.Generator,
    candidate_index: int,
) -> AssemblyBlueprint:
    """Resolve the generated scaffold blueprint for an asset family."""
    builder = _BLUEPRINT_BUILDERS.get(asset_graph.family, _generic_blueprint)
    return builder(asset_graph, rng, candidate_index)


__all__ = ["resolve_blueprint"]
