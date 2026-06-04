"""Foundry Lane G later validators.

Per northstar §10 Lane G "later tasks":
  - multi-angle silhouette validator
  - frequency-energy validator
  - topology class compliance by asset type
  - PBR chart compliance
  - style stack compatibility

Each validator returns a typed report compatible with the existing
``lathe/validators/`` infrastructure but lives in the Foundry tree
because the metric semantics depend on Foundry contracts (style
packs, capability matrix, family taxonomy).
"""

from __future__ import annotations

from .frequency_energy import (
    FREQUENCY_ENERGY_VERSION,
    FrequencyEnergyReport,
    evaluate_frequency_energy,
)
from .pbr_chart import (
    PBR_CHART_COMPLIANCE_VERSION,
    PbrChartReport,
    evaluate_pbr_chart_compliance,
)
from .silhouette_multi_angle import (
    SILHOUETTE_MULTI_ANGLE_VERSION,
    SilhouetteMultiAngleReport,
    evaluate_silhouette_multi_angle,
)
from .style_stack_compatibility import (
    STYLE_STACK_COMPATIBILITY_VERSION,
    StyleStackCompatibilityReport,
    evaluate_style_stack_compatibility,
)
from .topology_class_compliance import (
    TOPOLOGY_CLASS_COMPLIANCE_VERSION,
    TopologyClassReport,
    evaluate_topology_class_compliance,
)

__all__ = [
    "FREQUENCY_ENERGY_VERSION",
    "FrequencyEnergyReport",
    "PBR_CHART_COMPLIANCE_VERSION",
    "PbrChartReport",
    "SILHOUETTE_MULTI_ANGLE_VERSION",
    "SilhouetteMultiAngleReport",
    "STYLE_STACK_COMPATIBILITY_VERSION",
    "StyleStackCompatibilityReport",
    "TOPOLOGY_CLASS_COMPLIANCE_VERSION",
    "TopologyClassReport",
    "evaluate_frequency_energy",
    "evaluate_pbr_chart_compliance",
    "evaluate_silhouette_multi_angle",
    "evaluate_style_stack_compatibility",
    "evaluate_topology_class_compliance",
]
