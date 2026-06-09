"""Tests for reasoning-effort resolution and threading into Harbor config."""

from __future__ import annotations

import json
from pathlib import Path

from nasde_toolkit.runner import _build_merged_config, _resolve_effort


def _write_variant(variant_dir: Path, agent: str, effort: str | None = None) -> None:
    variant_dir.mkdir(parents=True, exist_ok=True)
    lines = [f'agent = "{agent}"', 'model = "m"']
    if effort is not None:
        lines.append(f'reasoning_effort = "{effort}"')
    (variant_dir / "variant.toml").write_text("\n".join(lines) + "\n")


def test_cli_effort_overrides_variant(tmp_path: Path) -> None:
    _write_variant(tmp_path, "claude", effort="high")
    assert _resolve_effort("xhigh", tmp_path) == "xhigh"


def test_variant_effort_used_when_no_cli(tmp_path: Path) -> None:
    _write_variant(tmp_path, "claude", effort="max")
    assert _resolve_effort(None, tmp_path) == "max"


def test_unset_effort_is_none(tmp_path: Path) -> None:
    _write_variant(tmp_path, "claude")
    assert _resolve_effort(None, tmp_path) is None  # unset → Harbor family default


def test_any_value_passes_through_validation_is_harbors_job(tmp_path: Path) -> None:
    # No local allow-list: scales differ per family and change often, so an unknown
    # value is passed straight to Harbor (the source of truth) rather than blocked here.
    _write_variant(tmp_path, "codex")
    assert _resolve_effort("xhigh", tmp_path) == "xhigh"  # would be wrong for codex, but Harbor decides
    assert _resolve_effort("some-future-level", tmp_path) == "some-future-level"


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
