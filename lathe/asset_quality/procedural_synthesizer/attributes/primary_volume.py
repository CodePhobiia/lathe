"""Typed attribute schema for node_type='primary_volume'.

A primary_volume is the dominant mass of an asset — its silhouette
anchor. Examples: the body of a crate, the body of a console terminal,
the trunk of a tree, the chassis of a vehicle. The schema describes
its shape, dimensions, symmetry, rounding, and scale intent.

Validated in Stage 4 of the procedural synthesizer pipeline before
the primary_volume generator consumes it. Schema violations emit
attribute_schema_violation trace entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_VALID_SHAPES: frozenset[str] = frozenset(
    {
        "box",
        "rounded_box",
        "cylinder",
        "sphere",
        "extruded_profile",
        "revolved_profile",
    }
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_SCALE_INTENTS: frozenset[str] = frozenset(
    {"small_prop", "human_scale", "structure"}
)

_VALID_EDGE_TREATMENTS: frozenset[str] = frozenset(
    {"sharp", "beveled", "chamfered"}
)


@dataclass(frozen=True)
class PrimaryVolumeAttributes:
    """Typed attribute contract for node_type='primary_volume'.

    Construction-graph ConstructionNode.attributes is validated against
    this schema. A node missing a required field, or carrying a value
    outside the enumerated set, fails validation.

    Fields:
        shape: which kernel primitive backs this volume. Must be in
            ``_VALID_SHAPES``.
        dimensions_cm: axis -> length-in-cm map. For "box" and
            "rounded_box", keys ``"x"``, ``"y"``, ``"z"`` are required.
            For "cylinder", ``"radius"`` and ``"height"`` are required.
            For "sphere", ``"radius"``. For profiles, schema-specific
            keys (consulted by the generator).
        symmetry: tuple of axes the volume is symmetric across. Empty
            means no symmetry. Each entry must be in ``_VALID_AXES``.
        rounding_cm: optional corner rounding in cm. Zero or absent
            means sharp corners. Only meaningful for "rounded_box";
            ignored by other shapes.
        scale_intent: hints downstream stages about appropriate
            material defaults and topology resolution. Must be in
            ``_VALID_SCALE_INTENTS``.
        edge_treatment: how the volume's edges are finished after the
            primary solid is emitted. Must be in
            ``_VALID_EDGE_TREATMENTS``:
              - "sharp": no edge op emitted; raw primitive edges
              - "beveled": an ``op.bevel`` op follows the primary solid
              - "chamfered": an ``op.chamfer`` op follows the primary solid
            Per Sprint 0 S0-3 (the visible-geometry detail-op work),
            beveled/chamfered is the default-on path for any hard-surface
            asset to escape the "looks like procedural blockout" failure
            mode. Style packs can declare a default via
            ``parameter_priors.primary_volume.edge_treatment``; per-node
            ``edge_treatment`` overrides the style default.
        edge_treatment_width_cm: width of the bevel/chamfer in cm
            (positive when edge_treatment != "sharp"). Style packs can
            declare a default via
            ``parameter_priors.primary_volume.edge_treatment_width_cm``.
        edge_treatment_segments: segment count for beveled rounding
            (>= 1; ignored for chamfered which is always 1 segment).
    """

    shape: str
    dimensions_cm: dict[str, float]
    symmetry: tuple[str, ...] = ()
    rounding_cm: float = 0.0
    scale_intent: str = "human_scale"
    edge_treatment: str = "sharp"
    edge_treatment_width_cm: float = 0.0
    edge_treatment_segments: int = 2

    def __post_init__(self) -> None:
        if self.shape not in _VALID_SHAPES:
            raise ValueError(
                f"primary_volume.shape={self.shape!r} not in "
                f"{sorted(_VALID_SHAPES)}"
            )
        if not isinstance(self.dimensions_cm, dict):
            raise TypeError(
                f"primary_volume.dimensions_cm must be dict, got "
                f"{type(self.dimensions_cm).__name__}"
            )
        for axis_or_key, value in self.dimensions_cm.items():
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"primary_volume.dimensions_cm[{axis_or_key!r}] must be "
                    f"numeric, got {type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(
                    f"primary_volume.dimensions_cm[{axis_or_key!r}]={value} "
                    f"must be positive"
                )
        for axis in self.symmetry:
            if axis not in _VALID_AXES:
                raise ValueError(
                    f"primary_volume.symmetry axis {axis!r} not in "
                    f"{sorted(_VALID_AXES)}"
                )
        if self.rounding_cm < 0:
            raise ValueError(
                f"primary_volume.rounding_cm={self.rounding_cm} must be >= 0"
            )
        if self.scale_intent not in _VALID_SCALE_INTENTS:
            raise ValueError(
                f"primary_volume.scale_intent={self.scale_intent!r} not in "
                f"{sorted(_VALID_SCALE_INTENTS)}"
            )
        if self.edge_treatment not in _VALID_EDGE_TREATMENTS:
            raise ValueError(
                f"primary_volume.edge_treatment={self.edge_treatment!r} not in "
                f"{sorted(_VALID_EDGE_TREATMENTS)}"
            )
        if self.edge_treatment != "sharp" and (
            not isinstance(self.edge_treatment_width_cm, (int, float))
            or float(self.edge_treatment_width_cm) <= 0
        ):
            raise ValueError(
                f"primary_volume.edge_treatment={self.edge_treatment!r} requires "
                f"edge_treatment_width_cm > 0; got "
                f"{self.edge_treatment_width_cm}"
            )
        if not isinstance(self.edge_treatment_segments, int) or self.edge_treatment_segments < 1:
            raise ValueError(
                f"primary_volume.edge_treatment_segments={self.edge_treatment_segments} "
                f"must be int >= 1"
            )

        # Per-shape dimension requirements
        if self.shape in {"box", "rounded_box"}:
            for axis in ("x", "y", "z"):
                if axis not in self.dimensions_cm:
                    raise ValueError(
                        f"primary_volume.dimensions_cm missing required "
                        f"axis {axis!r} for shape {self.shape!r}"
                    )
        elif self.shape == "cylinder":
            for key in ("radius", "height"):
                if key not in self.dimensions_cm:
                    raise ValueError(
                        f"primary_volume.dimensions_cm missing required "
                        f"key {key!r} for shape 'cylinder'"
                    )
        elif self.shape == "sphere" and "radius" not in self.dimensions_cm:
            raise ValueError(
                "primary_volume.dimensions_cm missing required "
                "key 'radius' for shape 'sphere'"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> PrimaryVolumeAttributes:
        """Validate a raw attribute dict and produce a typed instance.

        Raises ValueError / TypeError on validation failure. The caller
        (Stage 4 of the pipeline) captures the exception and emits an
        ``attribute_schema_violation`` trace entry instead of crashing.
        """
        if not isinstance(attrs, dict):
            raise TypeError(
                f"primary_volume attributes must be dict, got "
                f"{type(attrs).__name__}"
            )
        return cls(
            shape=str(attrs["shape"]) if "shape" in attrs else "box",
            dimensions_cm=dict(attrs.get("dimensions_cm") or {}),
            symmetry=tuple(attrs.get("symmetry") or ()),
            rounding_cm=float(attrs.get("rounding_cm") or 0.0),
            scale_intent=str(attrs.get("scale_intent") or "human_scale"),
            edge_treatment=str(attrs.get("edge_treatment") or "sharp"),
            edge_treatment_width_cm=float(attrs.get("edge_treatment_width_cm") or 0.0),
            edge_treatment_segments=int(attrs.get("edge_treatment_segments") or 2),
        )
