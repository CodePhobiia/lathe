"""Validator package: evidence-based certification for built assets.

Re-exports the ``evaluate_*`` entry points; individual validators live
in ``semantic_quality``, ``visual_quality``, ``flow_quality``,
``surface_quality`` and ``silhouette``. The :class:`ValidatorPipeline`
composition contract formalises how these validators are run together.
"""

from .box_stack_detector import evaluate_box_stack_detector
from .composition import FunctionValidator, Validator, ValidatorPipeline, ValidatorReport
from .curvature_distribution import evaluate_curvature_distribution
from .edge_density import evaluate_edge_density_variance
from .frequency_energy import evaluate_frequency_energy
from .geometry_integrity import evaluate_geometry_integrity
from .pbr_chart import evaluate_pbr_chart_compliance
from .render_class import evaluate_render_class_validators
from .semantic_quality import evaluate_semantic_quality
from .silhouette_multi_angle import evaluate_silhouette_multi_angle
from .texel_density import evaluate_texel_density_consistency
from .topology_class import evaluate_topology_class_compliance
from .visual_quality import evaluate_visual_quality

__all__ = [
    "FunctionValidator",
    "Validator",
    "ValidatorPipeline",
    "ValidatorReport",
    "evaluate_box_stack_detector",
    "evaluate_curvature_distribution",
    "evaluate_edge_density_variance",
    "evaluate_frequency_energy",
    "evaluate_geometry_integrity",
    "evaluate_pbr_chart_compliance",
    "evaluate_render_class_validators",
    "evaluate_semantic_quality",
    "evaluate_silhouette_multi_angle",
    "evaluate_texel_density_consistency",
    "evaluate_topology_class_compliance",
    "evaluate_visual_quality",
]
