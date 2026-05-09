"""Designer-graph mode (V0.1 §6.1 mode 1).

Substance-Designer-class authoring: 7-stage canonical recipe assembled
into a typed node DAG. The recipe is procedural and deterministic --
authors override seeds/frequencies/colours via the surface_program
``designer_graph { ... }`` body.

Recipe stages:
  1. Base pattern (stack of multi-octave noises).
  2. Pattern + geometry (bricks/tiles/weave + ShapeSplatter + Warp).
  3. Height & normal.
  4. Curvature-driven channels (edge_wear, cavity_dirt, roughness var).
  5. AO + position-based effects (streaks/bands).
  6. Color composition (layer stack gated by curvature + AO + position).
  7. Output: {basecolor, normal, metallic, roughness, height, ao,
     emissive, opacity} + packed ORM.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .nodes import (
    AO,
    Blend,
    ConstColor,
    CurvatureSmooth,
    EdgeDetect,
    GradientMap,
    HistogramScan,
    Layer,
    Levels,
    Mask,
    Noise,
    Normal,
    Output,
    Pattern,
    PositionMask,
    ShapeSplatter,
    SlopeBlur,
    SurfaceNode,
    Warp,
    node_from_dict,
)


class DesignerGraph:
    """Typed designer-graph IR + reference evaluator."""

    def __init__(self, nodes: list[SurfaceNode], outputs: dict[str, str]) -> None:
        self.nodes = nodes
        self.outputs = dict(outputs)

    @classmethod
    def from_recipe(cls, params: dict[str, Any]) -> "DesignerGraph":
        seed = int(params.get("seed", 1337))
        base_palette = params.get("palette", [(190, 190, 190), (88, 88, 88), (32, 32, 32)])
        nodes: list[SurfaceNode] = []
        # Stage 1: base pattern stack of noises.
        nodes.append(Noise(name="noise_base", params={"flavour": "perlin", "octaves": 4, "frequency": 6.0, "seed": seed}))
        nodes.append(Noise(name="noise_meso", params={"flavour": "fractal", "octaves": 3, "frequency": 12.0, "seed": seed + 11}))
        nodes.append(Noise(name="noise_micro", params={"flavour": "worley", "octaves": 1, "frequency": 24.0, "seed": seed + 23}))
        nodes.append(Blend(name="noise_stack_1", inputs={"a": "noise_base", "b": "noise_meso"}, params={"mode": "add"}))
        nodes.append(Blend(name="noise_stack", inputs={"a": "noise_stack_1", "b": "noise_micro"}, params={"mode": "overlay"}))
        # Stage 2: pattern + geometry + warp.
        pattern_kind = str(params.get("pattern", "brick")).lower()
        nodes.append(Pattern(
            name="pattern",
            params={"flavour": pattern_kind, "cols": int(params.get("cols", 8)),
                    "rows": int(params.get("rows", 4)), "mortar": float(params.get("mortar", 0.05))},
        ))
        nodes.append(ShapeSplatter(
            name="splatter",
            params={"count": int(params.get("rivets", 64)), "radius_px": float(params.get("rivet_radius_px", 4.0)),
                    "shape": str(params.get("rivet_shape", "disc")), "seed": seed + 47},
        ))
        nodes.append(Blend(name="pattern_with_rivets", inputs={"a": "pattern", "b": "splatter"}, params={"mode": "screen"}))
        nodes.append(Warp(
            name="pattern_warped",
            inputs={"source": "pattern_with_rivets"},
            params={"amplitude": float(params.get("warp_amount", 0.04)), "frequency": 3.0, "seed": seed + 53},
        ))
        nodes.append(EdgeDetect(
            name="pattern_edges",
            inputs={"source": "pattern_warped"},
            params={
                "radius": int(params.get("edge_detect_radius", 1)),
                "strength": float(params.get("edge_detect_strength", 1.35)),
            },
        ))
        nodes.append(Blend(name="height_raw", inputs={"a": "noise_stack", "b": "pattern_warped"}, params={"mode": "add"}))
        nodes.append(SlopeBlur(
            name="height_slope_blur",
            inputs={"source": "height_raw", "slope": "pattern_edges"},
            params={
                "samples": int(params.get("slope_blur_samples", 5)),
                "strength_px": float(params.get("slope_blur_strength_px", 1.5)),
                "mode": str(params.get("slope_blur_mode", "blur")),
            },
        ))
        nodes.append(Levels(
            name="height",
            inputs={"source": "height_slope_blur"},
            params={
                "low": float(params.get("height_level_low", 0.03)),
                "high": float(params.get("height_level_high", 0.97)),
                "gamma": float(params.get("height_level_gamma", 1.0)),
            },
        ))
        # Stage 3: normal from height.
        nodes.append(Normal(name="normal", inputs={"height": "height"}, params={"strength": float(params.get("normal_strength", 1.0))}))
        # Stage 4: curvature-driven masks.
        nodes.append(CurvatureSmooth(name="curvature", inputs={"normal": "normal"}, params={"radius": 3}))
        # Stage 5: AO + position bands.
        nodes.append(AO(name="ao", inputs={"height": "height"}, params={"radius": 4}))
        nodes.append(HistogramScan(
            name="mask_edge_scan",
            inputs={"source": "curvature"},
            params={
                "threshold": float(params.get("edge_scan_threshold", 0.56)),
                "softness": float(params.get("edge_scan_softness", 0.18)),
                "contrast": float(params.get("edge_scan_contrast", 1.15)),
            },
        ))
        nodes.append(Mask(
            name="mask_edge_wear_raw",
            inputs={"curvature": "curvature", "ao": "ao"},
            params={"preset": "edge_wear", "ao_gate": True},
        ))
        nodes.append(Blend(
            name="mask_edge_wear",
            inputs={"a": "mask_edge_wear_raw", "b": "mask_edge_scan"},
            params={"mode": "multiply"},
        ))
        nodes.append(Mask(name="mask_cavity", inputs={"curvature": "curvature"}, params={"preset": "cavity"}))
        nodes.append(Mask(name="mask_top", inputs={"normal": "normal"}, params={"preset": "top_dirt"}))
        nodes.append(PositionMask(
            name="mask_position_top",
            params={
                "axis": "y",
                "min": float(params.get("position_top_min", 0.58)),
                "max": 1.0,
                "softness": float(params.get("position_top_softness", 0.18)),
            },
        ))
        # Stage 6: color composition (layer stack of palette swatches gated by masks).
        # Bake each palette colour as a constant-coloured noise overlay.
        for index, rgb in enumerate(base_palette[:3]):
            nodes.append(_constant_color_node(f"color_layer_{index}", rgb))
        nodes.append(GradientMap(
            name="height_color_grade",
            inputs={"source": "height"},
            params={
                "stops": [
                    [0.0, base_palette[0] if base_palette else [190, 190, 190]],
                    [0.55, base_palette[1] if len(base_palette) > 1 else [88, 88, 88]],
                    [1.0, base_palette[2] if len(base_palette) > 2 else [32, 32, 32]],
                ]
            },
        ))
        nodes.append(Layer(name="comp_base", inputs={"base": "color_layer_0", "layer": "color_layer_1", "mask": "mask_cavity"}))
        nodes.append(Layer(name="comp_with_wear", inputs={"base": "comp_base", "layer": "color_layer_2", "mask": "mask_edge_wear"}))
        nodes.append(Layer(
            name="comp_height_position_grade",
            inputs={"base": "comp_with_wear", "layer": "height_color_grade", "mask": "mask_position_top"},
        ))
        # Stage 7: outputs.
        nodes.append(Output(name="out_basecolor", inputs={"source": "comp_height_position_grade"}))
        nodes.append(Output(name="out_normal", inputs={"source": "normal"}))
        nodes.append(Output(name="out_height", inputs={"source": "height"}))
        nodes.append(Output(name="out_ao", inputs={"source": "ao"}))
        nodes.append(Output(name="out_curvature", inputs={"source": "curvature"}))
        outputs = {
            "basecolor": "out_basecolor",
            "normal": "out_normal",
            "height": "out_height",
            "ao": "out_ao",
            "curvature": "out_curvature",
        }
        return cls(nodes=nodes, outputs=outputs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "designer_graph",
            "nodes": [node.to_dict() for node in self.nodes],
            "outputs": dict(self.outputs),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DesignerGraph":
        nodes = [node_from_dict(item) for item in payload.get("nodes", [])]
        outputs = dict(payload.get("outputs", {}))
        return cls(nodes=nodes, outputs=outputs)

    def evaluate(self, size: int = 512, attributes: dict[str, Any] | None = None) -> dict[str, np.ndarray]:
        """Evaluate the DAG and return numpy buffers per output channel."""
        ctx: dict[str, Any] = {
            "size": size,
            "buffers": {},
            "attributes": dict(attributes or {}),
        }
        for node in self.nodes:
            ctx["buffers"][node.name] = node.eval(ctx)
        return {channel: ctx["buffers"][bound] for channel, bound in self.outputs.items() if bound in ctx["buffers"]}


def _constant_color_node(name: str, rgb: Any) -> SurfaceNode:
    """A 'colour' node is a Noise of zero amplitude shifted by the rgb literal.

    We emit it as a Blend(add) of a zero-noise with itself plus a Pattern set
    to 1.0; downstream Layer eval handles 2D->3D broadcast. For simplicity
    we encode the literal in a Pattern node and post-multiply in Blend.
    """

    r, g, b = (float(rgb[0]) / 255.0, float(rgb[1]) / 255.0, float(rgb[2]) / 255.0)

    return ConstColor(name=name, params={"rgb": [r, g, b]})


def compile_designer_graph(values: dict[str, Any], *, asset_name: str = "asset") -> dict[str, Any]:
    """Compile a designer_graph surface_program block into a portable IR.

    Returns a dict containing the typed node graph IR, the output channel
    bindings, a deterministic trace, and a MaterialX 1.39 document
    (built lazily by the materialx compiler).
    """
    from .materialx import compile_materialx

    graph = DesignerGraph.from_recipe(values)
    materialx_doc = compile_materialx(
        mode="designer_graph",
        outputs=graph.outputs,
        params=values,
        asset_name=asset_name,
    )
    return {
        "mode": "designer_graph",
        "graph_ir": graph.to_dict(),
        "outputs": dict(graph.outputs),
        "channels": {
            "basecolor": {"source": "comp_height_position_grade", "kind": "color3"},
            "normal": {"source": "normal", "kind": "vector3"},
            "height": {"source": "height", "kind": "float"},
            "ao": {"source": "ao", "kind": "float"},
            "curvature": {"source": "curvature", "kind": "float"},
            "metallic": {"source": "constant", "kind": "float", "value": float(values.get("metallic", 0.0))},
            "roughness": {"source": "derived_from_curvature", "kind": "float"},
            "emissive": {"source": "constant", "kind": "color3", "value": list(values.get("emissive", [0, 0, 0]))},
            "opacity": {"source": "constant", "kind": "float", "value": float(values.get("opacity", 1.0))},
        },
        "materialx_doc": materialx_doc,
        "trace": {
            "kind": "designer_graph_recipe_v1",
            "stages": [
                "base_pattern_noise_stack",
                "pattern_geometry_warp_edge_detect",
                "height_normal",
                "curvature_histogram_masks",
                "ao_position_effects",
                "gradient_color_composition",
                "outputs_packed_orm",
            ],
            "node_count": len(graph.nodes),
            "deterministic": True,
        },
    }
