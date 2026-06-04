"""Reproducibility manifest (research §14).

Carries the inputs needed to deterministically reproduce a build:
lathe version, shape contract, knowledge pack versions, world/asset
seeds, IR hashes, provider proposal records.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReproducibilityManifest:
    """Build-level reproducibility record."""

    lathe_version: str
    shape_contract: str
    knowledge_pack_versions: Mapping[str, str] = field(default_factory=dict)
    world_seed: int = 0
    asset_seed: int = 0
    shape_graph_hash: str = ""
    compiled_ir_hash: str = ""
    provider_proposals: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "lathe_version": self.lathe_version,
            "shape_contract": self.shape_contract,
            "knowledge_pack_versions": dict(self.knowledge_pack_versions),
            "world_seed": self.world_seed,
            "asset_seed": self.asset_seed,
            "shape_graph_hash": self.shape_graph_hash,
            "compiled_ir_hash": self.compiled_ir_hash,
            "provider_proposals": [dict(p) for p in self.provider_proposals],
        }


def manifest_from_build_state(
    lathe_version: str,
    shape_contract: str,
    knowledge_pack_versions: Mapping[str, str],
    world_seed: int,
    asset_seed: int,
    shape_program_blob: Any | None = None,
    compiled_ir_blob: Any | None = None,
    provider_proposals: tuple[Mapping[str, Any], ...] = (),
) -> ReproducibilityManifest:
    """Construct a ReproducibilityManifest, hashing IRs to stable strings."""
    return ReproducibilityManifest(
        lathe_version=lathe_version,
        shape_contract=shape_contract,
        knowledge_pack_versions=dict(knowledge_pack_versions),
        world_seed=world_seed,
        asset_seed=asset_seed,
        shape_graph_hash=_hash_payload(shape_program_blob),
        compiled_ir_hash=_hash_payload(compiled_ir_blob),
        provider_proposals=provider_proposals,
    )


def _hash_payload(payload: Any | None) -> str:
    if payload is None:
        return ""
    try:
        text = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        text = repr(payload)
    h = hashlib.sha256(text.encode("utf-8"))
    return h.hexdigest()


__all__ = ["ReproducibilityManifest", "manifest_from_build_state"]
