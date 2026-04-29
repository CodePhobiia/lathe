from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from lathe.scene.io import write_bytes_atomic, write_json_atomic


def test_atomic_json_writes_use_unique_temp_files_under_parallel_writers(tmp_path) -> None:
    target = tmp_path / "scene_plan.json"
    payloads = [{"schema_version": "lathe.test.v1", "writer": index, "body": "x" * 2048} for index in range(16)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda payload: write_json_atomic(target, payload), payloads))

    final_payload = json.loads(target.read_text(encoding="utf-8"))
    assert final_payload in payloads
    assert list(tmp_path.glob("scene_plan.json.*.tmp")) == []


def test_atomic_binary_write_replaces_only_complete_payload(tmp_path) -> None:
    target = tmp_path / "scene.glb"

    write_bytes_atomic(target, b"glTF" + b"\x00" * 32)

    assert target.read_bytes() == b"glTF" + b"\x00" * 32
    assert list(tmp_path.glob("scene.glb.*.tmp")) == []
