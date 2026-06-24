"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from nasde_toolkit import pricing as pricing_module


@pytest.fixture(autouse=True)
def empty_user_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the layered-pricing user layer from the developer's real ~/.nasde.

    Autouse so every test in the tree is hermetic by default: `load_pricing_layered`
    never reads the host's `~/.nasde/pricing.toml`. Tests that need a real user
    layer request this fixture by name and write to the returned path.
    """
    user_file = tmp_path / "user-home" / ".nasde" / "pricing.toml"
    monkeypatch.setattr(pricing_module, "_user_pricing_path", lambda: user_file)
    return user_file
