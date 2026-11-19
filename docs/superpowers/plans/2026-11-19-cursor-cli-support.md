# Cursor CLI Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let nasde benchmark Cursor's `cursor-agent` as a variant (`agent = "cursor"`) and use it as an assessment judge (`[evaluation] backend = "cursor"`), with correct per-trial cost.

**Architecture:** A thin `ConfigurableCursor` subclass of Harbor 0.24's built-in `CursorCli` agent plus runner wiring that mirrors Codex (`AGENTS.md`, `agents_skills/`, native skill channel). Cursor model names are recorded `cursor/`-qualified, and the price lookup walks `cursor/<slug>` → `cursor/<base>` → `<slug>` → `<base>` so Cursor-specific rates (Claude cache writes at 1.25x) override vendor rates for Cursor trials only. A third subprocess judge backend runs `cursor-agent -p --mode ask` from a throwaway workspace.

**Tech Stack:** Python 3.13, Typer + Rich, Harbor 0.24 (`harbor.agents.installed.cursor_cli`), pytest, ruff, mypy, `uv`.

**Spec:** `docs/superpowers/specs/2026-11-19-cursor-cli-support-design.md`

## Global Constraints

- Code style (CLAUDE.md): type hints on all public functions; `@dataclass` for internal models; Rich console for all output, no bare `print()`.
- **No comments inside method bodies.** Docstrings are fine. Use descriptive names instead.
- Function order in a module: public functions first (alphabetical), then private helpers ordered caller-before-callee.
- Snake_case file names.
- Cursor sandbox auth is `CURSOR_API_KEY` only. No login-token injection.
- Cursor variants use `AGENTS.md` → `/app/AGENTS.md` and `agents_skills/` (native skill channel, ADR-012).
- A Cursor agent's recorded `model_name` is `cursor/<slug>`; the runner adds the prefix to a bare slug.
- No local validation of model names or effort levels; Harbor / `cursor-agent` reject bad values.
- Default Cursor judge model when `[evaluation] model` is absent: `claude-opus-5-5-high`.
- Bundled `cursor/` price entries: `as_of = "2026-11-19"`, `source = "https://cursor.com/docs/models-and-pricing"`.
- Every user-visible change gets a `CHANGELOG.md` `## [Unreleased]` entry with a `[#NN]` link-ref in the same PR.
- Quality gates before every commit that ends a PR: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/nasde_toolkit/`, `uv run pytest`.
- Every live LLM run (Tasks 10 and 14) must be individually authorized by the repo owner before it starts.

## Branches and PRs

Three PRs, as in the spec's rollout section:

| PR | Branch | Base | Tasks |
|---|---|---|---|
| 1. Economics | `feat/cursor-pricing` | `main` | 1–5 |
| 2. Cursor agent | `feat/cursor-agent` | `feat/cursor-pricing` | 6–10 |
| 3. Cursor judge | `feat/cursor-judge` | `main` | 11–14 |

The spec and this plan live on `feat/cursor-cli-support`; cherry-pick its commits onto `feat/cursor-pricing` so the design ships with PR 1.

Pushing needs write access to `origin` (`krzykrucz/nasde-toolkit`). The current account gets a 403; either get collaborator access or push to a fork and open the PRs from it.

```bash
git switch main && git pull --ff-only
git switch -c feat/cursor-pricing
git cherry-pick main..feat/cursor-cli-support
```

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/nasde_toolkit/pricing.py` | Modify | `normalize_model_slug`, `resolve_catalog_key`; `compute_cost_usd` / `pricing_as_of` use the layered lookup |
| `src/nasde_toolkit/pricing.toml` | Modify | `cursor/` entries + lookup comment |
| `src/nasde_toolkit/pricing_report.py` | Modify | `priced_as_label` |
| `src/nasde_toolkit/token_metrics.py` | Modify | Cache-write fallback to Cursor's `usage_totals`; `agent_reported_cost_*` |
| `src/nasde_toolkit/evaluator.py` | Modify | `AssessmentSummary` gains audit fields |
| `src/nasde_toolkit/results_exporter.py` | Modify | Audit fields in `metrics.json`; `catalog_key` in `pricing_used.json` |
| `src/nasde_toolkit/runner.py` | Modify | Pricing-used table labels; Cursor agent wiring; model qualification |
| `src/nasde_toolkit/agents/configurable_cursor.py` | Create | `ConfigurableCursor` |
| `src/nasde_toolkit/config.py` | Modify | Backend-aware default judge model |
| `src/nasde_toolkit/cli.py` | Modify | `--eval-backend cursor` |
| `src/nasde_toolkit/evaluator_backends/cursor_subprocess.py` | Create | `CursorSubprocessBackend` |
| `src/nasde_toolkit/evaluator_backends/__init__.py` | Modify | Factory branch |
| `src/nasde_toolkit/scaffold/__init__.py` | Modify | Commented `backend` line |
| `examples/ddd-architectural-challenges/variants/cursor-vanilla/` | Create | Example variant |
| `docs/adr/015-cursor-cli-agent-and-judge.md` | Create | ADR |
| `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `.claude/skills/nasde-*/SKILL.md` | Modify | Docs |
| `tests/test_pricing.py`, `tests/test_token_metrics.py`, `tests/test_results_exporter.py`, `tests/test_runner_economics.py`, `tests/test_evaluator.py`, `tests/test_runner.py`, `tests/test_runner_skills.py`, `tests/test_configurable_agents_options.py`, `tests/test_config.py`, `tests/test_cli.py`, `tests/test_evaluator_backends.py`, `tests/test_scaffold.py` | Modify | Tests |
| `tests/test_configurable_cursor.py` | Create | Agent tests |

---

## PR 1 — Economics

### Task 1: Layered price-key lookup

**Files:**
- Modify: `src/nasde_toolkit/pricing.py`
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: `normalize_model_slug(model: str) -> str` and `resolve_catalog_key(model: str, catalog: Mapping[str, object]) -> str | None` in `nasde_toolkit.pricing`. `compute_cost_usd` and `pricing_as_of` keep their signatures but now resolve through `resolve_catalog_key`.

- [ ] **Step 1: Write the failing tests**

Add `ModelPrice`, `normalize_model_slug` and `resolve_catalog_key` to the existing `from nasde_toolkit.pricing import (...)` block in `tests/test_pricing.py`, then append:

```python
@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("claude-opus-5-5-high", "claude-opus-5-5"),
        ("claude-sonnet-5-5-xhigh", "claude-sonnet-5-5"),
        ("claude-fable-5-thinking-high", "claude-fable-5"),
        ("claude-fable-5-thinking", "claude-fable-5"),
        ("gpt-5.6-sol-none", "gpt-5.6-sol"),
        ("gpt-5.3-codex-xhigh", "gpt-5.3-codex"),
        ("muse-wonder-1.0-minimal", "muse-wonder-1.0"),
        ("composer-2.5[effort=high]", "composer-2.5"),
        ("claude-opus-4-8[context=1m,effort=high,fast=false]", "claude-opus-4-8"),
        ("cursor/claude-opus-5-5-high", "cursor/claude-opus-5-5"),
        ("composer-2.5", "composer-2.5"),
        ("claude-opus-5-5-fast", "claude-opus-5-5-fast"),
        ("gpt-5.4-mini", "gpt-5.4-mini"),
    ],
)
def test_normalize_model_slug(slug: str, expected: str) -> None:
    assert normalize_model_slug(slug) == expected


def test_resolve_catalog_key_prefers_exact_match() -> None:
    catalog = {"cursor/claude-opus-5-5-high": 1, "cursor/claude-opus-5-5": 2, "claude-opus-5-5": 3}
    assert resolve_catalog_key("cursor/claude-opus-5-5-high", catalog) == "cursor/claude-opus-5-5-high"


def test_resolve_catalog_key_then_prefixed_base() -> None:
    catalog = {"cursor/claude-opus-5-5": 2, "claude-opus-5-5": 3}
    assert resolve_catalog_key("cursor/claude-opus-5-5-high", catalog) == "cursor/claude-opus-5-5"


def test_resolve_catalog_key_then_unprefixed_slug() -> None:
    catalog = {"claude-opus-5-5-high": 4, "claude-opus-5-5": 3}
    assert resolve_catalog_key("cursor/claude-opus-5-5-high", catalog) == "claude-opus-5-5-high"


def test_resolve_catalog_key_then_vendor_base() -> None:
    catalog = {"claude-opus-5-5": 3}
    assert resolve_catalog_key("cursor/claude-opus-5-5-high", catalog) == "claude-opus-5-5"


def test_resolve_catalog_key_unknown_is_none() -> None:
    assert resolve_catalog_key("cursor/auto", {"claude-opus-5-5": 3}) is None


def test_resolve_catalog_key_bare_model_never_reaches_cursor_entry() -> None:
    catalog = {"cursor/claude-opus-5-5": 2, "claude-opus-5-5": 3}
    assert resolve_catalog_key("claude-opus-5-5", catalog) == "claude-opus-5-5"
    assert resolve_catalog_key("claude-sonnet-5-5", {"cursor/claude-sonnet-5-5": 2}) is None


def test_resolve_catalog_key_strips_google_prefix() -> None:
    assert resolve_catalog_key("google/gemini-3-flash-preview", {"gemini-3-flash-preview": 1}) == "gemini-3-flash-preview"


def test_compute_cost_uses_normalized_key() -> None:
    pricing = {"m": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}
    assert compute_cost_usd(1_000_000, 1_000_000, "cursor/m-high", pricing) == pytest.approx(3.0)


def test_pricing_as_of_uses_normalized_key() -> None:
    pricing = {"m": ModelPrice(input_per_1m=1.0, output_per_1m=2.0, as_of="2026-11-19")}
    assert pricing_as_of("cursor/m-high", pricing) == "2026-11-19"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_pricing.py -v`
Expected: collection fails with `ImportError: cannot import name 'normalize_model_slug'`.

- [ ] **Step 3: Implement**

In `src/nasde_toolkit/pricing.py`, extend the imports:

```python
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
```

Below `console = Console()`, add:

```python
_BRACKET_PARAMS_RE = re.compile(r"\[[^\[\]]*\]$")
_EFFORT_SUFFIX_RE = re.compile(r"(?:-thinking)?-(?:none|minimal|low|medium|high|xhigh|max)$|-thinking$")
```

Replace the lookup at the top of `compute_cost_usd`'s body:

```python
    catalog_key = resolve_catalog_key(model, pricing)
    if catalog_key is None:
        console.print(
            f"  [yellow]No pricing for model {model!r} — cost left unset. "
            f"Add it (or its base model) to pricing.toml to enable cost metrics.[/yellow]"
        )
        return None
    price = pricing[catalog_key]
```

Insert `normalize_model_slug` between `load_pricing_layered` and `pricing_as_of`:

```python
def normalize_model_slug(model: str) -> str:
    """Strip bracket params and one trailing effort/thinking suffix from a model slug.

    Cursor encodes effort in its slugs (``claude-opus-5-5-high``,
    ``claude-fable-5-thinking-xhigh``) and accepts bracket overrides
    (``composer-2.5[effort=high]``); neither changes the per-token price.
    ``-fast`` is deliberately not stripped: fast modes bill at a higher rate.
    """
    without_params = _BRACKET_PARAMS_RE.sub("", model)
    return _EFFORT_SUFFIX_RE.sub("", without_params)
```

Replace `pricing_as_of`:

```python
def pricing_as_of(model: str, pricing: dict[str, ModelPrice]) -> str | None:
    """Return the as_of date stamped on the price that covers the model, if priced."""
    catalog_key = resolve_catalog_key(model, pricing)
    return pricing[catalog_key].as_of if catalog_key is not None else None
```

Insert `resolve_catalog_key` between `pricing_as_of` and `resolve_pricing_layers`:

```python
def resolve_catalog_key(model: str, catalog: Mapping[str, object]) -> str | None:
    """Return the catalog key that prices ``model``, or None if it is unpriced.

    Candidates in order, first hit wins: the recorded name, its effort-normalized
    form, the name without its provider prefix, and that effort-normalized. A
    ``cursor/`` entry therefore overrides the vendor rate for Cursor trials only,
    and an exact entry always beats a normalized one (ADR-015).
    """
    for candidate in _catalog_key_candidates(model):
        if candidate in catalog:
            return candidate
    return None
```

Insert the first private helper directly after `resolve_pricing_layers` (before `_load_bundled_pricing`):

```python
def _catalog_key_candidates(model: str) -> list[str]:
    unprefixed = model.split("/", 1)[-1]
    candidates = [model, normalize_model_slug(model), unprefixed, normalize_model_slug(unprefixed)]
    return list(dict.fromkeys(candidates))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_pricing.py tests/test_token_metrics.py tests/test_results_exporter.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/pricing.py tests/test_pricing.py
git commit -m "pricing: resolve prices through effort suffixes and provider prefixes"
```

### Task 2: Bundled `cursor/` price entries

**Files:**
- Modify: `src/nasde_toolkit/pricing.toml`
- Test: `tests/test_pricing.py`

**Interfaces:**
- Consumes: `resolve_catalog_key`, `compute_cost_usd` from Task 1.
- Produces: catalog keys `cursor/composer-2.5`, `cursor/claude-opus-5-5`, `cursor/claude-sonnet-5-5`, `cursor/claude-fable-5`, `cursor/claude-fable-5-1`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pricing.py`:

```python
CURSOR_CLAUDE_BASES = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5", "claude-fable-5-1")


@pytest.mark.parametrize("base", CURSOR_CLAUDE_BASES)
def test_cursor_claude_entries_bill_cache_writes_at_the_5_minute_rate(base: str) -> None:
    pricing = load_pricing()
    cursor_price = pricing[f"cursor/{base}"]
    vendor_price = pricing[base]
    assert cursor_price.cache_write_per_1m == pytest.approx(cursor_price.input_per_1m * 1.25)
    assert cursor_price.input_per_1m == vendor_price.input_per_1m
    assert cursor_price.output_per_1m == vendor_price.output_per_1m
    assert cursor_price.cached_input_per_1m == vendor_price.cached_input_per_1m


def test_cursor_trial_uses_cursor_rate_while_claude_code_keeps_vendor_rate() -> None:
    pricing = load_pricing()
    cursor_cost = compute_cost_usd(1_000_000, 0, "cursor/claude-opus-5-5-high", pricing, cache_write_tokens=1_000_000)
    claude_code_cost = compute_cost_usd(1_000_000, 0, "claude-opus-5-5", pricing, cache_write_tokens=1_000_000)
    assert cursor_cost == pytest.approx(5.0)
    assert claude_code_cost == pytest.approx(8.0)


def test_cursor_gpt_falls_through_to_vendor_entry() -> None:
    assert resolve_catalog_key("cursor/gpt-5.6-sol-high", load_pricing()) == "gpt-5.6-sol"


def test_cursor_auto_is_unpriced() -> None:
    assert resolve_catalog_key("cursor/auto", load_pricing()) is None


def test_cursor_composer_is_priced() -> None:
    price = load_pricing()["cursor/composer-2.5"]
    assert (price.input_per_1m, price.output_per_1m, price.cached_input_per_1m) == (0.5, 2.5, 0.2)
    assert price.cache_write_per_1m is None
    assert price.as_of == "2026-11-19"
    assert price.source == "https://cursor.com/docs/models-and-pricing"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_pricing.py -k cursor -v`
Expected: FAIL with `KeyError: 'cursor/claude-opus-5-5'`.

- [ ] **Step 3: Implement**

In `src/nasde_toolkit/pricing.toml`, replace the comment block that starts `# Lookup is an exact model-name match.` (four lines, ending `# pricing.toml. From 4.6 on, the dateless ID is the pinned snapshot.`) with:

```toml
# Lookup (pricing.resolve_catalog_key) tries, first hit wins: the exact model
# name, its effort-normalized form (Cursor's "-high" / "-thinking-xhigh" /
# "[effort=...]" stripped), the name without its provider prefix, and that
# normalized. Claude 4.5-generation entries (claude-opus-4-5, claude-sonnet-4-5,
# claude-haiku-4-5) are the aliases; a variant pinned to a dated snapshot ID
# needs its own entry in a project pricing.toml. From 4.6 on, the dateless ID is
# the pinned snapshot.
```

Append at the end of the file:

```toml

# Cursor (agent = "cursor") — harness-scoped keys (ADR-015).
# Cursor trials record model_name as "cursor/<slug>"; the lookup tries the
# cursor/ key before the vendor key, so these entries apply to Cursor runs only.
# Listed only where Cursor's rate differs from the vendor entry above: Cursor
# bills Claude cache writes at the 5-minute rate (1.25x input), not the 1-hour
# rate (2x) Claude Code uses. Cursor's OpenAI rates match the vendor entries, so
# GPT models fall through. "auto" has no per-token rate (Cursor bills it as
# whichever model serves the request) and is deliberately unpriced. Composer
# lists no cache-write charge, so the field is omitted (writes fall back to the
# input rate). Team/Enterprise plans add a $0.25/1M "Cursor Token Rate" on
# third-party models; it is not modelled (individual plans do not pay it).

[models."cursor/composer-2.5"]
input_per_1m = 0.5
output_per_1m = 2.5
cached_input_per_1m = 0.2
as_of = "2026-11-19"
source = "https://cursor.com/docs/models-and-pricing"

[models."cursor/claude-opus-5-5"]
input_per_1m = 4.0
output_per_1m = 20.0
cached_input_per_1m = 0.20
cache_write_per_1m = 5.0
as_of = "2026-11-19"
source = "https://cursor.com/docs/models-and-pricing"

[models."cursor/claude-sonnet-5-5"]
input_per_1m = 2.0
output_per_1m = 10.0
cached_input_per_1m = 0.10
cache_write_per_1m = 2.5
as_of = "2026-11-19"
source = "https://cursor.com/docs/models-and-pricing"

[models."cursor/claude-fable-5"]
input_per_1m = 10.0
output_per_1m = 50.0
cached_input_per_1m = 1.0
cache_write_per_1m = 12.5
as_of = "2026-11-19"
source = "https://cursor.com/docs/models-and-pricing"

[models."cursor/claude-fable-5-1"]
input_per_1m = 10.0
output_per_1m = 50.0
cached_input_per_1m = 0.25
cache_write_per_1m = 12.5
as_of = "2026-11-19"
source = "https://cursor.com/docs/models-and-pricing"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_pricing.py tests/test_pricing_report.py -v`
Expected: all PASS. If an existing test iterates over every bundled entry asserting a Claude-specific invariant (e.g. cache writes = 2x input), restrict it to keys without a `/` and note why in its docstring.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/pricing.toml tests/test_pricing.py
git commit -m "pricing: add cursor/ entries for Composer 2.5 and Claude-through-Cursor"
```

### Task 3: Show which catalog key priced each model

**Files:**
- Modify: `src/nasde_toolkit/pricing_report.py`, `src/nasde_toolkit/runner.py` (`_print_pricing_used`), `src/nasde_toolkit/results_exporter.py` (`_write_pricing_used`)
- Test: `tests/test_pricing_report.py`, `tests/test_runner_economics.py`, `tests/test_results_exporter.py`

**Interfaces:**
- Consumes: `resolve_catalog_key` (Task 1), `cursor/` entries (Task 2).
- Produces: `priced_as_label(model: str, catalog_key: str) -> str` in `nasde_toolkit.pricing_report`; `pricing_used.json` entries gain `"catalog_key"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pricing_report.py` (add `from nasde_toolkit.pricing_report import priced_as_label` to its imports):

```python
def test_priced_as_label_exact_match_is_bare() -> None:
    assert priced_as_label("claude-opus-5-5", "claude-opus-5-5") == "claude-opus-5-5"


def test_priced_as_label_names_the_catalog_key() -> None:
    assert (
        priced_as_label("cursor/claude-opus-5-5-high", "cursor/claude-opus-5-5")
        == "cursor/claude-opus-5-5-high (priced as cursor/claude-opus-5-5)"
    )
```

Append to `tests/test_runner_economics.py` (add `_print_pricing_used` to the `nasde_toolkit.runner` import and `from rich.console import Console` at the top):

```python
def test_print_pricing_used_labels_normalized_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Console(width=250, record=True)
    monkeypatch.setattr("nasde_toolkit.runner.console", recorder)

    _print_pricing_used([{"model": "cursor/claude-opus-5-5-high"}], None)

    output = recorder.export_text()
    assert "cursor/claude-opus-5-5-high (priced as cursor/claude-opus-5-5)" in output
```

Append to `tests/test_results_exporter.py`:

```python
def test_export_pricing_used_records_catalog_key(job_dir: Path, tmp_path: Path) -> None:
    for trial in ("demo-task__aaa111", "demo-task__bbb222"):
        config_path = job_dir / trial / "config.json"
        config = json.loads(config_path.read_text())
        config["agent"]["model_name"] = "cursor/claude-opus-5-5-high"
        config_path.write_text(json.dumps(config))

    dest = tmp_path / "export"
    export_results([job_dir], dest)
    report = json.loads((dest / "pricing_used.json").read_text())

    entry = report["cursor/claude-opus-5-5-high"]
    assert entry["catalog_key"] == "cursor/claude-opus-5-5"
    assert entry["layer"] == "bundled"
    assert entry["input_per_1m"] == 4.0


def test_export_pricing_used_exact_match_catalog_key(job_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "export"
    export_results([job_dir], dest)
    report = json.loads((dest / "pricing_used.json").read_text())

    assert report["claude-sonnet-5-5"]["catalog_key"] == "claude-sonnet-5-5"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_pricing_report.py tests/test_runner_economics.py tests/test_results_exporter.py -v`
Expected: FAIL (`ImportError: cannot import name 'priced_as_label'`; the exporter tests fail with `KeyError`).

- [ ] **Step 3: Implement**

In `src/nasde_toolkit/pricing_report.py`, add above `render_pricing_table`:

```python
def priced_as_label(model: str, catalog_key: str) -> str:
    """Label a model with the catalog key that priced it, when the two differ."""
    if model == catalog_key:
        return model
    return f"{model} (priced as {catalog_key})"
```

In `src/nasde_toolkit/runner.py`, replace `_print_pricing_used` with:

```python
def _print_pricing_used(rows: list[dict], project_dir: Path | None) -> None:
    from nasde_toolkit.pricing import ModelPrice, effective_pricing_with_source, resolve_catalog_key
    from nasde_toolkit.pricing_report import priced_as_label, render_pricing_table

    used_models = {row["model"] for row in rows if row["model"]}
    if not used_models:
        return
    effective = effective_pricing_with_source(project_dir)
    entries: dict[str, tuple[ModelPrice, str]] = {}
    for model in used_models:
        catalog_key = resolve_catalog_key(model, effective)
        if catalog_key is not None:
            entries[priced_as_label(model, catalog_key)] = effective[catalog_key]
    if not entries:
        return
    console.print(render_pricing_table(entries, show_source=True, title="Pricing used (effective)"))
```

In `src/nasde_toolkit/results_exporter.py`, replace `_write_pricing_used` with:

```python
def _write_pricing_used(dest: Path, trial_dirs: list[Path], project_dir: Path | None) -> None:
    from nasde_toolkit.pricing import effective_pricing_with_source, resolve_catalog_key

    used_models = {_resolve_model_name(td) for td in trial_dirs}
    used_models.discard("")
    if not used_models:
        return
    effective = effective_pricing_with_source(project_dir)
    report = {}
    for model in sorted(used_models):
        catalog_key = resolve_catalog_key(model, effective)
        if catalog_key is None:
            continue
        price, layer = effective[catalog_key]
        report[model] = {
            "input_per_1m": price.input_per_1m,
            "output_per_1m": price.output_per_1m,
            "as_of": price.as_of,
            "layer": layer,
            "catalog_key": catalog_key,
        }
    if report:
        (dest / "pricing_used.json").write_text(json.dumps(report, indent=2))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_pricing_report.py tests/test_runner_economics.py tests/test_results_exporter.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/pricing_report.py src/nasde_toolkit/runner.py src/nasde_toolkit/results_exporter.py tests/test_pricing_report.py tests/test_runner_economics.py tests/test_results_exporter.py
git commit -m "pricing: show which catalog entry priced each model"
```

### Task 4: Cursor cache writes and agent-reported cost

**Files:**
- Modify: `src/nasde_toolkit/token_metrics.py`, `src/nasde_toolkit/evaluator.py` (`AssessmentSummary`, `_enrich_with_economics`), `src/nasde_toolkit/results_exporter.py` (`_build_metrics`)
- Test: `tests/test_token_metrics.py`, `tests/test_evaluator.py`, `tests/test_results_exporter.py`

**Interfaces:**
- Consumes: `cursor/composer-2.5` entry (Task 2).
- Produces: `build_trial_economics(...)` dict gains `"agent_reported_cost_usd": float | None` and `"agent_reported_cost_source": str | None`. `AssessmentSummary` gains `agent_reported_cost_usd: float | None = None` and `agent_reported_cost_source: str | None = None`. `metrics.json` gains the same two keys.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_token_metrics.py`:

```python
CURSOR_TRAJ = {
    "final_metrics": {
        "total_prompt_tokens": 412_000,
        "total_completion_tokens": 9_800,
        "total_cached_tokens": 360_000,
        "total_cost_usd": 0.31,
        "extra": {
            "usage_totals": {
                "inputTokens": 40_000,
                "outputTokens": 9_800,
                "cacheReadTokens": 360_000,
                "cacheWriteTokens": 12_000,
            },
            "cost_source": "cursor_cli",
        },
    }
}


def test_extract_cursor_reads_cache_writes_from_usage_totals() -> None:
    usage = extract_token_usage(CURSOR_TRAJ)
    assert usage is not None
    assert usage.input_tokens == 412_000
    assert usage.cached_tokens == 360_000
    assert usage.cache_write_tokens == 12_000
    assert usage.output_tokens == 9_800


def test_extract_prefers_claude_cache_creation_counter() -> None:
    trajectory = {
        "final_metrics": {
            "total_prompt_tokens": 100,
            "extra": {"total_cache_creation_input_tokens": 7, "usage_totals": {"cacheWriteTokens": 99}},
        }
    }
    usage = extract_token_usage(trajectory)
    assert usage is not None
    assert usage.cache_write_tokens == 7


def test_build_trial_economics_cursor_composer(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps(CURSOR_TRAJ))
    econ = build_trial_economics(tmp_path, "cursor/composer-2.5", load_pricing())

    expected = 40_000 / 1e6 * 0.5 + 12_000 / 1e6 * 0.5 + 360_000 / 1e6 * 0.2 + 9_800 / 1e6 * 2.5
    assert econ["cost_usd"] == pytest.approx(expected)
    assert econ["pricing_as_of"] == "2026-11-19"
    assert econ["agent_reported_cost_usd"] == pytest.approx(0.31)
    assert econ["agent_reported_cost_source"] == "cursor_cli"


def test_build_trial_economics_without_reported_cost(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps(CLAUDE_TRAJ))
    econ = build_trial_economics(tmp_path, "claude-sonnet-4-6", load_pricing())

    assert econ["agent_reported_cost_usd"] is None
    assert econ["agent_reported_cost_source"] is None


def test_build_trial_economics_empty_has_audit_keys(tmp_path: Path) -> None:
    econ = build_trial_economics(tmp_path, "cursor/composer-2.5", load_pricing())

    assert econ["agent_reported_cost_usd"] is None
    assert econ["agent_reported_cost_source"] is None
```

Append to `tests/test_evaluator.py` (add `AssessmentSummary` and `_enrich_with_economics` to its `nasde_toolkit.evaluator` imports, plus `from nasde_toolkit.pricing import load_pricing` and `import json` if absent):

```python
def test_enrich_with_economics_stamps_agent_reported_cost(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"agent": {"model_name": "cursor/composer-2.5"}}))
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text(
        json.dumps(
            {
                "final_metrics": {
                    "total_prompt_tokens": 1_000,
                    "total_completion_tokens": 100,
                    "total_cost_usd": 0.002,
                    "extra": {"cost_source": "cursor_cli"},
                }
            }
        )
    )
    summary = AssessmentSummary(task_name="t", trial_name="t__1", agent_name="cursor-vanilla")

    _enrich_with_economics(summary, tmp_path, load_pricing())

    assert summary.model_name == "cursor/composer-2.5"
    assert summary.agent_reported_cost_usd == pytest.approx(0.002)
    assert summary.agent_reported_cost_source == "cursor_cli"
```

Append to `tests/test_results_exporter.py`:

```python
def test_export_metrics_include_agent_reported_cost(job_dir: Path, tmp_path: Path) -> None:
    trajectory_path = job_dir / "demo-task__aaa111" / "agent" / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text())
    trajectory["final_metrics"]["total_cost_usd"] = 1.23
    trajectory["final_metrics"]["extra"]["cost_source"] = "litellm"
    trajectory_path.write_text(json.dumps(trajectory))

    dest = tmp_path / "export"
    export_results([job_dir], dest)
    metrics = json.loads((dest / "2026-06-03__demo-job__demo-task__aaa111" / "metrics.json").read_text())

    assert metrics["agent_reported_cost_usd"] == pytest.approx(1.23)
    assert metrics["agent_reported_cost_source"] == "litellm"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_token_metrics.py tests/test_evaluator.py tests/test_results_exporter.py -v`
Expected: FAIL (`cache_write_tokens == 0`, `KeyError: 'agent_reported_cost_usd'`, `AttributeError` on the summary).

- [ ] **Step 3: Implement**

In `src/nasde_toolkit/token_metrics.py`, change the module docstring's cache-write line to:

```
  cache_write = extra.total_cache_creation_input_tokens   (Claude Code)
                or extra.usage_totals.cacheWriteTokens   (Cursor)
```

In `extract_token_usage`, replace the `cache_write_tokens = ...` line with:

```python
    cache_write_tokens = _cache_write_tokens(extra)
```

Replace the tail of `build_trial_economics` (from `cost_usd = compute_cost_usd(` to the end of the function) with:

```python
    cost_usd = compute_cost_usd(
        usage.input_tokens,
        usage.output_tokens,
        model,
        pricing,
        cache_read_tokens=usage.cached_tokens,
        cache_write_tokens=usage.cache_write_tokens,
    )
    reported_cost_usd, reported_cost_source = _agent_reported_cost(trajectory)
    return {
        "model_name": model,
        "token_usage": asdict(usage),
        "cost_usd": cost_usd,
        "pricing_as_of": pricing_as_of(model, pricing) if cost_usd is not None else None,
        "agent_reported_cost_usd": reported_cost_usd,
        "agent_reported_cost_source": reported_cost_source,
    }
```

Append to the docstring of `build_trial_economics`:

```
    ``agent_reported_cost_*`` is the agent harness's own cost figure (Harbor's
    ``final_metrics.total_cost_usd`` and its ``extra.cost_source``), recorded for
    audit only; ``cost_usd`` from the nasde catalog stays the source of truth.
```

Replace `_empty_economics` and add the two new helpers (order: `_agent_reported_cost`, `_empty_economics`, `_cache_write_tokens`):

```python
def _agent_reported_cost(trajectory: dict | None) -> tuple[float | None, str | None]:
    final_metrics = (trajectory or {}).get("final_metrics") or {}
    extra = final_metrics.get("extra") or {}
    return final_metrics.get("total_cost_usd"), extra.get("cost_source")


def _empty_economics(model: str) -> dict:
    return {
        "model_name": model,
        "token_usage": None,
        "cost_usd": None,
        "pricing_as_of": None,
        "agent_reported_cost_usd": None,
        "agent_reported_cost_source": None,
    }


def _cache_write_tokens(extra: dict) -> int:
    if "total_cache_creation_input_tokens" in extra:
        claude_cache_writes: int = extra["total_cache_creation_input_tokens"] or 0
        return claude_cache_writes
    usage_totals = extra.get("usage_totals") or {}
    cursor_cache_writes: int = usage_totals.get("cacheWriteTokens", 0) or 0
    return cursor_cache_writes
```

In `src/nasde_toolkit/evaluator.py`, add two fields at the end of `AssessmentSummary`:

```python
    agent_reported_cost_usd: float | None = None
    agent_reported_cost_source: str | None = None
```

and two lines at the end of `_enrich_with_economics`:

```python
    summary.agent_reported_cost_usd = economics["agent_reported_cost_usd"]
    summary.agent_reported_cost_source = economics["agent_reported_cost_source"]
```

In `src/nasde_toolkit/results_exporter.py` `_build_metrics`, add after the `"pricing_as_of"` entry:

```python
        "agent_reported_cost_usd": economics["agent_reported_cost_usd"],
        "agent_reported_cost_source": economics["agent_reported_cost_source"],
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: all PASS. If a test asserts the exact key set of `metrics.json` or `assessment_summary.json`, add the two new keys to its expectation.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/token_metrics.py src/nasde_toolkit/evaluator.py src/nasde_toolkit/results_exporter.py tests/test_token_metrics.py tests/test_evaluator.py tests/test_results_exporter.py
git commit -m "economics: count Cursor cache writes and record the agent-reported cost"
```

### Task 5: PR 1 docs, ADR, gates, PR

**Files:**
- Create: `docs/adr/015-cursor-cli-agent-and-judge.md`
- Modify: `CHANGELOG.md`, `CLAUDE.md`

- [ ] **Step 1: Write the ADR**

Create `docs/adr/015-cursor-cli-agent-and-judge.md`:

```markdown
# ADR-015: Cursor CLI as agent and judge

**Status:** Accepted
**Date:** 2026-11-19

## Context

nasde benchmarks Claude Code, Codex and Gemini CLI and judges with `claude` or
`codex`. Harbor 0.24 ships a `CursorCli` agent (install, headless run,
stream-json → ATIF trajectory, native skills into `~/.cursor/skills`, MCP into
`~/.cursor/mcp.json`). Cursor differs from the other harnesses in three ways that
matter to nasde:

1. **Model slugs embed effort** (`claude-opus-5-5-high`,
   `claude-fable-5-thinking-xhigh`); no bare `claude-opus-5-5` slug exists.
2. **The same model costs differently per harness.** Cursor bills third-party
   models at API list price. On 2026-11-19 its OpenAI rates match nasde's vendor
   entries exactly, but it bills Claude cache writes at the 5-minute rate (1.25x
   input), while nasde's Claude entries use the 1-hour rate Claude Code uses (2x).
3. **Auth.** Harbor's agent requires `CURSOR_API_KEY`; a Cursor user API key
   bills against the Cursor plan, so there is no subscription-vs-API split.

## Decision

- **Thin wrapper.** `ConfigurableCursor(CursorCli)` adds only `sandbox_files`
  (for `AGENTS.md`) and `--approve-mcps` when MCP servers are declared. Variants
  reuse the Codex layout: `AGENTS.md` and `agents_skills/` through the native
  skill channel (ADR-012).
- **Provider-qualified model names.** A Cursor agent's `model_name` is recorded as
  `cursor/<slug>`; the runner adds the prefix to a bare slug. This is the form
  Harbor's `CursorCli` requires and it scopes price keys to the harness.
- **Layered price-key lookup.** `pricing.resolve_catalog_key` tries the recorded
  name, its effort-normalized form, the name without its provider prefix, and
  that normalized. The bundled catalog carries `cursor/` entries only where
  Cursor's rate differs (Composer; Claude with 1.25x cache writes). OpenAI models
  fall through to vendor entries. `auto` is deliberately unpriced (no per-token
  rate). Effort normalization is not a validation gate: an unknown suffix
  degrades to "unpriced".
- **Audit, not truth.** The harness-reported cost (`final_metrics.total_cost_usd`
  + `extra.cost_source`) is recorded as `agent_reported_cost_*`; `cost_usd` from
  the catalog remains the source of truth (ADR-011/014).
- **Judge.** `CursorSubprocessBackend` runs `cursor-agent -p --output-format json
  --mode ask` (read-only; Cursor has no per-tool allow-list) from a throwaway
  `--workspace` holding `.cursor/skills` and `.cursor/mcp.json`, with the trial
  workspace attached via `--add-dir`, so nothing the CLI writes reaches the
  agent's diff. Host auth is `CURSOR_API_KEY` or `cursor-agent login`. The default
  judge model for this backend is `claude-opus-5-5-high`.
- **Sandbox auth is API-key only.** No login-token injection.

## Consequences

- Cursor trials and Claude Code trials of the same model are priced at the rate
  each harness actually bills.
- `google/gemini-*` names now fall through to an unprefixed catalog entry if one
  is added.
- A slug whose real price differs from its effort-stripped base (none known
  today) needs an exact entry; exact entries always win.
- Team/Enterprise "Cursor Token Rate" ($0.25/1M on third-party models) is not
  modelled.
- `max_turns` and `allowed_tools` have no Cursor equivalent; the judge warns on
  `allowed_tools` and ignores `max_turns`.
- Harbor drops `env` for stdio MCP servers in `~/.cursor/mcp.json`; nasde's
  `[nasde.plugin]` servers are unaffected (env-wrapped), hand-declared ones are.
```

- [ ] **Step 2: CHANGELOG**

In `CHANGELOG.md` under `## [Unreleased]`, add an `### Added` section above the existing `### Changed` (or extend it if one exists by then):

```markdown
### Added
- **Cursor pricing.** The bundled price catalog gains `cursor/` entries
  (Composer 2.5; Claude Opus 5.5, Sonnet 5.5, Fable 5 and Fable 5.1 at Cursor's
  rates, which bill cache writes at 1.25x input instead of the 2x Claude Code
  uses). `assessment_summary.json` and `metrics.json` also record the agent's
  own cost figure as `agent_reported_cost_usd` / `agent_reported_cost_source`
  for audit; `cost_usd` is unchanged as the source of truth. ([#NN])
```

Under `### Changed` add:

```markdown
- **Price lookup falls back through effort suffixes and provider prefixes.** A
  model such as `cursor/claude-opus-5-5-high` is priced by the first of
  `cursor/claude-opus-5-5-high`, `cursor/claude-opus-5-5`,
  `claude-opus-5-5-high`, `claude-opus-5-5` found in the catalog; an exact entry
  always wins. The "Pricing used" table and `pricing_used.json` (new
  `catalog_key` field) show which entry was used. ([#NN])
```

Under `### Fixed` add:

```markdown
- Cache writes reported by Cursor trajectories (`usage_totals.cacheWriteTokens`)
  are now counted in `token_usage.cache_write_tokens` and priced. ([#NN])
```

- [ ] **Step 3: CLAUDE.md**

In `CLAUDE.md`, in the **Token & cost metrics** architecture bullet, replace the sentence fragment `Pricing is loaded via` with:

```
Price keys are resolved by `pricing.resolve_catalog_key` (ADR-015): exact name, then effort-normalized (`normalize_model_slug` strips Cursor's `-high`/`-thinking-xhigh`/`[effort=...]`), then without the provider prefix, then that normalized — so harness-scoped `cursor/<model>` entries override vendor rates for Cursor trials only. The economics block also records the harness's own figure as `agent_reported_cost_usd`/`agent_reported_cost_source` (audit only). Pricing is loaded via
```

and in the package-structure listing change the `pricing.py / pricing.toml` comment to end with `; layered key lookup via resolve_catalog_key (ADR-015)`.

- [ ] **Step 4: Quality gates**

Run each; all must pass:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/nasde_toolkit/
uv run pytest
```

If `ruff format --check` fails, run `uv run ruff format src/ tests/` and re-run the check.

- [ ] **Step 5: Commit, push, open PR, fix the link-ref**

```bash
git add docs/adr/015-cursor-cli-agent-and-judge.md CHANGELOG.md CLAUDE.md
git commit -m "docs: ADR-015 and changelog for Cursor pricing"
git push -u origin feat/cursor-pricing
gh pr create --base main --title "pricing: Cursor price entries and layered key lookup" --body "Implements PR 1 of docs/superpowers/plans/2026-11-19-cursor-cli-support.md (spec: docs/superpowers/specs/2026-11-19-cursor-cli-support-design.md)."
```

Take the PR number `gh` prints, replace every `[#NN]` added in Step 2 with it, and append the link-ref at the bottom of `CHANGELOG.md` in the same format as the existing ones (`[#91]: https://github.com/NoesisVision/nasde-toolkit/pull/91`). Commit `changelog: link Cursor pricing PR` and push.

---

## PR 2 — Cursor agent

```bash
git switch feat/cursor-pricing
git switch -c feat/cursor-agent
```

### Task 6: `ConfigurableCursor` agent

**Files:**
- Create: `src/nasde_toolkit/agents/configurable_cursor.py`
- Create: `tests/test_configurable_cursor.py`
- Modify: `tests/test_configurable_agents_options.py`

**Interfaces:**
- Produces: `nasde_toolkit.agents.configurable_cursor:ConfigurableCursor` (import path used by the runner in Task 7), `ConfigurableCursorOptions`, `ConfigurableCursor.name() == "configurable-cursor-cli"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_configurable_cursor.py`:

```python
"""Tests for ConfigurableCursor agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from harbor.agents.installed.cursor_cli import CursorCli
from harbor.models.task.config import MCPServerConfig

from nasde_toolkit.agents.configurable_cursor import ConfigurableCursor

MODEL = "cursor/composer-2.5"


def test_name_returns_configurable_cursor_cli() -> None:
    assert ConfigurableCursor.name() == "configurable-cursor-cli"


def test_constructor_stores_sandbox_files() -> None:
    files = {"/app/AGENTS.md": "/tmp/AGENTS.md"}
    agent = ConfigurableCursor(sandbox_files=files, logs_dir=Path("/tmp/logs"), model_name=MODEL)
    assert agent._sandbox_files == files


def test_constructor_defaults_to_empty_sandbox_files() -> None:
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL)
    assert agent._sandbox_files == {}


def test_cli_flags_approve_mcps_when_servers_declared() -> None:
    server = MCPServerConfig(name="docs", transport="stdio", command="node")
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL, mcp_servers=[server])
    assert "--approve-mcps" in agent.build_cli_flags()


def test_cli_flags_omit_approve_mcps_without_servers() -> None:
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL)
    assert "--approve-mcps" not in agent.build_cli_flags()


def test_cli_flags_keep_harbor_flags_alongside_approve_mcps() -> None:
    server = MCPServerConfig(name="docs", transport="stdio", command="node")
    agent = ConfigurableCursor(logs_dir=Path("/tmp/logs"), model_name=MODEL, mcp_servers=[server], mode="ask")
    flags = agent.build_cli_flags()
    assert "--mode" in flags
    assert "--approve-mcps" in flags


def test_setup_uploads_sandbox_files_before_harbor_setup() -> None:
    agent = ConfigurableCursor(sandbox_files={"/app/AGENTS.md": __file__}, logs_dir=Path("/tmp/logs"), model_name=MODEL)
    order: list[str] = []
    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    async def record_upload(**_: object) -> None:
        order.append("upload")

    async def record_harbor_setup(_self: CursorCli, _environment: object) -> None:
        order.append("harbor-setup")

    env.upload_file.side_effect = record_upload
    with patch.object(CursorCli, "setup", record_harbor_setup):
        asyncio.run(agent.setup(env))

    assert order == ["upload", "harbor-setup"]


def test_setup_raises_on_missing_source() -> None:
    agent = ConfigurableCursor(
        sandbox_files={"/app/AGENTS.md": "/nonexistent/AGENTS.md"}, logs_dir=Path("/tmp/logs"), model_name=MODEL
    )
    env = AsyncMock()
    env.exec.return_value = MagicMock(return_code=0, stderr="")

    with (
        patch.object(CursorCli, "setup", new_callable=AsyncMock),
        pytest.raises(FileNotFoundError, match="does not exist"),
    ):
        asyncio.run(agent.setup(env))
```

In `tests/test_configurable_agents_options.py`, add the import and a case:

```python
from nasde_toolkit.agents.configurable_cursor import ConfigurableCursor
```

```python
AGENT_CASES = [
    (ConfigurableClaude, "claude-sonnet-5-5", "/app/CLAUDE.md"),
    (ConfigurableCodex, "gpt-6.1-sol", "/app/AGENTS.md"),
    (ConfigurableCursor, "cursor/composer-2.5", "/app/AGENTS.md"),
    (ConfigurableGemini, "google/gemini-3-flash-preview", "/app/GEMINI.md"),
]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_configurable_cursor.py tests/test_configurable_agents_options.py -v`
Expected: collection fails with `ModuleNotFoundError: No module named 'nasde_toolkit.agents.configurable_cursor'`.

- [ ] **Step 3: Implement**

Create `src/nasde_toolkit/agents/configurable_cursor.py`:

```python
"""Configurable Cursor CLI agent for Harbor evaluations.

Harbor's built-in CursorCli installs ``cursor-agent``, runs it headless, parses
its stream-json output into an ATIF trajectory, copies Harbor's native skills
(``config.agent.skills``) into ``~/.cursor/skills`` (ADR-012) and writes the
task's MCP servers to ``~/.cursor/mcp.json``. It lacks two things nasde needs:

1. Injecting arbitrary files (``AGENTS.md``) into the sandbox before the agent
   starts. ConfigurableCursor accepts a ``sandbox_files`` mapping via
   ``AgentConfig.kwargs`` and uploads each file during ``setup()``.
2. Approving the MCP servers it registers. A ``--print`` run cannot answer
   ``cursor-agent``'s approval prompt, so ``--approve-mcps`` is appended whenever
   the task declares MCP servers.

Authentication is ``CURSOR_API_KEY`` only (checked by the runner's
``_ensure_auth``; Harbor forwards it into the sandbox). Model names arrive
``cursor/``-qualified (the runner adds the prefix), the ``provider/model`` form
``CursorCli`` requires. See ADR-015.

Usage in harbor_config.json::

    {
      "agents": [{
        "import_path": "nasde_toolkit.agents.configurable_cursor:ConfigurableCursor",
        "model_name": "cursor/composer-2.5",
        "kwargs": {
          "sandbox_files": {
            "/app/AGENTS.md": "path/to/AGENTS.md"
          }
        }
      }]
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harbor.agents.installed.cursor_cli import CursorCli, CursorCliOptions
from harbor.environments.base import BaseEnvironment
from pydantic import Field


class ConfigurableCursorOptions(CursorCliOptions):
    """CursorCliOptions plus nasde's ``sandbox_files`` kwarg.

    Harbor's preflight validates raw kwargs against ``options_model`` with
    ``extra="forbid"`` before the agent is constructed, so every nasde kwarg
    must be declared here. The field has no ``Cli``/``Env`` annotation and is
    therefore never rendered into the agent command or environment.
    """

    sandbox_files: dict[str, str] | None = Field(
        default=None,
        description="Container path -> host file path, uploaded into the sandbox during setup().",
    )


class ConfigurableCursor(CursorCli):
    """CursorCli with declarative file injection and MCP auto-approval.

    Args:
        sandbox_files: Mapping of container paths to host file paths. Each entry
            is uploaded into the sandbox during setup() before Harbor installs
            the CLI. Paths are resolved relative to CWD.
    """

    options_model = ConfigurableCursorOptions

    def __init__(
        self,
        sandbox_files: dict[str, str] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._sandbox_files = sandbox_files or {}

    @staticmethod
    def name() -> str:
        return "configurable-cursor-cli"

    def build_cli_flags(self) -> str:
        """Harbor's flags, plus ``--approve-mcps`` when the task declares MCP servers."""
        harbor_flags = super().build_cli_flags()
        if not self.mcp_servers:
            return harbor_flags
        return f"{harbor_flags} --approve-mcps".strip()

    async def setup(self, environment: BaseEnvironment) -> None:
        """Upload sandbox files (e.g. AGENTS.md), then run Harbor's install."""
        await self._upload_sandbox_files(environment)
        await super().setup(environment)

    async def _upload_sandbox_files(self, environment: BaseEnvironment) -> None:
        for target_path, source_path in self._sandbox_files.items():
            resolved = Path(source_path).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(
                    f"sandbox_files: source '{source_path}' (resolved to '{resolved}') does not exist"
                )
            parent_dir = str(Path(target_path).parent)
            await environment.exec(command=f"mkdir -p {parent_dir}")
            await environment.upload_file(
                source_path=resolved,
                target_path=target_path,
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_configurable_cursor.py tests/test_configurable_agents_options.py -v && uv run mypy src/nasde_toolkit/agents/configurable_cursor.py`
Expected: all PASS; mypy `Success`. If mypy flags the `name()` override against Harbor's `@override`-decorated staticmethod, add `from typing import override` and decorate `name` with `@staticmethod` then `@override` in that order, matching Harbor.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/agents/configurable_cursor.py tests/test_configurable_cursor.py tests/test_configurable_agents_options.py
git commit -m "agents: add ConfigurableCursor (sandbox_files + MCP auto-approve)"
```

### Task 7: Runner wiring for `agent = "cursor"`

**Files:**
- Modify: `src/nasde_toolkit/runner.py`
- Test: `tests/test_runner.py`, `tests/test_runner_skills.py`, `tests/test_runner_economics.py`

**Interfaces:**
- Consumes: `ConfigurableCursor` import path from Task 6.
- Produces: `_is_cursor_agent(agent_import_path: str | None) -> bool`; `_qualify_model_name(import_path: str | None, model_name: str) -> str`; `"cursor"` accepted in `variant.toml`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_runner.py`, add `_is_cursor_agent` to the `nasde_toolkit.runner` import block, then append:

```python
# ---------------------------------------------------------------------------
# Cursor agent
# ---------------------------------------------------------------------------

CURSOR_PATH = "nasde_toolkit.agents.configurable_cursor:ConfigurableCursor"


def test_is_cursor_agent() -> None:
    assert _is_cursor_agent(CURSOR_PATH)
    assert not _is_cursor_agent("nasde_toolkit.agents.configurable_codex:ConfigurableCodex")
    assert not _is_cursor_agent(None)
    assert not _is_codex_agent(CURSOR_PATH)
    assert not _is_gemini_agent(CURSOR_PATH)


def test_load_variant_agent_type_accepts_cursor(tmp_path: Path) -> None:
    (tmp_path / "variant.toml").write_text('agent = "cursor"\nmodel = "composer-2.5"\n')
    assert load_variant_agent_type(tmp_path) == "cursor"


def test_generate_harbor_config_cursor_variant(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "cursor-vanilla"
    variant_dir.mkdir(parents=True)
    (variant_dir / "AGENTS.md").write_text("# Cursor")
    (variant_dir / "variant.toml").write_text('agent = "cursor"\nmodel = "composer-2.5"\n')
    skill_dir = variant_dir / "agents_skills" / "tactical-ddd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: tactical-ddd\n---\nbody")

    _generate_harbor_config(variant_dir, "cursor-vanilla")

    agent = json.loads((variant_dir / "harbor_config.json").read_text())["agents"][0]
    assert agent["import_path"] == CURSOR_PATH
    assert agent["kwargs"]["sandbox_files"] == {"/app/AGENTS.md": str(variant_dir / "AGENTS.md")}
    assert agent["skills"] == [str(skill_dir.resolve())]


def test_ensure_auth_cursor_with_api_key() -> None:
    with patch.dict("os.environ", {"CURSOR_API_KEY": "key_test"}, clear=True):
        _ensure_auth(CURSOR_PATH)


def test_ensure_auth_cursor_missing_raises(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True), pytest.raises(SystemExit):
        _ensure_auth(CURSOR_PATH)
    assert "CURSOR_API_KEY" in capsys.readouterr().out


def _write_cursor_variant(project_dir: Path, model_name: str | None = None) -> Path:
    variant_dir = project_dir / "variants" / "cursor-vanilla"
    variant_dir.mkdir(parents=True)
    agent: dict = {"import_path": CURSOR_PATH, "name": "cursor-vanilla", "kwargs": {"sandbox_files": {}}}
    if model_name is not None:
        agent["model_name"] = model_name
    path = variant_dir / "harbor_config.json"
    path.write_text(json.dumps({"agents": [agent]}))
    return path


def test_build_merged_config_qualifies_bare_cursor_model(tmp_project: ProjectConfig) -> None:
    variant_config_path = _write_cursor_variant(tmp_project.project_dir)
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="cursor-vanilla",
        model="composer-2.5",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert result["agents"][0]["model_name"] == "cursor/composer-2.5"


def test_build_merged_config_keeps_qualified_cursor_model(tmp_project: ProjectConfig) -> None:
    variant_config_path = _write_cursor_variant(tmp_project.project_dir)
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="cursor-vanilla",
        model="cursor/claude-opus-5-5-high",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert result["agents"][0]["model_name"] == "cursor/claude-opus-5-5-high"


def test_build_merged_config_qualifies_handwritten_cursor_model(tmp_project: ProjectConfig) -> None:
    variant_config_path = _write_cursor_variant(tmp_project.project_dir, model_name="composer-2.5")
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="cursor-vanilla",
        model="ignored-because-handwritten",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert result["agents"][0]["model_name"] == "cursor/composer-2.5"


def test_build_merged_config_leaves_other_agents_models_alone(tmp_project: ProjectConfig) -> None:
    variant_config_path = tmp_project.project_dir / "variants" / "vanilla" / "harbor_config.json"
    result = _build_merged_config(
        config=tmp_project,
        variant_config_path=variant_config_path,
        variant_name="vanilla",
        model="claude-sonnet-5-5",
        timeout_sec=None,
        tasks_filter=None,
    )
    assert result["agents"][0]["model_name"] == "claude-sonnet-5-5"
```

In `tests/test_runner_skills.py`, add `_collect_native_skill_dirs` is already imported; append:

```python
def _cursor_variant(variant_dir: Path) -> Path:
    variant_dir.mkdir(parents=True)
    (variant_dir / "AGENTS.md").write_text("# c")
    (variant_dir / "variant.toml").write_text('agent = "cursor"\nmodel = "composer-2.5"\n')
    return variant_dir


def test_collect_native_skill_dirs_cursor_reads_agents_skills(tmp_path: Path) -> None:
    variant_dir = _cursor_variant(tmp_path / "variants" / "v")
    skill = _make_native_skill(variant_dir, "agents_skills", "tactical-ddd")

    assert _collect_native_skill_dirs(variant_dir, "cursor") == [str(skill.resolve())]


def test_extra_skill_dirs_go_to_native_skills_for_cursor(tmp_path: Path) -> None:
    variant_dir = _cursor_variant(tmp_path / "variants" / "v")
    referenced = _standalone_skill(tmp_path / "src", "tactical-ddd")
    harbor_path = variant_dir / "harbor_config.json"
    _generate_harbor_config(variant_dir, "v")

    _ensure_harbor_config(variant_dir, "v", {}, [str(referenced)])

    assert _skills(harbor_path) == [str(referenced)]
```

In `tests/test_runner_economics.py`, extend `test_short_label_strips_family_and_skill_prefixes` with:

```python
    assert _short_label("cursor-vanilla", "cursor/composer-2.5") == "vanilla / composer-2.5"
    assert _short_label("cursor-vanilla", "cursor/claude-opus-5-5-high") == "vanilla / opus-5-5-high"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_runner.py tests/test_runner_skills.py tests/test_runner_economics.py -v`
Expected: collection fails with `ImportError: cannot import name '_is_cursor_agent'`.

- [ ] **Step 3: Implement**

All edits in `src/nasde_toolkit/runner.py`.

`_ensure_auth`: insert after the Gemini block, before the Claude check:

```python
    if _is_cursor_agent(agent_import_path):
        if os.environ.get("CURSOR_API_KEY"):
            return
        console.print("[red]ERROR: Set CURSOR_API_KEY (create a User API key in the Cursor dashboard)[/red]")
        raise SystemExit(1)
```

`_AGENT_SKILLS_SUBDIR`:

```python
_AGENT_SKILLS_SUBDIR = {"codex": "agents_skills", "cursor": "agents_skills", "gemini": "gemini_skills"}
```

In the `_collect_native_skill_dirs` docstring, change the first paragraph's location list to: `(``$HOME/.agents/skills`` for Codex, ``~/.cursor/skills`` for Cursor, ``~/.gemini/skills`` for Gemini)`.

In `_warn_if_skill_frontmatter_malformed`, change `"frontmatter line. Codex/Gemini may refuse to register the skill "` to `"frontmatter line. Codex/Cursor/Gemini may refuse to register the skill "`.

`_VALID_AGENT_TYPES`:

```python
_VALID_AGENT_TYPES = {"claude", "codex", "cursor", "gemini"}
```

In the `load_variant_config` docstring, change `an ``agent`` field set to ``"claude"`` or ``"codex"``.` to `an ``agent`` field set to one of ``_VALID_AGENT_TYPES``.`

`_agent_import_path`: add before the final `return`:

```python
    if agent_type == "cursor":
        return "nasde_toolkit.agents.configurable_cursor:ConfigurableCursor"
```

Add after `_is_codex_agent`:

```python
def _is_cursor_agent(agent_import_path: str | None) -> bool:
    return bool(agent_import_path and "cursor" in agent_import_path.lower())
```

`_agent_type_from_import_path`: add after the Codex branch:

```python
    if _is_cursor_agent(import_path):
        return "cursor"
```

`_build_merged_config`: replace the first line of the agents loop body so the loop reads:

```python
    for agent in variant.get("agents", []):
        agent.setdefault("model_name", model)
        agent["model_name"] = _qualify_model_name(agent.get("import_path"), agent["model_name"])
        if timeout_sec is not None:
            agent.setdefault("override_timeout_sec", timeout_sec)
        if reasoning_effort is not None:
            agent.setdefault("kwargs", {})["reasoning_effort"] = reasoning_effort
```

Add directly after `_build_merged_config`:

```python
def _qualify_model_name(import_path: str | None, model_name: str) -> str:
    """Prefix a bare Cursor slug with ``cursor/``.

    ``cursor/<slug>`` is the ``provider/model`` form Harbor's CursorCli requires,
    and it is what keys the harness-scoped ``cursor/`` price entries (ADR-015).
    Other agents' model names pass through unchanged.
    """
    if _is_cursor_agent(import_path) and "/" not in model_name:
        return f"cursor/{model_name}"
    return model_name
```

`_short_label`:

```python
def _short_label(agent: str, model: str) -> str:
    short_agent = (
        agent.removeprefix("claude-").removeprefix("codex-").removeprefix("cursor-").removeprefix("gemini-")
    )
    short_agent = short_agent.replace("ntcoding-tactical-ddd-", "").replace("ntcoding-tactical-ddd", "tactical-ddd")
    short_model = model.removeprefix("cursor/").removeprefix("claude-").removeprefix("google/")
    return f"{short_agent} / {short_model}" if short_model else short_agent
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_runner.py tests/test_runner_skills.py tests/test_runner_economics.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/runner.py tests/test_runner.py tests/test_runner_skills.py tests/test_runner_economics.py
git commit -m "runner: support agent = \"cursor\" variants"
```

### Task 8: Example variant

**Files:**
- Create: `examples/ddd-architectural-challenges/variants/cursor-vanilla/variant.toml`
- Create: `examples/ddd-architectural-challenges/variants/cursor-vanilla/AGENTS.md`

- [ ] **Step 1: Create the variant**

```bash
mkdir -p examples/ddd-architectural-challenges/variants/cursor-vanilla
cp examples/ddd-architectural-challenges/variants/codex-vanilla/AGENTS.md examples/ddd-architectural-challenges/variants/cursor-vanilla/AGENTS.md
```

Write `examples/ddd-architectural-challenges/variants/cursor-vanilla/variant.toml`:

```toml
agent = "cursor"
model = "composer-2.5"
```

- [ ] **Step 2: Check the variant is discovered**

Run: `uv run python -c "from pathlib import Path; from nasde_toolkit.runner import load_variant_agent_type; print(load_variant_agent_type(Path('examples/ddd-architectural-challenges/variants/cursor-vanilla')))"`
Expected: `cursor`

- [ ] **Step 3: Commit**

```bash
git add examples/ddd-architectural-challenges/variants/cursor-vanilla
git commit -m "examples: add cursor-vanilla variant"
```

### Task 9: PR 2 docs

**Files:**
- Modify: `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `.claude/skills/nasde-benchmark-creator/SKILL.md`, `.claude/skills/nasde-benchmark-runner/SKILL.md`, `.claude/skills/nasde-dev/SKILL.md`

- [ ] **Step 1: CHANGELOG**

Under `## [Unreleased]` → `### Added`:

```markdown
- **Cursor CLI agent.** Variants can set `agent = "cursor"` to benchmark
  Cursor's `cursor-agent`. They use `AGENTS.md` (injected into `/app/AGENTS.md`)
  and `agents_skills/` (registered natively into `~/.cursor/skills`), like Codex
  variants. Authenticate with `CURSOR_API_KEY`. Write the model as Cursor lists it
  (`cursor-agent --list-models`); nasde records it as `cursor/<model>` and prices
  it from the `cursor/` catalog entries. MCP servers declared by the task are
  auto-approved. Example: `examples/ddd-architectural-challenges/variants/cursor-vanilla`. ([#NN])
```

- [ ] **Step 2: README**

In `README.md` line 23, replace `**Today** it drives Claude Code, the Codex CLI, and the Gemini CLI; **planned:** Pi, Cursor, and router-based setups.` with `**Today** it drives Claude Code, the Codex CLI, the Gemini CLI, and the Cursor CLI; **planned:** Pi and router-based setups.`

On line 62 replace `Claude Code vs. Codex vs. Gemini` with `Claude Code vs. Codex vs. Gemini vs. Cursor`.

On line 93 replace ``Your existing `claude` / `codex` / `gemini` CLI auth covers it`` with ``Your existing `claude` / `codex` / `gemini` CLI auth covers it (Cursor variants need a `CURSOR_API_KEY`)``.

- [ ] **Step 3: CLAUDE.md**

1. Package structure: under `agents/`, add `configurable_cursor.py # Harbor-compatible Cursor CLI agent with sandbox file injection + MCP auto-approve`.
2. **Variant system** bullet: change `(\`agent = "claude"\`, \`agent = "codex"\`, or \`agent = "gemini"\`)` to `(\`agent = "claude"\`, \`agent = "codex"\`, \`agent = "cursor"\`, or \`agent = "gemini"\`)` and after the Gemini sentence add `Cursor variants reuse the Codex layout: \`AGENTS.md\` → \`/app/AGENTS.md\` and \`agents_skills/\` through the native channel into \`~/.cursor/skills\`.`
3. Add a new architecture bullet after **Gemini Google OAuth**:

```markdown
- **Cursor CLI agent (ADR-015)**: `ConfigurableCursor` subclasses Harbor's `CursorCli` and adds only `sandbox_files` and `--approve-mcps` (when the task declares MCP servers; a `--print` run cannot answer the approval prompt). Auth is `CURSOR_API_KEY` only (`_ensure_auth`); no login-token injection. `_build_merged_config` qualifies a bare model slug to `cursor/<slug>` (`_qualify_model_name`), the `provider/model` form Harbor requires; the qualified name is what `config.json`, summaries and pricing see, and it keys the harness-scoped `cursor/` price entries. Effort can live in the slug (`claude-opus-5-5-high`, as `cursor-agent --list-models` prints it) or in `reasoning_effort` (Harbor renders `[effort=X]`) — pick one.
```

4. `variant.toml` section: change the `agent` comment to `# "claude" | "codex" | "cursor" | "gemini"`.
5. Benchmark project structure: next to `AGENTS.md`, change the comment to `# Codex / Cursor instructions (injected into /app/AGENTS.md)`, and next to `agents_skills/` change it to `# Optional: Codex/Cursor skill snapshots (native skill-injection → $HOME/.agents/skills/ or ~/.cursor/skills/)`.

- [ ] **Step 4: ARCHITECTURE.md**

In the agent class diagram, add after the `GeminiCli` class:

```
    class CursorCli {
        <<Harbor built-in>>
        +setup(environment)
        +solve(task)
    }
```

after the `ConfigurableGemini` class:

```
    class ConfigurableCursor {
        -_sandbox_files: dict~str, str~
        +setup(environment)
        +build_cli_flags() str
        -_upload_sandbox_files(environment)
        +name() str
    }
```

after `GeminiCli <|-- ConfigurableGemini`: `    CursorCli <|-- ConfigurableCursor`, and after the Gemini note: `    note for ConfigurableCursor "Injects AGENTS.md into sandbox\nAuto-approves task MCP servers"`.

In the paragraph below the diagram, change `` `ConfigurableClaude`, `ConfigurableCodex`, and `ConfigurableGemini` each add `` to `` `ConfigurableClaude`, `ConfigurableCodex`, `ConfigurableGemini`, and `ConfigurableCursor` each add ``, and append: `` `ConfigurableCursor` additionally appends `--approve-mcps` when the task declares MCP servers. ``. In the next list change the `variant.toml` line to include `agent = "cursor"`, and in line 23's mermaid node change `Configurable{Claude,Codex,Gemini}.setup()` to `Configurable{Claude,Codex,Gemini,Cursor}.setup()`. Add `configurable_cursor.py # Harbor-compatible Cursor CLI agent with sandbox file injection` to the file listing next to `configurable_gemini.py`.

- [ ] **Step 5: Skills**

`.claude/skills/nasde-benchmark-creator/SKILL.md`:
- Line 260: `agent = "claude"   # or "codex", "cursor" or "gemini"`.
- After the Gemini model guidance block (ends near line 290), add:

```markdown
For Cursor CLI variants, use a model exactly as `cursor-agent --list-models` prints it.
nasde records it as `cursor/<model>`; Cursor puts effort in the name, so either pick
`claude-opus-5-5-high` **or** set `reasoning_effort`, not both:

```toml
agent = "cursor"
model = "composer-2.5"   # or e.g. "claude-opus-5-5-high", "gpt-5.6-sol-high"
```
```

- After the `### Gemini CLI variant` block, add:

```markdown
### Cursor CLI variant

```
variants/cursor-baseline/
  variant.toml       # agent = "cursor"
  AGENTS.md          # Instructions (injected to /app/AGENTS.md)
  agents_skills/     # Optional: skill snapshots (native injection -> ~/.cursor/skills/)
```
```

- In the note starting `> **Codex/Gemini skills are registered natively**`, change `Codex/Gemini` to `Codex/Cursor/Gemini` in both places on lines 338 and 341.

`.claude/skills/nasde-benchmark-runner/SKILL.md`:
- Line 26: `(Claude / Codex / Gemini / Cursor, any combination)`.
- Line 43: `Priority order: **Claude → Codex → Gemini → Cursor.**`
- After the Gemini CLI auth section, add:

```markdown
#### Cursor CLI

Cursor variants authenticate with an API key only (no OAuth injection into the sandbox):

| OS / shell | API key |
|---|---|
| macOS / Linux / WSL | `export CURSOR_API_KEY=...` (or put it in the project `.env`) |
| Windows PowerShell | `$env:CURSOR_API_KEY = '...'` |

Create the key in the Cursor dashboard. List the models your account can run with `cursor-agent --list-models`.
```

- In the combined-setup bash block add the line `export CURSOR_API_KEY=...                         # Cursor (API key)`.

`.claude/skills/nasde-dev/SKILL.md` line 101: append `; cursor → \`CURSOR_API_KEY\` in the environment or \`.env\` (no script)`.

- [ ] **Step 6: Quality gates, commit, push, PR**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/nasde_toolkit/
uv run pytest
git add CHANGELOG.md README.md CLAUDE.md ARCHITECTURE.md .claude/skills
git commit -m "docs: Cursor CLI agent"
git push -u origin feat/cursor-agent
gh pr create --base feat/cursor-pricing --title "Cursor CLI agent (agent = \"cursor\")" --body "Implements PR 2 of docs/superpowers/plans/2026-11-19-cursor-cli-support.md. Stacked on the Cursor pricing PR."
```

Replace `[#NN]` with the printed PR number, add the link-ref at the bottom of `CHANGELOG.md`, commit `changelog: link Cursor agent PR`, push.

### Task 10: Live smoke run of the Cursor agent (owner-authorized)

**Do not start without the repo owner's explicit go-ahead for this run.**

**Files:** none committed. Uses a throwaway canary variant.

- [ ] **Step 1: Create a throwaway canary variant**

```bash
V=examples/ddd-architectural-challenges/variants/cursor-skill-canary
mkdir -p $V/agents_skills/canary-report
cp examples/ddd-architectural-challenges/variants/codex-vanilla/AGENTS.md $V/AGENTS.md
printf 'agent = "cursor"\nmodel = "composer-2.5"\n' > $V/variant.toml
printf -- '---\nname: canary-report\ndescription: Use this skill when you finish the task. It tells you how to report completion.\n---\nWhen you have finished the task, create the file /app/CANARY_SKILL_USED.txt containing the single word: canary\n' > $V/agents_skills/canary-report/SKILL.md
```

- [ ] **Step 2: Run one trial**

Run (with `CURSOR_API_KEY` exported and Claude auth for the default judge):

```bash
source scripts/export_oauth_token.sh && \
  uv run nasde run --variant cursor-skill-canary --tasks ddd-threshold-discount \
  --eval-repetitions 1 -C examples/ddd-architectural-challenges
```

Expected: the run completes; the summary table shows a row for `cursor-skill-canary / composer-2.5` with a non-empty `$ Cost`; the "Pricing used" table lists `cursor/composer-2.5`.

- [ ] **Step 3: Check the artifacts**

```bash
J=$(ls -dt examples/ddd-architectural-challenges/jobs/*cursor-skill-canary* | head -1)
T=$(ls -d $J/*/ | head -1)
cat $T/verifier/reward.txt
python3 -c "import json,sys; s=json.load(open('$T/assessment_summary.json')); print(s['model_name'], s['cost_usd'], s['token_usage']['cache_write_tokens'], s['agent_reported_cost_source'])"
rg -c "canary-report|CANARY_SKILL_USED" $T/agent/trajectory.json
ls $T/artifacts/workspace/CANARY_SKILL_USED.txt
```

Pass criteria:
- `reward.txt` exists (0 or 1 — the agent's task outcome is not under test).
- `model_name` is `cursor/composer-2.5`, `cost_usd` is a number, `cache_write_tokens` > 0.
- The trajectory references `canary-report` and the workspace contains `CANARY_SKILL_USED.txt`.

If the skill check fails while everything else passes, stop and report: per the spec this triggers the approach-B fallback (a nasde-owned agent that registers skills inside `run()`), which needs its own design pass.

- [ ] **Step 4: Clean up**

```bash
rm -rf examples/ddd-architectural-challenges/variants/cursor-skill-canary
```

Export and commit results only if the owner asks for it (calibration protocol); `jobs/` is gitignored.

---

## PR 3 — Cursor judge

```bash
git switch main && git pull --ff-only
git switch -c feat/cursor-judge
```

### Task 11: Backend-aware default judge model and `--eval-backend cursor`

**Files:**
- Modify: `src/nasde_toolkit/config.py`, `src/nasde_toolkit/cli.py`
- Test: `tests/test_config.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `default_evaluator_model(backend: str) -> str` in `nasde_toolkit.config` (`"cursor"` → `"claude-opus-5-5-high"`, anything else → `"claude-opus-5-5"`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py` (add `default_evaluator_model` to its `nasde_toolkit.config` import):

```python
def test_cursor_backend_defaults_to_cursor_judge_slug(tmp_path: Path) -> None:
    (tmp_path / "nasde.toml").write_text('[project]\nname = "test"\n\n[evaluation]\nbackend = "cursor"\n')
    config = load_project_config(tmp_path)
    assert config.evaluation.backend == "cursor"
    assert config.evaluation.model == "claude-opus-5-5-high"


def test_cursor_backend_keeps_explicit_model(tmp_path: Path) -> None:
    (tmp_path / "nasde.toml").write_text(
        '[project]\nname = "test"\n\n[evaluation]\nbackend = "cursor"\nmodel = "claude-opus-5-5"\n'
    )
    config = load_project_config(tmp_path)
    assert config.evaluation.model == "claude-opus-5-5"


def test_default_evaluator_model() -> None:
    assert default_evaluator_model("cursor") == "claude-opus-5-5-high"
    assert default_evaluator_model("claude") == "claude-opus-5-5"
    assert default_evaluator_model("codex") == "claude-opus-5-5"
```

Append to `tests/test_cli.py`:

```python
def test_override_eval_judge_cursor_switches_default_model() -> None:
    from nasde_toolkit.cli import _override_eval_judge
    from nasde_toolkit.config import EvaluationConfig, ProjectConfig

    config = ProjectConfig(name="test", evaluation=EvaluationConfig())
    _override_eval_judge(config, model=None, backend="cursor")
    assert config.evaluation.backend == "cursor"
    assert config.evaluation.model == "claude-opus-5-5-high"


def test_override_eval_judge_cursor_keeps_custom_model() -> None:
    from nasde_toolkit.cli import _override_eval_judge
    from nasde_toolkit.config import EvaluationConfig, ProjectConfig

    config = ProjectConfig(name="test", evaluation=EvaluationConfig(model="claude-sonnet-5-5"))
    _override_eval_judge(config, model=None, backend="cursor")
    assert config.evaluation.model == "claude-sonnet-5-5"


def test_override_eval_judge_cursor_with_explicit_model() -> None:
    from nasde_toolkit.cli import _override_eval_judge
    from nasde_toolkit.config import EvaluationConfig, ProjectConfig

    config = ProjectConfig(name="test", evaluation=EvaluationConfig())
    _override_eval_judge(config, model="gpt-5.6-sol-high", backend="cursor")
    assert config.evaluation.model == "gpt-5.6-sol-high"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config.py tests/test_cli.py -k "cursor or default_evaluator" -v`
Expected: FAIL (`ImportError: cannot import name 'default_evaluator_model'`; the CLI test exits because `cursor` is rejected).

- [ ] **Step 3: Implement**

In `src/nasde_toolkit/config.py`, add near the top (after imports):

```python
_DEFAULT_EVALUATOR_MODEL = "claude-opus-5-5"
_BACKEND_DEFAULT_EVALUATOR_MODELS = {"cursor": "claude-opus-5-5-high"}
```

Add the public function in alphabetical position among the module's public functions:

```python
def default_evaluator_model(backend: str) -> str:
    """Judge model used when ``[evaluation] model`` is absent, per backend.

    The Cursor CLI has no bare ``claude-opus-5-5`` slug (it encodes effort in
    the name), so the cursor backend defaults to ``claude-opus-5-5-high``.
    """
    return _BACKEND_DEFAULT_EVALUATOR_MODELS.get(backend, _DEFAULT_EVALUATOR_MODEL)
```

In `_parse_toml`, add `eval_backend = eval_raw.get("backend", "claude")` after `eval_raw = raw.get("evaluation", {})`, and change the two `EvaluationConfig(...)` arguments to:

```python
            backend=eval_backend,
            model=eval_raw.get("model", default_evaluator_model(eval_backend)),
```

In `src/nasde_toolkit/cli.py`, replace `_override_eval_judge` with:

```python
def _override_eval_judge(config: ProjectConfig, model: str | None, backend: str | None) -> None:
    """Apply per-run judge overrides (judge-model comparison matrices).

    Switching backend without ``--eval-model`` moves an un-customized judge model
    to the new backend's default (Cursor slugs differ from Claude model IDs).
    """
    from nasde_toolkit.config import default_evaluator_model

    if backend is not None:
        if backend not in ("claude", "codex", "cursor"):
            console.print(f"[red]ERROR: --eval-backend must be 'claude', 'codex' or 'cursor', got '{backend}'.[/red]")
            raise typer.Exit(1)
        if model is None and config.evaluation.model == default_evaluator_model(config.evaluation.backend):
            config.evaluation.model = default_evaluator_model(backend)
        config.evaluation.backend = backend
    if model is not None:
        config.evaluation.model = model
```

Change the `--eval-backend` option help to `"Override the judge backend for this run: claude | codex | cursor."`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_config.py tests/test_cli.py -v`
Expected: all PASS (including the existing `test_override_eval_judge_*` tests).

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/config.py src/nasde_toolkit/cli.py tests/test_config.py tests/test_cli.py
git commit -m "config: backend-aware default judge model; accept --eval-backend cursor"
```

### Task 12: `CursorSubprocessBackend`

**Files:**
- Create: `src/nasde_toolkit/evaluator_backends/cursor_subprocess.py`
- Modify: `src/nasde_toolkit/evaluator_backends/__init__.py`
- Test: `tests/test_evaluator_backends.py`

**Interfaces:**
- Consumes: `EvaluationConfig` fields `model`, `allowed_tools`, `mcp_config`, `skills_dir`, `append_system_prompt`, `include_trajectory`; `AGENT_DIFF_FILENAME`.
- Produces: `CursorSubprocessBackend` satisfying `EvaluatorBackend`; `create_backend(EvaluationConfig(backend="cursor"))` returns it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_evaluator_backends.py` (add `import asyncio`, `import json`, `import subprocess` at the top if absent, and `from nasde_toolkit.evaluator_backends.cursor_subprocess import CursorSubprocessBackend`):

```python
CURSOR_MODULE = "nasde_toolkit.evaluator_backends.cursor_subprocess"


def test_create_backend_returns_cursor_when_configured() -> None:
    backend = create_backend(EvaluationConfig(backend="cursor"))
    assert isinstance(backend, CursorSubprocessBackend)
    assert isinstance(backend, EvaluatorBackend)


def test_create_backend_unknown_lists_cursor() -> None:
    with pytest.raises(ValueError, match="'cursor'"):
        create_backend(EvaluationConfig(backend="unknown-agent"))


def test_cursor_backend_validate_cli_installed_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(f"{CURSOR_MODULE}.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        CursorSubprocessBackend().validate_cli_installed()
    out = capsys.readouterr().out
    assert "cursor-agent" in out
    assert "cli not found" in out.lower()
    assert "[evaluation]" in out
    assert "--without-eval" in out


def test_cursor_backend_validate_auth_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "key_test")
    monkeypatch.setattr(f"{CURSOR_MODULE}.subprocess.run", lambda *a, **k: pytest.fail("status must not run"))
    CursorSubprocessBackend().validate_auth()


def test_cursor_backend_validate_auth_with_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.setattr(
        f"{CURSOR_MODULE}.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="✓ Logged in as dev@example.com\n", stderr=""),
    )
    CursorSubprocessBackend().validate_auth()


def test_cursor_backend_validate_auth_fails_when_logged_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.setattr(
        f"{CURSOR_MODULE}.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Not logged in\n", stderr=""),
    )
    with pytest.raises(SystemExit):
        CursorSubprocessBackend().validate_auth()


def test_cursor_backend_builds_read_only_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    temp_workspace = tmp_path / "temp"
    cmd = CursorSubprocessBackend()._build_command(
        "PROMPT", workspace, EvaluationConfig(backend="cursor", model="claude-opus-5-5-high"), temp_workspace, None
    )
    assert cmd[:4] == ["cursor-agent", "-p", "--output-format", "json"]
    assert cmd[cmd.index("--mode") + 1] == "ask"
    assert "--trust" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5-high"
    assert cmd[cmd.index("--workspace") + 1] == str(temp_workspace)
    assert cmd[cmd.index("--add-dir") + 1] == str(workspace)
    assert "--approve-mcps" not in cmd
    assert cmd[-2:] == ["--", "PROMPT"]


def test_cursor_backend_adds_trial_dir_for_agent_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    (trial_dir / "agent_changes.diff").write_text("diff --git a/x b/x\n")
    cmd = CursorSubprocessBackend()._build_command(
        "P", tmp_path / "ws", EvaluationConfig(backend="cursor"), tmp_path / "tmp", trial_dir
    )
    add_dirs = [cmd[i + 1] for i, part in enumerate(cmd) if part == "--add-dir"]
    assert add_dirs == [str(tmp_path / "ws"), str(trial_dir)]


def test_cursor_backend_skips_trial_dir_without_trajectory_or_diff(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    trial_dir.mkdir()
    cmd = CursorSubprocessBackend()._build_command(
        "P", tmp_path / "ws", EvaluationConfig(backend="cursor"), tmp_path / "tmp", trial_dir
    )
    assert cmd.count("--add-dir") == 1


def test_cursor_backend_approves_mcps_when_configured(tmp_path: Path) -> None:
    cmd = CursorSubprocessBackend()._build_command(
        "P", tmp_path, EvaluationConfig(backend="cursor", mcp_config="./mcp.json"), tmp_path / "tmp", None
    )
    assert "--approve-mcps" in cmd


def test_cursor_backend_prepends_system_prompt(tmp_path: Path) -> None:
    cmd = CursorSubprocessBackend()._build_command(
        "PROMPT", tmp_path, EvaluationConfig(backend="cursor", append_system_prompt="Be strict."), tmp_path / "t", None
    )
    assert cmd[-1] == "Be strict.\n\nPROMPT"


def test_cursor_backend_temp_workspace_holds_skills_and_mcp(tmp_path: Path) -> None:
    skill = tmp_path / "evaluator_skills" / "rubric-helper"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# helper")
    (tmp_path / "evaluator_mcp.json").write_text('{"mcpServers": {}}')
    eval_config = EvaluationConfig(
        backend="cursor", skills_dir="evaluator_skills", mcp_config="evaluator_mcp.json"
    )

    temp_workspace = CursorSubprocessBackend()._prepare_temp_workspace(eval_config, tmp_path)

    try:
        assert (temp_workspace / ".cursor" / "skills" / "rubric-helper" / "SKILL.md").exists()
        assert json.loads((temp_workspace / ".cursor" / "mcp.json").read_text()) == {"mcpServers": {}}
    finally:
        import shutil

        shutil.rmtree(temp_workspace, ignore_errors=True)


def test_cursor_backend_warns_on_allowed_tools(capsys: pytest.CaptureFixture[str]) -> None:
    CursorSubprocessBackend()._warn_unsupported_options(EvaluationConfig(backend="cursor", allowed_tools=["Read"]))
    assert "allowed_tools" in capsys.readouterr().out


def _fake_cursor_process(stdout: str, returncode: int = 0) -> object:
    class FakeProcess:
        def __init__(self) -> None:
            self.returncode = returncode

        async def communicate(self) -> tuple[bytes, bytes]:
            return stdout.encode(), b"stderr line"

    async def fake_exec(*_args: object, **_kwargs: object) -> FakeProcess:
        return FakeProcess()

    return fake_exec


def _patch_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CursorSubprocessBackend, "validate_cli_installed", lambda self: None)
    monkeypatch.setattr(CursorSubprocessBackend, "validate_auth", lambda self: None)


def test_cursor_backend_run_returns_result_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight(monkeypatch)
    created: list[Path] = []
    real_prepare = CursorSubprocessBackend._prepare_temp_workspace

    def tracking_prepare(self: CursorSubprocessBackend, eval_config: EvaluationConfig, project_root: Path) -> Path:
        path = real_prepare(self, eval_config, project_root)
        created.append(path)
        return path

    monkeypatch.setattr(CursorSubprocessBackend, "_prepare_temp_workspace", tracking_prepare)
    payload = json.dumps({"type": "result", "is_error": False, "result": '{"score": 7}'})
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process(payload))

    text = asyncio.run(
        CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path)
    )

    assert text == '{"score": 7}'
    assert created and not created[0].exists()


def test_cursor_backend_run_raises_on_is_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight(monkeypatch)
    payload = json.dumps({"type": "result", "is_error": True, "result": "model not available"})
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process(payload))

    with pytest.raises(RuntimeError, match="model not available"):
        asyncio.run(CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path))


def test_cursor_backend_run_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight(monkeypatch)
    monkeypatch.setattr(f"{CURSOR_MODULE}.asyncio.create_subprocess_exec", _fake_cursor_process("", returncode=2))

    with pytest.raises(RuntimeError, match="exit code 2"):
        asyncio.run(CursorSubprocessBackend().run_evaluation("P", tmp_path, EvaluationConfig(backend="cursor"), tmp_path))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_evaluator_backends.py -v`
Expected: collection fails with `ModuleNotFoundError: No module named 'nasde_toolkit.evaluator_backends.cursor_subprocess'`.

- [ ] **Step 3: Implement**

Create `src/nasde_toolkit/evaluator_backends/cursor_subprocess.py`:

```python
"""Cursor CLI subprocess evaluator backend."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends.protocol import AGENT_DIFF_FILENAME

console = Console()

_CURSOR_CLI = "cursor-agent"


class CursorSubprocessBackend:
    """Evaluator backend that spawns `cursor-agent -p` as a subprocess.

    Runs with ``--mode ask`` (read-only; Cursor has no per-tool allow-list) from a
    throwaway ``--workspace`` that holds the evaluator's ``.cursor/skills`` and
    ``.cursor/mcp.json``. The trial workspace is attached with ``--add-dir``, so
    nothing the CLI writes lands in the agent's diff. The prompt is passed as the
    final positional argument. Authenticates via ``CURSOR_API_KEY`` or the host's
    ``cursor-agent login`` (ADR-015).
    """

    async def run_evaluation(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        project_root: Path,
        trial_dir: Path | None = None,
    ) -> str:
        self.validate_cli_installed()
        self.validate_auth()
        self._warn_unsupported_options(eval_config)
        temp_workspace = self._prepare_temp_workspace(eval_config, project_root)
        try:
            cmd = self._build_command(prompt, workspace_path, eval_config, temp_workspace, trial_dir)
            return await self._run_subprocess(cmd, temp_workspace)
        finally:
            shutil.rmtree(temp_workspace, ignore_errors=True)

    def validate_auth(self) -> None:
        if os.environ.get("CURSOR_API_KEY"):
            return
        if _cursor_cli_logged_in():
            return
        console.print("[red]ERROR: Set CURSOR_API_KEY or log in via `cursor-agent login`[/red]")
        raise SystemExit(1)

    def validate_cli_installed(self) -> None:
        if shutil.which(_CURSOR_CLI) is not None:
            return
        console.print(
            "[red]ERROR: `cursor-agent` CLI not found on PATH.[/red]\n"
            "[yellow]Assessment evaluation with the Cursor backend requires the Cursor CLI.[/yellow]\n"
            "Install it with `curl https://cursor.com/install -fsS | bash`, then re-run. "
            'To use a different backend, set \\[evaluation] backend = "claude" in nasde.toml, '
            "or pass --without-eval to skip assessment evaluation."
        )
        raise SystemExit(1)

    def _warn_unsupported_options(self, eval_config: EvaluationConfig) -> None:
        if eval_config.allowed_tools:
            console.print(
                "[yellow]WARNING: \\[evaluation] allowed_tools is ignored by the cursor backend — "
                "it runs read-only via --mode ask.[/yellow]"
            )

    def _prepare_temp_workspace(self, eval_config: EvaluationConfig, project_root: Path) -> Path:
        temp_workspace = Path(tempfile.mkdtemp(prefix="nasde_eval_cursor_"))
        cursor_dir = temp_workspace / ".cursor"
        cursor_dir.mkdir()
        if eval_config.skills_dir:
            skills_source = _resolve_path(eval_config.skills_dir, project_root)
            if skills_source.is_dir():
                shutil.copytree(skills_source, cursor_dir / "skills")
        if eval_config.mcp_config:
            shutil.copyfile(_resolve_path(eval_config.mcp_config, project_root), cursor_dir / "mcp.json")
        return temp_workspace

    def _build_command(
        self,
        prompt: str,
        workspace_path: Path,
        eval_config: EvaluationConfig,
        temp_workspace: Path,
        trial_dir: Path | None,
    ) -> list[str]:
        cmd = [
            _CURSOR_CLI,
            "-p",
            "--output-format",
            "json",
            "--mode",
            "ask",
            "--trust",
            "--model",
            eval_config.model,
            "--workspace",
            str(temp_workspace),
            "--add-dir",
            str(workspace_path),
        ]
        if trial_dir is not None and _needs_trial_dir(eval_config, trial_dir):
            cmd.extend(["--add-dir", str(trial_dir)])
        if eval_config.mcp_config:
            cmd.append("--approve-mcps")
        cmd.extend(["--", _compose_prompt(prompt, eval_config.append_system_prompt)])
        return cmd

    async def _run_subprocess(self, cmd: list[str], cwd: Path) -> str:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=dict(os.environ),
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout_text = stdout_bytes.decode(errors="replace")
        if process.returncode != 0:
            raise RuntimeError(_failure_message(process.returncode, cmd, stdout_text, stderr_bytes))
        return _extract_result_text(stdout_text)


def _cursor_cli_logged_in() -> bool:
    try:
        completed = subprocess.run(
            [_CURSOR_CLI, "status"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "logged in as" in completed.stdout.lower()


def _resolve_path(relative_or_absolute: str, project_root: Path) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return project_root / path


def _needs_trial_dir(eval_config: EvaluationConfig, trial_dir: Path) -> bool:
    return eval_config.include_trajectory or (trial_dir / AGENT_DIFF_FILENAME).exists()


def _compose_prompt(prompt: str, preamble: str | None) -> str:
    if not preamble:
        return prompt
    return f"{preamble}\n\n{prompt}"


def _failure_message(returncode: int | None, cmd: list[str], stdout_text: str, stderr_bytes: bytes) -> str:
    stderr_text = stderr_bytes.decode(errors="replace").strip()
    stderr_tail = "\n".join(stderr_text.splitlines()[-10:]) or "<empty>"
    stdout_tail = "\n".join(stdout_text.strip().splitlines()[-10:]) or "<empty>"
    model = cmd[cmd.index("--model") + 1]
    return (
        f"Cursor process failed (exit code {returncode}). Model: {model}. "
        f"stderr (last 10 lines):\n{stderr_tail}\n"
        f"stdout (last 10 lines):\n{stdout_tail}"
    )


def _extract_result_text(stdout: str) -> str:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
    if not isinstance(data, dict):
        return stdout
    if data.get("is_error"):
        raise RuntimeError(f"cursor-agent reported an error: {data.get('result', '')}")
    result = data.get("result", "")
    return result if isinstance(result, str) else ""
```

In `src/nasde_toolkit/evaluator_backends/__init__.py`, replace the `else:` branch with:

```python
    elif eval_config.backend == "cursor":
        from nasde_toolkit.evaluator_backends.cursor_subprocess import CursorSubprocessBackend

        return CursorSubprocessBackend()
    else:
        raise ValueError(
            f"Unknown evaluator backend: '{eval_config.backend}'. Supported: 'claude', 'codex', 'cursor'"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_evaluator_backends.py -v && uv run mypy src/nasde_toolkit/evaluator_backends/`
Expected: all PASS; mypy `Success`.

- [ ] **Step 5: Commit**

```bash
git add src/nasde_toolkit/evaluator_backends/cursor_subprocess.py src/nasde_toolkit/evaluator_backends/__init__.py tests/test_evaluator_backends.py
git commit -m "evaluator: add the cursor judge backend"
```

### Task 13: PR 3 docs and scaffold

**Files:**
- Modify: `src/nasde_toolkit/scaffold/__init__.py`, `tests/test_scaffold.py`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `.claude/skills/nasde-benchmark-runner/SKILL.md`, `.claude/skills/nasde-dev/SKILL.md`

- [ ] **Step 1: Write the failing scaffold test**

Append to `tests/test_scaffold.py`:

```python
def test_nasde_toml_template_mentions_cursor_backend() -> None:
    from nasde_toolkit.scaffold import NASDE_TOML_TEMPLATE

    assert '# backend = "claude"  # "claude" | "codex" | "cursor"' in NASDE_TOML_TEMPLATE
```

Run: `uv run pytest tests/test_scaffold.py -v` — Expected: the new test FAILS.

- [ ] **Step 2: Implement the scaffold change**

In `src/nasde_toolkit/scaffold/__init__.py`, change the `[evaluation]` block of `NASDE_TOML_TEMPLATE` to:

```toml
[evaluation]
# backend = "claude"  # "claude" | "codex" | "cursor" (cursor defaults model to claude-opus-5-5-high)
model = "claude-opus-5-5"
dimensions_file = "assessment_dimensions.json"
# eval_repetitions = 3  # judge runs per trial; reported as a mean (the judge is non-deterministic)
```

Run: `uv run pytest tests/test_scaffold.py -v` — Expected: PASS (the asserted string is a prefix of the new line).

- [ ] **Step 3: Docs**

`CHANGELOG.md` → `## [Unreleased]` → `### Added`:

```markdown
- **Cursor judge backend.** `[evaluation] backend = "cursor"` (or
  `nasde eval --eval-backend cursor`) scores trials with `cursor-agent` in
  read-only `--mode ask`, run from a temporary workspace so nothing it writes
  ends up in the agent's diff. It uses `CURSOR_API_KEY` or your
  `cursor-agent login`, and defaults the judge model to `claude-opus-5-5-high`
  when `[evaluation] model` is not set. `allowed_tools` and `max_turns` have no
  Cursor equivalent (the former prints a warning). ([#NN])
```

`CLAUDE.md`:
1. Package structure under `evaluator_backends/`: add `cursor_subprocess.py # \`cursor-agent -p --mode ask\` subprocess backend`.
2. **Evaluator** bullet: change ``Backend selection via `[evaluation] backend` in `nasde.toml` (`"claude"` default, `"codex"` available).`` to ``Backend selection via `[evaluation] backend` in `nasde.toml` (`"claude"` default, `"codex"` and `"cursor"` available).`` and after the Codex backend sentence add ``Cursor backend runs `cursor-agent -p --output-format json --mode ask` (read-only) from a temp `--workspace` holding `.cursor/skills` + `.cursor/mcp.json`, with the trial workspace (and trial dir, under the same rule as Claude) attached via `--add-dir`; auth is `CURSOR_API_KEY` or `cursor-agent login` (checked by parsing `cursor-agent status`, which exits 0 either way); default model `claude-opus-5-5-high` (`config.default_evaluator_model`), `allowed_tools`/`max_turns` unsupported (ADR-015).``
3. `nasde.toml` example: change `backend = "claude" # "claude" (default) | "codex"` to `backend = "claude" # "claude" (default) | "codex" | "cursor"`.

`README.md` has no `backend` reference (checked 2026-11-19), so it needs no change in this PR.

`.claude/skills/nasde-benchmark-runner/SKILL.md` line 43: append ` With \`backend = "cursor"\`, the judge runs \`cursor-agent\` on the host instead and needs \`CURSOR_API_KEY\` or \`cursor-agent login\` rather than Claude auth.`

`.claude/skills/nasde-dev/SKILL.md`, in the **Evaluator** bullet of step 3: append ` With \`backend = "cursor"\`, the judge needs \`CURSOR_API_KEY\` or a logged-in \`cursor-agent\` instead.`

- [ ] **Step 4: Quality gates, commit, push, PR**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/nasde_toolkit/
uv run pytest
git add src/nasde_toolkit/scaffold/__init__.py tests/test_scaffold.py CHANGELOG.md README.md CLAUDE.md .claude/skills
git commit -m "docs: Cursor judge backend"
git push -u origin feat/cursor-judge
gh pr create --base main --title "evaluator: Cursor judge backend" --body "Implements PR 3 of docs/superpowers/plans/2026-11-19-cursor-cli-support.md. Independent of the pricing and agent PRs."
```

Replace `[#NN]` with the printed PR number, add the link-ref, commit `changelog: link Cursor judge PR`, push.

### Task 14: Live smoke run of the Cursor judge (owner-authorized)

**Do not start without the repo owner's explicit go-ahead for this run.**

- [ ] **Step 1: Re-evaluate an existing job with the Cursor judge**

Pick any existing job with completed trials (e.g. the one from Task 10, or any job under `examples/ddd-architectural-challenges/jobs/`):

```bash
J=$(ls -dt examples/ddd-architectural-challenges/jobs/*/ | head -1)
uv run nasde eval "$J" --eval-backend cursor --eval-repetitions 1 -C examples/ddd-architectural-challenges
```

- [ ] **Step 2: Check the evaluation**

```bash
T=$(ls -d $J/*/ | head -1)
N=$(ls $T/assessment_eval_*.json | sort -V | tail -1)
python3 -c "import json; e=json.load(open('$N')); print(e.get('evaluator_model'), e.get('normalized_score'))"
git -C "$T/artifacts/workspace" status --porcelain | rg "\.cursor" || echo "no .cursor leak"
```

Pass criteria:
- The newest `assessment_eval_<N>.json` has `evaluator_model == "claude-opus-5-5-high"` and a numeric `normalized_score`.
- `assessment_summary.json` shows it as its own cluster (different `evaluator_model` from earlier Claude-backend evaluations).
- The trial workspace shows `no .cursor leak`.

If the judge fails with a permissions error reading files under the `--add-dir` roots in `--mode ask`, stop and report: the fallback is to drop `--mode ask` and rely on the prompt alone, which is a security trade-off the owner must approve.
