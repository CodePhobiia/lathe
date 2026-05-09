"""Procedural surface authoring graph (V0.1 §6.1).

Three-mode procedural surface authoring under the stable
``lathe.shape.intent_mesh_handoff_v1`` contract:

- ``designer_graph`` (Substance-Designer-class): from-scratch authoring via
  a typed node DAG (Noise, Pattern, ShapeSplatter, Warp, Blend, Normal,
  CurvatureSmooth, AO, Mask, Layer, Output).
- ``photo_fit`` (Substance-Sampler-class): deterministic palette extraction
  + FFT tile detection from a reference photo, driving a designer graph.
- ``layer_stack`` (Substance-Painter-class): composite typed Smart
  Materials with mesh-aware mask expressions.

All three modes terminate in MaterialX 1.39 as the portable, neutral
surface DAG handoff to runtime/engine adapters.
"""

from __future__ import annotations

from .designer_graph import compile_designer_graph, DesignerGraph
from .layer_stack import compile_layer_stack, LayerStack
from .materialx import compile_materialx, write_materialx
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
    WorldYMask,
)
from .photo_fit import compile_photo_fit, fit_palette, fit_tile_period

__all__ = [
    "AO",
    "Blend",
    "ConstColor",
    "CurvatureSmooth",
    "DesignerGraph",
    "EdgeDetect",
    "GradientMap",
    "HistogramScan",
    "Layer",
    "LayerStack",
    "Levels",
    "Mask",
    "Noise",
    "Normal",
    "Output",
    "Pattern",
    "PositionMask",
    "ShapeSplatter",
    "SlopeBlur",
    "SurfaceNode",
    "Warp",
    "WorldYMask",
    "compile_designer_graph",
    "compile_layer_stack",
    "compile_materialx",
    "compile_photo_fit",
    "fit_palette",
    "fit_tile_period",
    "write_materialx",
]


def dispatch_surface_program(
    program_kind: str,
    program_values: dict,
    *,
    asset_name: str = "asset",
) -> dict:
    """Dispatch on a surface_program mode and return a compiled IR.

    Returns a dict with keys ``mode``, ``materialx_doc`` (a dict-shaped
    MaterialX 1.39 document), ``channels`` (per-output map metadata),
    ``layers`` (when applicable), and ``trace`` (deterministic record of
    the compile path taken so callers can attribute outputs back to mode).
    """
    kind = (program_kind or "").strip().lower()
    if kind in {"designer_graph", "designer", "from_scratch"}:
        return compile_designer_graph(program_values, asset_name=asset_name)
    if kind in {"photo_fit", "photo", "sampler"}:
        return compile_photo_fit(program_values, asset_name=asset_name)
    if kind in {"layer_stack", "painter", "smart_layers"}:
        return compile_layer_stack(program_values, asset_name=asset_name)
    return {
        "mode": "unrecognized",
        "materialx_doc": None,
        "channels": {},
        "layers": [],
        "trace": {
            "kind": "unrecognized_surface_program_mode",
            "received": program_kind,
            "fallback": "no_op",
        },
    }
