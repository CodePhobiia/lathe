"""Mock Codex ImageGen bridge fixture.

The real ``lathe.codex_imagegen_bridge`` emits request JSON files, expects
Codex to populate PNGs on disk, and then consumes them. These fixtures
short-circuit that dance for unit/integration tests: the mock writes the
seeded placeholder PNG into the expected output location whenever the
bridge "requests" a generation.

Seeded PNG fixtures live under ``tests/fixtures/codex_imagegen_samples/``.
``placeholder.png`` is a 4x4 grayscale stub.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest


SAMPLES_DIR = Path(__file__).resolve().parent / "codex_imagegen_samples"
DEFAULT_PLACEHOLDER = SAMPLES_DIR / "placeholder.png"


@dataclass
class MockCodexBridge:
    """Stand-in for ``lathe.codex_imagegen_bridge`` calls.

    Attributes:
        placeholder: Source PNG copied to every requested output path.
        requests: All ``emit_codex_imagegen_requests`` invocations captured.
        fulfillments: All ``consume_codex_imagegen_outputs`` invocations
            captured.
    """

    placeholder: Path = DEFAULT_PLACEHOLDER
    requests: list[dict[str, Any]] = field(default_factory=list)
    fulfillments: list[dict[str, Any]] = field(default_factory=list)
    fulfill_on_emit: bool = True

    def emit(self, *args: Any, **kwargs: Any) -> list[Path]:
        self.requests.append({"args": args, "kwargs": kwargs})
        if not self.fulfill_on_emit:
            return []
        outputs: list[Path] = []
        zones = kwargs.get("zones") or []
        request_dir = kwargs.get("request_dir")
        output_dir = kwargs.get("output_dir") or request_dir
        if output_dir is None:
            return outputs
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for zone in zones:
            for map_name in ("basecolor",):
                filename = f"{zone.get('part', 'zone')}_{map_name}.png"
                dest = output_dir / filename
                shutil.copyfile(self.placeholder, dest)
                outputs.append(dest)
        return outputs

    def consume(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.fulfillments.append({"args": args, "kwargs": kwargs})
        return {"status": "success", "consumed": len(self.fulfillments)}


@pytest.fixture()
def mock_codex_bridge(monkeypatch: pytest.MonkeyPatch) -> MockCodexBridge:
    """Patch the bridge's emit/consume entry points with the mock."""
    bridge = MockCodexBridge()
    try:
        import lathe.codex_imagegen_bridge as _codex
    except ImportError:
        return bridge

    if hasattr(_codex, "emit_codex_imagegen_requests"):
        monkeypatch.setattr(
            _codex, "emit_codex_imagegen_requests", bridge.emit, raising=True
        )
    if hasattr(_codex, "consume_codex_imagegen_outputs"):
        monkeypatch.setattr(
            _codex, "consume_codex_imagegen_outputs", bridge.consume, raising=True
        )
    return bridge
