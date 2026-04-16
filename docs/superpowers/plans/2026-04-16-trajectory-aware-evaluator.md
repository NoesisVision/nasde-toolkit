# Trajectory-Aware Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Claude Code evaluator optional access to ATIF trajectory data so benchmark authors can define assessment dimensions that evaluate the agent's process alongside its output.

**Architecture:** Add `include_trajectory` boolean to `EvaluationConfig`, thread it through `evaluate_trial()` → `_build_evaluator_prompt()` and `_build_claude_code_options()`. When enabled and trajectory exists, append a short info section to the prompt and add the trial dir to `add_dirs`.

**Tech Stack:** Python, dataclasses, Claude Code SDK, pytest

---

### Task 1: Add `include_trajectory` to EvaluationConfig

**Files:**
- Modify: `src/nasde_toolkit/config.py:32-41` (EvaluationConfig dataclass)
- Modify: `src/nasde_toolkit/config.py:126-134` (_parse_toml evaluation parsing)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test — default is False when section absent**

Add to `tests/test_config.py` inside the existing `test_evaluation_defaults_when_section_absent`:

```python
# Add this assertion at line 75, after the existing assertions:
    assert config.evaluation.include_trajectory is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_evaluation_defaults_when_section_absent -v`
Expected: FAIL — `AttributeError: 'EvaluationConfig' object has no attribute 'include_trajectory'`

- [ ] **Step 3: Add field to EvaluationConfig dataclass**

In `src/nasde_toolkit/config.py`, add after line 41 (`append_system_prompt`):

```python
    include_trajectory: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_evaluation_defaults_when_section_absent -v`
Expected: PASS

- [ ] **Step 5: Write failing test — include_trajectory parsed from toml**

Add to `tests/test_config.py` after the existing `test_evaluation_partial_override`:

```python
def test_evaluation_include_trajectory_from_toml(tmp_path: Path) -> None:
    _write_nasde_toml(
        tmp_path,
        """
[project]
name = "test"

[evaluation]
include_trajectory = true
""",
    )
    config = load_project_config(tmp_path)
    assert config.evaluation.include_trajectory is True
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_evaluation_include_trajectory_from_toml -v`
Expected: FAIL — `assert False is True` (field exists with default but not parsed from toml)

- [ ] **Step 7: Parse include_trajectory in _parse_toml**

In `src/nasde_toolkit/config.py`, inside `_parse_toml` at the `EvaluationConfig(...)` constructor (lines 126-134), add after `append_system_prompt`:

```python
            include_trajectory=eval_raw.get("include_trajectory", False),
```

- [ ] **Step 8: Run all config tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/nasde_toolkit/config.py tests/test_config.py
git commit -m "feat: add include_trajectory option to EvaluationConfig"
```

---

### Task 2: Thread trajectory info through evaluator prompt

**Files:**
- Modify: `src/nasde_toolkit/evaluator.py:192-268` (evaluate_trial)
- Modify: `src/nasde_toolkit/evaluator.py:333-398` (_build_evaluator_prompt)
- Test: `tests/test_evaluator.py` (new file)

- [ ] **Step 1: Write failing test — trajectory section absent when disabled**

Create `tests/test_evaluator.py`:

```python
"""Tests for evaluator trajectory integration."""

from __future__ import annotations

from nasde_toolkit.evaluator import _build_evaluator_prompt


def test_prompt_no_trajectory_section_when_disabled() -> None:
    prompt = _build_evaluator_prompt(
        instruction="Fix the bug",
        criteria="Check correctness",
        expected_dimensions=[{"name": "correctness", "title": "Correctness", "max_score": 25}],
        ground_truth="",
        artifacts_dir="/workspace",
        trajectory_path=None,
    )
    assert "trajectory" not in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluator.py::test_prompt_no_trajectory_section_when_disabled -v`
Expected: FAIL — `TypeError: _build_evaluator_prompt() got an unexpected keyword argument 'trajectory_path'`

- [ ] **Step 3: Add trajectory_path parameter and trajectory section to prompt**

Two changes in `src/nasde_toolkit/evaluator.py`:

**3a.** Modify `_build_evaluator_prompt` signature (line 333) — add `trajectory_path` parameter:

```python
def _build_evaluator_prompt(
    instruction: str,
    criteria: str,
    expected_dimensions: list[dict] | None,
    ground_truth: str = "",
    artifacts_dir: str | None = None,
    trajectory_path: str | None = None,
) -> str:
```

**3b.** Inside `_build_evaluator_prompt`, add trajectory section computation before the return statement and insert `{trajectory_section}` into the f-string between `{ground_truth_section}` and `## How to evaluate`:

```python
    trajectory_section = _format_trajectory_section(trajectory_path)
```

In the existing f-string, change:
```
{ground_truth_section}## How to evaluate
```
to:
```
{ground_truth_section}{trajectory_section}## How to evaluate
```

**3c.** Add `_format_trajectory_section` helper after `_format_ground_truth_section`:

```python
def _format_trajectory_section(trajectory_path: str | None) -> str:
    if not trajectory_path:
        return ""
    return f"""
## Agent trajectory

The agent's full ATIF execution trajectory is available at `{trajectory_path}`.
It contains the complete step-by-step record of the agent's work: messages, tool calls
with arguments and results, token usage per step, timestamps, and errors.

Use the Read tool to examine it when your assessment criteria require evaluating
the agent's process, efficiency, or decision-making — not just the final output.

"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluator.py::test_prompt_no_trajectory_section_when_disabled -v`
Expected: PASS

- [ ] **Step 5: Write failing test — trajectory section present when enabled**

Add to `tests/test_evaluator.py`:

```python
def test_prompt_includes_trajectory_section_when_path_provided() -> None:
    prompt = _build_evaluator_prompt(
        instruction="Fix the bug",
        criteria="Check correctness",
        expected_dimensions=[{"name": "correctness", "title": "Correctness", "max_score": 25}],
        ground_truth="",
        artifacts_dir="/workspace",
        trajectory_path="../../agent/trajectory.json",
    )
    assert "## Agent trajectory" in prompt
    assert "../../agent/trajectory.json" in prompt
    assert "ATIF" in prompt
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluator.py::test_prompt_includes_trajectory_section_when_path_provided -v`
Expected: PASS (implementation from Step 3 already handles this)

- [ ] **Step 7: Commit**

```bash
git add src/nasde_toolkit/evaluator.py tests/test_evaluator.py
git commit -m "feat: add trajectory section to evaluator prompt"
```

---

### Task 3: Wire trajectory into evaluate_trial and Claude Code options

**Files:**
- Modify: `src/nasde_toolkit/evaluator.py:192-268` (evaluate_trial — pass trajectory_path to prompt builder)
- Modify: `src/nasde_toolkit/evaluator.py:430-523` (_build_claude_code_options — add trial_dir to add_dirs)
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing test — _build_claude_code_options adds trial_dir when include_trajectory**

Add to `tests/test_evaluator.py`:

```python
from unittest.mock import patch
from pathlib import Path

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator import _build_claude_code_options


def test_claude_code_options_adds_trial_dir_when_trajectory_enabled(tmp_path: Path) -> None:
    workspace_path = tmp_path / "artifacts" / "workspace"
    workspace_path.mkdir(parents=True)
    trial_dir = tmp_path

    eval_config = EvaluationConfig(include_trajectory=True)
    options, temp_dir, stderr_path = _build_claude_code_options(
        workspace_path,
        eval_config,
        project_root=Path(),
        trial_dir=trial_dir,
    )
    assert str(trial_dir) in [str(d) for d in options.add_dirs]

    if temp_dir:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    if stderr_path:
        stderr_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluator.py::test_claude_code_options_adds_trial_dir_when_trajectory_enabled -v`
Expected: FAIL — `TypeError: _build_claude_code_options() got an unexpected keyword argument 'trial_dir'`

- [ ] **Step 3: Add trial_dir parameter to _build_claude_code_options**

In `src/nasde_toolkit/evaluator.py`, modify `_build_claude_code_options` signature (line 478):

```python
def _build_claude_code_options(
    workspace_path: Path,
    eval_config: EvaluationConfig,
    project_root: Path,
    trial_dir: Path | None = None,
) -> tuple[ClaudeCodeOptions, Path | None, Path | None]:
```

After the existing `add_dirs` logic (around line 493, after the skills_dir block), add:

```python
    if eval_config.include_trajectory and trial_dir:
        add_dirs.append(str(trial_dir))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluator.py::test_claude_code_options_adds_trial_dir_when_trajectory_enabled -v`
Expected: PASS

- [ ] **Step 5: Write test — trial_dir NOT added when include_trajectory is False**

Add to `tests/test_evaluator.py`:

```python
def test_claude_code_options_no_trial_dir_when_trajectory_disabled(tmp_path: Path) -> None:
    workspace_path = tmp_path / "artifacts" / "workspace"
    workspace_path.mkdir(parents=True)
    trial_dir = tmp_path

    eval_config = EvaluationConfig(include_trajectory=False)
    options, temp_dir, stderr_path = _build_claude_code_options(
        workspace_path,
        eval_config,
        project_root=Path(),
        trial_dir=trial_dir,
    )
    assert str(trial_dir) not in [str(d) for d in options.add_dirs]

    if temp_dir:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    if stderr_path:
        stderr_path.unlink(missing_ok=True)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluator.py::test_claude_code_options_no_trial_dir_when_trajectory_disabled -v`
Expected: PASS

- [ ] **Step 7: Wire evaluate_trial to pass trajectory info**

In `src/nasde_toolkit/evaluator.py`, in `evaluate_trial()` (around line 230-248):

1. After `ground_truth` resolution (line 230), add trajectory path detection:

```python
    trajectory_path = _resolve_trajectory_path(trial_dir, eval_config)
```

2. Pass `trajectory_path` to `_build_evaluator_prompt` (around line 233):

```python
    prompt = _build_evaluator_prompt(
        instruction,
        criteria,
        expected_dimensions,
        ground_truth,
        artifacts_dir,
        trajectory_path,
    )
```

3. Pass `trial_dir` to `_run_claude_code_evaluation` and down to `_build_claude_code_options`. Modify `_run_claude_code_evaluation` signature:

```python
async def _run_claude_code_evaluation(
    prompt: str,
    workspace_path: Path,
    eval_config: EvaluationConfig | None = None,
    project_root: Path = Path(),
    trial_dir: Path | None = None,
) -> str:
```

And pass it through:

```python
    options, temp_dir, stderr_path = _build_claude_code_options(
        workspace_path,
        eval_config,
        project_root,
        trial_dir,
    )
```

4. In `evaluate_trial()`, the call to `_run_claude_code_evaluation` (around line 244) needs `trial_dir`:

```python
    raw_response = await _run_claude_code_evaluation(
        prompt,
        workspace_path,
        eval_config,
        project_root,
        trial_dir,
    )
```

But `evaluate_trial` doesn't currently have `trial_dir` as a parameter. It needs it. Add it to the signature:

```python
async def evaluate_trial(
    trial_dir: Path,
    project_root: Path,
    eval_config: EvaluationConfig | None = None,
) -> EvaluationResult | None:
```

This is already the case — `trial_dir` is already the first parameter (line 193). The workspace is derived from it at line 199: `workspace_path = trial_dir / "artifacts" / "workspace"`. So `trial_dir` is already available.

5. Add the helper function in the resolution helpers section:

```python
def _resolve_trajectory_path(trial_dir: Path, eval_config: EvaluationConfig) -> str | None:
    if not eval_config.include_trajectory:
        return None
    trajectory_file = trial_dir / "agent" / "trajectory.json"
    if not trajectory_file.exists():
        return None
    return "../../agent/trajectory.json"
```

- [ ] **Step 8: Run all evaluator tests**

Run: `uv run pytest tests/test_evaluator.py -v`
Expected: All PASS

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add src/nasde_toolkit/evaluator.py tests/test_evaluator.py
git commit -m "feat: wire trajectory data through evaluator pipeline"
```

---

### Task 4: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Update CLAUDE.md**

In `CLAUDE.md`, in the `nasde.toml` reference section under `[evaluation]`, add `include_trajectory` to the commented-out options:

```toml
# include_trajectory = false           # Include ATIF trajectory in evaluation (default: false)
```

Also add `include_trajectory` to the `EvaluationConfig` mention in the Architecture decisions section under "Evaluator":

> Configurable via `[evaluation]` in `nasde.toml` — model, tools, MCP servers, skills, system prompt, and trajectory inclusion can all be customized.

- [ ] **Step 2: Update ARCHITECTURE.md**

In `ARCHITECTURE.md`, in the evaluator section, add a note about trajectory support:

> When `include_trajectory = true`, the evaluator also has access to the agent's ATIF trajectory (`agent/trajectory.json`), enabling assessment dimensions that evaluate the agent's process alongside its output.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md ARCHITECTURE.md
git commit -m "docs: document include_trajectory evaluation option"
```

---

### Task 5: Add test for _resolve_trajectory_path helper

**Files:**
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Write test — returns None when disabled**

Add to `tests/test_evaluator.py`:

```python
from nasde_toolkit.evaluator import _resolve_trajectory_path


def test_resolve_trajectory_path_none_when_disabled(tmp_path: Path) -> None:
    eval_config = EvaluationConfig(include_trajectory=False)
    result = _resolve_trajectory_path(tmp_path, eval_config)
    assert result is None


def test_resolve_trajectory_path_none_when_file_missing(tmp_path: Path) -> None:
    eval_config = EvaluationConfig(include_trajectory=True)
    result = _resolve_trajectory_path(tmp_path, eval_config)
    assert result is None


def test_resolve_trajectory_path_returns_relative_path(tmp_path: Path) -> None:
    trajectory_file = tmp_path / "agent" / "trajectory.json"
    trajectory_file.parent.mkdir(parents=True)
    trajectory_file.write_text("{}")

    eval_config = EvaluationConfig(include_trajectory=True)
    result = _resolve_trajectory_path(tmp_path, eval_config)
    assert result == "../../agent/trajectory.json"
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_evaluator.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_evaluator.py
git commit -m "test: add trajectory path resolution tests"
```
