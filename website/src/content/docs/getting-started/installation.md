---
title: Installation
description: Install nasde via uv, pipx, pip, or from source — plus upgrade and version-check details.
---

The [Quick Start](/nasde-toolkit/getting-started/quick-start/) uses `uv tool install` — recommended because it isolates `nasde` in its own environment and puts only the `nasde` command on PATH. Alternatives:

```bash
# pipx — analogous isolation, popular in Python community
pipx install nasde-toolkit --python 3.13

# Inside an existing virtual environment (3.12 or 3.13)
pip install nasde-toolkit

# Latest unreleased changes from main (for testing PRs and dev builds)
uv tool install git+https://github.com/NoesisVision/nasde-toolkit.git --python 3.13

# Local clone (for developing NASDE itself)
git clone git@github.com:NoesisVision/nasde-toolkit.git
cd nasde-toolkit
uv sync
```

## Upgrading

Upgrading to the newest release:

```bash
uv tool upgrade nasde-toolkit       # if installed via uv tool
pipx upgrade nasde-toolkit          # if installed via pipx
pip install --upgrade nasde-toolkit # if installed via pip
```

`nasde` checks PyPI for newer releases on startup and prints a one-line notice on stderr when an upgrade is available (severity-tinted: patch / minor / major). Disable with `NASDE_NO_UPDATE_CHECK=1` or `CI=true`.

## What gets installed

After installation, only `nasde` appears on PATH. Harbor and Opik are bundled as core dependencies. The reviewer agent spawns your already-installed `claude` or `codex` CLI as a subprocess (not bundled), so it reuses whatever authentication you've set up interactively.

Check the installed version with `nasde --version`. Stable releases follow semver tags (e.g. `v0.3.2`); dev installs from `main` show versions like `0.3.2.dev3`.

Release notes for every tagged version live in [CHANGELOG.md](https://github.com/NoesisVision/nasde-toolkit/blob/main/CHANGELOG.md). See [docs/RELEASING.md](https://github.com/NoesisVision/nasde-toolkit/blob/main/docs/RELEASING.md) if you're cutting a release yourself.
