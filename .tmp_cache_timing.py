"""One-shot cold/warm timing measurement for the quick-build cache.

Writes incremental progress to .tmp_cache_timing.log so we can read partial
results even if the harness times out the parent shell.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

LOG = Path(".tmp_cache_timing.log")


def emit(msg: str) -> None:
    LOG.open("a", encoding="utf-8").write(msg + "\n")
    print(msg, flush=True)


def main() -> None:
    LOG.write_text("", encoding="utf-8")
    asset_file = sys.argv[1] if len(sys.argv) > 1 else "examples/courier_drone.lth"
    asset_name = sys.argv[2] if len(sys.argv) > 2 else "courier_drone"

    cache_root = tempfile.mkdtemp(prefix="lcache_")
    os.environ["LATHE_CACHE_DIR"] = cache_root
    emit(f"asset={asset_name} src={asset_file} cache_root={cache_root}")

    from lathe.executor import quick_build_asset
    from lathe.parser import parse_file

    program = parse_file(Path(asset_file))
    out_root = Path(tempfile.mkdtemp(prefix="lbuild_"))
    glb = out_root / f"{asset_name}.glb"
    sd = out_root / "stage" / asset_name
    emit(f"out_root={out_root}")

    emit("--- COLD ---")
    t = time.monotonic()
    r1 = quick_build_asset(program, asset_name, sd, glb_path=glb)
    cold = time.monotonic() - t
    emit(
        f"COLD: {cold:.2f}s hit={r1.get('cache_hit')} "
        f"faces={r1['face_count']} parts={r1['part_count']} stages={r1['stage_timings_s']}"
    )

    emit("--- WARM ---")
    t = time.monotonic()
    r2 = quick_build_asset(program, asset_name, sd, glb_path=glb)
    warm = time.monotonic() - t
    emit(
        f"WARM: {warm:.2f}s hit={r2.get('cache_hit')} "
        f"faces={r2['face_count']} parts={r2['part_count']}"
    )
    emit(f"speedup = {cold / max(warm, 0.001):.1f}x")

    emit("--- MISS (runtime_config divergence) ---")
    t = time.monotonic()
    r3 = quick_build_asset(
        program, asset_name, sd, glb_path=glb, runtime_config={"_marker": "v2"}
    )
    miss = time.monotonic() - t
    emit(f"MISS: {miss:.2f}s hit={r3.get('cache_hit')}")

    emit("--- NOCACHE (use_cache=False) ---")
    t = time.monotonic()
    r4 = quick_build_asset(program, asset_name, sd, glb_path=glb, use_cache=False)
    nc = time.monotonic() - t
    emit(f"NOCACHE: {nc:.2f}s hit={r4.get('cache_hit')}")

    emit("DONE")


if __name__ == "__main__":
    main()
