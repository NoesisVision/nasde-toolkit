"""Tests for project scaffolding (nasde init)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.pricing import load_pricing
from nasde_toolkit.scaffold import create_project


def test_create_project_writes_pricing_example(tmp_path: Path) -> None:
    create_project(tmp_path, "demo")
    example = tmp_path / "pricing.toml.example"
    assert example.exists()
    body = example.read_text()
    assert "claude-sonnet-5-5" in body  # a real bundled model name to copy
    assert "decimal" in body.lower()  # the comma-vs-point hint


def test_create_project_pricing_example_is_inert(tmp_path: Path) -> None:
    create_project(tmp_path, "demo")
    parsed = tomllib.loads((tmp_path / "pricing.toml.example").read_text())
    assert parsed == {}  # fully commented — no active [models] until the user edits

    assert not (tmp_path / "pricing.toml").exists()  # scaffold never writes a LIVE override


def test_scaffolded_models_have_bundled_prices(tmp_path: Path) -> None:
    create_project(tmp_path, "demo")
    bundled = load_pricing()
    judge_model = tomllib.loads((tmp_path / "nasde.toml").read_text())["evaluation"]["model"]
    agent_model = tomllib.loads((tmp_path / "variants" / "vanilla" / "variant.toml").read_text())["model"]
    assert judge_model in bundled
    assert agent_model in bundled
    assert EvaluationConfig().model in bundled


def test_nasde_toml_template_mentions_cursor_backend() -> None:
    from nasde_toolkit.scaffold import NASDE_TOML_TEMPLATE

    assert '# backend = "claude"  # "claude" | "codex" | "cursor"' in NASDE_TOML_TEMPLATE


def test_nasde_toml_template_tells_cursor_users_to_set_the_model() -> None:
    from nasde_toolkit.scaffold import NASDE_TOML_TEMPLATE

    assert 'for "cursor", also set model = "claude-opus-5-5-high"' in NASDE_TOML_TEMPLATE
    assert "cursor defaults model" not in NASDE_TOML_TEMPLATE
