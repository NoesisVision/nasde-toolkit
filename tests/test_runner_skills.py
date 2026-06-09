"""Tests for runner skill collection + sandbox_files refresh (ADR-009).

Covers the latent-bug fix (variants/<v>/skills/ now carries references/),
the sandbox_files refresh contract that wires plugin / referenced skills
into harbor_config.json on every run while preserving hand-written
entries, the three collision warnings, and the homogeneous-plugin gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nasde_toolkit.config import PluginConfig, ProjectConfig, TaskConfig
from nasde_toolkit.runner import (
    _collect_native_skill_dirs,
    _collect_sandbox_files,
    _ensure_harbor_config,
    _generate_harbor_config,
    _require_homogeneous_plugins,
)


def _make_skill_in_variant(variant_dir: Path, name: str) -> None:
    skill = variant_dir / "skills" / name
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody")
    (skill / "references" / "deep.md").write_text("deep rules")


def _sandbox(harbor_path: Path, agent_index: int = 0) -> dict[str, str]:
    return json.loads(harbor_path.read_text())["agents"][agent_index]["kwargs"]["sandbox_files"]


def _derived_keys(harbor_path: Path, agent_index: int = 0) -> list[str]:
    return json.loads(harbor_path.read_text())["agents"][agent_index].get("_nasde_derived_keys", [])


def _skills(harbor_path: Path, agent_index: int = 0) -> list[str]:
    return json.loads(harbor_path.read_text())["agents"][agent_index].get("skills", [])


def _make_native_skill(variant_dir: Path, subdir: str, name: str) -> Path:
    skill = variant_dir / subdir / name
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody")
    (skill / "references" / "deep.md").write_text("deep rules")
    return skill


def _bare_variant(variant_dir: Path) -> Path:
    variant_dir.mkdir(parents=True)
    (variant_dir / "CLAUDE.md").write_text("# c")
    (variant_dir / "variant.toml").write_text('agent = "claude"\nmodel = "m"\n')
    return variant_dir


# ---------------------------------------------------------------------------
# _collect_claude_skills — latent-bug fix coverage
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# sandbox_files refresh — edge cases EC1..EC8 (see PR discussion)
# ---------------------------------------------------------------------------


def test_refresh_preserves_handwritten_entries_across_runs(tmp_path: Path) -> None:
    """EC1: a hand-written sandbox_files entry that does NOT correspond to
    anything in variant_dir must survive every refresh — CLAUDE.md documents
    hand-written harbor_config.json as a supported use case."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")
    handwritten = json.loads(harbor_path.read_text())
    handwritten["agents"][0]["kwargs"]["sandbox_files"]["/app/my-custom.yaml"] = "/host/custom.yaml"
    harbor_path.write_text(json.dumps(handwritten))

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/foo/SKILL.md": "/host/foo/SKILL.md"})

    sf = _sandbox(harbor_path)
    assert sf["/app/my-custom.yaml"] == "/host/custom.yaml"
    assert sf["/app/.claude/skills/foo/SKILL.md"] == "/host/foo/SKILL.md"
    assert sf["/app/CLAUDE.md"] == str(variant_dir / "CLAUDE.md")


def test_refresh_drops_stale_derived_between_runs(tmp_path: Path) -> None:
    """EC2 (bug 006): a [[skill]]/plugin skill removed between runs must
    drop its sandbox_files entry. The tracked _nasde_derived_keys says which
    keys nasde owns."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/old/SKILL.md": "/tmp/worktree/SKILL.md"})
    assert "/app/.claude/skills/old/SKILL.md" in _sandbox(harbor_path)
    assert _derived_keys(harbor_path) == ["/app/.claude/skills/old/SKILL.md"]

    _ensure_harbor_config(variant_dir, "v", {})
    assert "/app/.claude/skills/old/SKILL.md" not in _sandbox(harbor_path)
    assert _derived_keys(harbor_path) == []
    assert _sandbox(harbor_path)["/app/CLAUDE.md"] == str(variant_dir / "CLAUDE.md")


def test_refresh_updates_derived_host_path(tmp_path: Path) -> None:
    """EC3: the same container path mapping to a different host path
    between runs (e.g. new temp worktree on a new ref) must update."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/foo/SKILL.md": "/tmp/old-worktree/SKILL.md"})
    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/foo/SKILL.md": "/tmp/new-worktree/SKILL.md"})

    sf = _sandbox(harbor_path)
    assert sf["/app/.claude/skills/foo/SKILL.md"] == "/tmp/new-worktree/SKILL.md"


def test_refresh_handwritten_wins_over_derived_collision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """EC4a: hand-written entry colliding with [[skill]]/plugin-derived
    entry — hand-written wins (user explicit override) but a warning fires."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")
    cfg = json.loads(harbor_path.read_text())
    cfg["agents"][0]["kwargs"]["sandbox_files"]["/app/.claude/skills/foo/SKILL.md"] = "/host/custom-foo.md"
    harbor_path.write_text(json.dumps(cfg))

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/foo/SKILL.md": "/tmp/worktree/SKILL.md"})

    sf = _sandbox(harbor_path)
    assert sf["/app/.claude/skills/foo/SKILL.md"] == "/host/custom-foo.md"
    out_one_line = " ".join(capsys.readouterr().out.split())
    assert "collides with a derived entry" in out_one_line
    assert "hand-written wins" in out_one_line


def test_refresh_handwritten_wins_over_authored_collision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """EC4b: hand-written entry colliding with an authored file in
    variants/<v>/ — hand-written wins, warning fires."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")
    cfg = json.loads(harbor_path.read_text())
    cfg["agents"][0]["kwargs"]["sandbox_files"]["/app/CLAUDE.md"] = "/host/override-CLAUDE.md"
    harbor_path.write_text(json.dumps(cfg))

    _ensure_harbor_config(variant_dir, "v", {})

    sf = _sandbox(harbor_path)
    assert sf["/app/CLAUDE.md"] == "/host/override-CLAUDE.md"
    out_one_line = " ".join(capsys.readouterr().out.split())
    assert "collides with a file collected from variants/" in out_one_line


def test_refresh_authored_wins_over_derived_collision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """EC4c: same container path produced by both variants/<v>/skills/ AND
    [[skill]] — the file under variants/ wins (more explicit author
    intent), warning fires."""
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    (variant_dir / "CLAUDE.md").write_text("# c")
    (variant_dir / "variant.toml").write_text('agent = "claude"\nmodel = "m"\n')
    _make_skill_in_variant(variant_dir, "foo")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/foo/SKILL.md": "/tmp/derived-foo.md"})

    sf = _sandbox(harbor_path)
    assert sf["/app/.claude/skills/foo/SKILL.md"] == str(variant_dir / "skills" / "foo" / "SKILL.md")
    out = capsys.readouterr().out
    out_one_line = " ".join(out.split())
    assert "[[skill]]/[nasde.plugin] AND a file in variants/" in out_one_line


def test_refresh_greenfield_first_run(tmp_path: Path) -> None:
    """EC5: harbor_config.json does not exist yet — _ensure_harbor_config
    must generate it AND apply extra in the same call."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    assert not harbor_path.exists()

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/x/SKILL.md": "/host/x.md"})

    sf = _sandbox(harbor_path)
    assert sf["/app/.claude/skills/x/SKILL.md"] == "/host/x.md"
    assert sf["/app/CLAUDE.md"] == str(variant_dir / "CLAUDE.md")
    assert _derived_keys(harbor_path) == ["/app/.claude/skills/x/SKILL.md"]


def test_refresh_handles_multiple_agents(tmp_path: Path) -> None:
    """EC6: a hand-written config with multiple agents (e.g. comparing two
    setups in one trial) — both agents get refreshed, hand-written entries
    on each agent are preserved."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    handwritten = {
        "agents": [
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
                "name": "v-a",
                "kwargs": {"sandbox_files": {"/app/agent-a-only.txt": "/host/a.txt"}},
            },
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
                "name": "v-b",
                "kwargs": {"sandbox_files": {"/app/agent-b-only.txt": "/host/b.txt"}},
            },
        ]
    }
    harbor_path.write_text(json.dumps(handwritten))

    _ensure_harbor_config(variant_dir, "v", {"/app/.claude/skills/x/SKILL.md": "/host/x.md"})

    sf_a = _sandbox(harbor_path, agent_index=0)
    sf_b = _sandbox(harbor_path, agent_index=1)
    assert sf_a["/app/agent-a-only.txt"] == "/host/a.txt"
    assert sf_b["/app/agent-b-only.txt"] == "/host/b.txt"
    assert sf_a["/app/.claude/skills/x/SKILL.md"] == "/host/x.md"
    assert sf_b["/app/.claude/skills/x/SKILL.md"] == "/host/x.md"
    assert sf_a["/app/CLAUDE.md"] == str(variant_dir / "CLAUDE.md")


def test_refresh_is_idempotent(tmp_path: Path) -> None:
    """EC7: calling _ensure_harbor_config twice with the same inputs must
    produce the same file content (no drift, no warning duplication)."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    extra = {"/app/.claude/skills/x/SKILL.md": "/host/x.md"}

    _ensure_harbor_config(variant_dir, "v", extra)
    first_content = harbor_path.read_text()

    _ensure_harbor_config(variant_dir, "v", extra)
    second_content = harbor_path.read_text()

    assert first_content == second_content


def test_refresh_handles_missing_derived_keys_meta(tmp_path: Path) -> None:
    """EC8: forward-compat — a harbor_config.json written by an older nasde
    has no _nasde_derived_keys field. Entries that look like derived (e.g.
    they were derived before) get treated as hand-written and preserved.
    First refresh adopts the new meta; subsequent runs cleanly drop stale
    derived entries the normal way."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    old_format = {
        "agents": [
            {
                "import_path": "nasde_toolkit.agents.configurable_claude:ConfigurableClaude",
                "name": "v",
                "kwargs": {
                    "sandbox_files": {
                        "/app/CLAUDE.md": str(variant_dir / "CLAUDE.md"),
                        "/app/.claude/skills/legacy/SKILL.md": "/host/legacy.md",
                    }
                },
            }
        ]
    }
    harbor_path.write_text(json.dumps(old_format))

    _ensure_harbor_config(variant_dir, "v", {})

    sf = _sandbox(harbor_path)
    assert sf["/app/.claude/skills/legacy/SKILL.md"] == "/host/legacy.md"
    assert _derived_keys(harbor_path) == []


# ---------------------------------------------------------------------------
# _require_homogeneous_plugins — bug 013
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, task_plugins: list[PluginConfig | None]) -> ProjectConfig:
    tasks = []
    for i, plugin in enumerate(task_plugins):
        task_path = tmp_path / "tasks" / f"task-{i}"
        task_path.mkdir(parents=True)
        tasks.append(TaskConfig(name=f"task-{i}", path=task_path, plugin=plugin))
    return ProjectConfig(name="p", project_dir=tmp_path, tasks=tasks)


def test_require_homogeneous_plugins_ok_when_identical(tmp_path: Path) -> None:
    p = PluginConfig(path="../plugin", ref="abc", install_root="/opt/p")
    config = _make_project(tmp_path, [p, p, p])
    _require_homogeneous_plugins(config)


def test_require_homogeneous_plugins_ok_when_only_one(tmp_path: Path) -> None:
    config = _make_project(tmp_path, [PluginConfig(path="../plugin"), None, None])
    _require_homogeneous_plugins(config)


def test_require_homogeneous_plugins_ok_when_none(tmp_path: Path) -> None:
    config = _make_project(tmp_path, [None, None])
    _require_homogeneous_plugins(config)


def test_require_homogeneous_plugins_rejects_different_paths(tmp_path: Path) -> None:
    """Bug 013: two tasks with different plugins would silently contaminate
    trials via the variant-wide sandbox_files dict. Fail fast."""
    config = _make_project(
        tmp_path,
        [PluginConfig(path="../plugin-A"), PluginConfig(path="../plugin-B")],
    )
    with pytest.raises(SystemExit):
        _require_homogeneous_plugins(config)


def test_require_homogeneous_plugins_rejects_different_refs(tmp_path: Path) -> None:
    config = _make_project(
        tmp_path,
        [PluginConfig(path="../plugin", ref="abc"), PluginConfig(path="../plugin", ref="def")],
    )
    with pytest.raises(SystemExit):
        _require_homogeneous_plugins(config)


# ---------------------------------------------------------------------------
# Native skill injection — codex/gemini (bug: cwd skills never auto-discovered)
# ---------------------------------------------------------------------------
#
# Codex/Gemini auto-discover skills only from a HOME-scoped dir, never from a
# /app cwd dir. The old path wrote skill files into /app/.agents/skills and
# /app/.gemini/skills via sandbox_files, so they were never registered as
# native skills. The fix routes them through Harbor's config.agent.skills list.


def _codex_variant(variant_dir: Path) -> Path:
    variant_dir.mkdir(parents=True)
    (variant_dir / "AGENTS.md").write_text("# c")
    (variant_dir / "variant.toml").write_text('agent = "codex"\nmodel = "m"\n')
    return variant_dir


def test_collect_native_skill_dirs_codex(tmp_path: Path) -> None:
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    skill = _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")

    dirs = _collect_native_skill_dirs(variant_dir, "codex")

    assert dirs == [str(skill.resolve())]


def test_collect_native_skill_dirs_gemini(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "v"
    variant_dir.mkdir(parents=True)
    (variant_dir / "GEMINI.md").write_text("# g")
    (variant_dir / "variant.toml").write_text('agent = "gemini"\nmodel = "m"\n')
    skill = _make_native_skill(variant_dir, "gemini_skills", "tactical-ddd")

    dirs = _collect_native_skill_dirs(variant_dir, "gemini")

    assert dirs == [str(skill.resolve())]


def test_collect_native_skill_dirs_claude_is_empty(tmp_path: Path) -> None:
    """Claude is intentionally NOT routed through native skills — its
    variants/<v>/skills/ → sandbox_files path already lands where Claude
    Code discovers from cwd and is tested separately."""
    variant_dir = _bare_variant(tmp_path / "variants" / "v")
    _make_skill_in_variant(variant_dir, "analyze-conversation")

    assert _collect_native_skill_dirs(variant_dir, "claude") == []


def test_collect_native_skill_dirs_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    (variant_dir / "agents_skills" / "incomplete").mkdir(parents=True)
    (variant_dir / "agents_skills" / "incomplete" / "notes.md").write_text("x")

    assert _collect_native_skill_dirs(variant_dir, "codex") == []


def test_codex_skills_not_in_sandbox_files(tmp_path: Path) -> None:
    """Regression: agents_skills must NOT leak into sandbox_files (the old bug
    put them at /app/.agents/skills where Codex never scans)."""
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")
    harbor_path = variant_dir / "harbor_config.json"

    _generate_harbor_config(variant_dir, "v")

    assert not any(k.startswith("/app/.agents/skills/") for k in _sandbox(harbor_path))


def test_generate_harbor_config_codex_writes_native_skills(tmp_path: Path) -> None:
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    skill = _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")
    harbor_path = variant_dir / "harbor_config.json"

    _generate_harbor_config(variant_dir, "v")

    assert _skills(harbor_path) == [str(skill.resolve())]


def test_refresh_drops_stale_native_skill_between_runs(tmp_path: Path) -> None:
    """A skill dir removed between runs must drop from agent.skills, exactly
    like a removed [[skill]] drops from sandbox_files."""
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    skill = _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")
    assert _skills(harbor_path) == [str(skill.resolve())]

    import shutil

    shutil.rmtree(variant_dir / "agents_skills" / "tactical-ddd")
    _ensure_harbor_config(variant_dir, "v", {})

    assert _skills(harbor_path) == []


def test_refresh_preserves_handwritten_native_skill(tmp_path: Path) -> None:
    """A skill path an author wired into harbor_config.json by hand (not
    derived from a variant subdir) survives the refresh."""
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")
    config = json.loads(harbor_path.read_text())
    config["agents"][0]["skills"] = ["/host/hand/authored-skill"]
    harbor_path.write_text(json.dumps(config))

    _ensure_harbor_config(variant_dir, "v", {})

    assert "/host/hand/authored-skill" in _skills(harbor_path)


def test_refresh_native_skill_is_idempotent(tmp_path: Path) -> None:
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    skill = _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")

    _ensure_harbor_config(variant_dir, "v", {})
    _ensure_harbor_config(variant_dir, "v", {})

    assert _skills(harbor_path) == [str(skill.resolve())]


def test_collect_native_skill_dirs_warns_on_leading_comment_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Codex rejects a SKILL.md not starting with '---'. A leading provenance
    comment before the frontmatter is the usual culprit — warn loudly."""
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    skill = variant_dir / "agents_skills" / "tactical-ddd"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("<!-- Source: x -->\n---\nname: tactical-ddd\n---\nbody")

    dirs = _collect_native_skill_dirs(variant_dir, "codex")

    assert dirs == [str(skill.resolve())]
    assert "missing YAML frontmatter" in capsys.readouterr().out


def test_collect_native_skill_dirs_no_warning_on_clean_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    variant_dir = _codex_variant(tmp_path / "variants" / "v")
    _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")

    _collect_native_skill_dirs(variant_dir, "codex")

    assert "missing YAML frontmatter" not in capsys.readouterr().out
