# Windows compatibility issues — 2026-05-09

Discovered while verifying [PR #45](https://github.com/NoesisVision/nasde-toolkit/pull/45) end-to-end on Windows 11 + PowerShell 5.1 + Polish locale (cp1250). PR #45 itself works correctly; the issues below are pre-existing Windows-only friction points that surfaced during the verification run.

Verification environment:
- Windows 11 Pro 26100
- PowerShell 5.1 (default; not pwsh 7+)
- Console code page: **cp1250** (Polish locale)
- `git config --get core.autocrlf` → `true` (Windows default)
- uv 0.9.x, two interpreters installed: cpython 3.13.13 and 3.13.4

This document lists **3 open issues** that need follow-up tickets. Two issues found during the same session are already resolved on the [`fix/gitattributes-lf`](https://github.com/NoesisVision/nasde-toolkit/tree/fix/gitattributes-lf) branch and are summarized at the bottom for context.

## TL;DR — open issues (create tickets for these)

| # | Issue | Severity | Workaround |
|---|-------|----------|------------|
| 1 | `nasde install-skills` `UnicodeEncodeError` on `✓` (cp1250) | High (lies via exit code) | None — files are copied; ignore exit 1 |
| 2 | `nasde run` `UnicodeEncodeError` on `⠋` Braille spinner (cp1250) | **Blocker** (every nasde call dies) | `$env:PYTHONUTF8='1'` before any nasde call |
| 3 | Daytona extras missing — `harbor[daytona]` not pulled by nasde | High (any cloud env fails) | `uv run --with 'harbor[daytona]' nasde …` |

> **Already resolved (no ticket needed), listed for context:**
> - **uv selecting Python 3.14 → MSVC source-build of `pyiceberg`** — resolved in `README.md` (every install command documents `--python 3.13`, see lines 46, 52, 215, 221). The pitfall only hits operators who run `uv tool install .` without consulting README.
> - **Shell script CRLF breaks Linux verifier in sandbox** — resolved on `fix/gitattributes-lf`: repo-wide `.gitattributes` enforcing `*.sh text eol=lf` + dos2unix on 17 `.sh` and 8 `Dockerfile` files. Skill-level docs added to `nasde-benchmark-creator`, `nasde-benchmark-from-history`, `nasde-benchmark-from-public-repos`.
> - **`Path.write_text` default translates `\n`→`\r\n` on Windows** — resolved on `fix/gitattributes-lf`: `scaffold/__init__.py:_write_if_missing` now passes `newline=""` and `encoding="utf-8"` so `nasde init` writes deterministic LF on every OS.

---

## Issue 1 — `nasde install-skills` UnicodeEncodeError on `✓` (cp1250)

### Severity: High (skills are installed, but exit code is 1)

`nasde install-skills` exits with code 1 on Polish Windows PowerShell, even though the skill directories were correctly copied.

### Root cause

- `src/nasde_toolkit/skills_installer.py:_print_summary` prints `f"[green]✓ Installed {len(installed)} skill(s) …"`.
- Rich detects a Windows console and uses its `legacy_windows_render` path (`rich/_win32_console.py`).
- That path calls the system's locale-defined codec on each rune. On cp1250, U+2713 (✓) is not mapped, raising `UnicodeEncodeError` from `cp1250.py:19`.
- `shutil.copytree` for each skill runs **before** `_print_summary`, so all skills land on disk before the crash.

### Repro

```powershell
# Polish Windows console (cp1250 default):
nasde install-skills --force
# → UnicodeEncodeError: 'charmap' codec can't encode character '✓'
# → exit 1
# But:
ls $env:USERPROFILE\.claude\skills\
# → all 4 nasde-* skills present with fresh timestamps
```

### Impact

- Direct: misleading exit code; CI scripts and automation that check `$LASTEXITCODE` will treat a successful install as failure.
- Indirect: erodes trust in tooling; every nasde install on PL Windows looks broken.

### Workaround

```powershell
$env:PYTHONUTF8 = '1'
nasde install-skills --force
# → completes cleanly with exit 0
```

This works because `PYTHONUTF8=1` puts CPython in UTF-8 mode, so stdout encodes via UTF-8 instead of cp1250.

### Proposed fix

Either:
1. Replace `✓` and `•` glyphs in `_print_summary` with ASCII (`[OK]`, `-`). Trivial, eliminates the crash unconditionally.
2. At CLI entrypoint (`cli.py`), set `os.environ.setdefault("PYTHONUTF8", "1")` before importing Rich. Affects all commands.
3. Reconfigure stdout encoding manually:
   ```python
   import sys
   if sys.platform == "win32":
       sys.stdout.reconfigure(encoding="utf-8")
       sys.stderr.reconfigure(encoding="utf-8")
   ```

Recommendation: **(2)** — single-line change, fixes Issues 2 and 3 simultaneously.

---

## Issue 2 — `nasde run` UnicodeEncodeError on `⠋` (Braille progress spinner)

### Severity: Blocker — every benchmark run dies before doing real work

This is the same family as Issue 1 but more severe because it affects the main `nasde run` command, not just install.

### Root cause

- Rich's `Progress` widget uses Braille spinner glyphs U+2800..U+28FF (`⠁`, `⠂`, `⠋`, …).
- When stdout is redirected (`> log 2>&1` or in a non-TTY context), Rich SHOULD detect non-TTY and disable spinner — but on Windows, the detection path differs and the spinner still tries to write Braille characters.
- cp1250 doesn't include U+280B → `UnicodeEncodeError` → process exits before Harbor even creates a sandbox.

### Repro

```powershell
# No env vars set:
nasde run --variant claude-vanilla --tasks foo --without-eval -C examples/refactoring-skill
# → UnicodeEncodeError: 'charmap' codec can't encode character '⠋'
# → process dies immediately after printing the run-config banner
```

### Impact

`nasde run` is the primary command. Every Windows user with PL/non-UTF-8 locale hits this on their first attempt and gives up.

### Workaround

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
nasde run …
```

Alternative: change console code page to UTF-8 with `chcp 65001` before each session.

### Proposed fix

Same as Issue 1 — set `PYTHONUTF8=1` programmatically at CLI entrypoint. One-liner in `cli.py`:

```python
import os, sys
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
```

…executed before any Rich import.

---

## Issue 3 — `harbor[daytona]` extra not pulled by nasde

### Severity: High (any `--harbor-env daytona|modal|e2b|runloop|gke` fails)

### Root cause

`pyproject.toml` declares `harbor` as a plain dependency, not `harbor[daytona]` or `harbor[cloud]`. Harbor's daytona environment class raises `MissingExtraError` at constructor time when `daytona-sdk` isn't importable.

### Repro

```powershell
$env:DAYTONA_API_KEY = "..."
nasde run --variant foo --tasks bar -C bench --harbor-env daytona --without-eval
# → MissingExtraError: The 'daytona' package is required but not installed.
#    Install it with:
#      pip install 'harbor[daytona]'
#      uv tool install 'harbor[daytona]'
```

### Impact

Cross-platform issue, not Windows-specific — but on Windows it compounds with Issue 2 because Issue 2 hides Issue 3 behind a more confusing crash message.

### Workaround

```powershell
uv run --with 'harbor[daytona]' nasde run --harbor-env daytona …
```

Or for the global tool:
```powershell
uv tool install --reinstall --with 'harbor[daytona]' .
```

### Proposed fix

Three options, in order of preference:

1. **Add `harbor[cloud]` as a default dependency** — small package size impact, every user gets daytona/modal/e2b/runloop/gke out of the box.
2. **Document explicit `--with` syntax** in README and `--harbor-env` help text.
3. **Detect missing extra at CLI level** and print actionable message:
   ```
   error: --harbor-env daytona requires the 'harbor[daytona]' extra.
   install with: uv tool install --reinstall --with 'harbor[daytona]' .
   ```

Recommendation: **(1)**. The current behavior trades ~30 MB of disk for a setup wall every cloud user hits.

---

## Cross-cutting recommendations

### Tier 1 — should land before announcing nasde for Windows

- **Set `PYTHONUTF8=1` at CLI entrypoint** on Windows (fixes Issues 1, 2 with one line).

### Tier 2 — quality of life

- **Add `harbor[cloud]` to default deps** OR detect-and-actionable-error on missing extra (Issue 3).
- **Replace Unicode glyphs (`✓`, `•`) in user-facing print statements with ASCII fallbacks**, even with PYTHONUTF8 on, so error paths don't crash on font/console edge cases.

---

## Verification environment for reproduction

```
OS:          Windows 11 Pro 26100
Shell:       PowerShell 5.1 (powershell.exe, NOT pwsh 7+)
Locale:      Polish, console code page cp1250
Python:      cpython 3.13.13 + 3.14.4 installed (uv-managed)
uv:          0.9.x
git:         2.x with core.autocrlf=true (default)
nasde:       0.3.3.dev5 (PR #45 head)
```

To reproduce on a clean machine, ensure these conditions match — especially the cp1250 locale, which is what surfaces Issues 1 and 2. On `en-US` Windows (cp1252), Issue 1's `✓` (U+2713) would *not* crash, because cp1252 also lacks U+2713 but Rich's path differs. The Braille spinner from Issue 2 fails on both cp1250 and cp1252 since neither covers U+2800.
