"""Tests for project scaffolding (nasde init)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from nasde_toolkit.scaffold import create_project


def test_create_project_writes_pricing_example(tmp_path: Path) -> None:
    create_project(tmp_path, "demo")
    example = tmp_path / "pricing.toml.example"
    assert example.exists()
    body = example.read_text()
    assert "claude-sonnet-4-6" in body  # a real bundled model name to copy
    assert "decimal" in body.lower()  # the comma-vs-point hint


def test_create_project_pricing_example_is_inert(tmp_path: Path) -> None:
    create_project(tmp_path, "demo")
    parsed = tomllib.loads((tmp_path / "pricing.toml.example").read_text())
    assert parsed == {}  # fully commented — no active [models] until the user edits

    assert not (tmp_path / "pricing.toml").exists()  # scaffold never writes a LIVE override
