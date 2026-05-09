"""Layer-stack mode (V0.1 §6.1 mode 3).

Substance-Painter-class authoring: composite typed Smart Materials
with mesh-aware mask expressions. Each layer is

    (base_material, mask_expression, blend_mode)

Layers stack bottom-up; mask_expression uses the attribute mini-language
(``@P``, ``@N``, ``@curvature``, ``@ao``, ``@position``) which is shared
with the §6.4 attribute mini-language.
"""

from __future__ import annotations

from typing import Any


_VALID_BLEND_MODES = {"normal", "add", "multiply", "overlay", "screen", "subtract"}


class LayerStack:
    """Typed layer-stack IR.

    The stack is JSON-serializable and lowered to MaterialX. Materials
    are looked up by name in the program ``material_map`` at compile
    time so unknown materials surface as fallbacks rather than silent
    drops.
    """

    def __init__(self, layers: list[dict[str, Any]]) -> None:
        self.layers = list(layers)

    @classmethod
    def from_values(cls, values: dict[str, Any]) -> "LayerStack":
        raw_layers = values.get("layers") or values.get("stack") or []
        layers: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_layers):
            if isinstance(raw, dict):
                layer = {
                    "name": str(raw.get("name", f"layer_{index}")),
                    "material": str(raw.get("material") or raw.get("base_material") or ""),
                    "mask_expression": str(raw.get("mask_expression") or raw.get("mask") or "@curvature"),
                    "blend_mode": str(raw.get("blend_mode") or raw.get("blend") or "normal").lower(),
                    "opacity": float(raw.get("opacity", 1.0)),
                }
            else:
                # Loose form: "material:expression"
                text = str(raw).strip()
                material = ""
                expression = "@curvature"
                if ":" in text:
                    material, expression = text.split(":", 1)
                else:
                    material = text
                layer = {
                    "name": f"layer_{index}",
                    "material": material.strip(),
                    "mask_expression": expression.strip(),
                    "blend_mode": "normal",
                    "opacity": 1.0,
                }
            if layer["blend_mode"] not in _VALID_BLEND_MODES:
                layer["blend_mode"] = "normal"
            layers.append(layer)
        return cls(layers=layers)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "layer_stack", "layers": list(self.layers)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LayerStack":
        return cls(layers=list(payload.get("layers", [])))


def compile_layer_stack(values: dict[str, Any], *, asset_name: str = "asset") -> dict[str, Any]:
    """Compile a layer_stack surface_program block into a portable IR."""
    from .materialx import compile_materialx

    stack = LayerStack.from_values(values)
    layer_summaries = [
        {
            "name": layer["name"],
            "material": layer["material"],
            "mask_expression": layer["mask_expression"],
            "blend_mode": layer["blend_mode"],
            "opacity": layer["opacity"],
        }
        for layer in stack.layers
    ]
    materialx_doc = compile_materialx(
        mode="layer_stack",
        outputs={
            "basecolor": "layer_stack_basecolor",
            "normal": "layer_stack_normal",
            "ao": "layer_stack_ao",
        },
        params={**values, "layer_summaries": layer_summaries},
        asset_name=asset_name,
    )
    return {
        "mode": "layer_stack",
        "graph_ir": stack.to_dict(),
        "layers": layer_summaries,
        "outputs": {
            "basecolor": "layer_stack_basecolor",
            "normal": "layer_stack_normal",
            "ao": "layer_stack_ao",
        },
        "channels": {
            "basecolor": {"source": "layer_stack_basecolor", "kind": "color3"},
            "normal": {"source": "layer_stack_normal", "kind": "vector3"},
            "ao": {"source": "layer_stack_ao", "kind": "float"},
        },
        "materialx_doc": materialx_doc,
        "trace": {
            "kind": "layer_stack_v1",
            "layer_count": len(stack.layers),
            "blend_modes": sorted({layer["blend_mode"] for layer in stack.layers}),
            "mask_expressions_use_attributes": [
                token for layer in stack.layers
                for token in ("@P", "@N", "@curvature", "@ao", "@position")
                if token in layer["mask_expression"]
            ],
            "deterministic": True,
        },
    }
