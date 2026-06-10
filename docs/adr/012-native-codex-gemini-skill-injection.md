# ADR-012: Native Codex/Gemini skill injection

**Status:** Accepted
**Date:** 2026-06-09

## Context

nasde lets a variant ship a skill snapshot to a CLI agent so a benchmark can
measure the effect of giving an agent a skill. For Claude this is
`variants/<v>/skills/<name>/`; for Codex it is `agents_skills/<name>/`; for
Gemini it is `gemini_skills/<name>/`. The whole point — and the core of nasde's
offering — is **harness migration**: take the same skill, give it to a
different agent, and measure how that agent does with it. That measurement is
only valid if the skill is installed the way a real user would install it: as a
**native, auto-discovered skill** the agent registers as a first-class
mechanism (a slash-command / tool), not as a stray file the agent happens to
read with `cat`/`sed`.

The original implementation routed all three through `sandbox_files` — a map of
`{container_path: host_file}` that `ConfigurableClaude` / `ConfigurableCodex` /
`ConfigurableGemini` upload during `setup()`:

| Agent  | Old target (cwd-scoped)   | Native discovery root (HOME-scoped) |
| ------ | ------------------------- | ----------------------------------- |
| Claude | `/app/.claude/skills/`    | `~/.claude/skills/` (+ cwd)         |
| Codex  | `/app/.agents/skills/`    | `$HOME/.agents/skills`              |
| Gemini | `/app/.gemini/skills/`    | `~/.gemini/skills/`                 |

Claude Code **does** auto-discover skills from a `.claude/skills/` directory in
its working directory (`/app`), so the Claude path worked. Codex and Gemini do
**not**: their CLIs scan only HOME-scoped roots (verified against the official
`openai/codex` `core-skills` loader: `$CODEX_HOME/skills` and
`$HOME/.agents/skills`; Gemini scans `~/.gemini/skills`). A skill uploaded to
`/app/.agents/skills/` is in a directory the Codex CLI never looks at.

### Impact: the skill was never natively registered

The bug was silent and corrosive. The agent's `AGENTS.md` told it to "consult
the tactical-ddd skill", so it would find the file by path and read it by hand —
producing a trajectory that *looked* like the skill was in use. But the skill
was never registered as a native skill, so any benchmark result comparing
"agent + skill (native)" against "agent (vanilla)" was actually measuring
"agent + skill-as-a-document" — a different, weaker treatment. This invalidated
the Codex column of the skill×model matrix (the core deliverable).

### Why a different cwd path is not the fix

The obvious patch — upload to `$CODEX_HOME/skills` via `sandbox_files` instead —
was tried and **empirically failed**. The file landed in the right place with
valid frontmatter, yet Codex's "Available skills" list still showed only its
built-in `.system/` skills. The cause is **timing**: `setup()` (where
`sandbox_files` upload happens) runs in a different session/phase than the
`codex exec` skill scan inside `run()`. The upload was in the wrong moment
relative to the scan.

## Decision

Route Codex and Gemini skills through **Harbor's native skill-injection
mechanism** (`config.agent.skills`), not `sandbox_files`.

`config.agent.skills` is a list of host skill directories. At trial time Harbor
(`trial.py`):

1. resolves and **uploads** each skill dir into the container's `skills_dir`
   (default `/harbor/skills`),
2. passes `skills_dir` to the agent constructor,
3. and the agent's own `_build_register_skills_command` copies
   `{skills_dir}/* → $HOME/.agents/skills/` (Codex) or `~/.gemini/skills/`
   (Gemini) **inside `run()`, immediately before `codex exec` / the Gemini
   invocation** — the one point with the right timing and the right
   HOME-scoped, shell-expanded destination.

nasde's part is small: `runner._collect_native_skill_dirs(variant_dir,
agent_type)` returns the host paths of each `agents_skills/<name>/` (Codex) or
`gemini_skills/<name>/` (Gemini) dir that contains a `SKILL.md`, and the
harbor_config generator/refresher writes that list to the agent's `skills`
field. Like `sandbox_files`, the list is **regenerated each run** and tracked
via `_nasde_derived_skills`, so a removed skill dir drops out next run while a
hand-authored `skills` entry is preserved.

The skill subdir is keyed on **each agent's own type**, read back from its
`import_path` (`_agent_type_from_import_path`, falling back to the variant's
declared type). A variant is one agent type by contract, but a hand-written
multi-agent `harbor_config.json` can mix types — keying per agent keeps a codex
agent reading `agents_skills/` and a gemini agent reading `gemini_skills/`
instead of all agents sharing the variant's first declared type.

### Claude is deliberately left on the cwd path

The Claude `variants/<v>/skills/` → `sandbox_files` → `/app/.claude/skills/`
(plus a mirror to `~/.claude/skills/`) path **works** (Claude Code discovers
cwd skills natively), is tested, and is also the carrier for `[nasde.plugin]`
skills and `[[skill]]` by-reference (ADR-009) via `stage_skill_dir`. Migrating
it onto `config.agent.skills` would be a larger, riskier change with no
behavioral payoff. Scope is kept to the actual bug.

### All three skill paths, not just the snapshot

A skill reaches an agent three ways: the variant **snapshot**
(`agents_skills/`, `gemini_skills/`), **`[[skill]]` by-reference** in
`variant.toml`, and a **`[nasde.plugin]`**'s own `skills/`. The first revision
of this decision fixed only the snapshot path; the latter two still went
through `stage_skill_dir`'s hardcoded `/app/.claude/skills/` and so were broken
for Codex/Gemini in exactly the same way.

All three are now routed natively for Codex/Gemini. `[[skill]]`/plugin skills
are resolved to skill *directories* by `collect_referenced_skill_dirs` /
`collect_plugin_skill_dirs` (the dir-list counterparts of the unchanged
Claude-only `stage_referenced_skills` / `register_plugin_skills`), threaded as
`extra_skill_dirs` and **unioned** with the snapshot dirs inside
`_refresh_agent_skills`. The union is tracked by the single
`_nasde_derived_skills` marker, so stale-drop and hand-authored preservation
work across both sources. For a Claude agent `extra_skill_dirs` is dropped at
merge time (those skills already ride `sandbox_files`, so feeding the native
list too would double-inject). Because Harbor's `resolve_skills` keys skills by
basename (last-wins), nasde warns when two derived dirs share a basename so the
loser does not silently vanish.

### Frontmatter guardrail

Codex's loader is strict: a `SKILL.md` that does not **start** with a `---`
frontmatter line is rejected (`missing YAML frontmatter delimited by ---`) and
the skill is silently left unregistered. A leading provenance comment
(`<!-- Source: ... -->`) before the frontmatter is the common culprit.
`_collect_native_skill_dirs` warns (does not fail) when a skill's `SKILL.md`
does not open with `---`, so the gotcha surfaces at run time instead of as a
mysteriously-vanished skill. Example skill snapshots had their provenance
comments moved below the closing `---`.

## Consequences

- Codex/Gemini skills are now **natively registered** — the trajectory shows
  the skill in the CLI's own skill registry, loaded from the HOME-scoped path,
  not read by hand. Verified empirically on a live `ddd-threshold-discount` run
  for both agents:
  - **Codex** — `codex.txt` shows the CLI loading
    `/root/.agents/skills/<name>/SKILL.md` through its skill loader
    (`codex_core::session::session`); under the old code that path was never
    scanned.
  - **Gemini** — clean run (reward 1, 0 errors); the trajectory shows the skill
    used through Gemini's native `activate_skill` tool with an
    `<activated_skill>` observation carrying the full skill body, and
    `<available_resources>` reporting the skill at
    `/root/.gemini/skills/<name>/SKILL.md`. The agent activated the skill via
    its native mechanism, not by reading the file.
- Skill×model matrix results for Codex/Gemini collected under the old behavior
  are invalid (skill-as-document, not skill-as-native) and must be re-run.
- For Codex/Gemini, skills (snapshot, `[[skill]]`, and plugin) are all carried
  by `config.agent.skills`; the agent's effective `sandbox_files` is just
  `AGENTS.md` / `GEMINI.md`. The Claude `sandbox_files` skill map is still built
  unconditionally (so Claude stays byte-identical and tested) but a Codex/Gemini
  agent never consumes it.
- The brittle `_expand_skill_targets` workaround in `ConfigurableGemini` (which
  hardcoded `/root/.gemini/skills/`) is removed — Harbor's native command uses
  the shell-expanded `$HOME`, correct for non-root users too.

## References

- `runner._collect_native_skill_dirs`, `runner._refresh_agent_skills`,
  `runner._agent_type_from_import_path`, `runner._referenced_skill_dirs_for_agent`,
  `runner._warn_skill_basename_collisions`
- `plugin_registration.collect_referenced_skill_dirs`,
  `plugin_registration.collect_plugin_skill_dirs` (dir-list channel),
  `stage_referenced_skills` / `register_plugin_skills` (unchanged Claude sink)
- Harbor `agents/installed/codex.py::_build_register_skills_command`,
  `gemini_cli.py::_build_register_skills_command`, `trial.py` skill upload
- `openai/codex` `core-skills/src/loader.rs` (native discovery roots)
- [ADR-009](009-plugin-and-skill-by-reference.md) (the `[[skill]]` / plugin
  mechanism whose Claude sink this decision leaves untouched)
