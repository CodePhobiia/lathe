"""``uses``/profile/variant resolver for the normalized AST.

Walks ``uses`` chains, applies profile and contract inheritance, and
overlays variant patches to produce a single materialized asset that
the checker and planner can reason about without further lookups.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from .asset_class_profiles import (
    GENERIC_ASSET_CLASS,
    cascade_into_asset,
    resolve_asset_class_profile,
)

# re-export — authoritative definitions live in lathe/errors.py
from .errors import ResolutionError, UnresolvedNameError
from .logging_utils import debug as log_debug
from .normalizer import normalize_asset
from .paths import PathGuardError, safe_resolve
from .utils import append_by_path, deep_merge, has_path, remove_by_path, set_by_path, unset_by_path

__all__ = ["ResolutionError", "Resolver", "UnresolvedNameError", "materialize_asset"]


log = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_optional(name: str, mapping: dict[str, Any], kind: str) -> Any | None:
    if name in mapping:
        return mapping[name]
    log_debug(
        log,
        "lathe.resolver.optional_reference_missing",
        "skipping optional {kind} {name!r}: not in map",
        kind=kind,
        name=name,
    )
    return None


def _dedupe(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        key = repr(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _parse_semver(version: str) -> tuple[int, int, int] | None:
    """Parse a dotted semver-style version into a (major, minor, patch) tuple.

    Returns ``None`` for empty or unparseable inputs. Trailing components
    default to zero (e.g. ``"1.2"`` → ``(1, 2, 0)``).
    """
    if not version:
        return None
    parts = version.strip().split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _version_satisfies(version: str, constraint: str) -> bool:
    """Return True when ``version`` satisfies the npm-style ``constraint``.

    Supported constraint forms:
    - ``""`` (empty) → always satisfied (legacy / unversioned kit).
    - ``"=1.2.3"`` exact pin.
    - ``"^1.2.3"`` caret: same major (``>=1.2.3, <2.0.0``).
    - ``"~1.2.3"`` tilde: same minor (``>=1.2.3, <1.3.0``).
    - ``">=1.2.3"`` / ``">1.2.3"`` / ``"<=1.2.3"`` / ``"<1.2.3"`` range.
    - bare ``"1.2.3"`` is treated as ``=1.2.3``.
    """
    if not constraint:
        return True
    constraint = constraint.strip()
    parsed_version = _parse_semver(version)
    if parsed_version is None:
        return False
    if constraint.startswith("^"):
        target = _parse_semver(constraint[1:])
        if target is None:
            return False
        return parsed_version >= target and parsed_version[0] == target[0]
    if constraint.startswith("~"):
        target = _parse_semver(constraint[1:])
        if target is None:
            return False
        return (
            parsed_version >= target
            and parsed_version[0] == target[0]
            and parsed_version[1] == target[1]
        )
    for prefix, op in ((">=", "ge"), ("<=", "le"), (">", "gt"), ("<", "lt"), ("=", "eq")):
        if constraint.startswith(prefix):
            target = _parse_semver(constraint[len(prefix) :])
            if target is None:
                return False
            if op == "ge":
                return parsed_version >= target
            if op == "le":
                return parsed_version <= target
            if op == "gt":
                return parsed_version > target
            if op == "lt":
                return parsed_version < target
            return parsed_version == target
    target = _parse_semver(constraint)
    if target is None:
        return False
    return parsed_version == target


_HDA_PARAMETER_TYPES = {
    "number",
    "int",
    "boolean",
    "string",
    "enum",
    "vec2",
    "vec3",
    "vec4",
    "color",
}


def _validate_kit_ports_and_parameters(
    resolved_kit: dict[str, Any], bindings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return diagnostics for unwired ports and out-of-range parameters.

    The kit's input ports must each be present in ``bindings`` (which holds
    the asset-side wiring expressions). Output ports are informational and
    not checked here. Parameters with explicit ``min``/``max``/``enum``
    options have their bound values range-checked.
    """
    diags: list[dict[str, Any]] = []
    if not resolved_kit:
        return diags
    ports = resolved_kit.get("ports", []) or []
    parameters = resolved_kit.get("parameters", []) or []
    if not ports and not parameters:
        return diags
    binding_names = set(bindings.keys()) if isinstance(bindings, dict) else set()
    for port in ports:
        if not isinstance(port, dict):
            continue
        if port.get("direction") != "in":
            continue
        port_name = str(port.get("name", ""))
        if not port_name:
            continue
        if port_name not in binding_names:
            diags.append(
                {
                    "code": "K6502",
                    "kit": resolved_kit.get("name", ""),
                    "port": port_name,
                    "message": (
                        f"required input port '{port_name}' on kit "
                        f"'{resolved_kit.get('name', '')}' is not wired"
                    ),
                }
            )
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        param_name = str(parameter.get("name", ""))
        if not param_name or param_name not in binding_names:
            continue
        param_type = str(parameter.get("param_type", ""))
        if param_type and param_type not in _HDA_PARAMETER_TYPES:
            diags.append(
                {
                    "code": "K6505",
                    "kit": resolved_kit.get("name", ""),
                    "parameter": param_name,
                    "message": (
                        f"parameter '{param_name}' on kit "
                        f"'{resolved_kit.get('name', '')}' has unknown type '{param_type}'"
                    ),
                }
            )
        options = parameter.get("options", {}) or {}
        bound_value = bindings.get(param_name)
        if param_type in {"number", "int"} and isinstance(bound_value, (int, float)):
            if "min" in options and bound_value < options["min"]:
                diags.append(
                    {
                        "code": "K6503",
                        "kit": resolved_kit.get("name", ""),
                        "parameter": param_name,
                        "message": (
                            f"parameter '{param_name}'={bound_value} below "
                            f"minimum {options['min']}"
                        ),
                    }
                )
            if "max" in options and bound_value > options["max"]:
                diags.append(
                    {
                        "code": "K6503",
                        "kit": resolved_kit.get("name", ""),
                        "parameter": param_name,
                        "message": (
                            f"parameter '{param_name}'={bound_value} above "
                            f"maximum {options['max']}"
                        ),
                    }
                )
        if param_type == "enum" and isinstance(bound_value, str):
            allowed = options.get("values") or options.get("enum") or []
            if isinstance(allowed, list) and allowed and bound_value not in allowed:
                diags.append(
                    {
                        "code": "K6504",
                        "kit": resolved_kit.get("name", ""),
                        "parameter": param_name,
                        "message": (
                            f"parameter '{param_name}'='{bound_value}' is not "
                            f"one of {allowed}"
                        ),
                    }
                )
    return diags


def _merge_space_spec(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base or {})
    overlay = deepcopy(overlay or {})
    merged["use"] = overlay.get("use") or merged.get("use", "")
    merged["values"] = deep_merge(merged.get("values", {}), overlay.get("values", {}))
    merged["vary"] = [*merged.get("vary", []), *overlay.get("vary", [])]
    merged["freeze"] = _dedupe([*merged.get("freeze", []), *overlay.get("freeze", [])])
    merged["objectives"] = [*merged.get("objectives", []), *overlay.get("objectives", [])]
    merged["select"] = deep_merge(merged.get("select", {}), overlay.get("select", {}))
    return merged


def _merge_repair_policy_spec(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base or {})
    overlay = deepcopy(overlay or {})
    if overlay.get("use"):
        merged["use"] = overlay["use"]
    if overlay.get("mode"):
        merged["mode"] = overlay["mode"]
    if overlay.get("max_rounds") is not None:
        merged["max_rounds"] = overlay["max_rounds"]
    merged["allow"] = _dedupe([*merged.get("allow", []), *overlay.get("allow", [])])
    merged["deny"] = _dedupe([*merged.get("deny", []), *overlay.get("deny", [])])
    return merged


def _repair_policy_to_validate_repair(
    source_policy: dict[str, Any], validate_repair: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(validate_repair or {})
    if source_policy.get("mode"):
        merged["mode"] = source_policy["mode"]
    if source_policy.get("max_rounds") is not None:
        merged["max_rounds"] = source_policy["max_rounds"]
    merged["allow"] = _dedupe([*merged.get("allow", []), *source_policy.get("allow", [])])
    merged["deny"] = _dedupe([*merged.get("deny", []), *source_policy.get("deny", [])])
    return merged


class Resolver:
    """Resolver."""

    def __init__(self, program: dict[str, Any]) -> None:
        self.program = program
        self.profile_map = {decl["name"]: decl for decl in program.get("profiles", [])}
        self.contract_map = {decl["name"]: decl for decl in program.get("contracts", [])}
        self.library_map = {decl["name"]: decl for decl in program.get("libraries", [])}
        self.kit_map = {decl["name"]: decl for decl in program.get("kits", [])}
        self.pattern_map = {decl["name"]: decl for decl in program.get("patterns", [])}
        self.family_map = {decl["name"]: decl for decl in program.get("families", [])}
        self.component_map = {decl["name"]: decl for decl in program.get("components", [])}
        self.assembly_decl_map = {decl["name"]: decl for decl in program.get("assemblies", [])}
        self.trait_map = {decl["name"]: decl for decl in program.get("traits", [])}
        self.mechanism_map = {decl["name"]: decl for decl in program.get("mechanisms", [])}
        self.material_map = {decl["name"]: decl for decl in program.get("materials", [])}
        self.surface_program_map = {decl["name"]: decl for decl in program.get("surface_programs", [])}
        self.surface_backend_map = {decl["name"]: decl for decl in program.get("surface_backends", [])}
        self.surface_policy_map = {decl["name"]: decl for decl in program.get("surface_policies", [])}
        self.decal_library_map = {decl["name"]: decl for decl in program.get("decal_libraries", [])}
        self.mask_program_map = {decl["name"]: decl for decl in program.get("mask_programs", [])}
        self.trim_sheet_map = {decl["name"]: decl for decl in program.get("trim_sheets", [])}
        self.palette_map = {decl["name"]: decl for decl in program.get("palettes", [])}
        self.style_pack_map = {decl["name"]: decl for decl in program.get("style_packs", [])}
        # Roadmap §6.8: style_bridges are program-level decls that sanction
        # otherwise-incompatible style-stack pairings (e.g. Borderlands-style
        # PBR base + cel ramp overlay). The checker reads this map to decide
        # whether to suppress L6810-L6817 refusal diagnostics.
        self.style_bridge_map = {
            decl["name"]: decl for decl in program.get("style_bridges", [])
        }
        self.reference_set_map = {decl["name"]: decl for decl in program.get("reference_sets", [])}
        self.reconstruct_policy_map = {decl["name"]: decl for decl in program.get("reconstruct_policies", [])}
        self.adapt_policy_map = {decl["name"]: decl for decl in program.get("adapt_policies", [])}
        self.assembly_policy_map = {decl["name"]: decl for decl in program.get("assembly_policies", [])}
        self.fit_profile_map = {decl["name"]: decl for decl in program.get("fit_profiles", [])}
        self.transfer_rule_map = {decl["name"]: decl for decl in program.get("transfer_rules", [])}
        self.execution_profile_map = {decl["name"]: decl for decl in program.get("execution_profiles", [])}
        self.render_fixture_map = {decl["name"]: decl for decl in program.get("render_fixtures", [])}
        self.bake_profile_map = {decl["name"]: decl for decl in program.get("bake_profiles", [])}
        self.library_binding_map = {decl["name"]: decl for decl in program.get("library_bindings", [])}
        self.material_graph_map = {decl["name"]: decl for decl in program.get("material_graphs", [])}
        self.inspection_policy_map = {decl["name"]: decl for decl in program.get("inspection_policies", [])}
        self.asset_class_profile_map = {
            decl["name"]: decl for decl in program.get("asset_class_profiles", [])
        }
        self.vegetation_species_map = {
            decl["name"]: decl for decl in program.get("vegetation_species", [])
        }
        self.vegetation_kit_map = {
            decl["name"]: decl for decl in program.get("vegetation_kits", [])
        }
        self.wind_program_map = {
            decl["name"]: decl for decl in program.get("wind_programs", [])
        }
        self.repair_policy_map = {decl["name"]: decl for decl in program.get("repair_policies", [])}
        self.fixture_map = {decl["name"]: decl for decl in program.get("fixtures", [])}
        self.test_map = {decl["name"]: decl for decl in program.get("tests", [])}
        self.benchmark_map = {decl["name"]: decl for decl in program.get("benchmarks", [])}
        self.space_map = {decl["name"]: decl for decl in program.get("spaces", [])}
        self.world_map = {decl["name"]: decl for decl in program.get("worlds", [])}
        self.scene_map = {decl["name"]: decl for decl in program.get("scenes", [])}
        self.asset_map = {decl["name"]: decl for decl in program.get("assets", [])}
        self.variant_map = {decl["name"]: decl for decl in program.get("variants", [])}

    def _resolve_use_decl(self, name: str, caller_type: str) -> tuple[str, dict[str, Any]]:
        in_profiles = name in self.profile_map
        in_contracts = name in self.contract_map
        if in_profiles and in_contracts:
            raise ResolutionError(
                f"Ambiguous use reference '{name}' found in both profile and contract namespaces"
            )
        if caller_type == "profile" and in_contracts:
            raise ResolutionError(f"Profile cannot use contract '{name}'")
        if in_profiles:
            return "profile", self.profile_map[name]
        if in_contracts:
            return "contract", self.contract_map[name]
        raise ResolutionError(f"Unknown use reference '{name}'")

    def _resolve_named_decl(
        self, namespace: dict[str, dict[str, Any]], name: str, label: str
    ) -> dict[str, Any]:
        if name not in namespace:
            raise ResolutionError(f"Unknown {label} reference '{name}'")
        return namespace[name]

    def resolve_use_chain(self, uses: list[str]) -> list[dict[str, Any]]:
        """Resolve use chain.

        Args:
            uses: uses argument.

        Returns:
            The result.
        """
        ordered: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def walk(name: str, caller_type: str, stack: list[tuple[str, str]]) -> None:
            decl_type, decl = self._resolve_use_decl(name, caller_type)
            key = (decl_type, decl["name"])
            if key in stack:
                cycle = " -> ".join(n for _, n in [*stack, key])
                raise ResolutionError(f"Use cycle detected: {cycle}")
            stack.append(key)
            for dep in decl.get("uses", []):
                walk(dep, decl_type, stack)
            stack.pop()
            if key not in seen:
                seen.add(key)
                ordered.append(decl)

        for use_name in uses:
            walk(use_name, "asset", [])
        return ordered

    def derive_explicit_asset(self, name: str) -> dict[str, Any]:
        """Derive explicit asset.

        Args:
            name: name argument.

        Returns:
            The result.
        """
        if name in self.asset_map:
            asset = deepcopy(self.asset_map[name])
            asset["node_type"] = "asset"
            return asset
        if name in self.variant_map:
            variant = self.variant_map[name]
            base = self.derive_explicit_asset(variant["on"])
            base["name"] = variant["name"]
            for patch in variant.get("patches", []):
                self.apply_patch(base, patch)
            return base
        raise ResolutionError(f"Unknown asset or variant '{name}'")

    def apply_patch(self, asset: dict[str, Any], patch: dict[str, Any]) -> None:
        """Apply patch.

        Args:
            asset: asset argument.
            patch: patch argument.
        """
        path = patch["path"]
        if path == "name":
            raise ResolutionError("Variants may not patch 'name'")
        op = patch["op"]
        if op == "set":
            set_by_path(asset, path, patch["value"])
        elif op == "append":
            if not has_path(asset, path):
                set_by_path(asset, path, [])
            append_by_path(asset, path, patch["value"])
        elif op == "remove":
            if has_path(asset, path):
                remove_by_path(asset, path, patch["value"])
        elif op == "unset":
            unset_by_path(asset, path)
        else:
            raise ResolutionError(f"Unknown patch op '{op}'")

    def resolve_space_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Resolve space spec.

        Args:
            spec: spec argument.

        Returns:
            The result.
        """
        spec = deepcopy(spec or {})
        use_name = spec.get("use") or spec.get("values", {}).get("use")
        base: dict[str, Any] = {}
        resolved_name = ""
        if use_name:
            decl = self._resolve_named_decl(self.space_map, use_name, "space")
            base = {
                "use": use_name,
                "values": deepcopy(decl.get("values", {})),
                "vary": deepcopy(decl.get("vary", [])),
                "freeze": deepcopy(decl.get("freeze", [])),
                "objectives": deepcopy(decl.get("objectives", [])),
                "select": deepcopy(decl.get("select", {})),
            }
            resolved_name = use_name
        merged = _merge_space_spec(base, spec)
        merged["resolved_name"] = resolved_name
        return merged

    def resolve_repair_policy_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Resolve repair policy spec.

        Args:
            spec: spec argument.

        Returns:
            The result.
        """
        spec = deepcopy(spec or {})
        use_name = spec.get("use")
        base: dict[str, Any] = {}
        resolved_name = ""
        if use_name:
            decl = self._resolve_named_decl(self.repair_policy_map, use_name, "repair_policy")
            values = decl.get("values", {})
            base = {
                "use": use_name,
                "mode": decl.get("mode", values.get("mode")),
                "max_rounds": decl.get("max_rounds", values.get("max_rounds")),
                "allow": deepcopy(decl.get("allow", values.get("allow", []))),
                "deny": deepcopy(decl.get("deny", values.get("deny", []))),
            }
            resolved_name = use_name
        merged = _merge_repair_policy_spec(base, spec)
        merged["resolved_name"] = resolved_name
        return merged

    def _resolve_palette(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.palette_map, name, "palette"))

    def _resolve_material(self, name: str) -> dict[str, Any]:
        if name in self.material_map:
            return deepcopy(self.material_map[name])
        return {"node_type": "material", "name": name, "uses": [], "values": {}}

    def _resolve_surface_program(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.surface_program_map, name, "surface_program"))

    def _resolve_surface_backend(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.surface_backend_map, name, "surface_backend"))

    def _resolve_surface_policy(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.surface_policy_map, name, "surface_policy"))

    def _resolve_decal_library(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.decal_library_map, name, "decal_library"))

    def _resolve_mask_program(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.mask_program_map, name, "mask_program"))

    def _resolve_trim_sheet(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.trim_sheet_map, name, "trim_sheet"))

    def _resolve_pattern(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.pattern_map, name, "pattern"))

    def _resolve_component(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.component_map, name, "component"))

    def _resolve_trait(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.trait_map, name, "trait"))

    def _resolve_mechanism(self, name: str) -> dict[str, Any]:
        return deepcopy(self._resolve_named_decl(self.mechanism_map, name, "mechanism"))

    def _resolve_mapping_optional(
        self, namespace: dict[str, dict[str, Any]], name: str, label: str
    ) -> dict[str, Any]:
        if not name:
            return {}
        return deepcopy(self._resolve_named_decl(namespace, name, label))

    def _resolve_reference_sets(self, refs: dict[str, Any]) -> dict[str, Any]:
        refs = deepcopy(refs or {})
        reference_set_names = list(refs.get("reference_sets", []))
        resolved_sets: list[dict[str, Any]] = []
        merged = {
            "images": list(refs.get("images", [])),
            "meshes": list(refs.get("meshes", [])),
            "assets": list(refs.get("assets", [])),
            "materials": list(refs.get("materials", [])),
            "notes": list(refs.get("notes", [])),
            "reference_sets": reference_set_names,
        }
        for name in reference_set_names:
            decl = self._resolve_named_decl(self.reference_set_map, name, "reference_set")
            resolved_sets.append(decl)
            values = decl.get("values", {})
            for key in ("images", "meshes", "assets", "materials", "notes"):
                merged[key] = _dedupe([*merged.get(key, []), *values.get(key, [])])
        merged["resolved_reference_sets"] = resolved_sets
        return merged

    def _resolve_named_policies(self, asset: dict[str, Any]) -> dict[str, Any]:
        shape_cfg = asset.get("build", {}).get("shape", {})
        fit_profile_name = str(shape_cfg.get("fit_profile", "") or asset.get("fit", {}).get("profile", ""))
        reconstruct_policy_name = str(
            shape_cfg.get("reconstruct_policy", "") or asset.get("fit", {}).get("reconstruct_policy", "")
        )
        adapt_policy_name = str(
            shape_cfg.get("adapt_policy", "") or asset.get("transfer", {}).get("adapt_policy", "")
        )
        assembly_policy_name = str(
            shape_cfg.get("assembly_policy", "") or asset.get("constraints", {}).get("assembly_policy", "")
        )
        transfer_rule_names = list(asset.get("transfer", {}).get("rules", []))
        return {
            "fit_profile": self._resolve_mapping_optional(
                self.fit_profile_map, fit_profile_name, "fit_profile"
            ),
            "reconstruct_policy": self._resolve_mapping_optional(
                self.reconstruct_policy_map, reconstruct_policy_name, "reconstruct_policy"
            ),
            "adapt_policy": self._resolve_mapping_optional(
                self.adapt_policy_map, adapt_policy_name, "adapt_policy"
            ),
            "assembly_policy": self._resolve_mapping_optional(
                self.assembly_policy_map, assembly_policy_name, "assembly_policy"
            ),
            "transfer_rules": self._resolve_optional_list(
                transfer_rule_names, self.transfer_rule_map, "transfer_rule"
            ),
        }

    def _resolve_optional_list(
        self,
        names: list[str],
        mapping: dict[str, dict[str, Any]],
        kind: str,
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for item in names:
            decl = _resolve_optional(item, mapping, kind)
            if decl is None:
                continue
            resolved.append(deepcopy(decl))
        return resolved

    def materialize_asset(self, name: str, execution_profile_override: str | None = None) -> dict[str, Any]:
        """Materialize asset.

        Args:
            name: name argument.
            execution_profile_override: execution_profile_override argument.

        Returns:
            The result.
        """
        explicit = self.derive_explicit_asset(name)
        if execution_profile_override:
            explicit.setdefault("execution", {})
            explicit["execution"]["profile"] = execution_profile_override
        ordered_decls = self.resolve_use_chain(explicit.get("uses", []))

        merged: dict[str, Any] = {
            "node_type": "asset",
            "name": explicit["name"],
            "kind": explicit["kind"],
            "from": explicit.get("from", ""),
            "uses": list(explicit.get("uses", [])),
            "refs": deepcopy(explicit.get("refs", {})),
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
            "validate": {"rules": [], "repair": {}},
            "package": {},
            "publish": {},
        }

        inherited_rules: list[dict[str, Any]] = []
        inherited_repair: dict[str, Any] = {}

        for decl in ordered_decls:
            merged = deep_merge(merged, deepcopy(decl.get("defaults", {})))
            inherited_rules.extend(deepcopy(decl.get("rules", [])))
            inherited_repair = deep_merge(inherited_repair, deepcopy(decl.get("repair", {})))

        from_name = str(explicit.get("from", "") or "")
        resolved_kit: dict[str, Any] = {}
        kit_version_constraint = str(
            explicit.get("assembly", {}).get("kit_version", "") or ""
        )
        kit_bindings = deepcopy(explicit.get("assembly", {}).get("kit_bindings", {}) or {})
        kit_use_diagnostics: list[dict[str, Any]] = []
        family_name = explicit.get("assembly", {}).get("family", "")
        if not family_name and from_name in self.family_map:
            family_name = from_name
        if from_name and from_name in self.kit_map:
            resolved_kit = deepcopy(self._resolve_named_decl(self.kit_map, from_name, "kit"))
            kit_version = str(resolved_kit.get("version", "") or "")
            if kit_version_constraint and not _version_satisfies(kit_version, kit_version_constraint):
                kit_use_diagnostics.append(
                    {
                        "code": "K6501",
                        "kit": from_name,
                        "message": (
                            f"kit '{from_name}' version '{kit_version}' does not satisfy "
                            f"constraint '{kit_version_constraint}'"
                        ),
                    }
                )
            kit_use_diagnostics.extend(
                _validate_kit_ports_and_parameters(resolved_kit, kit_bindings)
            )
            family_name = str(
                resolved_kit.get("values", {}).get("family", "")
                or resolved_kit.get("values", {}).get("family_bias", "")
                or family_name
            )
        resolved_family: dict[str, Any] = {}
        if family_name:
            resolved_family = deepcopy(self._resolve_named_decl(self.family_map, family_name, "family"))
            merged = deep_merge(merged, deepcopy(resolved_family.get("defaults", {})))
            inherited_rules.extend(deepcopy(resolved_family.get("rules", [])))

        explicit_overlay = deepcopy(explicit)
        explicit_validate = explicit_overlay.pop("validate", {})
        merged = deep_merge(merged, explicit_overlay)

        if resolved_family:
            merged["geometry"] = deep_merge(
                deepcopy(resolved_family.get("geometry", {})), merged.get("geometry", {})
            )
            merged["features"] = deep_merge(
                deepcopy(resolved_family.get("features", {})), merged.get("features", {})
            )
            merged["surface"] = deep_merge(
                deepcopy(resolved_family.get("surface", {})), merged.get("surface", {})
            )
            merged["assembly"] = deep_merge(
                deepcopy(resolved_family.get("assembly", {})), merged.get("assembly", {})
            )
            merged["space"] = _merge_space_spec(
                deepcopy(resolved_family.get("space", {})), merged.get("space", {})
            )
            merged["repair_policy"] = _merge_repair_policy_spec(
                deepcopy(resolved_family.get("repair_policy", {})), merged.get("repair_policy", {})
            )

        merged.setdefault("validate", {})
        merged["validate"] = deep_merge(
            merged["validate"], {k: v for k, v in explicit_validate.items() if k not in {"rules", "repair"}}
        )
        merged["validate"]["rules"] = inherited_rules + deepcopy(explicit_validate.get("rules", []))
        merged["validate"]["repair"] = deep_merge(
            inherited_repair, deepcopy(explicit_validate.get("repair", {}))
        )

        merged["name"] = explicit["name"]
        merged["kind"] = explicit["kind"]
        merged["from"] = str(explicit.get("from", "") or family_name or "")
        merged["uses"] = list(explicit.get("uses", []))
        merged["refs"] = self._resolve_reference_sets(deepcopy(explicit.get("refs", {})))
        if family_name and not merged.get("assembly", {}).get("family"):
            merged.setdefault("assembly", {})
            merged["assembly"]["family"] = family_name
        if resolved_kit:
            merged.setdefault("assembly", {})
            merged["assembly"]["kit"] = from_name
            merged["assembly"]["resolved_kit"] = resolved_kit
            merged["assembly"]["resolved_kit_use"] = {
                "kit": from_name,
                "version": str(resolved_kit.get("version", "") or ""),
                "version_constraint": kit_version_constraint,
                "bindings": kit_bindings,
                "diagnostics": kit_use_diagnostics,
            }
            if not merged["assembly"].get("components"):
                merged["assembly"]["components"] = list(resolved_kit.get("values", {}).get("modules", []))
            merged["constraints"] = deep_merge(
                deepcopy(resolved_kit.get("values", {})), merged.get("constraints", {})
            )

        merged["space"] = self.resolve_space_spec(merged.get("space", {}))
        merged["repair_policy"] = self.resolve_repair_policy_spec(merged.get("repair_policy", {}))
        merged["validate"]["repair"] = _repair_policy_to_validate_repair(
            merged["repair_policy"], merged["validate"].get("repair", {})
        )

        palette_name = merged.get("surface", {}).get("palette")
        resolved_palette = self._resolve_palette(palette_name) if palette_name else {}
        palette_materials = list(
            resolved_palette.get("values", {}).get("materials", [])
            or resolved_palette.get("values", {}).get("slots", [])
        )
        declared_materials = list(merged.get("surface", {}).get("materials", []))
        intent_materials = list(merged.get("intent", {}).get("materials", []))
        material_names = _dedupe([*declared_materials, *intent_materials, *palette_materials])
        resolved_materials = {
            material_name: self._resolve_material(material_name) for material_name in material_names
        }

        component_names = _dedupe(list(merged.get("assembly", {}).get("components", [])))
        mechanism_names = _dedupe(list(merged.get("assembly", {}).get("mechanisms", [])))
        trait_names = _dedupe(list(merged.get("assembly", {}).get("traits", [])))
        resolved_components = [self._resolve_component(component_name) for component_name in component_names]
        resolved_mechanisms = [self._resolve_mechanism(item) for item in mechanism_names]
        resolved_traits = [self._resolve_trait(item) for item in trait_names]

        merged.setdefault("assembly", {})
        merged["assembly"]["resolved_family"] = resolved_family
        merged["assembly"]["resolved_components"] = resolved_components
        merged["assembly"]["resolved_mechanisms"] = resolved_mechanisms
        merged["assembly"]["resolved_traits"] = resolved_traits

        merged.setdefault("surface", {})
        merged["surface"]["resolved_palette"] = resolved_palette
        merged["surface"]["resolved_materials"] = resolved_materials
        surface_program_name = str(merged["surface"].get("program", "") or "")
        resolved_surface_program = (
            self._resolve_surface_program(surface_program_name) if surface_program_name else {}
        )
        if resolved_surface_program:
            merged["surface"] = deep_merge(
                deepcopy(resolved_surface_program.get("values", {})), merged["surface"]
            )
            merged["surface"]["program"] = surface_program_name
        surface_policy_name = str(
            merged["surface"].get("policy", "")
            or merged["build"].get("surface", {}).get("surface_policy", "")
            or ""
        )
        resolved_surface_policy = (
            self._resolve_surface_policy(surface_policy_name) if surface_policy_name else {}
        )
        if resolved_surface_policy:
            merged["surface"] = deep_merge(
                deepcopy(resolved_surface_policy.get("values", {})), merged["surface"]
            )
            merged["surface"]["policy"] = surface_policy_name
        surface_backend_name = str(
            merged["surface"].get("backend")
            or merged["surface"].get("authoring", {}).get("backend")
            or merged["build"].get("surface", {}).get("authoring_backend")
            or ""
        )
        resolved_surface_backend = (
            self._resolve_surface_backend(surface_backend_name)
            if surface_backend_name in self.surface_backend_map
            else {}
        )
        decal_library_names = _dedupe(list(merged["surface"].get("decal_libraries", [])))
        mask_program_names = _dedupe(list(merged["surface"].get("mask_programs", [])))
        trim_sheet_names = _dedupe(list(merged["surface"].get("trim_sheets", [])))
        pattern_names = _dedupe(list(merged["surface"].get("patterns", [])))
        merged["surface"]["resolved_patterns"] = self._resolve_optional_list(
            pattern_names, self.pattern_map, "pattern"
        )
        merged["surface"]["resolved_surface_program"] = resolved_surface_program
        merged["surface"]["resolved_surface_policy"] = resolved_surface_policy
        merged["surface"]["resolved_surface_backend"] = resolved_surface_backend
        merged["surface"]["resolved_decal_libraries"] = self._resolve_optional_list(
            decal_library_names, self.decal_library_map, "decal_library"
        )
        merged["surface"]["resolved_mask_programs"] = self._resolve_optional_list(
            mask_program_names, self.mask_program_map, "mask_program"
        )
        merged["surface"]["resolved_trim_sheets"] = self._resolve_optional_list(
            trim_sheet_names, self.trim_sheet_map, "trim_sheet"
        )
        material_graph_name = str(merged["surface"].get("material_graph", "") or "")
        resolved_material_graph = self._resolve_mapping_optional(
            self.material_graph_map, material_graph_name, "material_graph"
        )
        if resolved_material_graph:
            merged["surface"] = deep_merge(
                deepcopy(resolved_material_graph.get("values", {})), merged["surface"]
            )
            merged["surface"]["material_graph"] = material_graph_name
        merged["surface"]["resolved_material_graph"] = resolved_material_graph

        merged.setdefault("execution", {})
        execution_profile_name = str(merged["execution"].get("profile", "") or "")
        resolved_execution_profile = self._resolve_mapping_optional(
            self.execution_profile_map, execution_profile_name, "execution_profile"
        )
        if resolved_execution_profile:
            merged["execution"] = deep_merge(
                deepcopy(resolved_execution_profile.get("values", {})), merged["execution"]
            )
            merged["execution"]["profile"] = execution_profile_name
        inspection_policy_name = str(merged["execution"].get("inspection_policy", "") or "")
        resolved_inspection_policy = self._resolve_mapping_optional(
            self.inspection_policy_map, inspection_policy_name, "inspection_policy"
        )
        if resolved_inspection_policy:
            merged["execution"]["inspection_policy"] = inspection_policy_name
        explicit_library_bindings = _dedupe(list(merged["execution"].get("library_bindings", [])))
        if explicit_library_bindings:
            resolved_library_bindings = [
                self._resolve_mapping_optional(self.library_binding_map, item, "library_binding")
                for item in explicit_library_bindings
                if item in self.library_binding_map
            ]
        else:
            resolved_library_bindings = [
                deepcopy(binding)
                for binding in self.program.get("library_bindings", [])
                if str(binding.get("values", {}).get("target", "")) == "blender_assets"
            ]
        merged["execution"]["resolved_execution_profile"] = resolved_execution_profile
        merged["execution"]["resolved_inspection_policy"] = resolved_inspection_policy
        merged["execution"]["resolved_library_bindings"] = resolved_library_bindings

        surface_build = merged.setdefault("build", {}).setdefault("surface", {})
        bake_profile_name = str(surface_build.get("bake_profile", "") or "")
        resolved_bake_profile = self._resolve_mapping_optional(
            self.bake_profile_map, bake_profile_name, "bake_profile"
        )
        if resolved_bake_profile:
            merged["build"]["surface"] = deep_merge(
                deepcopy(resolved_bake_profile.get("values", {})), merged["build"]["surface"]
            )
            merged["build"]["surface"]["bake_profile"] = bake_profile_name
        merged["build"]["surface"]["resolved_bake_profile"] = resolved_bake_profile
        render_fixture_name = str(merged["build"]["surface"].get("render_fixture", "") or "")
        resolved_render_fixture = self._resolve_mapping_optional(
            self.render_fixture_map, render_fixture_name, "render_fixture"
        )
        if resolved_render_fixture:
            merged["build"]["surface"] = deep_merge(
                deepcopy(resolved_render_fixture.get("values", {})), merged["build"]["surface"]
            )
            merged["build"]["surface"]["render_fixture"] = render_fixture_name
        merged["build"]["surface"]["resolved_render_fixture"] = resolved_render_fixture
        resolved_policies = self._resolve_named_policies(merged)
        merged.setdefault("fit", {})
        merged["fit"]["resolved_fit_profile"] = resolved_policies["fit_profile"]
        merged["fit"]["resolved_reconstruct_policy"] = resolved_policies["reconstruct_policy"]
        merged.setdefault("transfer", {})
        merged["transfer"]["resolved_adapt_policy"] = resolved_policies["adapt_policy"]
        merged["transfer"]["resolved_transfer_rules"] = resolved_policies["transfer_rules"]
        merged.setdefault("constraints", {})
        merged["constraints"]["resolved_assembly_policy"] = resolved_policies["assembly_policy"]

        # Phase 13: resolve `experimental.references.use` to an absolute
        # path relative to the source `.lth` file. The checker validates
        # the resolved path; the executor uses `_resolved_path` to override
        # the convention reference-board base path.
        experimental = merged.get("experimental")
        if isinstance(experimental, dict):
            references = experimental.get("references")
            if isinstance(references, dict):
                use_value = references.get("use")
                if isinstance(use_value, str) and use_value:
                    references["_resolved_path"] = self._resolve_experimental_reference_path(
                        use_value
                    )
            merged["experimental"] = experimental

        # §5.10: cascade `intent.asset_class` budgets into the asset's
        # build/validate slots before normalization. Author-declared
        # values always win — cascade only fills missing leaves.
        self._apply_asset_class_cascade(merged)

        return normalize_asset(merged)

    def _apply_asset_class_cascade(self, asset: dict[str, Any]) -> None:
        intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
        raw = intent.get("asset_class") if isinstance(intent, dict) else None
        if not isinstance(raw, str):
            return
        name = raw.strip()
        if not name or name == GENERIC_ASSET_CLASS:
            return
        body = resolve_asset_class_profile(name, self.asset_class_profile_map)
        if body is None:
            return
        cascade_into_asset(asset, body)
        asset.setdefault("intent", {})
        asset["intent"]["resolved_asset_class_profile"] = {
            "name": name,
            "body": body,
        }

    def _resolve_experimental_reference_path(self, use_value: str) -> str:
        """Resolve ``experimental.references.use`` to an absolute path.

        Mirrors how the parser's import resolver locates files while
        using the shared hardened path resolver: first try a path
        contained under the source ``.lth`` directory, then a repo-root
        relative path. Returns an empty string when no contained
        candidate is found so downstream checks can surface ``L7103``.
        """
        source_path = self.program.get("_source_path")
        roots: list[Path] = []
        if source_path:
            roots.append(Path(source_path).resolve().parent)
        roots.append(_REPO_ROOT)
        last_error = ""
        for root in roots:
            try:
                resolved = safe_resolve(root, use_value)
            except (PathGuardError, OSError, RuntimeError) as exc:
                last_error = str(exc)
                continue
            if resolved.exists():
                return str(resolved)
        if last_error:
            log_debug(
                log,
                "lathe.resolver.experimental_reference_path_rejected",
                "experimental.references.use path {path!r} rejected: {error}",
                path=use_value,
                error=last_error,
            )
        return ""


def materialize_asset(
    program: dict[str, Any], name: str, execution_profile_override: str | None = None
) -> dict[str, Any]:
    """Materialize asset.

    Args:
        program: program argument.
        name: name argument.
        execution_profile_override: execution_profile_override argument.

    Returns:
        The result.
    """
    return Resolver(program).materialize_asset(name, execution_profile_override=execution_profile_override)
