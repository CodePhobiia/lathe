"""Validator package: evidence-based certification for built assets.

Re-exports the ``evaluate_*`` entry points; individual validators live
in ``semantic_quality``, ``visual_quality``, ``flow_quality``,
``surface_quality`` and ``silhouette``.
"""

from .semantic_quality import evaluate_semantic_quality
from .visual_quality import evaluate_visual_quality

__all__ = ["evaluate_semantic_quality", "evaluate_visual_quality"]
