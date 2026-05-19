# ADR-009: `[nasde.plugin]` and skill-by-reference

**Status:** Accepted
**Date:** 2026-05-19

## Context

nasde can ship a **local repo** into the benchmark sandbox as the task's
codebase via `[nasde.source]` in `task.toml`. It had **no equivalent for a
local Claude Code plugin** (a directory with `.claude-plugin/plugin.json`,
`skills/`, and an MCP server in `.mcp.json`).

A benchmark exercising a plugin therefore had to pay a triple tax:

1. **Vendor a frozen snapshot** of the whole plugin (~210 files for the
   noesis plugin) into the benchmark directory.
2. **Hand-wire three things separately**: a Dockerfile `COPY`, the task's
   `[environment.mcp_servers]` (with an env-export wrapper), and a
   `variants/<v>/skills/<name>/SKILL.md` copy.
3. **Refresh the snapshot manually** when the plugin changes (an explicit,
   documented procedure in the SDLC `analyze-conversation` benchmark's
   README — a workaround for this exact gap).

The same gap had a **second, smaller face**: nasde auto-collected skills
*only* from `variants/<v>/skills/<name>/`, by copy. A benchmark testing a
single skill had to physically copy that skill into the variant directory.
In `analyze-conversation` the *same* skill files existed byte-identically in
**three** places: the plugin source, the vendored snapshot, and the variant
copy.

A latent bug compounded face #2: `_collect_claude_skills` mapped only
`SKILL.md`, silently dropping `references/`. A skill like
`analyze-conversation` (which reads `references/extract-topics.md` at
runtime) was actually broken in the sandbox unless the baked plugin
snapshot happened to also provide those files.

### Hard constraint: the Docker build context is fixed

Harbor pins the Docker build context to the task's `environment/` directory
(`harbor/environments/docker/docker.py` → `context_dir =
environment_dir.resolve()`; `TaskPaths.environment_dir = task_dir /
"environment"`). Docker forbids `COPY` escaping the context and does not
follow symlinks out of it. A hand-written `environment/Dockerfile` cannot
`COPY ../../../plugin`. This is precisely why `[nasde.source]`
*auto-generates* the Dockerfile and redirects the compose build context to
a git worktree.

### Harbor has no plugin concept

A grep of Harbor 0.6.4 for `.claude-plugin`, `plugin.json`, `plugin_dir`,
`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` returns zero hits. MCP servers
are read **only** from each task's `task.toml [environment.mcp_servers]`
(`trial.py` → `self._task.config.environment.mcp_servers`). Skills are
copied by `claude_code.py:_build_register_skills_command` from
`self.skills_dir` into `$CLAUDE_CONFIG_DIR/skills/`. A plugin COPYed into
the image is *not* `claude plugin install`ed, so its skills are **not**
auto-discovered and its `.mcp.json` is **not** honored — nasde must
register both explicitly.

## Decision

Add `[nasde.plugin]` to `task.toml` (mirroring `[nasde.source]`) plus a
`[[skill]]` array in `variant.toml` (skill-by-reference). Both feed one
shared skill-registration mechanism.

### 1. Config — `PluginConfig`

A `PluginConfig` dataclass next to `SourceConfig`, parsed from
`[nasde.plugin]` next to the `[nasde.source]` parser:

```toml
[nasde.plugin]
path = "../../../src/plugins/noesis"   # dir with .claude-plugin/plugin.json (required)
ref = "abc1234"                        # optional git ref, same semantics as [nasde.source]
install_root = "/opt/noesis-plugin"    # optional, default /opt/<plugin-name>
build = "bun install --frozen-lockfile" # optional, run at image-build time
[nasde.plugin.env]                     # optional, exported in the MCP wrapper
CLAUDE_PLUGIN_DATA = "/opt/noesis-data"
NOESIS_PROJECT_DIR = "/app"
```

A plugin is declared only when `path` is set (mirrors "source only when
`git` is set"). Absent → behaviour is exactly as before.

### 2. Build-context strategy — stage into the active context

The plugin tree is copied (at `ref` via a temporary git worktree when set,
same mechanism as `[nasde.source]`, `node_modules`/`.git` excluded) into a
gitignored `_nasde-plugin/` staging directory **inside the active build
context**, and a fenced plugin stage is appended to the Dockerfile:

```
# >>> nasde plugin stage (generated — do not edit) >>>
COPY _nasde-plugin/ /opt/<name>/
RUN cd /opt/<name> && <build>
# <<< nasde plugin stage <<<
```

The stage is inserted *before* any trailing `CMD`/`ENTRYPOINT` and is
sentinel-fenced so re-runs replace it idempotently rather than appending
duplicates.

**Alternatives rejected.** A compose `context:` pointing at a common
ancestor conflicts with `[nasde.source]` (which already owns the compose
context) and forces a generated Dockerfile. BuildKit named contexts
(`--build-context`) are fragile across the docker-compose versions Harbor
drives and require Dockerfile opt-in. Staging into the active context is
the only option that composes with all four cases below and honours a
hand-written Dockerfile.

**Dockerfile / build-context precedence:**

| Case | Build context | Dockerfile | Plugin staged at |
|---|---|---|---|
| plugin only | `environment/` (Harbor default) | generated minimal base, plugin stage appended | `environment/_nasde-plugin/` |
| plugin + `[nasde.source]` | repo/worktree (source's compose override) | source-generated, plugin stage appended | `<source-context>/_nasde-plugin/` |
| plugin + hand-written Dockerfile | `environment/` | hand-written, plugin stage appended (preserved verbatim) | `environment/_nasde-plugin/` |
| neither | unchanged | unchanged | n/a |

When `[nasde.source]` is present, `ensure_task_environment` has already
redirected the compose context; nasde reads that context back out of the
generated `docker-compose.yaml` and stages the plugin there so the same
relative `COPY _nasde-plugin/` works. A base Dockerfile is generated only
when there is no source *and* no real (non-generated) Dockerfile content.

### 3. Shared skill + MCP registration

A single module, `plugin_registration.py`, owns the machinery:

- `stage_skill_dir` expands a **whole** skill directory (incl.
  `references/` and siblings) into the flat `{container_path: host_file}`
  map `ConfigurableClaude` uploads (it uploads regular files only, mirroring
  `_collect_codex_skills`'s `rglob`). Target:
  `/app/.claude/skills/<name>/<relative>` (Harbor mirrors that to
  `~/.claude/skills`). **This also fixes the latent `references/`-dropping
  bug** for the existing copy-into-`variants/` path, which now routes
  through the same helper.
- `register_plugin_skills` registers a shipped plugin's own
  `skills/<name>/` (each carried whole) — necessary because a
  baked-not-installed plugin's skills are invisible to auto-discovery.
- `inject_mcp_server` derives a stdio MCP server from the plugin's
  `.mcp.json`, wraps it with the env a baked-not-installed plugin needs
  (`CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA`/`CLAUDE_PROJECT_DIR` defaults
  plus `[nasde.plugin].env` overrides), and writes it into the task's
  `task.toml` between sentinel comments — Harbor reads MCP servers *only*
  from `task.toml`, so that is the sole injection point. It is idempotent
  and **respects an author-declared server of the same name** (logs and
  skips, never clobbers). When the plugin's command is already `sh -c
  <script>`, the env prefix is merged into that script rather than nesting
  a second `sh -c`.

### 4. Skill-by-reference — `[[skill]]` in `variant.toml`

A `[[skill]]` array of tables inside the existing `variant.toml` (no new
file, variant-scoped — matching how skills are variant-scoped today):

```toml
agent = "claude"
model = "claude-sonnet-4-6"

[[skill]]
path = "../../../src/plugins/noesis/skills/analyze-conversation"
ref  = "abc1234"   # optional, same semantics as [nasde.source]
```

Each entry is resolved (optionally via a temp worktree at `ref`) and fed to
the **same** `stage_skill_dir` machinery as the plugin path — the whole
skill dir (incl. `references/`) lands at `/app/.claude/skills/<name>/**`
with no copy under `variants/<v>/skills/`. The legacy
copy-into-`variants/<v>/skills/` path is untouched and keeps working.

Derived sandbox files (plugin skills + referenced skills) are merged into
the variant's `harbor_config.json` on every run — they are derived, not
authored, and staged source paths can change between runs.

## Consequences

- **Backward compatible.** No `[nasde.plugin]`, no `[[skill]]` → behaviour
  is byte-for-byte as before. Existing `variants/<v>/skills/` copies keep
  working (now also carrying `references/` — a strict improvement).
- **Removes the triple copy.** A plugin-exercising benchmark declares the
  plugin once; the snapshot, the manual MCP wiring, and the variant skill
  copy all disappear. The downstream SDLC `analyze-conversation` and
  `draft-to-design-doc` benchmarks can drop their `_plugin-staging/`
  snapshots and `variants/with-skill/skills/` copies (tracked separately in
  the SDLC repo, not part of this change).
- **`task.toml` is mutated** by MCP injection. This is the only mechanism
  Harbor offers (it reads MCP solely from `task.toml`). It is fenced,
  idempotent, visibly generated, and never overrides an explicit author
  declaration — the same "generate in place where the tool reads it"
  pattern nasde already uses for `environment/Dockerfile` and
  `docker-compose.yaml`.
- **`_nasde-plugin/` is a generated artifact**, gitignored like the rest of
  `environment/` (benchmark `.gitignore`s already ignore `tasks/*/environment/`).
- **Validation is strict.** A `[nasde.plugin].path` that is missing or has
  no `.claude-plugin/plugin.json`, or a `[[skill]]` with no `path` / no
  `SKILL.md`, fails fast with a clear error rather than producing a broken
  sandbox.

## References

- ADR-007 — `[nasde.source]` worktree / build-context precedent reused here.
- Harbor 0.6.4: `environments/docker/docker.py` (fixed build context),
  `agents/installed/claude_code.py:949-1004` (skills + MCP registration),
  `trial/trial.py:188-189` (MCP read from task.toml).
- SDLC `evals/analyze-conversation/` — the motivating downstream consumer
  whose README documents the snapshot-refresh workaround this removes.
