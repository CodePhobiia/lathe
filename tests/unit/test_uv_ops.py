from __future__ import annotations

import math

import numpy as np
import pytest
import trimesh
from lathe.core.mesh import RuntimeMesh
from lathe.core.uv_ops import apply_box_uv, apply_xatlas_uv_per_part


def test_box_uv_packing_report_includes_resolution() -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    runtime = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (128, 128, 128)},
        units="cm",
    )
    asset = {
        "build": {
            "uv": {
                "sets": ["base", "lightmap"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 1024,
            }
        }
    }

    _, meta = apply_box_uv(runtime, asset)

    assert meta["packing_report"]["resolution"] == 1024
    assert meta["packing_report"]["padding_normalized"] > 0


def test_box_uv_does_not_depend_on_trimesh_cached_face_normals(monkeypatch) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    runtime = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (128, 128, 128)},
        units="cm",
    )
    asset = {
        "build": {
            "uv": {
                "sets": ["base"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 1024,
            }
        }
    }

    def fail_face_normals(_self):
        raise AssertionError("apply_box_uv must compute normals directly")

    monkeypatch.setattr(trimesh.Trimesh, "face_normals", property(fail_face_normals))

    uv_runtime, meta = apply_box_uv(runtime, asset)

    assert len(uv_runtime.mesh.faces) == len(mesh.faces)
    assert meta["uv_sets"][0]["name"] == "base"


def _build_multi_part_runtime(part_names: list[str]) -> RuntimeMesh:
    all_v: list[np.ndarray] = []
    all_f: list[np.ndarray] = []
    face_parts: list[str] = []
    offset = 0
    for index, name in enumerate(part_names):
        box = trimesh.creation.box(extents=(1.0, 0.4 + 0.1 * index, 1.0))
        box.apply_translation((index * 2.0, 0.0, 0.0))
        all_v.append(np.asarray(box.vertices))
        all_f.append(np.asarray(box.faces) + offset)
        offset += len(box.vertices)
        face_parts.extend([name] * len(box.faces))
    mesh = trimesh.Trimesh(
        vertices=np.concatenate(all_v, axis=0),
        faces=np.concatenate(all_f, axis=0),
        process=False,
    )
    colors = {name: (128, 128, 128) for name in set(part_names)}
    return RuntimeMesh(mesh=mesh, face_parts=face_parts, part_colors=colors, units="cm")


def test_per_part_xatlas_preserves_named_parts_and_packs_shared_atlas() -> None:
    pytest.importorskip("xatlas")
    runtime = _build_multi_part_runtime(["body", "lid_panel", "foot_l"])
    asset = {
        "build": {
            "uv": {
                "sets": ["base", "lightmap"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 1024,
                "pack_rotate": True,
            }
        }
    }

    uv_runtime, meta, execution = apply_xatlas_uv_per_part(
        runtime, asset, {"uv": {"xatlas": {"resolution": 1024}}}
    )

    assert execution["mode"] == "xatlas_per_part"
    assert execution["part_count"] == 3
    assert sorted(set(uv_runtime.face_parts)) == ["body", "foot_l", "lid_panel"]
    islands = {entry["part"]: entry for entry in meta["packing_report"]["per_part_islands"]}
    # Body's importance weight (0.40) dwarfs foot_l (0.025), even after
    # normalization, so body must end up with a higher allocation.
    assert islands["body"]["importance_weight"] > islands["foot_l"]["importance_weight"]
    assert meta["packing_report"]["chart_count"] >= 3
    # With a global texels_per_unit (1024 px/m default), xatlas may split into
    # multiple atlas pages when the parts together can't fit at the requested
    # density on a single page. That's the intended hero-asset trade-off.
    assert meta["packing_report"]["atlas_count"] >= 1
    coords = uv_runtime.mesh.visual.uv
    assert coords is not None
    assert coords.min() >= 0.0 and coords.max() <= 1.0


def test_per_part_xatlas_falls_back_for_single_part() -> None:
    pytest.importorskip("xatlas")
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    runtime = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (128, 128, 128)},
        units="cm",
    )
    asset = {
        "build": {
            "uv": {
                "sets": ["base"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 512,
            }
        }
    }

    _, _meta, execution = apply_xatlas_uv_per_part(
        runtime, asset, {"uv": {"xatlas": {"resolution": 512}}}
    )
    # Single-part input degrades to the merged-mesh xatlas execution mode.
    assert execution["mode"] == "xatlas"


def test_per_part_xatlas_uniform_texel_density_across_disparate_areas() -> None:
    """Two parts with very different surface areas must end up with
    uniform texels-per-world-unit, not 8x density variance.

    Regression: prior code pre-scaled vertices by sqrt(importance/area)
    before atlas.generate, producing >900,000x density spread on real
    assets. Setting pack_options.texels_per_unit to a global px/m and
    feeding unscaled vertices is the industry-standard fix.
    """
    pytest.importorskip("xatlas")
    # Two parts whose surface areas differ by ~10000x — without a uniform
    # texels_per_unit, the prior code would assign each part its own atlas
    # area share producing a >1000x density spread.
    big = trimesh.creation.box(extents=(10.0, 10.0, 0.1))
    small = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
    small.apply_translation((20.0, 0.0, 0.0))
    vertices = np.concatenate([np.asarray(big.vertices), np.asarray(small.vertices)], axis=0)
    faces = np.concatenate(
        [np.asarray(big.faces), np.asarray(small.faces) + len(big.vertices)], axis=0
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    face_parts = (["body"] * len(big.faces)) + (["rivet"] * len(small.faces))
    runtime = RuntimeMesh(
        mesh=mesh,
        face_parts=face_parts,
        part_colors={"body": (128, 128, 128), "rivet": (200, 100, 100)},
        units="cm",
    )
    # Pick a px/m high enough that both parts get well-resolved UV islands
    # under cm mesh units — at 10000 px_per_m (= 100 px/cm, ~1 texel/mm) the
    # small 0.1cm box still gets ~10 px/side instead of being clamped to
    # xatlas's minimum chart size, which would otherwise inflate its UV area
    # disproportionately and break density uniformity.
    asset = {
        "build": {
            "uv": {
                "sets": ["base"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 4096,
                "texel_density": {"type": "unit", "value": 10000, "unit": "px_per_m"},
            }
        }
    }

    uv_runtime, _meta, execution = apply_xatlas_uv_per_part(
        runtime, asset, {"uv": {"xatlas": {"resolution": 4096}}}
    )

    assert execution["mode"] == "xatlas_per_part"
    uv = uv_runtime.mesh.visual.uv
    verts = np.asarray(uv_runtime.mesh.vertices, dtype=np.float64)
    tris = np.asarray(uv_runtime.mesh.faces, dtype=np.int64)
    resolution = 4096
    densities: list[float] = []
    for tri in tris:
        v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        world_area = float(np.linalg.norm(np.cross(v1 - v0, v2 - v0))) * 0.5
        u0, u1, u2 = uv[tri[0]], uv[tri[1]], uv[tri[2]]
        uv_area = abs((u1[0] - u0[0]) * (u2[1] - u0[1]) - (u2[0] - u0[0]) * (u1[1] - u0[1])) * 0.5
        if world_area < 1e-9 or uv_area < 1e-12:
            continue
        # px/m = sqrt(uv_area_in_pixels) / sqrt(world_area_in_meters)
        densities.append(math.sqrt(uv_area * resolution * resolution) / math.sqrt(world_area))
    assert len(densities) > 0
    log_densities = np.log(np.asarray(densities))
    log_variance = float(np.var(log_densities))
    ratio = float(max(densities) / min(densities))
    # log-variance under 0.10 ~= e^0.32 ~ 1.38x relative spread, comfortably
    # inside the +/-25% hero-asset tolerance band (RebusFarm, Beyond Extent).
    assert log_variance < 0.10, (
        f"texel-density log-variance {log_variance:.4f} exceeds 0.10 — "
        f"density spread {ratio:.2f}x indicates non-uniform packing"
    )
    assert ratio < 2.0, f"max/min density ratio {ratio:.2f}x must stay under 2.0x"


def test_per_part_xatlas_consumes_multi_part_scene_manifest_tags() -> None:
    pytest.importorskip("xatlas")
    from lathe.topology_runtime import MultiPartScene, PartManifest

    scene = trimesh.Scene()
    manifest: list[PartManifest] = []
    for index, name in enumerate(["body", "lid_panel", "foot_l"]):
        box = trimesh.creation.box(extents=(1.0, 0.4 + 0.1 * index, 1.0))
        box.apply_translation((index * 2.0, 0.0, 0.0))
        scene.add_geometry(box, geom_name=name, node_name=name)
        manifest.append(
            PartManifest(
                name=name,
                face_count=len(box.faces),
                vertex_count=len(box.vertices),
                tags=["plank_displacement", "oak_planks"] if name == "body" else ["chest"],
                parent_blueprint_component=f"chest_{name}",
            )
        )
    multi_scene = MultiPartScene(scene=scene, manifest=manifest, units="cm")

    flattened, face_parts = multi_scene.flatten_to_single_mesh()
    runtime = RuntimeMesh(
        mesh=flattened,
        face_parts=face_parts,
        part_colors={p.name: (128, 128, 128) for p in manifest},
        units="cm",
    )
    asset = {
        "build": {
            "uv": {
                "sets": ["base"],
                "padding": {"type": "unit", "value": 8, "unit": "px"},
                "resolution": 1024,
            }
        }
    }

    _uv_runtime, meta, execution = apply_xatlas_uv_per_part(
        runtime,
        asset,
        {"uv": {"xatlas": {"resolution": 1024}}},
        multi_part_scene=multi_scene,
    )

    assert execution["mode"] == "xatlas_per_part"
    assert execution["part_source"] == "multi_part_scene"
    assert execution["part_count"] == 3
    by_part = {entry["part"]: entry for entry in meta["packing_report"]["per_part_islands"]}
    assert by_part["body"]["tags"] == ["plank_displacement", "oak_planks"]
    assert by_part["body"]["parent_blueprint_component"] == "chest_body"
    assert by_part["foot_l"]["tags"] == ["chest"]
    # Order from the manifest, not alphabetical sort.
    ordered_names = [entry["part"] for entry in meta["packing_report"]["per_part_islands"]]
    assert ordered_names == ["body", "lid_panel", "foot_l"]
