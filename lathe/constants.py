"""Shared module-level constants for Lathe.

This module holds tiny, widely-referenced constants to avoid magic-number
scatter across the codebase. Add a constant here only when it's used in
more than one module.
"""

from __future__ import annotations

# Prime offset used to derive a deterministic per-candidate RNG seed in
# the shape stage. Chosen because it's a prime with good mixing properties
# near the expected candidate-index range (0..~100). Changing this value
# would change the shape-provider candidate output for every existing
# seed, so it is treated as part of the shape-stage determinism contract —
# do not bump without an ADR.
RNG_PRIME_OFFSET: int = 7919
