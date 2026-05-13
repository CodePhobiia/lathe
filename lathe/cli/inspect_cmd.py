"""``lathe inspect`` / ``lathe inspect-blend`` / ``lathe serve`` subcommands.

Dump human-readable views of normalized assets and retained Blender
artefacts for debugging, and serve a completed build's ``.glb`` via
the vendored ``<model-viewer>`` web component.
"""

from __future__ import annotations

from pathlib import Path

from ._common import _dump, _emit_error


def _run_view_mode(build_dir: Path) -> None:
    """``lathe inspect <dir> --view``: open the build's .glb in trimesh."""
    try:
        import trimesh  # type: ignore
    except ImportError:
        _emit_error(
            "lathe.cli.inspect.trimesh_missing",
            "The --view mode requires the optional 'trimesh' package.",
            "Install it with: pip install trimesh",
            exit_code=3,
        )
        return

    from ..viewer import _find_glb

    glb = _find_glb(build_dir)
    if glb is None or not glb.exists():
        _emit_error(
            "lathe.cli.inspect.no_glb",
            f"No .glb artifact found under {build_dir}.",
            "Run 'lathe build <file> <asset>' first, or pass a different build directory.",
            exit_code=3,
        )
        return

    scene = trimesh.load(str(glb), force="scene")
    if not hasattr(scene, "show"):
        scene = trimesh.Scene(scene)
    scene.show()


def run_inspect(args) -> None:
    """Run inspect.

    Args:
        args: args argument.
    """
    build_dir = Path(args.build_dir).resolve()
    if getattr(args, "view", False):
        _run_view_mode(build_dir)
        return

    from ..bridge.blender_plan import inspect_completed_build

    _dump(inspect_completed_build(build_dir))


def run_serve(args) -> None:
    """``lathe serve <build_dir>``: HTTP-serve the artifact viewer."""
    build_dir = Path(args.build_dir).resolve()
    if not build_dir.is_dir():
        _emit_error(
            "lathe.cli.serve.missing_build_dir",
            f"Build directory does not exist: {build_dir}",
            "Run 'lathe build <file> <asset>' first, or pass a valid --out directory.",
            exit_code=2,
        )
        return

    from ..viewer import serve as _serve_viewer

    _serve_viewer(build_dir, port=int(getattr(args, "port", 8765) or 8765))


def run_inspect_blend(args) -> None:
    """Run inspect blend.

    Args:
        args: args argument.
    """
    from ..blender_execution import inspect_blend_artifact

    _dump(inspect_blend_artifact(Path(args.build_dir).resolve()))


def run_render_fixture(args) -> None:
    """Run render fixture.

    Args:
        args: args argument.
    """
    from ..bridge.blender_plan import build_render_fixture_report

    _dump(build_render_fixture_report(Path(args.build_dir).resolve()))


def run_bake_audit(args) -> None:
    """Run bake audit.

    Args:
        args: args argument.
    """
    from ..bridge.blender_plan import build_bake_audit

    _dump(build_bake_audit(Path(args.build_dir).resolve()))


def run_export_blend(args) -> None:
    """Run export blend.

    Args:
        args: args argument.
    """
    from ..blender_execution import export_blend_artifact

    destination = Path(args.out).resolve() if args.out else None
    _dump(export_blend_artifact(Path(args.build_dir).resolve(), destination))


def run_explain(args) -> None:
    """Run explain.

    Args:
        args: args argument.
    """
    from ..errors import BuildError
    from ..io_json import load_json_dict

    build_dir = Path(args.build_dir).resolve()
    try:
        report = load_json_dict(build_dir / "build_report.json", label="build_report.json")
        shape_bundle = load_json_dict(
            build_dir / "stages" / "shape" / "bundle.json",
            label="shape stage bundle",
        )
        validate_report = load_json_dict(
            build_dir / "stages" / "validate" / "report.json",
            label="validate stage report",
        )
    except BuildError as exc:
        _emit_error(
            "lathe.cli.inspect.bundle_unreadable",
            str(exc),
            "Re-run the build to regenerate the artifact, or check filesystem permissions.",
            exit_code=1,
        )
        return
    selected_id = shape_bundle.get("selected_candidate_id")
    selected = next(
        (item for item in shape_bundle.get("candidates", []) if item.get("candidate_id") == selected_id),
        {},
    )
    _dump(
        {
            "asset": report.get("asset"),
            "kind": report.get("kind"),
            "certified": report.get("certified"),
            "score": report.get("score"),
            "threshold": report.get("threshold"),
            "family": shape_bundle.get("asset_graph", {}).get("family"),
            "blueprint_id": shape_bundle.get("blueprint_id"),
            "authoritative_candidate_reason": shape_bundle.get("authoritative_candidate_reason"),
            "selected_candidate_id": selected_id,
            "candidate_params": selected.get("candidate_params", {}),
            "repairs_changed_result": validate_report.get("semantic_repairs_applied", []),
            "repair_suggestions": validate_report.get("repair_suggestions", []),
            "diagnostics": validate_report.get("diagnostics", []),
            "geometry_metrics": validate_report.get("visual_quality", {}).get("metrics", {}),
            "semantic_metrics": validate_report.get("semantic_quality", {}).get("metrics", {}),
        }
    )


def run_explain_fit(args) -> None:
    """Run explain fit.

    Args:
        args: args argument.
    """
    from ..errors import BuildError
    from ..io_json import load_json_dict

    build_dir = Path(args.build_dir).resolve()
    try:
        shape_bundle = load_json_dict(
            build_dir / "stages" / "shape" / "bundle.json",
            label="shape stage bundle",
        )
        validate_report = load_json_dict(
            build_dir / "stages" / "validate" / "report.json",
            label="validate stage report",
        )
    except BuildError as exc:
        _emit_error(
            "lathe.cli.inspect.bundle_unreadable",
            str(exc),
            "Re-run the build to regenerate the artifact, or check filesystem permissions.",
            exit_code=1,
        )
        return
    _dump(
        {
            "reference_ir": shape_bundle.get("reference_ir", {}),
            "fit_ir": shape_bundle.get("fit_ir", {}),
            "transfer_ir": shape_bundle.get("transfer_ir", {}),
            "kit_ir": shape_bundle.get("kit_ir", {}),
            "conditioning_report": shape_bundle.get("conditioning_report", {}),
            "shape_assessment": shape_bundle.get("shape_assessment", {}),
            "diagnostics": validate_report.get("diagnostics", []),
        }
    )
