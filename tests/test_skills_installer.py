from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from nasde_toolkit.skills_installer import install_bundled_skills

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_SCRIPTS = REPO_ROOT / "scripts"
SKILL_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "nasde-benchmark-runner" / "scripts"
BUNDLED_AUTH_SCRIPTS = (
    "export_oauth_token.sh",
    "export_oauth_token.ps1",
    "export_codex_oauth_token.sh",
    "export_codex_oauth_token.ps1",
    "export_gemini_oauth_token.sh",
    "export_gemini_oauth_token.ps1",
)


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


@pytest.mark.parametrize("name", BUNDLED_AUTH_SCRIPTS)
def test_runner_skill_bundles_auth_script(tmp_path: Path, name: str) -> None:
    target = tmp_path / "skills"
    install_bundled_skills(console=Console(), scope="user", target_dir=target, force=False)
    assert (target / "nasde-benchmark-runner" / "scripts" / name).is_file()


@pytest.mark.parametrize("name", BUNDLED_AUTH_SCRIPTS)
def test_skill_scripts_match_repo_scripts(name: str) -> None:
    repo_copy = REPO_SCRIPTS / name
    skill_copy = SKILL_SCRIPTS / name
    assert repo_copy.read_bytes() == skill_copy.read_bytes(), (
        f"{name} drifted between scripts/ and .claude/skills/nasde-benchmark-runner/scripts/. "
        "Update both copies — repo scripts/ is the public-facing copy and skill scripts/ ships "
        "in the wheel via hatch force-include. Tip: cp scripts/* .claude/skills/nasde-benchmark-runner/scripts/"
    )
