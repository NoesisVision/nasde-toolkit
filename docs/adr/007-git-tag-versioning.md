# ADR-007: Git tag-based versioning via hatch-vcs

**Status:** Accepted
**Date:** 2026-03-26

## Context

nasde-toolkit has its version hardcoded in two places (`pyproject.toml` and `src/nasde_toolkit/__init__.py`). There are no git tags and no release automation. This means:

- Version bumps require manual edits in two files
- `nasde --version` can drift from the actual release state
- There is no way to install a specific tagged release
- Users install from HEAD, potentially getting broken commits

We want a single source of truth for versioning derived from git tags, enabling proper release workflows.

## Decision

Use **hatch-vcs** to derive the package version from git tags.

## Alternatives considered

### setuptools-scm (directly)

setuptools-scm is the mature, widely-used engine for git-based versioning. However, nasde-toolkit already uses `hatchling` as its build backend. Using setuptools-scm directly would require either:

- Switching the build backend to setuptools (unnecessary churn, diverges from UV ecosystem conventions)
- Using setuptools-scm as a standalone library with custom integration (non-standard, fragile)

### hatch-vcs

hatch-vcs is a hatchling plugin that wraps setuptools-scm. It is the native versioning plugin for the hatchling build backend. Benefits:

- **Zero backend change** — hatchling is already the build backend
- **UV ecosystem alignment** — UV generates hatchling projects by default; ruff, uv, and hatch themselves use this pattern
- **Automatic `_version.py` generation** — build hook creates the version file at build time
- **Dev version support** — commits after a tag produce versions like `0.1.1.dev3+gabcdef`

## Consequences

- Version is derived from git tags (format: `v0.1.0`)
- `_version.py` is auto-generated and gitignored
- Releasing = creating a git tag
- Developers working from a shallow clone or detached HEAD get a fallback version
