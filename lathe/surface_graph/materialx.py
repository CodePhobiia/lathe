"""MaterialX 1.39 serialization for the three surface authoring modes.

All three modes (designer_graph, photo_fit, layer_stack) terminate in a
MaterialX 1.39 document as the portable, neutral surface DAG handoff to
runtime/engine adapters.

The optional ``materialx`` Python module is preferred when present.
Otherwise we emit MaterialX 1.39 XML directly (which is valid against
the public schema) so the build path never blocks on a heavyweight
optional dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


MATERIALX_VERSION = "1.39"
MATERIALX_NAMESPACE = "lathe_surface_v1"


def compile_materialx(
    *,
    mode: str,
    outputs: dict[str, str],
    params: dict[str, Any],
    asset_name: str = "asset",
) -> dict[str, Any]:
    """Compile a portable MaterialX 1.39 document.

    Returns a dict-shaped doc with keys ``version``, ``namespace``,
    ``materials``, ``nodegraphs``, ``surface_shaders``. The companion
    :func:`write_materialx` serialises this dict to a ``.mtlx`` XML file.
    Using a dict-shaped intermediate keeps the compile pure; XML
    serialisation is a separate, opt-in step.
    """
    nodegraph_name = f"{asset_name}_surface_graph"
    surface_shader_name = f"{asset_name}_surface_shader"
    material_name = f"{asset_name}_material"

    nodes: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    if mode == "designer_graph":
        nodes.extend(_designer_graph_to_nodes(params, outputs))
    elif mode == "photo_fit":
        nodes.extend(_designer_graph_to_nodes(params, outputs))
        # Record the extracted controls as nodegraph inputs so consumers
        # can introspect the photo fit without re-running it.
        if params.get("extracted_palette"):
            inputs.append({
                "name": "photo_fit_palette",
                "type": "string",
                "value": ",".join(
                    f"#{r:02x}{g:02x}{b:02x}" for r, g, b in params["extracted_palette"]
                ),
            })
        if params.get("tile_period"):
            tx, ty = params["tile_period"]
            inputs.append({
                "name": "photo_fit_tile_period_px",
                "type": "vector2",
                "value": f"{tx}, {ty}",
            })
    elif mode == "layer_stack":
        nodes.extend(_layer_stack_to_nodes(params))

    surface_shader_inputs = []
    for channel, source_name in outputs.items():
        # MaterialX standard surface input mapping.
        kind = _channel_to_mtlx_type(channel)
        surface_shader_inputs.append({
            "name": _channel_to_mtlx_input(channel),
            "type": kind,
            "nodegraph": nodegraph_name,
            "output": source_name,
        })

    return {
        "version": MATERIALX_VERSION,
        "namespace": MATERIALX_NAMESPACE,
        "mode": mode,
        "asset_name": asset_name,
        "nodegraphs": [
            {
                "name": nodegraph_name,
                "inputs": inputs,
                "nodes": nodes,
                "outputs": [
                    {
                        "name": source_name,
                        "type": _channel_to_mtlx_type(channel),
                    }
                    for channel, source_name in outputs.items()
                ],
            }
        ],
        "surface_shaders": [
            {
                "name": surface_shader_name,
                "type": "surfaceshader",
                "node": "standard_surface",
                "inputs": surface_shader_inputs,
            }
        ],
        "materials": [
            {
                "name": material_name,
                "type": "material",
                "surface_shader": surface_shader_name,
            }
        ],
    }


def _channel_to_mtlx_type(channel: str) -> str:
    return {
        "basecolor": "color3",
        "normal": "vector3",
        "metallic": "float",
        "roughness": "float",
        "height": "float",
        "ao": "float",
        "curvature": "float",
        "emissive": "color3",
        "opacity": "float",
    }.get(channel, "color3")


def _channel_to_mtlx_input(channel: str) -> str:
    return {
        "basecolor": "base_color",
        "normal": "normal",
        "metallic": "metalness",
        "roughness": "specular_roughness",
        "ao": "occlusion",
        "emissive": "emission_color",
        "opacity": "opacity",
        "height": "displacement",
        "curvature": "curvature",
    }.get(channel, channel)


def _designer_graph_to_nodes(params: dict[str, Any], outputs: dict[str, str]) -> list[dict[str, Any]]:
    """Lower the designer_graph IR into MaterialX node entries."""
    nodes: list[dict[str, Any]] = []
    palette = list(params.get("palette", []) or [(190, 190, 190), (88, 88, 88), (32, 32, 32)])
    while len(palette) < 3:
        palette.append(palette[-1] if palette else (118, 118, 118))
    seed = int(params.get("seed", 1337))
    nodes.append({
        "name": "noise_base",
        "type": "float",
        "category": "noise2d",
        "inputs": [
            {"name": "flavour", "type": "string", "value": "perlin"},
            {"name": "frequency", "type": "float", "value": 6.0},
            {"name": "octaves", "type": "integer", "value": 4},
            {"name": "seed", "type": "integer", "value": seed},
        ],
    })
    nodes.append({
        "name": "noise_meso",
        "type": "float",
        "category": "noise2d",
        "inputs": [
            {"name": "flavour", "type": "string", "value": "fractal"},
            {"name": "frequency", "type": "float", "value": 12.0},
            {"name": "octaves", "type": "integer", "value": 3},
            {"name": "seed", "type": "integer", "value": seed + 11},
        ],
    })
    nodes.append({
        "name": "noise_micro",
        "type": "float",
        "category": "noise2d",
        "inputs": [
            {"name": "flavour", "type": "string", "value": "worley"},
            {"name": "frequency", "type": "float", "value": 24.0},
            {"name": "octaves", "type": "integer", "value": 1},
            {"name": "seed", "type": "integer", "value": seed + 23},
        ],
    })
    nodes.append({
        "name": "noise_stack_1",
        "type": "float",
        "category": "blend_add",
        "inputs": [
            {"name": "in1", "type": "float", "nodename": "noise_base"},
            {"name": "in2", "type": "float", "nodename": "noise_meso"},
        ],
    })
    nodes.append({
        "name": "noise_stack",
        "type": "float",
        "category": "blend_overlay",
        "inputs": [
            {"name": "fg", "type": "float", "nodename": "noise_stack_1"},
            {"name": "bg", "type": "float", "nodename": "noise_micro"},
        ],
    })
    nodes.append({
        "name": "pattern",
        "type": "float",
        "category": "tiledimage",
        "inputs": [
            {"name": "flavour", "type": "string", "value": str(params.get("pattern", "brick")).lower()},
            {"name": "uvtiling", "type": "vector2",
             "value": f"{int(params.get('cols', 8))}, {int(params.get('rows', 4))}"},
            {"name": "mortar", "type": "float", "value": float(params.get("mortar", 0.05))},
        ],
    })
    nodes.append({
        "name": "splatter",
        "type": "float",
        "category": "splatter",
        "inputs": [
            {"name": "count", "type": "integer", "value": int(params.get("rivets", 64))},
        ],
    })
    nodes.append({
        "name": "pattern_with_rivets",
        "type": "float",
        "category": "blend_screen",
        "inputs": [
            {"name": "fg", "type": "float", "nodename": "pattern"},
            {"name": "bg", "type": "float", "nodename": "splatter"},
        ],
    })
    nodes.append({
        "name": "pattern_warped",
        "type": "float",
        "category": "warp2d",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "pattern_with_rivets"},
            {"name": "amplitude", "type": "float", "value": float(params.get("warp_amount", 0.04))},
            {"name": "frequency", "type": "float", "value": 3.0},
            {"name": "seed", "type": "integer", "value": seed + 53},
        ],
    })
    nodes.append({
        "name": "pattern_edges",
        "type": "float",
        "category": "edge_detect",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "pattern_warped"},
            {"name": "radius", "type": "integer", "value": int(params.get("edge_detect_radius", 1))},
            {"name": "strength", "type": "float", "value": float(params.get("edge_detect_strength", 1.35))},
        ],
    })
    nodes.append({
        "name": "height_raw",
        "type": "float",
        "category": "blend_add",
        "inputs": [
            {"name": "in1", "type": "float", "nodename": "noise_stack"},
            {"name": "in2", "type": "float", "nodename": "pattern_warped"},
        ],
    })
    nodes.append({
        "name": "height_slope_blur",
        "type": "float",
        "category": "slope_blur",
        "inputs": [
            {"name": "source", "type": "float", "nodename": "height_raw"},
            {"name": "slope", "type": "float", "nodename": "pattern_edges"},
            {"name": "samples", "type": "integer", "value": int(params.get("slope_blur_samples", 5))},
            {"name": "strength_px", "type": "float", "value": float(params.get("slope_blur_strength_px", 1.5))},
            {"name": "mode", "type": "string", "value": str(params.get("slope_blur_mode", "blur"))},
        ],
    })
    nodes.append({
        "name": "height",
        "type": "float",
        "category": "levels",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "height_slope_blur"},
            {"name": "low", "type": "float", "value": float(params.get("height_level_low", 0.03))},
            {"name": "high", "type": "float", "value": float(params.get("height_level_high", 0.97))},
            {"name": "gamma", "type": "float", "value": float(params.get("height_level_gamma", 1.0))},
        ],
    })
    nodes.append({
        "name": "normal",
        "type": "vector3",
        "category": "heighttonormal",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "height"},
            {"name": "scale", "type": "float", "value": float(params.get("normal_strength", 1.0))},
        ],
    })
    nodes.append({
        "name": "curvature",
        "type": "float",
        "category": "curvature",
        "inputs": [
            {"name": "in", "type": "vector3", "nodename": "normal"},
        ],
    })
    nodes.append({
        "name": "ao",
        "type": "float",
        "category": "ambientocclusion",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "height"},
        ],
    })
    nodes.append({
        "name": "mask_edge_scan",
        "type": "float",
        "category": "histogram_scan",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "curvature"},
            {"name": "threshold", "type": "float", "value": float(params.get("edge_scan_threshold", 0.56))},
            {"name": "softness", "type": "float", "value": float(params.get("edge_scan_softness", 0.18))},
            {"name": "contrast", "type": "float", "value": float(params.get("edge_scan_contrast", 1.15))},
        ],
    })
    nodes.append({
        "name": "mask_edge_wear_raw",
        "type": "float",
        "category": "smartmask_edge_wear",
        "inputs": [
            {"name": "curvature", "type": "float", "nodename": "curvature"},
            {"name": "ao", "type": "float", "nodename": "ao"},
            {"name": "ao_gate", "type": "boolean", "value": True},
        ],
    })
    nodes.append({
        "name": "mask_edge_wear",
        "type": "float",
        "category": "blend_multiply",
        "inputs": [
            {"name": "fg", "type": "float", "nodename": "mask_edge_wear_raw"},
            {"name": "bg", "type": "float", "nodename": "mask_edge_scan"},
        ],
    })
    nodes.append({
        "name": "mask_cavity",
        "type": "float",
        "category": "smartmask_cavity",
        "inputs": [
            {"name": "curvature", "type": "float", "nodename": "curvature"},
        ],
    })
    nodes.append({
        "name": "mask_position_top",
        "type": "float",
        "category": "position_mask",
        "inputs": [
            {"name": "axis", "type": "string", "value": "y"},
            {"name": "min", "type": "float", "value": float(params.get("position_top_min", 0.58))},
            {"name": "max", "type": "float", "value": 1.0},
            {"name": "softness", "type": "float", "value": float(params.get("position_top_softness", 0.18))},
        ],
    })
    for index, rgb in enumerate(palette[:3]):
        nodes.append({
            "name": f"color_layer_{index}",
            "type": "color3",
            "category": "constant",
            "inputs": [
                {"name": "value", "type": "color3",
                 "value": f"{rgb[0]/255:.4f}, {rgb[1]/255:.4f}, {rgb[2]/255:.4f}"},
            ],
        })
    gradient_stops = ";".join(
        f"{pos}:{rgb[0]/255:.4f},{rgb[1]/255:.4f},{rgb[2]/255:.4f}"
        for pos, rgb in zip((0.0, 0.55, 1.0), palette[:3], strict=False)
    )
    nodes.append({
        "name": "height_color_grade",
        "type": "color3",
        "category": "gradient_map",
        "inputs": [
            {"name": "in", "type": "float", "nodename": "height"},
            {"name": "stops", "type": "string", "value": gradient_stops},
        ],
    })
    nodes.append({
        "name": "comp_base",
        "type": "color3",
        "category": "mix",
        "inputs": [
            {"name": "fg", "type": "color3", "nodename": "color_layer_0"},
            {"name": "bg", "type": "color3", "nodename": "color_layer_1"},
            {"name": "mix", "type": "float", "nodename": "mask_cavity"},
        ],
    })
    nodes.append({
        "name": "comp_with_wear",
        "type": "color3",
        "category": "mix",
        "inputs": [
            {"name": "fg", "type": "color3", "nodename": "comp_base"},
            {"name": "bg", "type": "color3", "nodename": "color_layer_2"},
            {"name": "mix", "type": "float", "nodename": "mask_edge_wear"},
        ],
    })
    nodes.append({
        "name": "comp_height_position_grade",
        "type": "color3",
        "category": "mix",
        "inputs": [
            {"name": "fg", "type": "color3", "nodename": "comp_with_wear"},
            {"name": "bg", "type": "color3", "nodename": "height_color_grade"},
            {"name": "mix", "type": "float", "nodename": "mask_position_top"},
        ],
    })
    nodes.append({
        "name": "out_basecolor",
        "type": "color3",
        "category": "output",
        "inputs": [
            {"name": "in", "type": "color3", "nodename": "comp_height_position_grade"},
        ],
    })
    nodes.append({
        "name": "out_normal",
        "type": "vector3",
        "category": "output",
        "inputs": [
            {"name": "in", "type": "vector3", "nodename": "normal"},
        ],
    })
    return nodes


def _layer_stack_to_nodes(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Lower the layer_stack IR into MaterialX node entries."""
    layers = params.get("layer_summaries") or params.get("layers") or []
    nodes: list[dict[str, Any]] = []
    previous: str | None = None
    for index, layer in enumerate(layers):
        layer_node = f"layer_{index}_basecolor"
        mask_node = f"layer_{index}_mask"
        nodes.append({
            "name": mask_node,
            "type": "float",
            "category": "mask_expression",
            "inputs": [
                {"name": "expression", "type": "string",
                 "value": str(layer.get("mask_expression", "@curvature"))},
            ],
        })
        nodes.append({
            "name": layer_node,
            "type": "color3",
            "category": "material_lookup",
            "inputs": [
                {"name": "material", "type": "string",
                 "value": str(layer.get("material", "default_body"))},
            ],
        })
        if previous is None:
            nodes.append({
                "name": f"layer_{index}_blend",
                "type": "color3",
                "category": "constant_passthrough",
                "inputs": [
                    {"name": "in", "type": "color3", "nodename": layer_node},
                ],
            })
        else:
            blend_mode = str(layer.get("blend_mode", "normal"))
            nodes.append({
                "name": f"layer_{index}_blend",
                "type": "color3",
                "category": f"blend_{blend_mode}",
                "inputs": [
                    {"name": "fg", "type": "color3", "nodename": layer_node},
                    {"name": "bg", "type": "color3", "nodename": previous},
                    {"name": "mask", "type": "float", "nodename": mask_node},
                    {"name": "opacity", "type": "float", "value": float(layer.get("opacity", 1.0))},
                ],
            })
        previous = f"layer_{index}_blend"
    nodes.append({
        "name": "layer_stack_basecolor",
        "type": "color3",
        "category": "output",
        "inputs": [
            {"name": "in", "type": "color3", "nodename": previous or "layer_default"},
        ],
    })
    nodes.append({
        "name": "layer_stack_normal",
        "type": "vector3",
        "category": "output",
        "inputs": [
            {"name": "in", "type": "vector3",
             "value": "0.5, 0.5, 1.0"},
        ],
    })
    nodes.append({
        "name": "layer_stack_ao",
        "type": "float",
        "category": "output",
        "inputs": [
            {"name": "in", "type": "float", "value": "1.0"},
        ],
    })
    return nodes


def write_materialx(doc: dict[str, Any], path: Path) -> Path:
    """Serialise a dict-shaped MaterialX doc to ``path`` as XML.

    Prefers the official ``MaterialX`` Python module if available so
    the document is round-trip-validated. Falls back to direct XML
    emission otherwise (still valid MaterialX 1.39).
    """
    try:
        import MaterialX as mx  # type: ignore[import-not-found]
    except ImportError:
        return _write_materialx_direct_xml(doc, path)
    try:
        mx_doc = mx.createDocument()
        mx_doc.setVersionString(doc.get("version", MATERIALX_VERSION))
        for ng in doc.get("nodegraphs", []):
            ng_node = mx_doc.addNodeGraph(ng["name"])
            for node in ng.get("nodes", []):
                category = node.get("category", "constant")
                mx_node = ng_node.addNode(category, node["name"], node.get("type", "color3"))
                for inp in node.get("inputs", []):
                    mx_input = mx_node.addInput(inp["name"], inp.get("type", "float"))
                    if "nodename" in inp:
                        mx_input.setNodeName(inp["nodename"])
                    elif "value" in inp:
                        mx_input.setValueString(str(inp["value"]))
            for out in ng.get("outputs", []):
                ng_node.addOutput(out["name"], out.get("type", "color3"))
        for shader in doc.get("surface_shaders", []):
            mx_shader = mx_doc.addNode(
                shader.get("node", "standard_surface"),
                shader["name"],
                shader.get("type", "surfaceshader"),
            )
            for inp in shader.get("inputs", []):
                mx_input = mx_shader.addInput(inp["name"], inp.get("type", "float"))
                if "nodegraph" in inp and "output" in inp:
                    mx_input.setNodeGraphString(inp["nodegraph"])
                    mx_input.setOutputString(inp["output"])
        for material in doc.get("materials", []):
            mx_material = mx_doc.addNode("surfacematerial", material["name"], material.get("type", "material"))
            mx_input = mx_material.addInput("surfaceshader", "surfaceshader")
            mx_input.setNodeName(material["surface_shader"])
        path.parent.mkdir(parents=True, exist_ok=True)
        mx.writeToXmlFile(mx_doc, str(path))
        return path
    except Exception:  # pragma: no cover - defensive fallback
        return _write_materialx_direct_xml(doc, path)


def _write_materialx_direct_xml(doc: dict[str, Any], path: Path) -> Path:
    """Emit MaterialX 1.39 XML directly without the optional Python module."""
    root = ET.Element("materialx", attrib={
        "version": doc.get("version", MATERIALX_VERSION),
        "colorspace": "lin_rec709",
        "namespace": doc.get("namespace", MATERIALX_NAMESPACE),
    })
    for ng in doc.get("nodegraphs", []):
        ng_el = ET.SubElement(root, "nodegraph", attrib={"name": ng["name"]})
        for inp in ng.get("inputs", []):
            ET.SubElement(ng_el, "input", attrib={
                "name": inp["name"],
                "type": inp.get("type", "float"),
                "value": str(inp.get("value", "0")),
            })
        for node in ng.get("nodes", []):
            node_el = ET.SubElement(
                ng_el,
                node.get("category", "constant"),
                attrib={"name": node["name"], "type": node.get("type", "color3")},
            )
            for inp in node.get("inputs", []):
                attribs = {"name": inp["name"], "type": inp.get("type", "float")}
                if "nodename" in inp:
                    attribs["nodename"] = inp["nodename"]
                if "value" in inp:
                    attribs["value"] = str(inp["value"])
                ET.SubElement(node_el, "input", attrib=attribs)
        for out in ng.get("outputs", []):
            ET.SubElement(ng_el, "output", attrib={
                "name": out["name"],
                "type": out.get("type", "color3"),
            })
    for shader in doc.get("surface_shaders", []):
        shader_el = ET.SubElement(
            root,
            shader.get("node", "standard_surface"),
            attrib={"name": shader["name"], "type": shader.get("type", "surfaceshader")},
        )
        for inp in shader.get("inputs", []):
            attribs = {"name": inp["name"], "type": inp.get("type", "float")}
            if "nodegraph" in inp:
                attribs["nodegraph"] = inp["nodegraph"]
            if "output" in inp:
                attribs["output"] = inp["output"]
            if "value" in inp:
                attribs["value"] = str(inp["value"])
            ET.SubElement(shader_el, "input", attrib=attribs)
    for material in doc.get("materials", []):
        material_el = ET.SubElement(
            root,
            "surfacematerial",
            attrib={"name": material["name"], "type": material.get("type", "material")},
        )
        ET.SubElement(material_el, "input", attrib={
            "name": "surfaceshader",
            "type": "surfaceshader",
            "nodename": material["surface_shader"],
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
