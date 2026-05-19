"""Tests for runner skill collection + harbor_config merge (ADR-009).

Covers the latent-bug fix (variants/<v>/skills/ now carries references/)
and the derived-sandbox-files merge that wires plugin / referenced skills
into harbor_config.json on every run.
"""

from __future__ import annotations

import json
from pathlib import Path

from nasde_toolkit.runner import (
    _collect_sandbox_files,
    _generate_harbor_config,
    _merge_sandbox_files,
)


def _make_skill_in_variant(variant_dir: Path, name: str) -> None:
    skill = variant_dir / "skills" / name
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody")
    (skill / "references" / "deep.md").write_text("deep rules")


def test_collect_claude_skills_now_carries_references(tmp_path: Path) -> None:
    """Backward-compat + bug fix: copy-into-variants path keeps working AND
    now carries references/ (previously only SKILL.md was mapped)."""
    variant_dir = tmp_path / "variants" / "with-skill"
    variant_dir.mkdir(parents=True)
    (variant_dir / "CLAUDE.md").write_text("# c")
    _make_skill_in_variant(variant_dir, "analyze-conversation")

    sandbox = _collect_sandbox_files(variant_dir)

    assert sandbox["/app/CLAUDE.md"] == str(variant_dir / "CLAUDE.md")
    assert "/app/.claude/skills/analyze-conversation/SKILL.md" in sandbox
    assert "/app/.claude/skills/analyze-conversation/references/deep.md" in sandbox


def test_collect_claude_skills_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    (variant_dir / "skills" / "incomplete").mkdir(parents=True)
    (variant_dir / "skills" / "incomplete" / "notes.md").write_text("x")

    sandbox = _collect_sandbox_files(variant_dir)

    assert not any("incomplete" in k for k in sandbox)


def test_merge_sandbox_files_adds_to_existing_agent(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    (variant_dir / "CLAUDE.md").write_text("# c")
    (variant_dir / "variant.toml").write_text('agent = "claude"\nmodel = "m"\n')
    _generate_harbor_config(variant_dir, "v")
    harbor_path = variant_dir / "harbor_config.json"

    _merge_sandbox_files(
        harbor_path,
        {"/app/.claude/skills/foo/SKILL.md": "/host/foo/SKILL.md"},
    )

    config = json.loads(harbor_path.read_text())
    sandbox = config["agents"][0]["kwargs"]["sandbox_files"]
    assert sandbox["/app/CLAUDE.md"] == str(variant_dir / "CLAUDE.md")
    assert sandbox["/app/.claude/skills/foo/SKILL.md"] == "/host/foo/SKILL.md"


def test_merge_sandbox_files_preserves_handwritten_config(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    handwritten = {
        "agents": [
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
                "name": "v",
                "kwargs": {"sandbox_files": {"/app/CLAUDE.md": "/x/CLAUDE.md"}},
            }
        ]
    }
    harbor_path = variant_dir / "harbor_config.json"
    harbor_path.write_text(json.dumps(handwritten))

    _merge_sandbox_files(harbor_path, {"/app/.claude/skills/s/SKILL.md": "/h/s/SKILL.md"})

    config = json.loads(harbor_path.read_text())
    sandbox = config["agents"][0]["kwargs"]["sandbox_files"]
    assert sandbox["/app/CLAUDE.md"] == "/x/CLAUDE.md"
    assert sandbox["/app/.claude/skills/s/SKILL.md"] == "/h/s/SKILL.md"
    assert config["agents"][0]["name"] == "v"
