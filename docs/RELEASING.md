# Releasing nasde-toolkit

This document describes how to cut a new release of nasde-toolkit. It is
written so that **a contributor who has never released before can follow it
end-to-end without asking questions**. If you hit a step that's unclear or
out of date, fix the doc in the same PR as the release.

## TL;DR

```bash
# 1. Start from a clean, green main
git checkout main && git pull

# 2. Move [Unreleased] section under the new version header in CHANGELOG.md,
#    add a fresh empty [Unreleased] block, update compare links, and add
#    a new PR link-ref (`[#NN]: …/pull/NN`) at the bottom for any PR
#    cited in this release's entries
$EDITOR CHANGELOG.md

# 3. Commit the changelog and push the PR
git checkout -b chore/release-vX.Y.Z
git add CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git push -u origin chore/release-vX.Y.Z
gh pr create --fill

# 4. Merge the PR once CI is green, then tag and push from main
git checkout main && git pull
git tag vX.Y.Z
git push origin vX.Y.Z

# That's it. The tag push triggers publish.yml which:
#   - runs quality-gate (lint/mypy/test/audit)
#   - builds wheel + sdist
#   - publishes to TestPyPI
#   - smoke-tests fresh install from TestPyPI in a clean venv
#   - publishes to PyPI (gated by the smoke test passing)
#   - smoke-tests fresh install from PyPI
#   - creates a GitHub Release with auto-generated notes

# Watch the run:
gh run watch
```

The rest of this document explains each step, how the publish workflow
works in detail, how to pick the version number, how to hotfix an older
release, and what **not** to do.

## Versioning

nasde-toolkit follows [Semantic Versioning 2.0.0](https://semver.org/) and
its [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) section
convention.

| Bump      | When                                                                       | Example       |
|-----------|-----------------------------------------------------------------------------|---------------|
| **Major** | Breaking change for users of the CLI, config, or benchmark project layout | `0.2.3 → 1.0.0` |
| **Minor** | Backwards-compatible new feature, or a meaningful change in behavior      | `0.1.4 → 0.2.0` |
| **Patch** | Backwards-compatible bugfix or doc-only change                            | `0.2.0 → 0.2.1` |

**Pre-1.0 policy.** While we're on `0.x`, a minor bump (`0.x → 0.(x+1)`) is
allowed to contain breaking changes to *internal* APIs or to evaluator /
runner internals, as long as the **user-facing CLI, `nasde.toml` schema,
and benchmark project layout** stay backwards-compatible. Any breaking
change to those three is a major bump.

**`CHANGELOG.md` section → bump rule of thumb:**

- Only `### Fixed`, `### Docs`, or `### Security` entries → patch bump.
- Any `### Added` or `### Changed` → at least a minor bump.
- A `### Removed` entry or a `### Changed` marked *(breaking)* → major bump.

**Dependency upgrades follow the impact on the user, not the upstream
semver.** A `harbor 0.1 → 0.4` or `opik 1 → 2` in our lockfile is an
implementation detail as long as the user's benchmark still runs the same
way. Apply these three cases:

- **Transitive or internal dep bump with no visible behavior change** →
  patch. The user's `nasde.toml`, benchmark layout, and CLI output are
  unchanged. The CVE noise in `### Security` and the lockfile churn in
  `### Changed` stay in a patch release.
- **Dep bump that changes `nasde.toml` schema, CLI output, benchmark
  project layout, or the format of trial artifacts** → at least minor.
  The user has to do something or notices something different.
- **Dep bump that drops a supported integration or breaks existing
  benchmarks** (e.g. Harbor drops a sandbox provider we exposed via
  `--harbor-env`) → major.

The rule is "what does the person running `nasde run` see differently",
not "did an upstream major bump". Otherwise every quarterly refresh of
`uv.lock` would push us toward `v2.x` without adding features.

**How the version is actually set.** We use
[`hatch-vcs`](https://github.com/ofek/hatch-vcs) (see
`pyproject.toml` → `[tool.hatch.version] source = "vcs"`). The version is
derived from the latest annotated git tag at build time. **Do not edit a
`version = "…"` line** — there isn't one, and adding one would break the
build. `src/nasde_toolkit/_version.py` is auto-generated and gitignored.

This means:

- Between releases, dev builds carry a version like `0.2.1.dev3+gabcdef`.
- As soon as you create tag `vX.Y.Z`, any build from that tag resolves to
  exactly `X.Y.Z`.
- Tags **must** follow the `vMAJOR.MINOR.PATCH` pattern (lowercase `v`,
  no suffixes) for `hatch-vcs` to interpret them as release versions.

## Pre-flight checklist

Before you start the release commit, confirm on `main`:

- [ ] **CI is green on main.** Open the Actions tab and check the latest
      run of `quality-gate.yml`. All of `lint`, `typecheck`, `test`,
      `audit`, `validate-configs`, and `docker-smoke` must be passing.
- [ ] **`example-validation.yml` is green on main** — the examples still
      build and run.
- [ ] **No `### Unreleased` entries are in a half-finished state.** If
      something is still in review, either land it first or leave it out
      of this release and bump the PR description to target the next one.
- [ ] **`pip-audit` shows zero known vulnerabilities** (the quality gate
      already enforces this; double-check locally with
      `uv run pip-audit` if you're paranoid).
- [ ] **Working tree is clean** — `git status` should be spotless.
- [ ] **TestPyPI dry-run from main is green** (recommended for non-trivial
      releases — dep bumps, build config changes, etc.):
      ```bash
      gh workflow run publish.yml --ref main
      gh run watch
      ```
      If it fails, the same failure will block your tag-push release.
      Skipping this check is fine for pure CHANGELOG-only releases.

If any of those fail: **do not release**. Fix the underlying issue in a
separate PR first.

## Step 1 — Update `CHANGELOG.md`

The source of truth for what's in each release is `CHANGELOG.md`.

1. Open `CHANGELOG.md`. Under `## [Unreleased]` you'll find entries
   accumulated since the last tag.
2. Rename the section header to the new version and add today's date
   (ISO 8601):

   ```diff
   -## [Unreleased]
   +## [Unreleased]
   +
   +## [0.2.1] — 2026-05-04
   ```

3. Scan the moved entries. Make sure each one is:
   - **User-facing.** "Refactored internal cache" isn't worth listing;
     "`nasde eval` now forwards `[evaluation]` config" is.
   - **One sentence.** Link to the PR (`([#25])`) for detail.
   - **In the right section.** `### Added` / `### Changed` / `### Fixed` /
     `### Removed` / `### Security` / `### Docs`.

4. At the bottom of the file, add a new compare link for the version and
   shift `[Unreleased]`:

   ```diff
   -[Unreleased]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.2.0...HEAD
   +[Unreleased]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.2.1...HEAD
   +[0.2.1]: https://github.com/NoesisVision/nasde-toolkit/compare/v0.2.0...v0.2.1
   ```

5. **Also at the bottom, keep the PR link-ref table in sync.** The
   `## [Unreleased]` section uses [Keep a Changelog][kac-linkrefs]-style
   shortcuts like `([#25])` instead of inline URLs. Every PR number that
   appears in a changelog entry needs a matching `[#NN]: …/pull/NN` line
   at the bottom of the file. Add a row for any new PR referenced in
   this release.

   ```diff
   +[#27]: https://github.com/NoesisVision/nasde-toolkit/pull/27
   ```

   [kac-linkrefs]: https://keepachangelog.com/en/1.1.0/#how

6. Open a PR titled `chore: release vX.Y.Z`. The PR body should be the
   changelog section for this release, so reviewers see exactly what
   goes out.

7. **Wait for CI to go green, then merge.** Prefer a squash merge so the
   release commit is a single entry.

## Step 2 — Tag and push

After the changelog PR is merged:

```bash
git checkout main
git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```

Notes:

- **Always tag `main` after the changelog merge**, not the PR branch.
  `publish.yml` enforces this: it rejects tags whose commit is not
  reachable from `origin/main`.
- **Do not push a tag with `git push --tags`** — push the single tag by
  name. This avoids accidentally publishing stale local tags.

The tag push triggers `publish.yml`. Watch it:

```bash
gh run watch
# or
gh run list --workflow=publish.yml --limit 1
```

GitHub Release with auto-generated notes is created by the workflow as
the last step of `publish-pypi`. **Do not** create it manually with
`gh release create` — the workflow does that and attaches the published
artifacts.

## Step 3 — Verify the release

After `publish.yml` finishes (≈ 5–7 min):

```bash
# 1. PyPI page renders the new version
open https://pypi.org/project/nasde-toolkit/

# 2. Fresh install resolves the tagged version
uv tool install nasde-toolkit
nasde --version    # should print X.Y.Z (no .devN suffix)

# 3. GitHub Release exists with auto-generated notes
gh release view vX.Y.Z
```

If `publish.yml` failed, see [Recovering from a failed release](#recovering-from-a-failed-release) below.

## Hotfixing an older release line

If `main` has moved on (say we're on `0.3.x`) and a user on `0.2.x` hits
a critical bug that needs a `0.2.4`:

1. **Create a release branch from the last tag in that line.**
   ```bash
   git checkout -b release/0.2.x v0.2.3
   git push -u origin release/0.2.x
   ```

2. **Cherry-pick the fix commits from main** onto the release branch.
   ```bash
   git cherry-pick <sha1> <sha2>
   ```

3. **Update `CHANGELOG.md` on the release branch** — insert a new
   `## [0.2.4] — YYYY-MM-DD` section between the previous entries.
   Do *not* touch `[Unreleased]` on this branch; that's only meaningful
   on `main`.

4. **Tag the release branch, not `main`.**
   ```bash
   git tag v0.2.4
   git push origin v0.2.4
   ```

   ⚠️ `publish.yml` enforces "tag must be reachable from main". For a
   hotfix on a release branch, that check **will fail** and block the
   PyPI publish. You have two options:

   - **Recommended:** forward-port the fix to `main` first (step 7
     below), then cherry-pick the merge commit onto `release/0.X.x`,
     then tag. The tag commit will be ancestor-equal to a commit on
     main, satisfying the guard.
   - **Alternative:** publish manually with `uv publish` from the
     release branch checkout. Document the deviation in the GitHub
     Release notes.

5. **Mark the GitHub Release as "not latest"** so it doesn't overshadow
   the newer main-line release. The workflow creates it with
   auto-generated notes; edit afterwards:
   ```bash
   gh release edit v0.2.4 --latest=false
   ```

6. **Keep the release branch alive** — `release/0.X.x` is the home for
   future fixes on that line. Do not delete it.

7. **Forward-port the fix to `main`** if it isn't there already (usually
   the cherry-pick came from main, but double-check).

We currently only commit to supporting the **latest** release line in
`SECURITY.md`. If you find yourself hotfixing an older line, update that
doc in the same PR so the promise matches reality.

## How `publish.yml` works

The release pipeline is one workflow with linear jobs gated by smoke
tests. Source: `.github/workflows/publish.yml`.

```
quality-gate (lint + mypy + pytest + audit)
    │
    ▼
build (uv build → wheel + sdist; verifies version matches tag)
    │
    ▼
publish-testpypi (Trusted Publisher OIDC, skip-existing on conflict)
    │
    ▼
smoke-test-testpypi (fresh install in clean venv, runs `nasde --version`/`--help`)
    │  ◄── GATE: failure here blocks publish-pypi
    ▼
publish-pypi (Trusted Publisher OIDC; rejects tags not on main; creates GH Release)
    │
    ▼
smoke-test-pypi (final fresh-install sanity check from production PyPI)
```

### Triggers

| Trigger | Result | When to use |
|---|---|---|
| Tag push (`v*`) on commit reachable from main | Full flow → PyPI release | Standard release |
| Tag push from non-main branch | Build + TestPyPI succeed; publish-pypi rejects with "not on main" | Catches accidental tags from feature branches |
| Manual `gh workflow run publish.yml --ref <branch>` (default) | Build + TestPyPI + smoke; publish-pypi **skipped** | Pre-release dry-run, debugging the pipeline |
| Manual `gh workflow run publish.yml --ref main --field publish_to_prod=true` | Full flow → PyPI publish without a tag | Disaster recovery only |
| Weekly cron (Mon 09:00 UTC) | TestPyPI + smoke; publish-pypi **skipped** | Catches transitive-dep breakage between releases |

### TestPyPI dry-run from any branch

Verify a release candidate without cutting a tag — useful for testing
release-related changes (build config, deps bumps, etc.):

```bash
gh workflow run publish.yml --ref <your-branch>
```

Output goes to https://test.pypi.org/project/nasde-toolkit/ as
`X.Y.Z.devN` (where N is the commit count since the last tag). The
smoke-test-testpypi job verifies the install works in a clean venv.
PyPI is never touched.

If two branches happen to produce the same `devN` filename, TestPyPI
rejects the second upload and `skip-existing: true` makes the workflow
ignore that error — but **the file on TestPyPI is the older one**. To
force a fresh upload, add an empty commit (`git commit --allow-empty`)
to bump the dev counter, or delete the file from TestPyPI manually.

### Recovering from a failed release

| Failure point | What happened | Fix |
|---|---|---|
| `quality-gate` red on tag commit | Tests broke between PR merge and tag | Push fix to main, tag `vX.Y.(Z+1)` |
| `build` reports version mismatch | Tag pointed at wrong commit | Delete the tag, re-tag the right commit |
| `publish-testpypi` 400 "File already exists" | TestPyPI already has this `devN` | Workflow ignores via `skip-existing`. If you actually need a new file, bump dev counter (empty commit) |
| `smoke-test-testpypi` failed on import error | Broken transitive dep wheel (e.g. supabase 2.28.3 historically) | Pin the broken transitive dep in `pyproject.toml`, push fix to main, tag a new patch release |
| `smoke-test-testpypi` failed on flaky network | TestPyPI index propagation delay | "Re-run failed jobs" in GitHub Actions UI — uses cached build artifact, doesn't re-tag |
| `publish-pypi` rejected with "not on main" | Tag was pushed from a feature branch | Push the tag from main: `git checkout main && git tag vX.Y.Z <commit-on-main> && git push origin vX.Y.Z` |
| `publish-pypi` failed on PyPI auth | OIDC token issue or PyPI outage | Wait, then "Re-run failed jobs". Or: `gh workflow run publish.yml --ref main --field publish_to_prod=true` (disaster recovery) |
| Workflow succeeded but installed package broken | Smoke test missed something | Yank on PyPI: `uv tool run twine yank nasde-toolkit X.Y.Z`. Then publish `X.Y.(Z+1)` with the fix |

**Do not** edit a published tag or re-publish over an existing PyPI version. PyPI rejects file reuse anyway.

## What NOT to do

- **Do not amend or move a published tag.** If `vX.Y.Z` went out wrong,
  cut `vX.Y.(Z+1)` with the fix. Tags are immutable from the user's
  perspective the moment they're on GitHub. PyPI also rejects file reuse,
  so re-publishing the same version is impossible anyway.
- **Do not `git push --force` to `main`.** Even if nobody has pulled yet,
  force-push rewrites the commit that `hatch-vcs` will anchor future
  versions on. Fix-forward with a new commit.
- **Do not skip CI** (`--no-verify` on the release commit, etc.). If CI
  is flaky, file an issue and wait; if CI found a real problem, the
  release stops until it's fixed.
- **Do not bundle a release with unrelated work.** The release PR should
  only touch `CHANGELOG.md` (and this document, if you're updating the
  procedure). Feature work lands in its own PR first.
- **Do not hand-edit `src/nasde_toolkit/_version.py`.** It's generated by
  `hatch-vcs` at build time and gitignored. Any manual changes will be
  lost on the next build.
- **Do not create the GitHub Release manually.** `publish.yml` does it as
  the last step of `publish-pypi` and attaches the published artifacts.
  A manually-created release would race with the workflow and leave you
  with two releases for the same tag.
- **Do not use `publish_to_prod=true` for routine verification.** Default
  manual dispatch (`gh workflow run publish.yml`) goes to TestPyPI only —
  that's the right tool for dry-runs. `publish_to_prod=true` is for
  disaster recovery (publishing without a tag) and leaves a confusing
  `X.Y.Z.devN` "release" on PyPI.

## Future work (tracked, not required today)

- **Dependency automation.** Dependabot or Renovate would keep
  `uv.lock` fresh without a human in the loop. For now, the `pip-audit`
  CI gate catches anything that acquires a CVE.
- **Automated changelog assist.** `release-drafter` or similar to pre-fill
  the `[Unreleased]` section from merged PR titles. Nice to have, not
  urgent.
- **Smoke test should exercise `nasde run`.** Today it only runs
  `--version` and `--help`. A minimal benchmark trial (e.g. one task on
  the simplest example) would catch runner/evaluator regressions that
  pure import smoke misses.

## Questions, wake-ups, gotchas

- **What if I forgot to update `CHANGELOG.md` before tagging?** Not the
  end of the world — edit the GitHub Release notes, then backfill the
  CHANGELOG in the next commit on `main`. The next release PR picks it
  up naturally.
- **What if `hatch-vcs` reports a weird version like
  `0.2.1.dev0+dirty`?** Your working tree wasn't clean at build time. Run
  `git status`, stash or commit the stray changes, and `uv build` again.
- **What if I want to pre-release something (`v0.3.0a1`)?** Tag it
  exactly like that; hatch-vcs handles PEP 440 suffixes. Create the GH
  Release with `--prerelease` instead of `--latest`. CHANGELOG entry goes
  under a `## [0.3.0a1] — YYYY-MM-DD` header.
