"""Kit IR: V1.1 ``kit`` block, extended with HDA-class fields (§6.5).

Represents a reusable set of components and policies that an asset
can compose via ``reuse`` or ``assembly_rules``.

Phase 2 §6.5 grows this toward Houdini-HDA semantics by adding:

- ``version``: semver-style version pin for the kit.
- ``ports``: typed input/output port declarations.
- ``parameters``: parameter UI specs (range/default/step/ui hint).
- ``body_kit_uses``: composability — a kit can depend on other versioned kits.
- ``resolved_kit_use``: how the asset bound this kit (constraint + bindings).

Legacy kit blocks (V1.1 loose key/value mappings) are still supported.
``hda`` is True only when the kit declared at least one HDA field.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class KitIR:
    """KitIR."""

    kit_name: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    assembly_policy: dict[str, Any] = field(default_factory=dict)
    version: str = ""
    ports: list[dict[str, Any]] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    body_kit_uses: list[dict[str, Any]] = field(default_factory=list)
    body_values: dict[str, Any] = field(default_factory=dict)
    resolved_kit_use: dict[str, Any] = field(default_factory=dict)
    hda: bool = False

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> KitIR:
        """From asset.

        Args:
            asset: asset argument.

        Returns:
            The result.
        """
        assembly = asset.get("assembly", {})
        constraints = asset.get("constraints", {})
        resolved_kit = assembly.get("resolved_kit", {}) or {}
        body = resolved_kit.get("body", {}) or {}
        ports = list(resolved_kit.get("ports", []) or [])
        parameters = list(resolved_kit.get("parameters", []) or [])
        version = str(resolved_kit.get("version", "") or "")
        is_hda = bool(version or ports or parameters or body)
        return cls(
            kit_name=str(assembly.get("kit", "")),
            values=dict(resolved_kit.get("values", {})),
            assembly_policy=dict(constraints.get("resolved_assembly_policy", {})),
            version=version,
            ports=ports,
            parameters=parameters,
            body_kit_uses=list(body.get("kit_uses", []) or []),
            body_values=dict(body.get("values", {}) or {}),
            resolved_kit_use=dict(assembly.get("resolved_kit_use", {}) or {}),
            hda=is_hda,
        )

    def required_input_ports(self) -> list[dict[str, Any]]:
        """Return port declarations marked direction='in'."""
        return [p for p in self.ports if p.get("direction") == "in"]

    def output_ports(self) -> list[dict[str, Any]]:
        """Return port declarations marked direction='out'."""
        return [p for p in self.ports if p.get("direction") == "out"]

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
