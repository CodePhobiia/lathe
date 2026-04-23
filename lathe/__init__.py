from __future__ import annotations

import importlib

__version__ = "0.1.0"

_LAZY_EXPORTS = {
    "build_asset": ("lathe.executor", "build_asset"),
    "build_plan": ("lathe.planner", "build_plan"),
    "check_program": ("lathe.checker", "check_program"),
    "get_schema": ("lathe.schema", "get_schema"),
    "list_backends": ("lathe.backends", "list_backends"),
    "list_stacks": ("lathe.backends", "list_stacks"),
    "materialize_asset": ("lathe.resolver", "materialize_asset"),
    "normalize_asset": ("lathe.normalizer", "normalize_asset"),
    "normalize_program": ("lathe.normalizer", "normalize_program"),
    "parse_file": ("lathe.parser", "parse_file"),
    "parse_text": ("lathe.parser", "parse_text"),
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str) -> object:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'lathe' has no attribute '{name}'")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
