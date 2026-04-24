"""Topology adapter: ``lathe.topology.blender_subdiv_v1`` (BL-34 scope).

Subdivision-surface topology adapter plumbed as the proof-of-plugin-model
for the ``lathe.stack.soft_surface_prop_v1`` second backend stack (Plan 08
Phase 4, scoped down per Wave 4.IV.e).

Current behavior -- intentional scaffolding:

* When Blender is available, delegate to the existing hard-surface
  Blender topology adapter. The result is deterministic end-to-end but
  does not yet honor soft-surface curvature-continuity constraints.
* When Blender is unavailable, fall back to the reference topology
  cleanup path (the same fallback the hard-surface stack uses).

# TODO(BL-34-followup): real subdivision surfaces with curvature
# continuity and fold-crease detection are deferred. The full Plan 08
# Phase 4 scope (2-week implementation) would introduce a dedicated
# Blender script that applies a Catmull-Clark subdivision modifier
# with explicit crease tags, honors ``build.topology.preserve = [soft_folds]``,
# and emits a ``subdiv_report`` with per-edge curvature continuity
# metrics. Document the gap in ``docs/second_backend_stack.md``.

The adapter registers metadata so downstream code can query which
adapter path was taken. Actual runtime dispatch still happens inside
``lathe/core/stages/topology.py`` -- the backend ID recorded on the
topology bundle simply tells consumers which contract was in force.
"""

from __future__ import annotations

from typing import Any


ADAPTER_ID = "lathe.topology.blender_subdiv_v1"


def describe() -> dict[str, Any]:
    """Return the adapter's self-description.

    Callable by docs tooling and tests to verify the adapter is
    importable and has the expected identity.
    """
    return {
        "adapter_id": ADAPTER_ID,
        "stage": "topology",
        "delegates_to": "lathe.topology.blender_hard_surface_v1",
        "fallback": "reference_topology_cleanup",
        "status": "scaffold",
        "notes": (
            "Second-stack proof-of-plugin-model. Real subdivision "
            "surfaces with curvature continuity are deferred -- see "
            "docs/second_backend_stack.md for the full 2-week scope "
            "amendment."
        ),
    }


def run(runtime_mesh: Any, stage_dir: Any, runtime_config: dict[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    """Execute the adapter.

    Scoped implementation: delegate to the existing Blender topology
    adapter when available, otherwise fall back to reference cleanup.
    This keeps the proof runnable end-to-end without requiring a new
    Blender script.

    The caller is expected to already have passed the standard
    ``probe_topology_backend`` gate in ``core/stages/topology.py``.
    When this adapter's path is explicitly requested on an asset, the
    core stage's Blender-delegation branch runs unmodified and tags
    the bundle with this adapter's ID via the stack binding.
    """
    # Lazy import to avoid pulling in the Blender subprocess module at
    # import time (keeps `lathe doctor` and `lathe backends` fast).
    from ..core.stages.topology import run_blender_topology

    return run_blender_topology(runtime_mesh, stage_dir, runtime_config)
