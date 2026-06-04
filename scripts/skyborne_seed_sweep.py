"""Build Skyborne Village seed sweep evidence.

This is a product-evidence helper, not a test. It builds `.lthworld`
directories for a deterministic seed set, records same-seed normalized
hash evidence, and records layout-variation evidence across seeds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lathe.asset_foundry.runtime.signed_package import verify_lthworld_signature
from lathe.asset_foundry.world_writer import write_lthworld
from lathe.forge import compose_world
from lathe.wonder.prompt_parser import parse_wonder_prompt

DEFAULT_PROMPT = (
    "small floating fantasy village at sunset with waterfall, rope bridge, "
    "three cottages, hero inn"
)


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _strip_volatile(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, raw in value.items():
            if key in {"created_utc", "signed_at_unix", "pkg_dir", "world_dir"}:
                continue
            if key == "path" and isinstance(raw, str):
                normalized = raw.replace("\\", "/")
                root_text = str(root).replace("\\", "/")
                out[key] = normalized.replace(root_text, "<WORLD>")
                continue
            out[key] = _strip_volatile(raw, root)
        return out
    if isinstance(value, list):
        return [_strip_volatile(item, root) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        root_text = str(root).replace("\\", "/")
        return normalized.replace(root_text, "<WORLD>")
    return value


def normalized_world_hash(world_dir: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in world_dir.rglob("*") if p.is_file()):
        rel = str(path.relative_to(world_dir)).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        if path.suffix.lower() == ".json":
            payload = _strip_volatile(_json_load(path), world_dir)
            h.update(json.dumps(payload, sort_keys=True, default=str).encode("utf-8"))
        else:
            h.update(path.read_bytes())
    return h.hexdigest()


def layout_signature(world_dir: Path) -> str:
    graph = _json_load(world_dir / "world_graph.json")
    assets = [
        {
            "role": asset["role"],
            "position_cm": asset["placement"]["position_cm"],
            "rotation_y_deg": asset["placement"]["rotation_y_deg"],
            "scale": asset["placement"]["scale"],
        }
        for asset in graph["assets"]
    ]
    canonical = json.dumps(assets, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_world(prompt: str, seed: int, out_dir: Path) -> Path:
    parsed = parse_wonder_prompt(prompt, seed=seed)
    composition = compose_world(parsed.to_skyborne_intent(), seed=seed)
    world_dir = out_dir / f"seed_{seed:02d}.lthworld"
    write_lthworld(composition, world_dir, package_members=True, mode="seed_sweep")
    return world_dir


def summarize_world(seed: int, world_dir: Path) -> dict[str, Any]:
    manifest = _json_load(world_dir / "world_manifest.json")
    gate = _json_load(world_dir / "visual_quality_gate.json")
    signature_valid, signature_reason = verify_lthworld_signature(world_dir)
    return {
        "seed": seed,
        "world_dir": str(world_dir),
        "layout_signature": layout_signature(world_dir),
        "normalized_world_hash": normalized_world_hash(world_dir),
        "signature_valid": signature_valid,
        "signature_reason": signature_reason,
        "asset_count": manifest["asset_count"],
        "linked_package_count": manifest["asset_package_summary"]["linked"],
        "style_compatible": manifest["style_compatibility"]["compatible"],
        "achieved_level": gate["achieved_level"],
        "certified": gate["certified"],
        "blocking_findings": [finding["code"] for finding in gate["findings"]],
    }


def run_seed_sweep(prompt: str, seeds: list[int], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    deterministic_a = build_world(prompt, seeds[0], out_dir / "determinism_a")
    deterministic_b = build_world(prompt, seeds[0], out_dir / "determinism_b")
    hash_a = normalized_world_hash(deterministic_a)
    hash_b = normalized_world_hash(deterministic_b)
    determinism = {
        "version": "lathe.skyborne.determinism_evidence_v1",
        "prompt": prompt,
        "seed": seeds[0],
        "world_a": str(deterministic_a),
        "world_b": str(deterministic_b),
        "normalized_hash_a": hash_a,
        "normalized_hash_b": hash_b,
        "same_seed_match": hash_a == hash_b,
        "normalization": [
            "created_utc",
            "signed_at_unix",
            "pkg_dir",
            "world_dir",
            "world-root path substrings",
        ],
    }
    _write_json(out_dir / "determinism_evidence.json", determinism)

    seed_summaries = [summarize_world(seed, build_world(prompt, seed, out_dir / "seeds")) for seed in seeds]
    layout_hashes = [summary["layout_signature"] for summary in seed_summaries]
    variation = {
        "version": "lathe.skyborne.variation_evidence_v1",
        "prompt": prompt,
        "seeds": seeds,
        "seed_summaries": seed_summaries,
        "all_layouts_distinct": len(set(layout_hashes)) == len(layout_hashes),
        "all_signature_valid": all(summary["signature_valid"] for summary in seed_summaries),
        "all_style_compatible": all(summary["style_compatible"] for summary in seed_summaries),
        "all_level6_certified": all(
            summary["achieved_level"] >= 6 and summary["certified"]
            for summary in seed_summaries
        ),
        "current_blockers": sorted(
            {code for summary in seed_summaries for code in summary["blocking_findings"]}
        ),
    }
    _write_json(out_dir / "variation_evidence.json", variation)
    return {"determinism": determinism, "variation": variation}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--out", default=".tmp_skyborne_world_probe/seed_sweep_20260514")
    parser.add_argument(
        "--seeds",
        nargs="*",
        type=int,
        default=list(range(10)),
        help="Seed set to build; defaults to 0..9.",
    )
    args = parser.parse_args()
    result = run_seed_sweep(args.prompt, list(args.seeds), Path(args.out))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
