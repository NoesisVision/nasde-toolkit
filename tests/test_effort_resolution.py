"""Tests for reasoning-effort resolution, validation, and threading into Harbor config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nasde_toolkit.runner import _build_merged_config, _resolve_effort


def _write_variant(variant_dir: Path, agent: str, effort: str | None = None) -> None:
    variant_dir.mkdir(parents=True, exist_ok=True)
    lines = [f'agent = "{agent}"', 'model = "m"']
    if effort is not None:
        lines.append(f'reasoning_effort = "{effort}"')
    (variant_dir / "variant.toml").write_text("\n".join(lines) + "\n")


def test_cli_effort_overrides_variant(tmp_path: Path) -> None:
    _write_variant(tmp_path, "claude", effort="high")
    assert _resolve_effort("xhigh", tmp_path, "claude") == "xhigh"


def test_variant_effort_used_when_no_cli(tmp_path: Path) -> None:
    _write_variant(tmp_path, "claude", effort="max")
    assert _resolve_effort(None, tmp_path, "claude") == "max"


def test_unset_effort_is_none(tmp_path: Path) -> None:
    _write_variant(tmp_path, "claude")
    assert _resolve_effort(None, tmp_path, "claude") is None  # unset → Harbor family default


def test_out_of_scale_effort_aborts(tmp_path: Path) -> None:
    _write_variant(tmp_path, "codex")
    with pytest.raises(SystemExit):
        _resolve_effort("xhigh", tmp_path, "codex")  # xhigh is Claude-only


def test_each_family_accepts_its_own_top_level(tmp_path: Path) -> None:
    _write_variant(tmp_path, "codex")
    assert _resolve_effort("high", tmp_path, "codex") == "high"
    _write_variant(tmp_path / "g", "gemini")
    assert _resolve_effort("minimal", tmp_path / "g", "gemini") == "minimal"


def _harbor_config(tmp_path: Path) -> Path:
    config = {
        "agents": [
            {
                "import_path": "x:Y",
                "name": "v",
                "kwargs": {"sandbox_files": {"/app/CLAUDE.md": "/x"}},
            }
        ]
    }
    path = tmp_path / "harbor_config.json"
    path.write_text(json.dumps(config))
    return path


def _minimal_project_config(tmp_path: Path):  # type: ignore[no-untyped-def]
    from nasde_toolkit.config import ProjectConfig

    return ProjectConfig(name="p", project_dir=tmp_path)


def test_build_merged_config_writes_effort_without_clobbering_sandbox_files(tmp_path: Path) -> None:
    merged = _build_merged_config(
        config=_minimal_project_config(tmp_path),
        variant_config_path=_harbor_config(tmp_path),
        variant_name="v",
        model="m",
        timeout_sec=None,
        tasks_filter=None,
        reasoning_effort="xhigh",
    )
    kwargs = merged["agents"][0]["kwargs"]
    assert kwargs["reasoning_effort"] == "xhigh"
    assert kwargs["sandbox_files"] == {"/app/CLAUDE.md": "/x"}  # pre-existing kwargs untouched


def test_build_merged_config_omits_effort_when_unset(tmp_path: Path) -> None:
    merged = _build_merged_config(
        config=_minimal_project_config(tmp_path),
        variant_config_path=_harbor_config(tmp_path),
        variant_name="v",
        model="m",
        timeout_sec=None,
        tasks_filter=None,
        reasoning_effort=None,
    )
    assert "reasoning_effort" not in merged["agents"][0]["kwargs"]
