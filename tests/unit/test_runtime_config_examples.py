from __future__ import annotations

import json
from pathlib import Path

import pytest
from lathe.providers.registry import get_provider, provider_config
from lathe.runtime_config import load_runtime_config

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CONFIG_DIR = REPO_ROOT / "examples" / "runtime_configs"


@pytest.mark.parametrize("config_path", sorted(RUNTIME_CONFIG_DIR.glob("*.json")), ids=lambda path: path.name)
def test_shipped_runtime_config_loads(config_path: Path) -> None:
    config = load_runtime_config(config_path)

    assert isinstance(config, dict)
    assert "shape" in config
    provider = config.get("shape", {}).get("provider")
    if provider and provider != "auto":
        assert get_provider(provider)["id"]


@pytest.mark.parametrize(
    "config_name",
    [
        "auto_learned.json",
        "hunyuan_http.json",
        "mock_hunyuan_http.json",
        "real_learned_hunyuan_http.json",
    ],
)
def test_hunyuan_runtime_config_examples_pin_url_allowlist(config_name: str) -> None:
    config = load_runtime_config(RUNTIME_CONFIG_DIR / config_name)
    hunyuan = provider_config(config, "hunyuan2_1_http")

    assert hunyuan["url_allowlist"]
    assert (
        hunyuan["base_url"].split("://", 1)[1].split("/", 1)[0].split(":", 1)[0] in hunyuan["url_allowlist"]
    )


def test_runtime_config_examples_are_documented() -> None:
    docs = (
        (REPO_ROOT / "docs" / "cookbook" / "08_runtime_config.md").read_text(encoding="utf-8")
        + "\n"
        + (REPO_ROOT / "docs" / "cookbook" / "runtime_config_schema.md").read_text(encoding="utf-8")
    )
    files = {path.name for path in RUNTIME_CONFIG_DIR.glob("*.json")}
    documented = {name for name in files if name in docs}

    assert documented == files


def test_runtime_config_examples_are_pretty_printed_json() -> None:
    for path in sorted(RUNTIME_CONFIG_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = json.dumps(payload, indent=2) + "\n"
        assert path.read_text(encoding="utf-8") == expected
