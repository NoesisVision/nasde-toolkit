"""Tests for the shared skill + MCP registration machinery (ADR-009)."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from nasde_toolkit.docker import StagedPlugin, cleanup_worktrees, create_ref_worktree
from nasde_toolkit.plugin_registration import (
    inject_mcp_server,
    register_plugin_skills,
    stage_referenced_skills,
    stage_skill_dir,
)


def _make_skill(parent: Path, name: str) -> Path:
    skill = parent / name
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody")
    (skill / "references" / "a.md").write_text("ref a")
    (skill / "references" / "b.md").write_text("ref b")
    return skill


def _staged_plugin(tmp_path: Path, *, with_mcp: bool = True, env: dict | None = None) -> StagedPlugin:
    staged_dir = tmp_path / "_nasde-plugin"
    (staged_dir / ".claude-plugin").mkdir(parents=True)
    (staged_dir / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "noesis"}))
    _make_skill(staged_dir / "skills", "analyze-conversation")
    if with_mcp:
        (staged_dir / ".mcp.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "noesis-graph": {
                            "command": "bun",
                            "args": ["run", "mcp/noesis-graph/server.ts"],
                        }
                    }
                }
            )
        )
    return StagedPlugin(
        staged_dir=staged_dir,
        install_root="/opt/noesis-plugin",
        plugin_name="noesis",
        env=env or {},
    )


# --- stage_skill_dir: whole dir incl references/ ---------------------------


def test_stage_skill_dir_carries_whole_tree(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path, "analyze-conversation")
    sandbox: dict[str, str] = {}

    stage_skill_dir(skill, sandbox)

    assert sandbox["/app/.claude/skills/analyze-conversation/SKILL.md"] == str(skill / "SKILL.md")
    assert sandbox["/app/.claude/skills/analyze-conversation/references/a.md"] == str(skill / "references" / "a.md")
    assert "/app/.claude/skills/analyze-conversation/references/b.md" in sandbox
    assert len(sandbox) == 3


# --- register_plugin_skills ------------------------------------------------


def test_register_plugin_skills_registers_each_skill(tmp_path: Path) -> None:
    staged = _staged_plugin(tmp_path)
    sandbox: dict[str, str] = {}

    register_plugin_skills(staged, sandbox)

    assert "/app/.claude/skills/analyze-conversation/SKILL.md" in sandbox
    assert "/app/.claude/skills/analyze-conversation/references/a.md" in sandbox


def test_register_plugin_skills_noop_without_skills_dir(tmp_path: Path) -> None:
    staged_dir = tmp_path / "_nasde-plugin"
    (staged_dir / ".claude-plugin").mkdir(parents=True)
    (staged_dir / ".claude-plugin" / "plugin.json").write_text("{}")
    staged = StagedPlugin(staged_dir=staged_dir, install_root="/opt/x", plugin_name="x", env={})
    sandbox: dict[str, str] = {}

    register_plugin_skills(staged, sandbox)

    assert sandbox == {}


# --- inject_mcp_server -----------------------------------------------------


def test_inject_mcp_server_writes_fenced_block(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text('[task]\nname = "p/t"\n\n[agent]\ntimeout_sec = 60\n')
    staged = _staged_plugin(tmp_path, env={"CLAUDE_PLUGIN_DATA": "/opt/noesis-data"})

    inject_mcp_server(task_dir, staged)

    text = (task_dir / "task.toml").read_text()
    assert "nasde plugin MCP server (generated" in text
    parsed = tomllib.loads(text)
    servers = parsed["environment"]["mcp_servers"]
    assert len(servers) == 1
    server = servers[0]
    assert server["name"] == "noesis-graph"
    assert server["transport"] == "stdio"
    assert server["command"] == "sh"
    wrapper = server["args"][1]
    assert "CLAUDE_PLUGIN_ROOT=/opt/noesis-plugin" in wrapper
    assert "CLAUDE_PLUGIN_DATA=/opt/noesis-data" in wrapper
    assert "cd /opt/noesis-plugin" in wrapper
    assert "bun run mcp/noesis-graph/server.ts" in wrapper
    assert parsed["task"]["name"] == "p/t"


def test_inject_mcp_server_is_idempotent(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text('[task]\nname = "p/t"\n')
    staged = _staged_plugin(tmp_path)

    for _ in range(3):
        inject_mcp_server(task_dir, staged)

    text = (task_dir / "task.toml").read_text()
    assert text.count("nasde plugin MCP server (generated") == 1
    assert len(tomllib.loads(text)["environment"]["mcp_servers"]) == 1


def test_inject_mcp_server_respects_author_declaration(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    authored = (
        '[task]\nname = "p/t"\n\n'
        "[[environment.mcp_servers]]\n"
        'name = "noesis-graph"\n'
        'transport = "stdio"\n'
        'command = "my-own-thing"\n'
    )
    (task_dir / "task.toml").write_text(authored)
    staged = _staged_plugin(tmp_path)

    inject_mcp_server(task_dir, staged)

    text = (task_dir / "task.toml").read_text()
    assert "nasde plugin MCP server (generated" not in text
    servers = tomllib.loads(text)["environment"]["mcp_servers"]
    assert servers[0]["command"] == "my-own-thing"


def test_inject_mcp_server_env_override_wins(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text('[task]\nname = "p/t"\n')
    staged = _staged_plugin(tmp_path, env={"CLAUDE_PLUGIN_ROOT": "/custom/root"})

    inject_mcp_server(task_dir, staged)

    wrapper = tomllib.loads((task_dir / "task.toml").read_text())["environment"]["mcp_servers"][0]["args"][1]
    assert "CLAUDE_PLUGIN_ROOT=/custom/root" in wrapper
    assert "CLAUDE_PLUGIN_ROOT=/opt/noesis-plugin" not in wrapper


def test_inject_mcp_server_no_mcp_json_is_noop(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text('[task]\nname = "p/t"\n')
    staged = _staged_plugin(tmp_path, with_mcp=False)

    inject_mcp_server(task_dir, staged)

    text = (task_dir / "task.toml").read_text()
    assert "mcp_servers" not in text


# --- stage_referenced_skills (variant.toml [[skill]]) ----------------------


def test_stage_referenced_skills_carries_whole_dir(tmp_path: Path) -> None:
    src_skills = tmp_path / "src" / "skills"
    src_skills.mkdir(parents=True)
    _make_skill(src_skills, "analyze-conversation")

    variant_dir = tmp_path / "variants" / "with-skill"
    variant_dir.mkdir(parents=True)
    (variant_dir / "variant.toml").write_text(
        'agent = "claude"\nmodel = "claude-sonnet-4-6"\n\n[[skill]]\npath = "../../src/skills/analyze-conversation"\n'
    )
    sandbox: dict[str, str] = {}

    stage_referenced_skills(variant_dir, sandbox, create_ref_worktree)

    assert "/app/.claude/skills/analyze-conversation/SKILL.md" in sandbox
    assert "/app/.claude/skills/analyze-conversation/references/a.md" in sandbox
    assert "/app/.claude/skills/analyze-conversation/references/b.md" in sandbox


def test_stage_referenced_skills_no_entries_is_noop(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "vanilla"
    variant_dir.mkdir(parents=True)
    (variant_dir / "variant.toml").write_text('agent = "claude"\nmodel = "claude-sonnet-4-6"\n')
    sandbox: dict[str, str] = {}

    stage_referenced_skills(variant_dir, sandbox, create_ref_worktree)

    assert sandbox == {}


def test_stage_referenced_skills_ref_uses_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skills = repo / "src" / "skills"
    skills.mkdir(parents=True)
    _make_skill(skills, "analyze-conversation")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (skills / "analyze-conversation" / "SKILL.md").write_text("CHANGED")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "later"], cwd=repo, capture_output=True, check=True)

    variant_dir = tmp_path / "variants" / "with-skill"
    variant_dir.mkdir(parents=True)
    (variant_dir / "variant.toml").write_text(
        'agent = "claude"\nmodel = "m"\n\n'
        "[[skill]]\n"
        f'path = "../../repo/src/skills/analyze-conversation"\nref = "{commit}"\n'
    )
    sandbox: dict[str, str] = {}

    try:
        stage_referenced_skills(variant_dir, sandbox, create_ref_worktree)
        staged_skill_md = Path(sandbox["/app/.claude/skills/analyze-conversation/SKILL.md"])
        assert "CHANGED" not in staged_skill_md.read_text()
    finally:
        cleanup_worktrees()


def test_stage_referenced_skills_missing_skill_md_raises(tmp_path: Path) -> None:
    bad = tmp_path / "src" / "not-a-skill"
    bad.mkdir(parents=True)
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    (variant_dir / "variant.toml").write_text(
        'agent = "claude"\nmodel = "m"\n\n[[skill]]\npath = "../../src/not-a-skill"\n'
    )

    with pytest.raises(RuntimeError, match="no SKILL.md"):
        stage_referenced_skills(variant_dir, {}, create_ref_worktree)


def test_stage_referenced_skills_entry_without_path_raises(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    (variant_dir / "variant.toml").write_text('agent = "claude"\nmodel = "m"\n\n[[skill]]\nref = "abc"\n')

    with pytest.raises(RuntimeError, match="needs a 'path'"):
        stage_referenced_skills(variant_dir, {}, create_ref_worktree)
