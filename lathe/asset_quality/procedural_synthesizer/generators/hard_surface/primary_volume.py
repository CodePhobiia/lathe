"""Generator for node_type='primary_volume' in the hard_surface domain.

Translates a typed PrimaryVolumeAttributes into the corresponding
ShapeIR v2 solid op. No family-name awareness; all parameter biasing
flows through StyleKnowledge.
"""

from __future__ import annotations

from collections.abc import Iterable

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
        "edge_treatment",
        "edge_treatment_width_cm",
        "edge_treatment_segments",
    ),
    consumed_style_fields=("parameter_priors", "proportion_priors"),
    emitted_op_kinds=(
        "solid.box",
        "solid.rounded_box",
        "solid.cylinder",
        "solid.sphere",
        "solid.extruded_profile",
        "solid.revolved_profile",
        "op.bevel",
        "op.chamfer",
    ),
    required_kernel_capabilities=("solid.box", "solid.rounded_box"),
    fallback_diagnostics=(
        "primary_volume_unsupported_shape",
        "primary_volume_dimension_default_used",
        "primary_volume_edge_treatment_default_used",
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


def _style_string(ctx: SynthesizerContext, field: str) -> str | None:
    """Return style.parameter_priors[primary_volume][field] as str or None."""
    if ctx.style is None:
        return None
    priors = ctx.style.parameter_priors.get("primary_volume") or {}
    value = priors.get(field)
    if isinstance(value, str) and value:
        return value
    return None


def _resolve_rounding(attrs: PrimaryVolumeAttributes, ctx: SynthesizerContext) -> float:
    """Typed attribute wins; else style; else 0.0."""
    if attrs.rounding_cm > 0:
        return float(attrs.rounding_cm)
    style_value = _style_parameter(ctx, "rounding_cm")
    if style_value is not None and style_value >= 0:
        return float(style_value)
    return 0.0


def _resolve_edge_treatment(
    attrs: PrimaryVolumeAttributes, ctx: SynthesizerContext
) -> tuple[str, float, int]:
    """Resolve (edge_treatment, width_cm, segments) — attrs win, else style.

    Returns ``("sharp", 0.0, 0)`` when no edge treatment is requested
    or the requested width is non-positive. Otherwise returns the
    resolved (treatment, width, segments) triple.
    """
    treatment = attrs.edge_treatment
    width = float(attrs.edge_treatment_width_cm or 0.0)
    segments = int(attrs.edge_treatment_segments or 2)

    if treatment == "sharp":
        # Attribute didn't request a treatment — consult style for a default.
        style_treatment = _style_string(ctx, "edge_treatment")
        if style_treatment in ("beveled", "chamfered"):
            treatment = style_treatment
            style_width = _style_parameter(ctx, "edge_treatment_width_cm")
            if style_width is not None and style_width > 0:
                width = float(style_width)
            style_segments = _style_parameter(ctx, "edge_treatment_segments")
            if style_segments is not None and style_segments >= 1:
                segments = int(style_segments)

    if treatment in ("beveled", "chamfered") and width > 0:
        return treatment, width, max(1, segments)
    return "sharp", 0.0, 0


def _emit_edge_treatment(
    target: str,
    treatment: str,
    width: float,
    segments: int,
    purpose_prefix: str,
) -> ShapeOp | None:
    """Build the op.bevel / op.chamfer follow-up op for a primary volume.

    Returns None when no edge treatment is requested. Otherwise emits
    an ``op.bevel`` (rounded edge, ``segments`` interpolated) or
    ``op.chamfer`` (single 45° face) keyed to the primary volume's
    target so the kernel applies the treatment to its edges.
    """
    if treatment == "sharp" or width <= 0:
        return None
    if treatment == "beveled":
        return ShapeOp(
            op="op.bevel",
            target=target,
            parameters={
                "width_cm": float(width),
                "segments": int(max(1, segments)),
            },
            purpose=f"{purpose_prefix}.edge_treatment.beveled",
        )
    if treatment == "chamfered":
        return ShapeOp(
            op="op.chamfer",
            target=target,
            parameters={
                "width_cm": float(width),
            },
            purpose=f"{purpose_prefix}.edge_treatment.chamfered",
        )
    return None


def _impl(
    node: ConstructionNodeTyped, ctx: SynthesizerContext
) -> Iterable[ShapeOp]:
    attrs: PrimaryVolumeAttributes = node.typed_attributes
    purpose = f"procedural_primary_volume.{attrs.scale_intent}"
    edge_treatment, edge_width, edge_segments = _resolve_edge_treatment(attrs, ctx)

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
    elif attrs.shape == "rounded_box":
        rounding = _resolve_rounding(attrs, ctx)
        yield ShapeOp(
            op="solid.rounded_box",
            target=node.node_id,
            parameters={
                "width_cm": float(attrs.dimensions_cm["x"]),
                "height_cm": float(attrs.dimensions_cm["y"]),
                "depth_cm": float(attrs.dimensions_cm["z"]),
                # Kernel expects ``radius_cm`` for solid.rounded_box's
                # corner radius. The aliases the kernel recognizes are
                # ``radius`` / ``corner_radius_cm`` / ``corner_radius``;
                # NOT ``rounding_cm`` (despite the attribute's own
                # name, which matches the typed-attribute schema's
                # ``PrimaryVolumeAttributes.rounding_cm`` field). Diagnosed
                # 2026-05-12 as the silent body-drop bug — without this
                # rename, every synthesizer-driven build loses its
                # primary_volume primitive in the v1 lowering.
                "radius_cm": rounding,
            },
            purpose=purpose,
        )
    elif attrs.shape == "cylinder":
        yield ShapeOp(
            op="solid.cylinder",
            target=node.node_id,
            parameters={
                "radius_cm": float(attrs.dimensions_cm["radius"]),
                "height_cm": float(attrs.dimensions_cm["height"]),
            },
            purpose=purpose,
        )
    elif attrs.shape == "sphere":
        yield ShapeOp(
            op="solid.sphere",
            target=node.node_id,
            parameters={
                "radius_cm": float(attrs.dimensions_cm["radius"]),
            },
            purpose=purpose,
        )
    elif attrs.shape in ("extruded_profile", "revolved_profile"):
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
    else:
        return

    # Sprint 0 S0-3: emit the post-primitive edge-treatment op so
    # the kernel applies visible bevels / chamfers. Sphere is skipped
    # since it has no straight edges; everything else gets the option.
    if attrs.shape != "sphere":
        edge_op = _emit_edge_treatment(
            node.node_id, edge_treatment, edge_width, edge_segments, purpose
        )
        if edge_op is not None:
            yield edge_op


GENERATOR = NodeTypeGenerator(manifest=_MANIFEST, implementation=_impl)
