"""Validator package: evidence-based certification for built assets.

Re-exports the ``evaluate_*`` entry points; individual validators live
in ``semantic_quality``, ``visual_quality``, ``flow_quality``,
``surface_quality`` and ``silhouette``. The :class:`ValidatorPipeline`
composition contract formalises how these validators are run together.
"""

from .composition import FunctionValidator, Validator, ValidatorPipeline, ValidatorReport
from .semantic_quality import evaluate_semantic_quality
from .visual_quality import evaluate_visual_quality

__all__ = [
    "FunctionValidator",
    "Validator",
    "ValidatorPipeline",
    "ValidatorReport",
    "evaluate_semantic_quality",
    "evaluate_visual_quality",
]
