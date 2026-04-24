from __future__ import annotations

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


def resolve_blueprint(
    asset_graph: AssetGraph,
    conditioning: dict[str, Any],
    rng: np.random.Generator,
    candidate_index: int,
) -> AssemblyBlueprint:
    family = asset_graph.family
    if family == "brassbound_chest":
        return _chest_blueprint(asset_graph, rng, candidate_index)
    if family == "courier_drone":
        return _drone_blueprint(asset_graph, rng, candidate_index)
    if family == "sci_fi_wall_panel":
        return _wall_panel_blueprint(asset_graph, rng, candidate_index)
    if family == "industrial_crate":
        return _crate_blueprint(asset_graph, rng, candidate_index)
    if family == "mechanical_door":
        return _door_blueprint(asset_graph, rng, candidate_index)
    if family == "console_terminal":
        return _console_blueprint(asset_graph, rng, candidate_index)
    if family == "service_cabinet":
        return _service_cabinet_blueprint(asset_graph, rng, candidate_index)
    if family == "control_pedestal":
        return _control_pedestal_blueprint(asset_graph, rng, candidate_index)
    if family == "supply_container":
        return _supply_container_blueprint(asset_graph, rng, candidate_index)
    return _generic_blueprint(asset_graph, rng, candidate_index)


__all__ = ["resolve_blueprint"]
