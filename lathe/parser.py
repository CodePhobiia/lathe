from __future__ import annotations

import ast as py_ast
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from lark import Transformer, v_args


def _find_grammar_path() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "grammar" / "lathe.lark"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate grammar/lathe.lark")


GRAMMAR_PATH = _find_grammar_path()
REPO_ROOT = GRAMMAR_PATH.parent.parent


class LatheParseError(Exception):
    pass


class DuplicateFieldError(LatheParseError):
    def __init__(self, path: str, context: str) -> None:
        super().__init__(f"Duplicate assignment to '{path}' in {context} block")
        self.path = path
        self.context = context


_UNIT_RE = re.compile(
    r"^(?P<value>(?:\d+\.\d+|\d+))(?P<unit>mm|cm|m|deg|rad|g|kg|ms|s|kb|mb|gb|px|px_per_m|px_per_cm)$"
)

PROGRAM_ARRAY_KEYS = [
    "profiles",
    "contracts",
    "critics",
    "libraries",
    "kits",
    "patterns",
    "families",
    "components",
    "assemblies",
    "traits",
    "mechanisms",
    "materials",
    "surface_programs",
    "surface_backends",
    "surface_policies",
    "decal_libraries",
    "mask_programs",
    "trim_sheets",
    "palettes",
    "reference_sets",
    "reconstruct_policies",
    "adapt_policies",
    "assembly_policies",
    "fit_profiles",
    "transfer_rules",
    "execution_profiles",
    "render_fixtures",
    "bake_profiles",
    "library_bindings",
    "material_graphs",
    "inspection_policies",
    "repair_policies",
    "fixtures",
    "tests",
    "benchmarks",
    "spaces",
    "assets",
    "variants",
]


def _empty_program() -> dict[str, Any]:
    return {
        "module": None,
        "imports": [],
        "profiles": [],
        "contracts": [],
        "critics": [],
        "libraries": [],
        "kits": [],
        "patterns": [],
        "families": [],
        "components": [],
        "assemblies": [],
        "traits": [],
        "mechanisms": [],
        "materials": [],
        "surface_programs": [],
        "surface_backends": [],
        "surface_policies": [],
        "decal_libraries": [],
        "mask_programs": [],
        "trim_sheets": [],
        "palettes": [],
        "reference_sets": [],
        "reconstruct_policies": [],
        "adapt_policies": [],
        "assembly_policies": [],
        "fit_profiles": [],
        "transfer_rules": [],
        "execution_profiles": [],
        "render_fixtures": [],
        "bake_profiles": [],
        "library_bindings": [],
        "material_graphs": [],
        "inspection_policies": [],
        "repair_policies": [],
        "fixtures": [],
        "tests": [],
        "benchmarks": [],
        "spaces": [],
        "assets": [],
        "variants": [],
    }


def _num(text: str) -> int | float:
    if any(c in text for c in ".eE"):
        return float(text)
    return int(text)


def _dedupe_keep_first(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _set_nested(target: dict[str, Any], path: str, value: Any, context: str) -> None:
    parts = path.split(".")
    cursor = target
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if nxt is None:
            nxt = {}
            cursor[part] = nxt
        elif not isinstance(nxt, dict):
            raise DuplicateFieldError(path, context)
        cursor = nxt
    leaf = parts[-1]
    if leaf in cursor:
        raise DuplicateFieldError(path, context)
    cursor[leaf] = value


def _merge_programs(imported: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    merged = _empty_program()
    merged["module"] = local.get("module")
    merged["imports"] = _dedupe_keep_first([*imported.get("imports", []), *local.get("imports", [])])
    for key in PROGRAM_ARRAY_KEYS:
        merged[key] = [*imported.get(key, []), *local.get(key, [])]
    return merged


def _resolve_import_path(source_path: Path, import_name: str) -> Path:
    rel = Path(*import_name.split(".")).with_suffix(".lth")
    candidates = [
        source_path.parent / rel,
        REPO_ROOT / rel,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
    raise LatheParseError(f"Could not resolve import '{import_name}' from '{source_path}'")


@v_args(inline=True)
class _LatheTransformer(Transformer):
    def program(self, *items: Any) -> dict[str, Any]:
        program = _empty_program()
        for item in items:
            if not item:
                continue
            kind = item["node_type"]
            if kind == "module":
                program["module"] = item["name"]
            elif kind == "import":
                program["imports"].append(item["name"])
            elif kind == "profile":
                program["profiles"].append(item)
            elif kind == "contract":
                program["contracts"].append(item)
            elif kind == "critic":
                program["critics"].append(item)
            elif kind == "library":
                program["libraries"].append(item)
            elif kind == "kit":
                program["kits"].append(item)
            elif kind == "pattern":
                program["patterns"].append(item)
            elif kind == "family":
                program["families"].append(item)
            elif kind == "component":
                program["components"].append(item)
            elif kind == "assembly_decl":
                program["assemblies"].append(item)
            elif kind == "trait":
                program["traits"].append(item)
            elif kind == "mechanism":
                program["mechanisms"].append(item)
            elif kind == "material":
                program["materials"].append(item)
            elif kind == "surface_program":
                program["surface_programs"].append(item)
            elif kind == "surface_backend":
                program["surface_backends"].append(item)
            elif kind == "surface_policy":
                program["surface_policies"].append(item)
            elif kind == "decal_library":
                program["decal_libraries"].append(item)
            elif kind == "mask_program":
                program["mask_programs"].append(item)
            elif kind == "trim_sheet":
                program["trim_sheets"].append(item)
            elif kind == "palette":
                program["palettes"].append(item)
            elif kind == "reference_set":
                program["reference_sets"].append(item)
            elif kind == "reconstruct_policy":
                program["reconstruct_policies"].append(item)
            elif kind == "adapt_policy":
                program["adapt_policies"].append(item)
            elif kind == "assembly_policy":
                program["assembly_policies"].append(item)
            elif kind == "fit_profile":
                program["fit_profiles"].append(item)
            elif kind == "transfer_rule":
                program["transfer_rules"].append(item)
            elif kind == "execution_profile":
                program["execution_profiles"].append(item)
            elif kind == "render_fixture":
                program["render_fixtures"].append(item)
            elif kind == "bake_profile":
                program["bake_profiles"].append(item)
            elif kind == "library_binding":
                program["library_bindings"].append(item)
            elif kind == "material_graph":
                program["material_graphs"].append(item)
            elif kind == "inspection_policy":
                program["inspection_policies"].append(item)
            elif kind == "repair_policy":
                program["repair_policies"].append(item)
            elif kind == "fixture":
                program["fixtures"].append(item)
            elif kind == "test":
                program["tests"].append(item)
            elif kind == "benchmark":
                program["benchmarks"].append(item)
            elif kind == "space_decl":
                program["spaces"].append(item)
            elif kind == "asset":
                program["assets"].append(item)
            elif kind == "variant":
                program["variants"].append(item)
            else:
                raise LatheParseError(f"Unknown program item: {kind}")
        program["imports"] = _dedupe_keep_first(program["imports"])
        return program

    def module_decl(self, name: str) -> dict[str, Any]:
        return {"node_type": "module", "name": name}

    def import_decl(self, name: str) -> dict[str, Any]:
        return {"node_type": "import", "name": name}

    def use_clause(self, first: str, *rest: str) -> list[str]:
        return [first, *rest]

    def profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._profile_or_contract("profile", name, *rest)

    def contract_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._profile_or_contract("contract", name, *rest)

    def _profile_or_contract(self, node_type: str, name: str, *rest: Any) -> dict[str, Any]:
        uses: list[str] = []
        defaults: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        repair: dict[str, Any] = {}
        for item in rest:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, dict) and item.get("node_type") == "defaults":
                defaults = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "repair":
                repair = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "rule":
                rules.append(item)
            else:
                raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
        return {
            "node_type": node_type,
            "name": name,
            "uses": _dedupe_keep_first(uses),
            "defaults": defaults,
            "rules": rules,
            "repair": repair,
        }

    def critic_decl(self, name: str, param_name: str, body: Any) -> dict[str, Any]:
        return {
            "node_type": "critic",
            "name": name,
            "param": {"name": param_name, "type": "asset"},
            "body": body,
        }

    def weighted_critic(self, *items: Any) -> dict[str, Any]:
        return {"type": "weighted", "items": list(items)}

    def weighted_item(self, metric: Any, weight: int | float) -> dict[str, Any]:
        return {"metric": metric, "weight": float(weight)}

    def family_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        decl_kind: str | None = None
        remaining: list[Any] = []
        for item in rest:
            if decl_kind is None and isinstance(item, str) and item in {"hard_surface_prop", "env_module", "mechanical_assembly"}:
                decl_kind = item
            else:
                remaining.append(item)
        return self._structured_decl("family", name, *remaining, kind=decl_kind)

    def component_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._structured_decl("component", name, *rest)

    def assembly_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._structured_decl("assembly_decl", name, *rest)

    def trait_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._structured_decl("trait", name, *rest)

    def mechanism_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._structured_decl("mechanism", name, *rest)

    def library_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("library", name, *rest)

    def kit_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("kit", name, *rest)

    def pattern_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("pattern", name, *rest)

    def material_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("material", name, *rest)

    def surface_program_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("surface_program", name, *rest)

    def surface_backend_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("surface_backend", name, *rest)

    def surface_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("surface_policy", name, *rest)

    def decal_library_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("decal_library", name, *rest)

    def mask_program_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("mask_program", name, *rest)

    def trim_sheet_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("trim_sheet", name, *rest)

    def palette_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("palette", name, *rest)

    def reference_set_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("reference_set", name, *rest)

    def reconstruct_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("reconstruct_policy", name, *rest)

    def adapt_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("adapt_policy", name, *rest)

    def assembly_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("assembly_policy", name, *rest)

    def fit_profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("fit_profile", name, *rest)

    def transfer_rule_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("transfer_rule", name, *rest)

    def execution_profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("execution_profile", name, *rest)

    def render_fixture_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("render_fixture", name, *rest)

    def bake_profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("bake_profile", name, *rest)

    def library_binding_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("library_binding", name, *rest)

    def material_graph_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("material_graph", name, *rest)

    def inspection_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._mapping_decl("inspection_policy", name, *rest)

    def repair_policy_decl(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "repair_policy",
            "name": name,
            "values": self._assignments(assignments, "repair_policy"),
        }

    def fixture_decl(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "fixture",
            "name": name,
            "values": self._assignments(assignments, "fixture"),
        }

    def test_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        values: list[tuple[str, Any]] = []
        asserts: list[dict[str, Any]] = []
        for item in rest:
            if isinstance(item, tuple) and len(item) == 2:
                values.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "assert":
                asserts.append(item)
            else:
                raise LatheParseError(f"Unexpected test item: {item!r}")
        return {
            "node_type": "test",
            "name": name,
            "values": self._assignments(values, "test"),
            "asserts": asserts,
        }

    def benchmark_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        values: list[tuple[str, Any]] = []
        asserts: list[dict[str, Any]] = []
        for item in rest:
            if isinstance(item, tuple) and len(item) == 2:
                values.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "assert":
                asserts.append(item)
            else:
                raise LatheParseError(f"Unexpected benchmark item: {item!r}")
        return {
            "node_type": "benchmark",
            "name": name,
            "values": self._assignments(values, "benchmark"),
            "asserts": asserts,
        }

    def space_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._space_spec("space_decl", name, *rest)

    def asset_decl(self, name: str, kind: str, *rest: Any) -> dict[str, Any]:
        from_family = ""
        uses: list[str] = []
        refs: dict[str, Any] = {}
        intent: dict[str, Any] = {}
        geometry: dict[str, Any] = {}
        features: dict[str, Any] = {}
        surface: dict[str, Any] = {}
        assembly: dict[str, Any] = {}
        fit: dict[str, Any] = {}
        transfer: dict[str, Any] = {}
        reuse: dict[str, Any] = {}
        constraints: dict[str, Any] = {}
        ingest: dict[str, Any] = {}
        assembly_rules: dict[str, Any] = {}
        execution: dict[str, Any] = {}
        space: dict[str, Any] = {}
        repair_policy: dict[str, Any] = {}
        build: dict[str, Any] = {}
        validate: dict[str, Any] = {}
        package: dict[str, Any] = {}
        publish: dict[str, Any] = {}
        for item in rest:
            if item is None:
                continue
            if isinstance(item, dict) and item.get("node_type") == "from_clause":
                from_family = item["name"]
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, dict) and item.get("node_type") == "refs":
                refs = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "intent":
                intent = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "geometry":
                geometry = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "features":
                features = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "source_surface":
                surface = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "assembly":
                assembly = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "fit":
                fit = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "transfer":
                transfer = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "reuse":
                reuse = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "constraints":
                constraints = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "ingest":
                ingest = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "assembly_rules":
                assembly_rules = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "execution":
                execution = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "space_inline":
                space = item
            elif isinstance(item, dict) and item.get("node_type") == "search_inline":
                space = item
            elif isinstance(item, dict) and item.get("node_type") == "repair_policy_inline":
                repair_policy = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "build":
                build = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "validate":
                validate = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "package":
                package = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "publish":
                publish = item["values"]
            else:
                raise LatheParseError(f"Unexpected asset item: {item!r}")
        return {
            "node_type": "asset",
            "name": name,
            "kind": kind,
            "from": from_family,
            "uses": _dedupe_keep_first(uses),
            "refs": refs,
            "intent": intent,
            "geometry": geometry,
            "features": features,
            "surface": surface,
            "assembly": assembly,
            "fit": fit,
            "transfer": transfer,
            "reuse": reuse,
            "constraints": constraints,
            "ingest": ingest,
            "assembly_rules": assembly_rules,
            "execution": execution,
            "space": space,
            "repair_policy": repair_policy,
            "build": build,
            "validate": validate,
            "package": package,
            "publish": publish,
        }

    def variant_decl(self, name: str, base: str, *patches: Any) -> dict[str, Any]:
        return {
            "node_type": "variant",
            "name": name,
            "on": base,
            "patches": list(patches),
        }

    def kind(self, token: Any) -> str:
        return str(token)

    def defaults_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "defaults", "values": self._assignments(assignments, "defaults")}

    def repair_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "repair", "values": self._assignments(assignments, "repair")}

    def params_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "params", "values": self._assignments(assignments, "params")}

    def refs_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "refs", "values": self._assignments(assignments, "refs")}

    def intent_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "intent", "values": self._assignments(assignments, "intent")}

    def geometry_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "geometry", "values": self._assignments(assignments, "geometry")}

    def features_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "features", "values": self._assignments(assignments, "features")}

    def source_surface_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "source_surface", "values": self._assignments(assignments, "surface")}

    def assembly_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "assembly", "values": self._assignments(assignments, "assembly")}

    def fit_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "fit", "values": self._assignments(assignments, "fit")}

    def transfer_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "transfer", "values": self._assignments(assignments, "transfer")}

    def reuse_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "reuse", "values": self._assignments(assignments, "reuse")}

    def constraints_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "constraints", "values": self._assignments(assignments, "constraints")}

    def ingest_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "ingest", "values": self._assignments(assignments, "ingest")}

    def assembly_rules_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "assembly_rules", "values": self._assignments(assignments, "assembly_rules")}

    def execution_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "execution", "values": self._assignments(assignments, "execution")}

    def space_inline_block(self, *rest: Any) -> dict[str, Any]:
        return self._space_spec("space_inline", None, *rest)

    def search_inline_block(self, *rest: Any) -> dict[str, Any]:
        return self._space_spec("search_inline", None, *rest)

    def repair_policy_inline_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "repair_policy_inline", "values": self._assignments(assignments, "repair_policy")}

    def from_clause(self, name: str) -> dict[str, Any]:
        return {"node_type": "from_clause", "name": name}

    def shape_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "shape", "values": self._assignments(assignments, "shape")}

    def topology_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "topology", "values": self._assignments(assignments, "topology")}

    def uv_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "uv", "values": self._assignments(assignments, "uv")}

    def build_surface_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "surface", "values": self._assignments(assignments, "build.surface")}

    def rig_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "rig", "values": self._assignments(assignments, "rig")}

    def interfaces_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "interfaces", "values": self._assignments(assignments, "interfaces")}

    def physics_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "physics", "values": self._assignments(assignments, "physics")}

    def optimize_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "optimize", "values": self._assignments(assignments, "optimize")}

    def build_block(self, *stage_blocks: Any) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for item in stage_blocks:
            if item is None:
                continue
            values[item["node_type"]] = item["values"]
        return {"node_type": "build", "values": values}

    def validate_block(self, *items: Any) -> dict[str, Any]:
        rules: list[dict[str, Any]] = []
        values: dict[str, Any] = {}
        repair: dict[str, Any] = {}
        assignments: list[tuple[str, Any]] = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, dict) and item.get("node_type") == "rule":
                rules.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "repair":
                repair = item["values"]
            elif isinstance(item, tuple) and len(item) == 2:
                assignments.append(item)
            else:
                raise LatheParseError(f"Unexpected validate item: {item!r}")
        values.update(self._assignments(assignments, "validate"))
        values["rules"] = rules
        values["repair"] = repair
        return {"node_type": "validate", "values": values}

    def package_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "package", "values": self._assignments(assignments, "package")}

    def publish_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "publish", "values": self._assignments(assignments, "publish")}

    def ensure_rule(self, expr: Any) -> dict[str, Any]:
        return {"node_type": "rule", "kind": "ensure", "expr": expr}

    def prefer_rule(self, expr: Any, weight: Any = None) -> dict[str, Any]:
        rule = {"node_type": "rule", "kind": "prefer", "expr": expr}
        if weight is not None:
            rule["weight"] = float(weight)
        return rule

    def vary_stmt(self, path: str, domain: Any) -> dict[str, Any]:
        return {"node_type": "space_stmt", "kind": "vary", "path": path, "domain": domain}

    def freeze_stmt(self, path: str) -> dict[str, Any]:
        return {"node_type": "space_stmt", "kind": "freeze", "path": path}

    def objective_stmt(self, direction: str, metric: Any, weight: Any = None) -> dict[str, Any]:
        item = {"node_type": "space_stmt", "kind": "objective", "direction": direction, "metric": metric}
        if weight is not None:
            item["weight"] = float(weight)
        return item

    def maximize_dir(self) -> str:
        return "maximize"

    def minimize_dir(self) -> str:
        return "minimize"

    def select_best_of_stmt(self, value: int | float) -> dict[str, Any]:
        return {"node_type": "space_stmt", "kind": "select", "best_of": int(value)}

    def space_stmt(self, item: Any) -> Any:
        return item

    def assert_stmt(self, expr: Any) -> dict[str, Any]:
        return {"node_type": "assert", "expr": expr}

    def assign_stmt(self, path: str, value: Any) -> tuple[str, Any]:
        return (path, value)

    def set_patch(self, path: str, value: Any) -> dict[str, Any]:
        return {"op": "set", "path": path, "value": value}

    def append_patch(self, path: str, value: Any) -> dict[str, Any]:
        return {"op": "append", "path": path, "value": value}

    def remove_patch(self, path: str, value: Any) -> dict[str, Any]:
        return {"op": "remove", "path": path, "value": value}

    def unset_patch(self, path: str) -> dict[str, Any]:
        return {"op": "unset", "path": path}

    def list(self, *items: Any) -> list[Any]:
        return list(items)

    def call(self, name: str, args: list[Any] | None = None) -> dict[str, Any]:
        return {"type": "call", "name": name, "args": args or []}

    def args(self, *items: Any) -> list[Any]:
        return list(items)

    def named_arg(self, name: str, value: Any) -> dict[str, Any]:
        return {"name": name, "value": value}

    def positional_arg(self, value: Any) -> dict[str, Any]:
        return {"name": None, "value": value}

    def qident(self, first: str, *rest: str) -> str:
        return ".".join([first, *rest])

    def path(self, first: str, *rest: str) -> str:
        return ".".join([first, *rest])

    def ident_expr(self, name: str) -> str:
        return name

    def string_lit(self, token: str) -> str:
        return py_ast.literal_eval(token)

    def number(self, token: Any) -> int | float:
        return _num(str(token))

    def number_lit(self, value: int | float) -> int | float:
        return value

    def unit_lit(self, token: Any) -> dict[str, Any]:
        text = str(token)
        match = _UNIT_RE.match(text)
        if not match:
            raise LatheParseError(f"Invalid unit literal: {text}")
        return {
            "type": "unit",
            "value": _num(match.group("value")),
            "unit": match.group("unit"),
        }

    def true_lit(self) -> bool:
        return True

    def false_lit(self) -> bool:
        return False

    def range_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return {"type": "range", "from": left, "to": right}

    def not_expr(self, value: Any) -> dict[str, Any]:
        return {"type": "unary", "op": "not", "value": value}

    def neg_expr(self, value: Any) -> dict[str, Any]:
        return {"type": "unary", "op": "-", "value": value}

    def _binary(self, op: str, left: Any, right: Any) -> dict[str, Any]:
        return {"type": "binary", "op": op, "left": left, "right": right}

    def or_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("or", left, right)

    def and_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("and", left, right)

    def eq_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("==", left, right)

    def neq_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("!=", left, right)

    def lt_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("<", left, right)

    def lte_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("<=", left, right)

    def gt_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary(">", left, right)

    def gte_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary(">=", left, right)

    def in_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("in", left, right)

    def add_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("+", left, right)

    def sub_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("-", left, right)

    def mul_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("*", left, right)

    def div_expr(self, left: Any, right: Any) -> dict[str, Any]:
        return self._binary("/", left, right)

    def IDENT(self, token: Any) -> str:
        return str(token)

    def _assignments(self, assignments: Iterable[tuple[str, Any]], context: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for path, value in assignments:
            _set_nested(values, path, value, context)
        return values

    def _structured_decl(self, node_type: str, name: str, *rest: Any, kind: str | None = None) -> dict[str, Any]:
        uses: list[str] = []
        defaults: dict[str, Any] = {}
        params: dict[str, Any] = {}
        geometry: dict[str, Any] = {}
        features: dict[str, Any] = {}
        surface: dict[str, Any] = {}
        assembly: dict[str, Any] = {}
        space: dict[str, Any] = {}
        repair_policy: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        assigns: list[tuple[str, Any]] = []
        for item in rest:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, dict):
                node = item.get("node_type")
                if node == "defaults":
                    defaults = item["values"]
                elif node == "params":
                    params = item["values"]
                elif node == "geometry":
                    geometry = item["values"]
                elif node == "features":
                    features = item["values"]
                elif node == "source_surface":
                    surface = item["values"]
                elif node == "assembly":
                    assembly = item["values"]
                elif node == "space_inline":
                    space = item
                elif node == "search_inline":
                    space = item
                elif node == "repair_policy_inline":
                    repair_policy = item["values"]
                elif node == "rule":
                    rules.append(item)
                else:
                    raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
            elif isinstance(item, tuple) and len(item) == 2:
                assigns.append(item)
            else:
                raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
        return {
            "node_type": node_type,
            "name": name,
            "kind": kind,
            "uses": _dedupe_keep_first(uses),
            "defaults": defaults,
            "params": params,
            "geometry": geometry,
            "features": features,
            "surface": surface,
            "assembly": assembly,
            "space": space,
            "repair_policy": repair_policy,
            "rules": rules,
            "values": self._assignments(assigns, node_type),
        }

    def _mapping_decl(self, node_type: str, name: str, *rest: Any) -> dict[str, Any]:
        uses: list[str] = []
        assigns: list[tuple[str, Any]] = []
        for item in rest:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, tuple) and len(item) == 2:
                assigns.append(item)
            else:
                raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
        return {
            "node_type": node_type,
            "name": name,
            "uses": _dedupe_keep_first(uses),
            "values": self._assignments(assigns, node_type),
        }

    def _space_spec(self, node_type: str, name: str | None, *rest: Any) -> dict[str, Any]:
        assigns: list[tuple[str, Any]] = []
        vary: list[dict[str, Any]] = []
        freeze: list[str] = []
        objectives: list[dict[str, Any]] = []
        select: dict[str, Any] = {}
        for item in rest:
            if item is None:
                continue
            if isinstance(item, tuple) and len(item) == 2:
                assigns.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "space_stmt":
                kind = item["kind"]
                if kind == "vary":
                    vary.append({"path": item["path"], "domain": item["domain"]})
                elif kind == "freeze":
                    freeze.append(item["path"])
                elif kind == "objective":
                    objective = {"direction": item["direction"], "metric": item["metric"]}
                    if "weight" in item:
                        objective["weight"] = item["weight"]
                    objectives.append(objective)
                elif kind == "select":
                    select["best_of"] = item["best_of"]
            else:
                raise LatheParseError(f"Unexpected space item: {item!r}")
        payload = {
            "node_type": node_type,
            "values": self._assignments(assigns, "space"),
            "vary": vary,
            "freeze": _dedupe_keep_first(freeze),
            "objectives": objectives,
            "select": select,
        }
        if name is not None:
            payload["name"] = name
        return payload


TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<line_comment>//[^\n]*)
  | (?P<block_comment>/\*[\s\S]*?\*/)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<unit>-?(?:\d+\.\d+|\d+)(?:mm|cm|m|deg|rad|g|kg|ms|s|kb|mb|gb|px|px_per_m|px_per_cm)\b)
  | (?P<number>-?(?:\d+\.\d+|\d+))
  | (?P<op>\.\.|==|!=|<=|>=|[{}()\[\],:=.+\-*/<>])
  | (?P<ident>[a-z][a-z0-9_]*)
    """,
    re.VERBOSE,
)


class _TokenStream:
    def __init__(self, source: str) -> None:
        self.tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(source):
            match = TOKEN_RE.match(source, pos)
            if not match:
                snippet = source[pos : pos + 40].splitlines()[0]
                raise LatheParseError(f"Unexpected token near: {snippet!r}")
            pos = match.end()
            kind = match.lastgroup or ""
            value = match.group()
            if kind in {"ws", "line_comment", "block_comment"}:
                continue
            self.tokens.append((kind, value))
        self.tokens.append(("eof", ""))
        self.index = 0

    def peek(self, value: str | None = None) -> str:
        current = self.tokens[self.index][1]
        return current if value is None else current == value

    def kind(self) -> str:
        return self.tokens[self.index][0]

    def pop(self, expected: str | None = None) -> str:
        value = self.tokens[self.index][1]
        if expected is not None and value != expected:
            raise LatheParseError(f"Expected '{expected}', got '{value or 'end of file'}'")
        self.index += 1
        return value

    def pop_ident(self) -> str:
        if self.kind() != "ident":
            raise LatheParseError(f"Expected identifier, got '{self.peek() or 'end of file'}'")
        return self.pop()

    def eof(self) -> bool:
        return self.kind() == "eof"


class _FastParser:
    MAPPING_DECLS = {
        "library",
        "kit",
        "pattern",
        "material",
        "surface_program",
        "surface_backend",
        "surface_policy",
        "decal_library",
        "mask_program",
        "trim_sheet",
        "palette",
        "reference_set",
        "reconstruct_policy",
        "adapt_policy",
        "assembly_policy",
        "fit_profile",
        "transfer_rule",
        "execution_profile",
        "render_fixture",
        "bake_profile",
        "library_binding",
        "material_graph",
        "inspection_policy",
    }
    STRUCTURED_DECLS = {"family", "component", "assembly", "trait", "mechanism"}
    SIMPLE_MAPPING_DECLS = {"repair_policy", "fixture"}
    ASSET_BLOCKS = {
        "refs",
        "intent",
        "geometry",
        "features",
        "surface",
        "assembly",
        "fit",
        "transfer",
        "reuse",
        "constraints",
        "ingest",
        "assembly_rules",
        "execution",
        "package",
        "publish",
    }
    BUILD_BLOCKS = {"shape", "topology", "uv", "surface", "rig", "interfaces", "physics", "optimize"}
    DECL_KEYS = {
        "library": "libraries",
        "kit": "kits",
        "pattern": "patterns",
        "material": "materials",
        "surface_program": "surface_programs",
        "surface_backend": "surface_backends",
        "surface_policy": "surface_policies",
        "decal_library": "decal_libraries",
        "mask_program": "mask_programs",
        "trim_sheet": "trim_sheets",
        "palette": "palettes",
        "reference_set": "reference_sets",
        "reconstruct_policy": "reconstruct_policies",
        "adapt_policy": "adapt_policies",
        "assembly_policy": "assembly_policies",
        "fit_profile": "fit_profiles",
        "transfer_rule": "transfer_rules",
        "execution_profile": "execution_profiles",
        "render_fixture": "render_fixtures",
        "bake_profile": "bake_profiles",
        "library_binding": "library_bindings",
        "material_graph": "material_graphs",
        "inspection_policy": "inspection_policies",
    }
    STRUCTURED_KEYS = {
        "family": "families",
        "component": "components",
        "assembly": "assemblies",
        "trait": "traits",
        "mechanism": "mechanisms",
    }

    def __init__(self, source: str) -> None:
        self.ts = _TokenStream(source)

    def parse(self) -> dict[str, Any]:
        program = _empty_program()
        while not self.ts.eof():
            keyword = self.ts.pop_ident()
            if keyword == "module":
                program["module"] = self._qident()
            elif keyword == "import":
                program["imports"].append(self._qident())
            elif keyword in {"profile", "contract"}:
                program[f"{keyword}s"].append(self._profile_or_contract(keyword))
            elif keyword == "critic":
                program["critics"].append(self._critic())
            elif keyword in self.MAPPING_DECLS:
                program[self.DECL_KEYS[keyword]].append(self._mapping_decl(keyword))
            elif keyword in self.STRUCTURED_DECLS:
                node_type = "assembly_decl" if keyword == "assembly" else keyword
                program[self.STRUCTURED_KEYS[keyword]].append(self._structured_decl(node_type, keyword))
            elif keyword in self.SIMPLE_MAPPING_DECLS:
                key = "repair_policies" if keyword == "repair_policy" else "fixtures"
                program[key].append(self._simple_mapping_decl(keyword))
            elif keyword == "test":
                program["tests"].append(self._test_like("test"))
            elif keyword == "benchmark":
                program["benchmarks"].append(self._test_like("benchmark"))
            elif keyword == "space":
                program["spaces"].append(self._space_decl())
            elif keyword == "asset":
                program["assets"].append(self._asset_decl())
            elif keyword == "variant":
                program["variants"].append(self._variant_decl())
            else:
                raise LatheParseError(f"Unknown declaration '{keyword}'")
        program["imports"] = _dedupe_keep_first(program["imports"])
        return program

    def _qident(self) -> str:
        parts = [self.ts.pop_ident()]
        while self.ts.peek("."):
            self.ts.pop(".")
            parts.append(self.ts.pop_ident())
        return ".".join(parts)

    def _path(self) -> str:
        return self._qident()

    def _optional_uses(self) -> list[str]:
        if not self.ts.peek("uses"):
            return []
        self.ts.pop("uses")
        uses = [self._qident()]
        while self.ts.peek(","):
            self.ts.pop(",")
            uses.append(self._qident())
        return uses

    def _profile_or_contract(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        uses = self._optional_uses()
        defaults: dict[str, Any] = {}
        repair: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            keyword = self.ts.pop_ident()
            if keyword == "defaults":
                defaults = self._assign_block("defaults")
            elif keyword == "repair":
                repair = self._assign_block("repair")
            elif keyword in {"ensure", "prefer"}:
                rules.append(self._rule(keyword))
            else:
                raise LatheParseError(f"Unexpected {node_type} item '{keyword}'")
        self.ts.pop("}")
        return {"node_type": node_type, "name": name, "uses": _dedupe_keep_first(uses), "defaults": defaults, "rules": rules, "repair": repair}

    def _critic(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        self.ts.pop("(")
        param = self.ts.pop_ident()
        self.ts.pop(":")
        asset_type = self.ts.pop_ident()
        if asset_type != "asset":
            raise LatheParseError("Critic parameter type must be asset")
        self.ts.pop(")")
        self.ts.pop("=")
        if self.ts.peek("weighted"):
            self.ts.pop("weighted")
            self.ts.pop("{")
            items = []
            while not self.ts.peek("}"):
                metric = self._metric_ref()
                weight = self._number_value()
                items.append({"metric": metric, "weight": float(weight)})
            self.ts.pop("}")
            body: Any = {"type": "weighted", "items": items}
        else:
            body = self._expr()
        return {"node_type": "critic", "name": name, "param": {"name": param, "type": "asset"}, "body": body}

    def _mapping_decl(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        uses = self._optional_uses()
        values = self._assign_block(node_type)
        return {"node_type": node_type, "name": name, "uses": _dedupe_keep_first(uses), "values": values}

    def _simple_mapping_decl(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values = self._assign_block(node_type)
        return {"node_type": node_type, "name": name, "values": values}

    def _structured_decl(self, node_type: str, keyword: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        decl_kind = None
        if keyword == "family" and self.ts.peek(":"):
            self.ts.pop(":")
            decl_kind = self.ts.pop_ident()
        uses = self._optional_uses()
        defaults: dict[str, Any] = {}
        params: dict[str, Any] = {}
        geometry: dict[str, Any] = {}
        features: dict[str, Any] = {}
        surface: dict[str, Any] = {}
        assembly: dict[str, Any] = {}
        space: dict[str, Any] = {}
        repair_policy: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        assigns: list[tuple[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item in {"defaults", "params", "geometry", "features", "surface", "assembly"}:
                values = self._assign_block(item)
                if item == "defaults":
                    defaults = values
                elif item == "params":
                    params = values
                elif item == "geometry":
                    geometry = values
                elif item == "features":
                    features = values
                elif item == "surface":
                    surface = values
                elif item == "assembly":
                    assembly = values
            elif item in {"space", "search"}:
                space = self._space_body("space_inline" if item == "space" else "search_inline")
            elif item == "repair_policy":
                repair_policy = self._assign_block("repair_policy")
            elif item in {"ensure", "prefer"}:
                rules.append(self._rule(item))
            else:
                assigns.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        return {
            "node_type": node_type,
            "name": name,
            "kind": decl_kind,
            "uses": _dedupe_keep_first(uses),
            "defaults": defaults,
            "params": params,
            "geometry": geometry,
            "features": features,
            "surface": surface,
            "assembly": assembly,
            "space": space,
            "repair_policy": repair_policy,
            "rules": rules,
            "values": self._assignments(assigns, node_type),
        }

    def _asset_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        self.ts.pop(":")
        kind = self.ts.pop_ident()
        from_family = ""
        if self.ts.peek("from"):
            self.ts.pop("from")
            from_family = self._qident()
        uses = self._optional_uses()
        values: dict[str, Any] = {
            "node_type": "asset",
            "name": name,
            "kind": kind,
            "from": from_family,
            "uses": _dedupe_keep_first(uses),
            "refs": {},
            "intent": {},
            "geometry": {},
            "features": {},
            "surface": {},
            "assembly": {},
            "fit": {},
            "transfer": {},
            "reuse": {},
            "constraints": {},
            "ingest": {},
            "assembly_rules": {},
            "execution": {},
            "space": {},
            "repair_policy": {},
            "build": {},
            "validate": {},
            "package": {},
            "publish": {},
        }
        self.ts.pop("{")
        while not self.ts.peek("}"):
            block = self.ts.pop_ident()
            if block in self.ASSET_BLOCKS:
                key = "surface" if block == "surface" else block
                values[key] = self._assign_block(block)
            elif block in {"space", "search"}:
                values["space"] = self._space_body("space_inline" if block == "space" else "search_inline")
            elif block == "repair_policy":
                values["repair_policy"] = self._assign_block("repair_policy")
            elif block == "build":
                values["build"] = self._build_block()
            elif block == "validate":
                values["validate"] = self._validate_block()
            else:
                raise LatheParseError(f"Unexpected asset block '{block}'")
        self.ts.pop("}")
        return values

    def _build_block(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            block = self.ts.pop_ident()
            if block not in self.BUILD_BLOCKS:
                raise LatheParseError(f"Unexpected build block '{block}'")
            values[block] = self._assign_block(block)
        self.ts.pop("}")
        return values

    def _validate_block(self) -> dict[str, Any]:
        assignments: list[tuple[str, Any]] = []
        rules: list[dict[str, Any]] = []
        repair: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item in {"ensure", "prefer"}:
                rules.append(self._rule(item))
            elif item == "repair":
                repair = self._assign_block("repair")
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "validate")
        values["rules"] = rules
        values["repair"] = repair
        return values

    def _test_like(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values: list[tuple[str, Any]] = []
        asserts: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "assert":
                asserts.append({"node_type": "assert", "expr": self._expr()})
            else:
                values.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        return {"node_type": node_type, "name": name, "values": self._assignments(values, node_type), "asserts": asserts}

    def _space_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        payload = self._space_body("space_decl")
        payload["name"] = name
        return payload

    def _space_body(self, node_type: str) -> dict[str, Any]:
        assigns: list[tuple[str, Any]] = []
        vary: list[dict[str, Any]] = []
        freeze: list[str] = []
        objectives: list[dict[str, Any]] = []
        select: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "vary":
                vary.append({"path": self._path(), "domain": self._expect_in_expr()})
            elif item == "freeze":
                freeze.append(self._path())
            elif item == "objective":
                direction = self.ts.pop_ident()
                if direction not in {"maximize", "minimize"}:
                    raise LatheParseError("objective must use maximize or minimize")
                metric = self._metric_ref()
                objective = {"direction": direction, "metric": metric}
                if self.ts.peek("weight"):
                    self.ts.pop("weight")
                    objective["weight"] = float(self._number_value())
                objectives.append(objective)
            elif item == "select":
                if self.ts.pop_ident() != "best_of":
                    raise LatheParseError("select currently supports best_of")
                select["best_of"] = int(self._number_value())
            else:
                assigns.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        return {
            "node_type": node_type,
            "values": self._assignments(assigns, "space"),
            "vary": vary,
            "freeze": _dedupe_keep_first(freeze),
            "objectives": objectives,
            "select": select,
        }

    def _variant_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        if self.ts.pop_ident() != "on":
            raise LatheParseError("variant requires 'on'")
        base = self._qident()
        patches = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            op = self.ts.pop_ident()
            if op not in {"set", "append", "remove", "unset"}:
                raise LatheParseError(f"Unknown patch op '{op}'")
            path = self._path()
            patch = {"op": op, "path": path}
            if op != "unset":
                patch["value"] = self._assign_value()
            patches.append(patch)
        self.ts.pop("}")
        return {"node_type": "variant", "name": name, "on": base, "patches": patches}

    def _assign_block(self, context: str) -> dict[str, Any]:
        assignments: list[tuple[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            path = self._path()
            assignments.append((path, self._assign_value()))
        self.ts.pop("}")
        return self._assignments(assignments, context)

    def _assign_value(self) -> Any:
        self.ts.pop("=")
        return self._expr()

    def _expect_in_expr(self) -> Any:
        if self.ts.pop_ident() != "in":
            raise LatheParseError("vary requires 'in'")
        return self._expr()

    def _finish_path(self, first: str) -> str:
        parts = [first]
        while self.ts.peek("."):
            self.ts.pop(".")
            parts.append(self.ts.pop_ident())
        return ".".join(parts)

    def _rule(self, kind: str) -> dict[str, Any]:
        rule = {"node_type": "rule", "kind": kind, "expr": self._expr()}
        if kind == "prefer" and self.ts.peek("weight"):
            self.ts.pop("weight")
            rule["weight"] = float(self._number_value())
        return rule

    def _metric_ref(self) -> Any:
        return self._atom()

    def _expr(self) -> Any:
        return self._or_expr()

    def _or_expr(self) -> Any:
        left = self._and_expr()
        while self.ts.peek("or"):
            self.ts.pop("or")
            left = {"type": "binary", "op": "or", "left": left, "right": self._and_expr()}
        return left

    def _and_expr(self) -> Any:
        left = self._equality()
        while self.ts.peek("and"):
            self.ts.pop("and")
            left = {"type": "binary", "op": "and", "left": left, "right": self._equality()}
        return left

    def _equality(self) -> Any:
        left = self._comparison()
        while self.ts.peek() in {"==", "!="}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._comparison()}
        return left

    def _comparison(self) -> Any:
        left = self._sum()
        while self.ts.peek() in {"<", "<=", ">", ">=", "in"}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._sum()}
        return left

    def _sum(self) -> Any:
        left = self._term()
        while self.ts.peek() in {"+", "-"}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._term()}
        return left

    def _term(self) -> Any:
        left = self._factor()
        while self.ts.peek() in {"*", "/"}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._factor()}
        return left

    def _factor(self) -> Any:
        if self.ts.peek("not"):
            self.ts.pop("not")
            return {"type": "unary", "op": "not", "value": self._factor()}
        if self.ts.peek("-") and self.ts.kind() == "op":
            self.ts.pop("-")
            return {"type": "unary", "op": "-", "value": self._factor()}
        return self._range()

    def _range(self) -> Any:
        left = self._atom()
        if self.ts.peek(".."):
            self.ts.pop("..")
            return {"type": "range", "from": left, "to": self._atom()}
        return left

    def _atom(self) -> Any:
        kind = self.ts.kind()
        value = self.ts.peek()
        if value == "(":
            self.ts.pop("(")
            expr = self._expr()
            self.ts.pop(")")
            return expr
        if value == "[":
            return self._list()
        if kind == "string":
            return py_ast.literal_eval(self.ts.pop())
        if kind == "unit":
            return self._unit_value(self.ts.pop())
        if kind == "number":
            return self._number_value()
        if kind == "ident":
            name = self._qident()
            if name == "true":
                return True
            if name == "false":
                return False
            if self.ts.peek("("):
                return self._call_after_name(name)
            return name
        raise LatheParseError(f"Expected expression, got '{value or 'end of file'}'")

    def _list(self) -> list[Any]:
        items: list[Any] = []
        self.ts.pop("[")
        while not self.ts.peek("]"):
            items.append(self._expr())
            if self.ts.peek(","):
                self.ts.pop(",")
                if self.ts.peek("]"):
                    break
            else:
                break
        self.ts.pop("]")
        return items

    def _call_after_name(self, name: str) -> dict[str, Any]:
        args = []
        self.ts.pop("(")
        while not self.ts.peek(")"):
            if self.ts.kind() == "ident" and self.ts.tokens[self.ts.index + 1][1] == ":":
                arg_name = self.ts.pop_ident()
                self.ts.pop(":")
                args.append({"name": arg_name, "value": self._expr()})
            else:
                args.append({"name": None, "value": self._expr()})
            if self.ts.peek(","):
                self.ts.pop(",")
                if self.ts.peek(")"):
                    break
            else:
                break
        self.ts.pop(")")
        return {"type": "call", "name": name, "args": args}

    def _number_value(self) -> int | float:
        if self.ts.kind() != "number":
            raise LatheParseError(f"Expected number, got '{self.ts.peek()}'")
        return _num(self.ts.pop())

    def _unit_value(self, text: str) -> dict[str, Any]:
        match = _UNIT_RE.match(text)
        if not match:
            raise LatheParseError(f"Invalid unit literal: {text}")
        return {"type": "unit", "value": _num(match.group("value")), "unit": match.group("unit")}

    def _assignments(self, assignments: Iterable[tuple[str, Any]], context: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for path, value in assignments:
            _set_nested(values, path, value, context)
        return values


def parse_text(source: str) -> dict[str, Any]:
    try:
        return _FastParser(source).parse()
    except Exception as exc:  # noqa: BLE001
        raise LatheParseError(str(exc)) from exc


def _parse_file_recursive(path: Path, stack: list[Path], cache: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in stack:
        cycle = " -> ".join(str(item) for item in [*stack, resolved])
        raise LatheParseError(f"Import cycle detected: {cycle}")
    if resolved in cache:
        return deepcopy(cache[resolved])

    raw = parse_text(resolved.read_text(encoding="utf-8"))
    merged_imports = _empty_program()
    for import_name in raw.get("imports", []):
        import_path = _resolve_import_path(resolved, import_name)
        imported = _parse_file_recursive(import_path, [*stack, resolved], cache)
        merged_imports = _merge_programs(merged_imports, imported)

    merged = _merge_programs(merged_imports, raw)
    cache[resolved] = deepcopy(merged)
    return merged


def parse_file(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    program = _parse_file_recursive(resolved, [], {})
    program["_source_path"] = str(resolved)
    return program


if __name__ == "__main__":
    import sys

    program = parse_file(sys.argv[1])
    print(json.dumps(program, indent=2, sort_keys=False))
