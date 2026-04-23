"""Cross-stage helpers: hashing, seed resolution, unit conversion, paths.

Extracted from ``lathe/executor.py`` during Stage 2.IV. These utilities are
pure (no dependence on trimesh or numpy) and are consumed by stage modules
and ``BuildExecutor``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def relpath(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(root))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")


def resolve_seed(seed: Any, asset_name: str) -> int:
    if isinstance(seed, int):
        return seed
    if isinstance(seed, str) and seed != "auto":
        try:
            return int(seed)
        except ValueError:
            pass
    digest = hashlib.sha256(asset_name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def hash_obj(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_ref(value: Any) -> str:
    try:
        path = Path(str(value))
        if path.exists() and path.is_file():
            return hash_file(path)
    except OSError:
        pass
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def output_entry(root: Path, path: Path, fmt: str) -> dict[str, Any]:
    return {
        "format": fmt,
        "uri": relpath(root, path),
        "sha256": hash_file(path),
        "size_bytes": path.stat().st_size,
    }


def unit_to_cm(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "mm":
        return amount / 10.0
    if unit == "cm":
        return amount
    if unit == "m":
        return amount * 100.0
    if unit == "px":
        return amount
    if unit == "px_per_m":
        return amount
    if unit == "px_per_cm":
        return amount * 100.0
    if unit == "kb":
        return amount * 1024.0
    if unit == "mb":
        return amount * 1024.0 * 1024.0
    if unit == "gb":
        return amount * 1024.0 * 1024.0 * 1024.0
    return amount


def unit_to_bytes(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "kb":
        return int(amount * 1024)
    if unit == "mb":
        return int(amount * 1024 * 1024)
    if unit == "gb":
        return int(amount * 1024 * 1024 * 1024)
    raise ValueError(f"Cannot convert unit '{unit}' to bytes")


def unit_to_px_per_m(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "px_per_m":
        return amount
    if unit == "px_per_cm":
        return amount * 100.0
    raise ValueError(f"Cannot convert unit '{unit}' to px_per_m")


def characteristic_scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    if "dimensions" in intent and isinstance(intent["dimensions"], dict) and intent["dimensions"].get("type") == "call":
        args = intent["dimensions"].get("args", [])
        values = [unit_to_cm(item["value"]) for item in args if isinstance(item, dict) and item.get("value") is not None]
        if values:
            return max(values)
    if "scale" in intent:
        return max(1.0, unit_to_cm(intent["scale"]))
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)
