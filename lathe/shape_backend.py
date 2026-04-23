# Shim — see ADR-0005. Remove after V1.4.
from .shape.backend import collect_shape_conditioning, run_shape_backend

__all__ = ["collect_shape_conditioning", "run_shape_backend"]
