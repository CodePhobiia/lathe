"""Publish stage step body (BL-31, Plan 08 Phase 1).

Reads ``runtime_config.publish`` and dispatches the configured driver from
``lathe.publish.PUBLISH_DRIVERS``. Behaves as a no-op when no target is
configured, keeping the default build loop ergonomic.

Stage contract:

    run(executor, package_bundle) -> dict

Returned bundle is serialized to ``stages/publish/bundle.json``.
"""

from __future__ import annotations

import logging
from typing import Any

from ...logging_utils import info as log_info
from ...publish import get_driver
from ..common import dump_json, relpath

_LOG = logging.getLogger(__name__)


def run(executor: Any, package_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run the publish stage.

    Args:
        executor: Host ``BuildExecutor``.
        package_bundle: The ``package`` stage bundle (unused but kept for
            stage-body convention symmetry — downstream tests may inspect the
            link between package outputs and publish targets here).

    Returns:
        Bundle dict. ``published`` is False when no target is configured.
    """
    stage_dir = executor.stage_dirs.get("publish")
    if stage_dir is None:
        stage_dir = executor.out_dir / "stages" / "publish"
        stage_dir.mkdir(parents=True, exist_ok=True)

    runtime_config = getattr(executor, "runtime_config", {}) or {}
    publish_cfg = runtime_config.get("publish") if isinstance(runtime_config, dict) else None
    target = None
    if isinstance(publish_cfg, dict):
        target = publish_cfg.get("target")

    bundle: dict[str, Any]
    if not target:
        log_info(
            _LOG,
            "lathe.core.stages.publish.skipped",
            "publish stage: no runtime_config.publish.target configured; skipping",
        )
        bundle = {
            "published": False,
            "driver": None,
            "manifest_uri": None,
            "signature_uri": None,
            "reason": "no_publish_target_configured",
        }
    else:
        try:
            driver = get_driver(str(target))
        except ValueError as exc:
            bundle = {
                "published": False,
                "driver": str(target),
                "manifest_uri": None,
                "signature_uri": None,
                "error": str(exc),
            }
        else:
            target_config = dict(publish_cfg)  # shallow copy
            result = driver.publish(executor.out_dir, target_config)
            bundle = {
                "published": True,
                "driver": result.get("driver", str(target)),
                "manifest_uri": result.get("manifest_uri"),
                "signature_uri": result.get("signature_uri"),
                "published_files": result.get("published_files", []),
                "manifest_path": relpath(executor.out_dir, stage_dir / "manifest.json"),
            }
            if result.get("manifest"):
                dump_json(stage_dir / "manifest.json", result["manifest"])

    dump_json(stage_dir / "bundle.json", bundle)
    if hasattr(executor, "runtime"):
        executor.runtime["publish"] = {"bundle": bundle}
    return bundle
