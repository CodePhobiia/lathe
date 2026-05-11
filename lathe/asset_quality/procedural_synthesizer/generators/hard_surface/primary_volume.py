"""Generator for node_type='primary_volume' in the hard_surface domain.

Translates a typed PrimaryVolumeAttributes into the corresponding
ShapeIR v2 solid op. No family-name awareness; all parameter biasing
flows through StyleKnowledge.
"""

from __future__ import annotations

from typing import Iterable

from ....shape_ir_v2 import ShapeOp
from ...attributes.primary_volume import PrimaryVolumeAttributes
from ...context import ConstructionNodeTyped, SynthesizerContext
from ...registry import GeneratorCapabilityManifest, NodeTypeGenerator


_MANIFEST = GeneratorCapabilityManifest(
    node_type="primary_volume",
    domain="hard_surface",
    consumed_attribute_fields=(
        "shape",
        "dimensions_cm",
        "symmetry",
        "rounding_cm",
        "scale_intent",
    ),
    consumed_style_fields=("parameter_priors", "proportion_priors"),
    emitted_op_kinds=(
        "solid.box",
        "solid.rounded_box",
        "solid.cylinder",
        "solid.sphere",
        "solid.extruded_profile",
        "solid.revolved_profile",
    ),
    required_kernel_capabilities=("solid.box", "solid.rounded_box"),
    fallback_diagnostics=(
        "primary_volume_unsupported_shape",
        "primary_volume_dimension_default_used",
    ),
    output_kind="visible_geometry",
)


def _style_parameter(ctx: SynthesizerContext, field: str) -> float | None:
    """Return style.parameter_priors[primary_volume][field] or None."""
    if ctx.style is None:
        return None
    priors = ctx.style.parameter_priors.get("primary_volume") or {}
    value = priors.get(field)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _resolve_rounding(attrs: PrimaryVolumeAttributes, ctx: SynthesizerContext) -> float:
    """Typed attribute wins; else style; else 0.0."""
    if attrs.rounding_cm > 0:
        return float(attrs.rounding_cm)
    style_value = _style_parameter(ctx, "rounding_cm")
    if style_value is not None and style_value >= 0:
        return float(style_value)
    return 0.0


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: PrimaryVolumeAttributes = node.typed_attributes
    purpose = f"procedural_primary_volume.{attrs.scale_intent}"

    if attrs.shape == "box":
        yield ShapeOp(
            op="solid.box",
            target=node.node_id,
            parameters={
                "width_cm": float(attrs.dimensions_cm["x"]),
                "height_cm": float(attrs.dimensions_cm["y"]),
                "depth_cm": float(attrs.dimensions_cm["z"]),
            },
            purpose=purpose,
        )
        return

    if attrs.shape == "rounded_box":
        rounding = _resolve_rounding(attrs, ctx)
        yield ShapeOp(
            op="solid.rounded_box",
            target=node.node_id,
            parameters={
                "width_cm": float(attrs.dimensions_cm["x"]),
                "height_cm": float(attrs.dimensions_cm["y"]),
                "depth_cm": float(attrs.dimensions_cm["z"]),
                "rounding_cm": rounding,
            },
            purpose=purpose,
        )
        return

    if attrs.shape == "cylinder":
        yield ShapeOp(
            op="solid.cylinder",
            target=node.node_id,
            parameters={
                "radius_cm": float(attrs.dimensions_cm["radius"]),
                "height_cm": float(attrs.dimensions_cm["height"]),
            },
            purpose=purpose,
        )
        return

    if attrs.shape == "sphere":
        yield ShapeOp(
            op="solid.sphere",
            target=node.node_id,
            parameters={
                "radius_cm": float(attrs.dimensions_cm["radius"]),
            },
            purpose=purpose,
        )
        return

    if attrs.shape in ("extruded_profile", "revolved_profile"):
        # Profile shapes pass dimension keys through to the kernel.
        # The kernel rejects unknown / missing keys with a clear error.
        params = {
            f"{k}_cm" if not k.endswith("_cm") else k: float(v)
            for k, v in attrs.dimensions_cm.items()
        }
        yield ShapeOp(
            op=f"solid.{attrs.shape}",
            target=node.node_id,
            parameters=params,
            purpose=purpose,
        )
        return


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
