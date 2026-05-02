"""``lathe asset-quality`` commands for Phase 14 examples."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..asset_quality.certification import (
    MODE_STRICT,
    MODE_WARNING,
    catalog_examples,
    certify_to_directory,
    validate_example,
    write_catalog,
)
from ..asset_quality.semantic_patch import apply_semantic_patch, compare_before_after
from ._common import _dump, _emit_error


def register(sub: argparse._SubParsersAction) -> None:
    """Register the ``asset-quality`` command group."""
    p = sub.add_parser(
        "asset-quality",
        help="Validate and certify Phase 14 asset-quality example fixtures",
    )
    aq_sub = p.add_subparsers(dest="asset_quality_cmd", required=True)

    p_validate = aq_sub.add_parser(
        "validate-example",
        help="Validate one asset-quality example fixture",
    )
    p_validate.add_argument("example_dir")
    p_validate.add_argument(
        "--mode",
        choices=[MODE_WARNING, MODE_STRICT],
        default=MODE_WARNING,
        help="Certification mode to validate (default: warning)",
    )

    p_certify = aq_sub.add_parser(
        "certify",
        help="Write a computed certificate and report for one example fixture",
    )
    p_certify.add_argument("example_dir")
    p_certify.add_argument("--out", required=True, help="Output directory")
    p_certify.add_argument(
        "--mode",
        choices=[MODE_WARNING, MODE_STRICT],
        default=MODE_WARNING,
        help="Certification mode to write (default: warning)",
    )

    p_catalog = aq_sub.add_parser(
        "catalog-examples",
        help="Catalog all direct asset-quality example fixture directories",
    )
    p_catalog.add_argument("examples_root")
    p_catalog.add_argument("--out", default=None, help="Optional JSON output path")

    p_patch = aq_sub.add_parser(
        "patch",
        help="Apply a deterministic semantic patch to one example fixture",
    )
    p_patch.add_argument("example_dir")
    p_patch.add_argument("patch_json")
    p_patch.add_argument("--out", required=True, help="Output fixture directory")

    p_compare = aq_sub.add_parser(
        "compare-before-after",
        help="Compare two asset-quality example fixtures",
    )
    p_compare.add_argument("before_dir")
    p_compare.add_argument("after_dir")
    p_compare.add_argument("--out", required=True, help="Output comparison JSON path")


def _require_dir(path: str, *, code: str) -> Path:
    candidate = Path(path)
    if not candidate.exists():
        _emit_error(
            code,
            f"Directory not found: {candidate}",
            "Check the fixture path and rerun the command.",
            exit_code=2,
            source_path=str(candidate),
        )
    if not candidate.is_dir():
        _emit_error(
            code,
            f"Expected a directory: {candidate}",
            "Pass an asset-quality example directory.",
            exit_code=2,
            source_path=str(candidate),
        )
    return candidate


def _run_validate_example(args: argparse.Namespace) -> None:
    example_dir = _require_dir(
        args.example_dir,
        code="lathe.cli.asset_quality.example_not_found",
    )
    payload = validate_example(example_dir, mode=args.mode)
    _dump(payload)
    if not payload["ok"]:
        raise SystemExit(1)


def _run_certify(args: argparse.Namespace) -> None:
    example_dir = _require_dir(
        args.example_dir,
        code="lathe.cli.asset_quality.example_not_found",
    )
    payload = certify_to_directory(example_dir, args.out, mode=args.mode)
    _dump(payload)
    if not payload["ok"]:
        raise SystemExit(1)


def _run_catalog_examples(args: argparse.Namespace) -> None:
    root = _require_dir(
        args.examples_root,
        code="lathe.cli.asset_quality.root_not_found",
    )
    if args.out:
        payload = write_catalog(root, args.out)
        payload = {**payload, "out": args.out}
    else:
        payload = catalog_examples(root)
    _dump(payload)
    if not payload["ok"]:
        raise SystemExit(1)


def _require_file(path: str, *, code: str) -> Path:
    candidate = Path(path)
    if not candidate.exists():
        _emit_error(
            code,
            f"File not found: {candidate}",
            "Check the patch path and rerun the command.",
            exit_code=2,
            source_path=str(candidate),
        )
    if not candidate.is_file():
        _emit_error(
            code,
            f"Expected a file: {candidate}",
            "Pass a semantic patch JSON file.",
            exit_code=2,
            source_path=str(candidate),
        )
    return candidate


def _run_patch(args: argparse.Namespace) -> None:
    example_dir = _require_dir(
        args.example_dir,
        code="lathe.cli.asset_quality.example_not_found",
    )
    patch_json = _require_file(
        args.patch_json,
        code="lathe.cli.asset_quality.patch_not_found",
    )
    payload = apply_semantic_patch(example_dir, patch_json, args.out)
    _dump(payload)
    if not payload["ok"]:
        raise SystemExit(1)


def _run_compare_before_after(args: argparse.Namespace) -> None:
    before_dir = _require_dir(
        args.before_dir,
        code="lathe.cli.asset_quality.example_not_found",
    )
    after_dir = _require_dir(
        args.after_dir,
        code="lathe.cli.asset_quality.example_not_found",
    )
    payload = compare_before_after(before_dir, after_dir, args.out)
    payload = {**payload, "out": args.out}
    _dump(payload)


_DISPATCH = {
    "validate-example": _run_validate_example,
    "certify": _run_certify,
    "catalog-examples": _run_catalog_examples,
    "patch": _run_patch,
    "compare-before-after": _run_compare_before_after,
}


def run_asset_quality(args: argparse.Namespace) -> None:
    """Dispatch ``lathe asset-quality <subcommand>``."""
    command = getattr(args, "asset_quality_cmd", None)
    handler = _DISPATCH.get(command)
    if handler is None:
        _emit_error(
            "lathe.cli.asset_quality.unknown_command",
            "unknown asset-quality subcommand",
            "See lathe asset-quality --help for supported subcommands.",
            exit_code=2,
        )
    handler(args)
