"""Language-surface checks common to all declarations.

Covers identifier shape, unit literals, reserved keywords and other
grammar-adjacent rules that are easier to enforce semantically than
at the grammar level.
"""

from __future__ import annotations

from typing import Any

from ..resolver import ResolutionError
from .utils import diag


def check_duplicate_names(checker: Any) -> None:
    """Check duplicate names.

    Args:
        checker: checker argument.
    """
    namespaces = [
        ("profiles", "L2001"),
        ("contracts", "L2002"),
        ("critics", "L2003"),
        ("libraries", "L2004"),
        ("kits", "L2005"),
        ("patterns", "L2006"),
        ("families", "L2006"),
        ("components", "L2007"),
        ("assemblies", "L2008"),
        ("traits", "L2009"),
        ("mechanisms", "L2010"),
        ("materials", "L2011"),
        ("surface_programs", "L2011"),
        ("surface_backends", "L2011"),
        ("surface_policies", "L2011"),
        ("decal_libraries", "L2011"),
        ("mask_programs", "L2011"),
        ("trim_sheets", "L2011"),
        ("palettes", "L2012"),
        ("style_packs", "L2012"),
        ("style_bridges", "L2012"),
        ("reference_sets", "L2012"),
        ("reconstruct_policies", "L2012"),
        ("adapt_policies", "L2012"),
        ("assembly_policies", "L2012"),
        ("fit_profiles", "L2012"),
        ("transfer_rules", "L2012"),
        ("execution_profiles", "L2012"),
        ("render_fixtures", "L2012"),
        ("bake_profiles", "L2012"),
        ("library_bindings", "L2012"),
        ("material_graphs", "L2012"),
        ("inspection_policies", "L2012"),
        ("asset_class_profiles", "L2012"),
        ("vegetation_species", "L2012"),
        ("vegetation_kits", "L2012"),
        ("wind_programs", "L2012"),
        ("volume_programs", "L2012"),
        ("wfc_tilesets", "L2012"),
        ("wfc_adjacencies", "L2012"),
        ("repair_policies", "L2013"),
        ("fixtures", "L2014"),
        ("tests", "L2015"),
        ("benchmarks", "L2016"),
        ("spaces", "L2017"),
        ("worlds", "L2018"),
        ("scenes", "L2018"),
        ("assets", "L2004"),
        ("variants", "L2005"),
    ]
    for ns_key, code in namespaces:
        seen: set[str] = set()
        for decl in checker.program.get(ns_key, []):
            name = decl["name"]
            if name in seen:
                checker.diagnostics.append(
                    diag(
                        code,
                        "duplicate_name",
                        "error",
                        "resolve",
                        f"Duplicate declaration '{name}' in {ns_key[:-1]} namespace",
                    )
                )
            seen.add(name)


def check_use_graphs(checker: Any) -> None:
    """Check use graphs.

    Args:
        checker: checker argument.
    """
    for decl_type, ns_key in [("profile", "profiles"), ("contract", "contracts")]:
        for decl in checker.program.get(ns_key, []):
            try:
                _walk_decl_uses(checker, decl_type, decl["name"], [])
            except ResolutionError as exc:
                checker.diagnostics.append(
                    diag(
                        "L2101",
                        "use_cycle_or_invalid_use",
                        "error",
                        "resolve",
                        str(exc),
                        path=f"{decl_type}.{decl['name']}.uses",
                    )
                )


def _walk_decl_uses(checker: Any, decl_type: str, decl_name: str, stack: list[tuple[str, str]]) -> None:
    decl = (
        checker.resolver.profile_map[decl_name]
        if decl_type == "profile"
        else checker.resolver.contract_map[decl_name]
    )
    key = (decl_type, decl_name)
    if key in stack:
        cycle = " -> ".join(name for _, name in [*stack, key])
        raise ResolutionError(f"Use cycle detected: {cycle}")
    stack.append(key)
    for use_name in decl.get("uses", []):
        child_type, child_decl = checker.resolver._resolve_use_decl(use_name, decl_type)
        _walk_decl_uses(checker, child_type, child_decl["name"], stack)
    stack.pop()


def check_critics(checker: Any) -> None:
    """Check critics.

    Args:
        checker: checker argument.
    """
    for critic in checker.program.get("critics", []):
        body = critic.get("body")
        if isinstance(body, dict) and body.get("type") == "weighted":
            total = 0.0
            for item in body.get("items", []):
                raw_weight = item.get("weight", 0.0)
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    checker.diagnostics.append(
                        diag(
                            "L3203",
                            "non_numeric_critic_weight",
                            "error",
                            "typecheck",
                            (
                                f"Critic '{critic['name']}' has a non-numeric weight "
                                f"{raw_weight!r}"
                            ),
                            path=f"critic.{critic['name']}",
                        )
                    )
                    continue
                total += weight
                if weight < 0:
                    checker.diagnostics.append(
                        diag(
                            "L3201",
                            "negative_critic_weight",
                            "error",
                            "typecheck",
                            f"Critic '{critic['name']}' has a negative weight",
                            path=f"critic.{critic['name']}",
                        )
                    )
            if total == 0:
                checker.diagnostics.append(
                    diag(
                        "L3202",
                        "zero_total_critic_weight",
                        "error",
                        "typecheck",
                        f"Critic '{critic['name']}' has zero total weight",
                        path=f"critic.{critic['name']}",
                    )
                )


def check_tests_and_benchmarks(checker: Any) -> None:
    """Check tests and benchmarks.

    Args:
        checker: checker argument.
    """
    for decl in checker.program.get("tests", []):
        asset_name = decl.get("values", {}).get("asset")
        if (
            asset_name
            and asset_name not in checker.resolver.asset_map
            and asset_name not in checker.resolver.variant_map
        ):
            checker.diagnostics.append(
                diag(
                    "L5301",
                    "unknown_test_asset",
                    "error",
                    "resolve",
                    f"Test '{decl['name']}' references unknown asset '{asset_name}'",
                    path=f"test.{decl['name']}.values.asset",
                )
            )
    for decl in checker.program.get("benchmarks", []):
        values = decl.get("values", {})
        asset_name = values.get("asset")
        if (
            asset_name
            and asset_name not in checker.resolver.asset_map
            and asset_name not in checker.resolver.variant_map
        ):
            checker.diagnostics.append(
                diag(
                    "L5302",
                    "unknown_benchmark_asset",
                    "error",
                    "resolve",
                    f"Benchmark '{decl['name']}' references unknown asset '{asset_name}'",
                    path=f"benchmark.{decl['name']}.values.asset",
                )
            )
        for fixture_name in values.get("compare_against", []):
            if fixture_name not in checker.resolver.fixture_map:
                checker.diagnostics.append(
                    diag(
                        "L5303",
                        "unknown_fixture_reference",
                        "error",
                        "resolve",
                        f"Benchmark '{decl['name']}' references unknown fixture '{fixture_name}'",
                        path=f"benchmark.{decl['name']}.values.compare_against",
                    )
                )
