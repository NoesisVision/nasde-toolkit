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

# 2b. (Temporary — until PyPI.) Bump the pinned tag in user-facing docs
#     so copy-paste installs land on the new version:
#       grep -rn "@vOLD" README.md docs/ examples/
#     then update every hit (README has two install commands).

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

# 5. Publish the GitHub Release from the tag
gh release create vX.Y.Z \
  --title "vX.Y.Z — <one-line theme>" \
  --notes-file .release-notes.tmp \
  --latest

# Optional sanity check: version derived from the tag
uv build
ls dist/    # should contain nasde_toolkit-X.Y.Z-*.whl and *.tar.gz
```

The rest of this document explains each step, how to pick the version
number, how to hotfix an older release, and what **not** to do.

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

6. **Bump the pinned version in user-facing docs** *(temporary — remove
   this step once we publish to PyPI).* Until `nasde` is on PyPI, the
   install command in the README pins to a specific git tag, and that
   tag number has to be updated alongside the release. Otherwise a
   copy-paste from the README installs a stale version and nobody
   notices.

   Find the stale pins:

   ```bash
   grep -rn "@v[0-9]" README.md docs/ examples/
   ```

   Expected hits today: two `uv tool install …@vOLD` lines in `README.md`
   (one in *Quick start*, one in *Installation reference*), plus the
   `(e.g. \`vOLD\`)` example sentence nearby. Update each to `vNEW`.
   Anywhere else `@vOLD` appears in user-facing docs, update it too.

   Skip: anything inside `CHANGELOG.md` (those pins are historical and
   must stay on the version they described) and anywhere `vOLD` appears
   as a reference for a diff/compare link.

7. Open a PR titled `chore: release vX.Y.Z`. The PR body should be the
   changelog section for this release, so reviewers see exactly what
   goes out.

8. **Wait for CI to go green, then merge.** Prefer a squash merge so the
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
- **Do not push a tag with `git push --tags`** — push the single tag by
  name. This avoids accidentally publishing stale local tags.
- The tag triggers no workflow today. `hatch-vcs` picks up the tag at
  build time; nothing else is automated yet.

## Step 3 — Create the GitHub Release

```bash
# Extract the notes for this version from CHANGELOG.md
awk "/^## \\[X\\.Y\\.Z\\]/,/^## \\[/" CHANGELOG.md \
  | sed '$d' > .release-notes.tmp     # drop trailing "## [" of next section

gh release create vX.Y.Z \
  --title "vX.Y.Z — <one-line theme>" \
  --notes-file .release-notes.tmp \
  --latest

rm .release-notes.tmp
```

The `--latest` flag controls what users see on the repo homepage. Always
set it on the newest release and never on a hotfix for an older line.

If the `awk` / `sed` dance is finicky for you, paste the release section
from `CHANGELOG.md` manually into `gh release create ... --notes "..."`
or drop the `--notes-file` flag and let `gh` open `$EDITOR`. Either way,
the release notes on GitHub should match the CHANGELOG entry for that
version — **don't let them drift.**

## Step 4 — Sanity check the build (optional but recommended)

```bash
git checkout vX.Y.Z
uv build
ls dist/
```

You should see exactly `nasde_toolkit-X.Y.Z-py3-none-any.whl` and
`nasde_toolkit-X.Y.Z.tar.gz`. If you see `X.Y.Z.dev…+gabcdef`, the tag
isn't pointing where you think it is — check `git describe`.

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

5. **Create the GitHub Release without `--latest`** so it doesn't
   overshadow the newer `main`-line release:
   ```bash
   gh release create v0.2.4 --title "v0.2.4" --notes-file …
   ```

6. **Keep the release branch alive** — `release/0.X.x` is the home for
   future fixes on that line. Do not delete it.

7. **Forward-port the fix to `main`** if it isn't there already (usually
   the cherry-pick came from main, but double-check).

We currently only commit to supporting the **latest** release line in
`SECURITY.md`. If you find yourself hotfixing an older line, update that
doc in the same PR so the promise matches reality.

## What NOT to do

- **Do not amend or move a published tag.** If `vX.Y.Z` went out wrong,
  cut `vX.Y.(Z+1)` with the fix. Tags are immutable from the user's
  perspective the moment they're on GitHub.
- **Do not `git push --force` to `main`.** Even if nobody has pulled yet,
  force-push rewrites the commit that `hatch-vcs` will anchor future
  versions on. Fix-forward with a new commit.
- **Do not skip CI** (`--no-verify` on the release commit, manual
  `gh release create` while the quality gate is red, etc.). If CI is
  flaky, file an issue and wait; if CI found a real problem, the release
  stops until it's fixed.
- **Do not bundle a release with unrelated work.** The release PR should
  only touch `CHANGELOG.md` (and this document, if you're updating the
  procedure). Feature work lands in its own PR first.
- **Do not hand-edit `src/nasde_toolkit/_version.py`.** It's generated by
  `hatch-vcs` at build time and gitignored. Any manual changes will be
  lost on the next build.
- **Do not publish to PyPI** until we've set that up properly (PyPI org
  account, `publish-to-pypi` workflow with trusted publisher, signature
  policy). Until then, users install from a git tag:
  `uv tool install git+https://github.com/NoesisVision/nasde-toolkit.git@vX.Y.Z`.

## Future work (tracked, not required today)

- **PyPI publishing.** We'll want a `publish-to-pypi.yml` workflow that
  triggers on tag push, uses PyPI Trusted Publishers (no long-lived token),
  and `uv publish` from the same wheel `hatch-vcs` produces. Document here
  once set up and link back from the README. **When this lands, delete
  Step 6 ("Bump the pinned version in user-facing docs") and the matching
  `# 2b` block in the TL;DR** — `pip install nasde-toolkit` is
  version-agnostic, so the README pins go away too.
- **Dependency automation.** Dependabot or Renovate would keep
  `uv.lock` fresh without a human in the loop. For now, the `pip-audit`
  CI gate catches anything that acquires a CVE.
- **Automated changelog assist.** `release-drafter` or similar to pre-fill
  the `[Unreleased]` section from merged PR titles. Nice to have, not
  urgent.

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
