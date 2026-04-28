"""Native reference-conditioned shape provider adapter.

The reference-conditioned provider doesn't *execute* externally — it is the
deterministic fallback path.  ``maybe_run_shape_provider`` short-circuits
before any adapter dispatch when this provider is selected.  This module
exists as the canonical home for that contract so other layers can import
the provider ID from one place, and so a future reference-conditioned
executor has a place to land without touching selection.
"""

from __future__ import annotations

PROVIDER_ID = "lathe.provider.shape.reference_conditioned_v1"


def reference_conditioned_provider() -> dict[str, str]:
    """Entry-point shim for ``lathe.providers.shape``.

    Returns the provider id so the plugin-discovery code can look the
    full descriptor up in :mod:`lathe.providers.registry`.
    """
    return {"id": PROVIDER_ID}
