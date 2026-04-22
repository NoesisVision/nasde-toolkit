from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from nasde_toolkit.skills_installer import install_bundled_skills


def test_install_bundled_skills_copies_all_nasde_benchmark_skills(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    install_bundled_skills(console=Console(), scope="user", target_dir=target, force=False)

    installed = sorted(p.name for p in target.iterdir() if p.is_dir())
    assert installed == [
        "nasde-benchmark-creator",
        "nasde-benchmark-from-history",
        "nasde-benchmark-from-public-repos",
        "nasde-benchmark-runner",
    ]
    for skill_dir in target.iterdir():
        assert (skill_dir / "SKILL.md").is_file()


def test_install_bundled_skills_skips_existing_without_force(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    install_bundled_skills(console=Console(), scope="user", target_dir=target, force=False)

    sentinel = target / "nasde-benchmark-creator" / "SKILL.md"
    original = sentinel.read_text()
    sentinel.write_text("LOCAL EDIT")

    install_bundled_skills(console=Console(), scope="user", target_dir=target, force=False)
    assert sentinel.read_text() == "LOCAL EDIT"

    install_bundled_skills(console=Console(), scope="user", target_dir=target, force=True)
    assert sentinel.read_text() == original


def test_install_bundled_skills_rejects_unknown_scope(tmp_path: Path) -> None:
    import typer

    with pytest.raises(typer.BadParameter):
        install_bundled_skills(console=Console(), scope="nope", target_dir=None, force=False)
