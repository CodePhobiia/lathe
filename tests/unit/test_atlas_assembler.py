"""Unit tests for ``lathe.atlas_assembler.build_atlas_assembly_ir``.

The assembler emits the ``lathe.atlas_assembly_ir.v1`` schema: it wraps
a surface config, a surface control pack manifest, and a per-map output
dict into the atlas IR consumed by the V1.2 surface runtime. There is no
validation in the function itself — the resolver/checker enforce
semantic rules — so these tests focus on the shape of the emitted IR,
default behavior for empty/single-sprite inputs, and determinism.
"""

from __future__ import annotations

import unittest

from lathe.atlas_assembler import build_atlas_assembly_ir


def _surface_cfg(maps: list[str] | None = None, padding: dict | None = None) -> dict:
    cfg: dict = {}
    if maps is not None:
        cfg["maps"] = maps
    if padding is not None:
        cfg["padding"] = padding
    return cfg


def _control_pack(manifest_uri: str = "control_pack/manifest.json") -> dict:
    return {"manifest_uri": manifest_uri}


def _outputs(names: list[str]) -> dict:
    return {name: {"uri": f"atlas/{name}.png"} for name in names}


class BuildAtlasAssemblyIRTests(unittest.TestCase):
    def test_assemble_atlas_from_three_sprites(self) -> None:
        ir = build_atlas_assembly_ir(
            _surface_cfg(maps=["basecolor", "normal", "roughness"]),
            _control_pack(),
            _outputs(["basecolor", "normal", "roughness"]),
        )
        self.assertEqual(ir["schema"], "lathe.atlas_assembly_ir.v1")
        self.assertEqual(ir["mode"], "zone_first")
        self.assertEqual(ir["control_pack"], "control_pack/manifest.json")
        self.assertEqual(ir["compose"]["maps"], ["basecolor", "normal", "roughness"])
        self.assertEqual(len(ir["outputs"]), 3)
        self.assertEqual(ir["outputs"]["basecolor"], "atlas/basecolor.png")
        self.assertEqual(ir["outputs"]["normal"], "atlas/normal.png")

    def test_empty_sprite_list_yields_empty_outputs(self) -> None:
        ir = build_atlas_assembly_ir(_surface_cfg(maps=[]), _control_pack(), {})
        self.assertEqual(ir["compose"]["maps"], [])
        self.assertEqual(ir["outputs"], {})
        # Schema and mode must still be populated even in the empty case.
        self.assertEqual(ir["schema"], "lathe.atlas_assembly_ir.v1")
        self.assertEqual(ir["mode"], "zone_first")
        self.assertTrue(ir["compose"]["mip_safe"])

    def test_single_sprite_atlas(self) -> None:
        ir = build_atlas_assembly_ir(
            _surface_cfg(maps=["basecolor"]),
            _control_pack(),
            _outputs(["basecolor"]),
        )
        self.assertEqual(ir["compose"]["maps"], ["basecolor"])
        self.assertEqual(len(ir["outputs"]), 1)
        self.assertEqual(ir["outputs"]["basecolor"], "atlas/basecolor.png")

    def test_padding_default_is_applied_when_cfg_omits_it(self) -> None:
        ir = build_atlas_assembly_ir(
            _surface_cfg(maps=["basecolor"]),
            _control_pack(),
            _outputs(["basecolor"]),
        )
        padding = ir["compose"]["padding"]
        self.assertEqual(padding["type"], "unit")
        self.assertEqual(padding["value"], 8)
        self.assertEqual(padding["unit"], "px")

    def test_padding_passes_through_when_provided(self) -> None:
        custom_padding = {"type": "unit", "value": 16, "unit": "px"}
        ir = build_atlas_assembly_ir(
            _surface_cfg(maps=["basecolor"], padding=custom_padding),
            _control_pack(),
            _outputs(["basecolor"]),
        )
        self.assertEqual(ir["compose"]["padding"], custom_padding)

    def test_deterministic_packing_given_same_inputs(self) -> None:
        cfg = _surface_cfg(maps=["basecolor", "normal"])
        pack = _control_pack()
        outs = _outputs(["basecolor", "normal"])
        a = build_atlas_assembly_ir(cfg, pack, outs)
        b = build_atlas_assembly_ir(cfg, pack, outs)
        self.assertEqual(a, b)
        self.assertEqual(a["compose"]["maps"], b["compose"]["maps"])
        self.assertEqual(list(a["outputs"].keys()), list(b["outputs"].keys()))

    def test_malformed_output_missing_uri_raises(self) -> None:
        # Each output entry is dereferenced via entry["uri"]. A malformed
        # entry without that key must raise.
        bad_outputs = {"basecolor": {"wrong_key": "x.png"}}
        with self.assertRaises(KeyError):
            build_atlas_assembly_ir(_surface_cfg(maps=["basecolor"]), _control_pack(), bad_outputs)

    def test_control_pack_missing_manifest_uri_yields_none(self) -> None:
        ir = build_atlas_assembly_ir(_surface_cfg(maps=["basecolor"]), {}, _outputs(["basecolor"]))
        self.assertIsNone(ir["control_pack"])


if __name__ == "__main__":
    unittest.main()
