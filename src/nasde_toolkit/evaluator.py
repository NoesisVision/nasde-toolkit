"""Post-hoc assessment evaluation using Claude Code SDK.

Analyzes AI-generated artifacts from Harbor trials against assessment criteria
and optional ground truth. Scores are written locally and optionally uploaded
to Opik as feedback scores on existing traces.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, query
from claude_code_sdk._errors import ProcessError
from claude_code_sdk._internal import client as _sdk_client
from claude_code_sdk._internal import message_parser as _mp
from claude_code_sdk.types import AssistantMessage, TextBlock
from rich.console import Console

from nasde_toolkit.config import EvaluationConfig

# ---------------------------------------------------------------------------
# Monkeypatch: claude-code-sdk 0.0.25 — unknown message type crash
#
# Bug:     SDK's parse_message() raises MessageParseError on message types it
#          doesn't recognize (e.g. "rate_limit_event"). This crashes the entire
#          async query stream — there is no way to catch it per-message because
#          the exception is raised inside the SDK's async generator.
#
# Fix:     Replace parse_message in the client module (where it's imported as a
#          local name) with a wrapper that returns None for unknown types.
#          The async for loop in _run_claude_code_evaluation() skips None.
#
# When to remove:  when claude-code-sdk handles unknown message types gracefully.
#                  Check: `grep "Unknown message type" .venv/.../message_parser.py`
#                  If the line raises logger.debug instead of MessageParseError,
#                  this monkeypatch is no longer needed.
# ---------------------------------------------------------------------------
_original_parse_message = _mp.parse_message


def _patched_parse_message(data: dict) -> object:
    try:
        return _original_parse_message(data)
    except _mp.MessageParseError:
        return None


_sdk_client.parse_message = _patched_parse_message  # type: ignore[assignment]

console = Console()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    name: str
    score: int
    max_score: int = 25
    reasoning: str = ""


@dataclass
class EvaluationResult:
    """Complete evaluation result for a single trial."""

    task_name: str
    trial_name: str
    agent_name: str
    evaluator_model: str
    timestamp: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    total_score: int = 0
    normalized_score: float = 0.0
    summary: str = ""
    harbor_reward: float = 0.0
    duration_sec: float = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def evaluate_job(
    job_dir: Path,
    project_root: Path,
    project_name: str,
    with_opik: bool = False,
    max_concurrent: int = 10,
    eval_config: EvaluationConfig | None = None,
) -> list[EvaluationResult]:
    """Evaluate all trials in a job directory (concurrently)."""
    eval_config = eval_config or EvaluationConfig()
    trial_dirs = _collect_trial_dirs(job_dir)

    if not trial_dirs:
        console.print("[yellow]No trial directories found.[/yellow]")
        return []

    _warn_if_throttled(trial_dirs, max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    coros = [
        _evaluate_and_record_trial(
            td,
            project_root,
            project_name,
            with_opik,
            semaphore,
            eval_config,
        )
        for td in trial_dirs
    ]
    all_results = await asyncio.gather(*coros)
    return [r for r in all_results if r is not None]


async def evaluate_and_record_trial(
    trial_dir: Path,
    project_root: Path,
    project_name: str,
    with_opik: bool,
    semaphore: asyncio.Semaphore,
    eval_config: EvaluationConfig | None = None,
) -> EvaluationResult | None:
    """Evaluate a single trial with semaphore-based concurrency control.

    Public wrapper used by runner.py for streaming (Level 2) assessment.
    """
    eval_config = eval_config or EvaluationConfig()
    return await _evaluate_and_record_trial(
        trial_dir,
        project_root,
        project_name,
        with_opik,
        semaphore,
        eval_config,
    )


async def _evaluate_and_record_trial(
    trial_dir: Path,
    project_root: Path,
    project_name: str,
    with_opik: bool,
    semaphore: asyncio.Semaphore,
    eval_config: EvaluationConfig | None = None,
) -> EvaluationResult | None:
    eval_config = eval_config or EvaluationConfig()
    async with semaphore:
        console.print(f"\n[bold]Evaluating: {trial_dir.name}[/bold]")
        try:
            evaluation = await evaluate_trial(trial_dir, project_root, eval_config)
            if not evaluation:
                return None
            _write_evaluation_result(trial_dir, evaluation)
            if with_opik:
                await asyncio.to_thread(_upload_to_opik, evaluation, project_name)
            return evaluation
        except Exception as exc:
            console.print(f"[red]Assessment failed for {trial_dir.name}: {exc}[/red]")
            return None


def _warn_if_throttled(trial_dirs: list[Path], max_concurrent: int) -> None:
    if len(trial_dirs) <= max_concurrent:
        return
    unique_tasks = {td.name.rsplit("__", 1)[0] for td in trial_dirs}
    n_tasks = len(unique_tasks)
    n_attempts = len(trial_dirs) // max(n_tasks, 1)
    breakdown = f"{n_tasks} tasks x {n_attempts} attempts" if n_attempts > 1 else f"{n_tasks} tasks"
    console.print(
        f"[yellow]Warning: {len(trial_dirs)} trials to evaluate ({breakdown}), "
        f"but max concurrent evals is {max_concurrent}. "
        f"Evaluations will be throttled. Use --max-concurrent-eval to adjust.[/yellow]"
    )


async def evaluate_trial(
    trial_dir: Path,
    project_root: Path,
    eval_config: EvaluationConfig | None = None,
) -> EvaluationResult | None:
    """Orchestrate assessment evaluation for a single trial."""
    eval_config = eval_config or EvaluationConfig()
    workspace_path = trial_dir / "artifacts" / "workspace"
    if not workspace_path.exists():
        console.print(f"  [dim]SKIP: No artifacts/workspace/ in {trial_dir.name}[/dim]")
        return None

    result_json = _load_json(trial_dir / "result.json")

    if result_json.get("exception_info"):
        console.print(f"  [dim]SKIP: Trial {trial_dir.name} failed with exception (agent never ran)[/dim]")
        return None

    task_name = _resolve_task_name(result_json)
    task_dir = _resolve_task_dir(result_json, project_root)
    trial_name = result_json.get("trial_name", trial_dir.name)
    agent_name = _resolve_agent_name(trial_dir)
    harbor_reward = (result_json.get("verifier_result") or {}).get("rewards", {}).get("reward", 0.0)
    duration_sec = _compute_duration_sec(result_json)

    dimensions_path = task_dir.parent.parent / "assessment_dimensions.json"
    expected_dimensions = _load_expected_dimensions(dimensions_path)

    criteria_path = task_dir / "assessment_criteria.md"
    if not criteria_path.exists():
        console.print(f"  [dim]SKIP: No assessment_criteria.md for task '{task_name}'[/dim]")
        return None

    instruction_path = task_dir / "instruction.md"
    criteria = criteria_path.read_text()
    instruction = instruction_path.read_text() if instruction_path.exists() else ""

    ground_truth_path = task_dir / "ground_truth_decisions.json"
    ground_truth = ground_truth_path.read_text() if ground_truth_path.exists() else ""

    trajectory_path = _resolve_trajectory_path(trial_dir, eval_config)
    artifacts_dir = str(workspace_path) if eval_config.skills_dir else None
    prompt = _build_evaluator_prompt(
        instruction,
        criteria,
        expected_dimensions,
        ground_truth,
        artifacts_dir,
        trajectory_path,
    )
    console.print(f"  Task: {task_name}")
    console.print(f"  Workspace: {workspace_path}")
    console.print("  Running Claude Code evaluation...")

    raw_response = await _run_claude_code_evaluation(
        prompt,
        workspace_path,
        eval_config,
        project_root,
        trial_dir,
    )
    evaluation = _parse_evaluation_response(raw_response, expected_dimensions)

    if not evaluation:
        console.print("  [red]ERROR: Failed to parse evaluation response[/red]")
        return None

    evaluation.task_name = task_name
    evaluation.trial_name = trial_name
    evaluation.agent_name = agent_name
    evaluation.harbor_reward = harbor_reward
    evaluation.duration_sec = duration_sec
    evaluation.evaluator_model = eval_config.model
    evaluation.timestamp = datetime.now(UTC).isoformat()

    console.print(f"  Score: {evaluation.total_score}/100 ({evaluation.normalized_score:.2f})")
    for dim in evaluation.dimensions:
        console.print(f"    {dim.name}: {dim.score}/{dim.max_score}")

    return evaluation


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _collect_trial_dirs(job_dir: Path) -> list[Path]:
    if not job_dir.exists():
        return []
    return sorted(
        [d for d in job_dir.iterdir() if d.is_dir() and (d / "result.json").exists()],
        key=lambda p: p.name,
    )


def _compute_duration_sec(result: dict) -> float:
    started = result.get("started_at", "")
    finished = result.get("finished_at", "")
    if not started or not finished:
        return 0.0
    start_dt = datetime.fromisoformat(started)
    end_dt = datetime.fromisoformat(finished)
    return (end_dt - start_dt).total_seconds()


def _load_expected_dimensions(dimensions_path: Path) -> list[dict] | None:
    if not dimensions_path.exists():
        return None
    data = _load_json(dimensions_path)
    dims: list[dict] | None = data.get("dimensions", [])
    return dims


def _resolve_agent_name(trial_dir: Path) -> str:
    config_path = trial_dir / "config.json"
    if config_path.exists():
        config = _load_json(config_path)
        name: str = config.get("agent", {}).get("name", "")
        return name
    return ""


def _resolve_task_dir(result: dict, project_root: Path) -> Path:
    task_path: str = result.get("task_id", {}).get("path", "")
    if task_path:
        return project_root / task_path
    task_name: str = result.get("task_name", "")
    source: str = result.get("source", "")
    if source and task_name:
        return project_root / "evals" / source / "tasks" / task_name
    return Path()


def _resolve_task_name(result: dict) -> str:
    name: str = result.get("task_name", "")
    return name


def _resolve_trajectory_path(trial_dir: Path, eval_config: EvaluationConfig) -> str | None:
    if not eval_config.include_trajectory:
        return None
    trajectory_file = trial_dir / "agent" / "trajectory.json"
    if not trajectory_file.exists():
        return None
    return "../../agent/trajectory.json"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_evaluator_prompt(
    instruction: str,
    criteria: str,
    expected_dimensions: list[dict] | None,
    ground_truth: str = "",
    artifacts_dir: str | None = None,
    trajectory_path: str | None = None,
) -> str:
    """Build the evaluation prompt with optional dimension constraints and ground truth."""
    dimension_constraint = _format_dimension_constraint(expected_dimensions)
    ground_truth_section = _format_ground_truth_section(ground_truth)
    trajectory_section = _format_trajectory_section(trajectory_path)

    location_hint = (
        f"Analyze the artifacts in `{artifacts_dir}`."
        if artifacts_dir
        else "Analyze the artifacts in the current working directory."
    )

    return f"""You are an expert evaluator assessing AI-generated artifacts against defined criteria.

## Your task

{location_hint} These were generated by an AI agent that was given the following task instruction:

<task_instruction>
{instruction}
</task_instruction>

## Evaluation criteria

Score the output on the following dimensions. Each dimension is 0–25 points.
Follow the rubric EXACTLY — assign the score that matches the description, not higher.

<criteria>
{criteria}
</criteria>
{ground_truth_section}{trajectory_section}## How to evaluate

1. Use `Glob` to discover all output files in the workspace.
2. Use `Read` to examine the content of each output file.
3. Use `Grep` to search for specific patterns or keywords.
4. For each dimension, find concrete evidence before assigning a score.

## Output format

After your analysis, output a single JSON block with your evaluation.
The JSON MUST be the last code block in your response:

```json
{{
  "dimensions": [
    {{"name": "<dimension_snake_case>", "score": <0-25>, "max_score": 25,
      "reasoning": "<1-3 sentences with specific evidence references>"}},
    ...
  ],
  "total_score": <sum of all dimension scores>,
  "normalized_score": <total_score / 100.0>,
  "summary": "<2-3 sentence overall assessment>"
}}
```

IMPORTANT:
- Be precise — reference specific files and content you found.
- Do NOT inflate scores. If evidence is missing, score lower.
{dimension_constraint}- Output exactly {len(expected_dimensions) if expected_dimensions else 4} dimensions.
"""


def _format_dimension_constraint(expected_dimensions: list[dict] | None) -> str:
    if not expected_dimensions:
        return "- The dimension names must be snake_case and match the criteria headings.\n"
    names = [d["name"] for d in expected_dimensions]
    names_list = ", ".join(f"`{n}`" for n in names)
    return f"- Output EXACTLY these dimension names in this order: {names_list}.\n"


def _format_ground_truth_section(ground_truth: str) -> str:
    if not ground_truth:
        return ""
    return f"""
## Ground truth reference

Use the following ground truth to evaluate completeness and accuracy.
The agent's output should capture these decisions — missing or incorrect
decisions should lower the score.

<ground_truth>
{ground_truth}
</ground_truth>
"""


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


# ---------------------------------------------------------------------------
# Claude Code SDK interaction
# ---------------------------------------------------------------------------


async def _run_claude_code_evaluation(
    prompt: str,
    workspace_path: Path,
    eval_config: EvaluationConfig | None = None,
    project_root: Path = Path(),
    trial_dir: Path | None = None,
) -> str:
    eval_config = eval_config or EvaluationConfig()
    _validate_auth()
    options, temp_dir, stderr_path = _build_claude_code_options(
        workspace_path,
        eval_config,
        project_root,
        trial_dir,
    )

    try:
        text_parts: list[str] = []
        async for message in query(prompt=prompt, options=options):
            if message is None:
                continue
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)

        return "\n".join(text_parts)
    except ProcessError as exc:
        stderr_detail = _extract_stderr_detail(stderr_path)
        raise RuntimeError(
            f"Claude Code process failed (exit code {exc.exit_code}). "
            f"Model: {eval_config.model}, cwd: {workspace_path}. "
            f"{stderr_detail}"
        ) from exc
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        if stderr_path:
            stderr_path.unlink(missing_ok=True)


def _extract_stderr_detail(stderr_path: Path | None) -> str:
    if stderr_path and stderr_path.exists():
        content = stderr_path.read_text().strip()
        if content:
            last_lines = "\n".join(content.splitlines()[-10:])
            return f"stderr (last 10 lines):\n{last_lines}"
    return "Enable debug-to-stderr for more details."


def _build_claude_code_options(
    workspace_path: Path,
    eval_config: EvaluationConfig,
    project_root: Path,
    trial_dir: Path | None = None,
) -> tuple[ClaudeCodeOptions, Path | None, Path | None]:
    allowed_tools = eval_config.allowed_tools or ["Read", "Glob", "Grep"]
    cwd = str(workspace_path)
    add_dirs: list[str | Path] = []
    temp_dir: Path | None = None

    if eval_config.skills_dir:
        temp_dir = Path(tempfile.mkdtemp(prefix="nasde_eval_"))
        skills_source = _resolve_path(eval_config.skills_dir, project_root)
        _prepare_skills_workspace(temp_dir, skills_source)
        add_dirs.append(str(workspace_path))
        cwd = str(temp_dir)

    if eval_config.include_trajectory and trial_dir:
        add_dirs.append(str(trial_dir))

    mcp_servers: dict | str | Path = {}
    if eval_config.mcp_config:
        mcp_config_path = _resolve_path(eval_config.mcp_config, project_root)
        mcp_servers = str(mcp_config_path)

    kwargs: dict = {}
    if mcp_servers:
        kwargs["mcp_servers"] = mcp_servers
    if eval_config.append_system_prompt:
        kwargs["append_system_prompt"] = eval_config.append_system_prompt

    stderr_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="nasde_stderr_", suffix=".log", delete=False
    )
    stderr_path = Path(stderr_file.name)

    options = ClaudeCodeOptions(
        allowed_tools=allowed_tools,
        cwd=cwd,
        max_turns=eval_config.max_turns,
        model=eval_config.model,
        env={"CLAUDECODE": ""},
        add_dirs=add_dirs,
        extra_args={"debug-to-stderr": None},
        debug_stderr=stderr_file,
        **kwargs,
    )

    return options, temp_dir, stderr_path


def _prepare_skills_workspace(temp_dir: Path, skills_source: Path) -> None:
    if not skills_source.is_dir():
        console.print(f"  [yellow]WARN: skills_dir '{skills_source}' not found or not a directory[/yellow]")
        return
    target_skills_dir = temp_dir / ".claude" / "skills"
    shutil.copytree(skills_source, target_skills_dir)


def _resolve_path(relative_or_absolute: str, project_root: Path) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return project_root / path


def _validate_auth() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    if not env:
        console.print("[red]ERROR: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN[/red]")
        raise SystemExit(1)
    return env


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_evaluation_response(
    raw: str,
    expected_dimensions: list[dict] | None,
) -> EvaluationResult | None:
    """Parse Claude's JSON response and validate dimension names."""
    json_blocks = re.findall(r"```json\s*\n(.*?)\n```", raw, re.DOTALL)
    if not json_blocks:
        return None

    try:
        data = json.loads(json_blocks[-1])
    except json.JSONDecodeError:
        return None

    dimensions = [
        DimensionScore(
            name=d["name"],
            score=max(0, min(25, int(d["score"]))),
            max_score=d.get("max_score", 25),
            reasoning=d.get("reasoning", ""),
        )
        for d in data.get("dimensions", [])
    ]

    _validate_dimensions(dimensions, expected_dimensions)

    total = sum(d.score for d in dimensions)

    return EvaluationResult(
        task_name="",
        trial_name="",
        agent_name="",
        evaluator_model="",
        timestamp="",
        dimensions=dimensions,
        total_score=total,
        normalized_score=round(total / 100.0, 4),
        summary=data.get("summary", ""),
    )


def _validate_dimensions(
    actual: list[DimensionScore],
    expected: list[dict] | None,
) -> None:
    if not expected:
        return
    expected_names = [d["name"] for d in expected]
    actual_names = [d.name for d in actual]
    if actual_names != expected_names:
        console.print(f"  [yellow]WARN: Dimension mismatch — expected {expected_names}, got {actual_names}[/yellow]")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _write_evaluation_result(trial_dir: Path, evaluation: EvaluationResult) -> None:
    output_path = trial_dir / "assessment_eval.json"
    with open(output_path, "w") as f:
        json.dump(asdict(evaluation), f, indent=2)
    console.print(f"  Written: {output_path}")


# ---------------------------------------------------------------------------
# Opik integration
# ---------------------------------------------------------------------------


def _upload_to_opik(evaluation: EvaluationResult, project_name: str) -> None:
    try:
        import opik
    except ImportError:
        console.print("  [yellow]WARN: opik not installed, skipping upload[/yellow]")
        return

    client = opik.Opik()
    trace_id = _find_opik_trace(client, evaluation.trial_name, evaluation.agent_name, project_name)

    if not trace_id:
        console.print(f"  Creating new trace for {evaluation.trial_name}")
        new_trace = client.trace(
            name=f"{evaluation.trial_name}__assessment-eval",
            project_name=project_name,
            input={"task_name": evaluation.task_name},
            output={"summary": evaluation.summary},
        )
        trace_id = new_trace.id

    scores = _build_opik_scores(trace_id, evaluation)
    client.log_traces_feedback_scores(scores, project_name=project_name)  # type: ignore[arg-type]
    client.flush()
    console.print(f"  Uploaded {len(scores)} feedback scores to Opik (trace {trace_id})")


def _build_opik_scores(trace_id: str, evaluation: EvaluationResult) -> list[dict]:
    scores = [
        {
            "id": trace_id,
            "name": f"arch_{dim.name}",
            "value": float(dim.score) / float(dim.max_score),
            "reason": dim.reasoning,
        }
        for dim in evaluation.dimensions
    ]
    scores.append(
        {
            "id": trace_id,
            "name": "arch_total",
            "value": evaluation.normalized_score,
            "reason": evaluation.summary,
        }
    )
    scores.append(
        {
            "id": trace_id,
            "name": "reward",
            "value": evaluation.harbor_reward,
        }
    )
    scores.append(
        {
            "id": trace_id,
            "name": "duration_sec",
            "value": evaluation.duration_sec,
        }
    )
    return scores


def _find_opik_trace(
    client: object,
    trial_name: str,
    agent_name: str,
    project_name: str,
) -> str | None:
    search_name = f"{agent_name}/{trial_name}" if agent_name else trial_name

    try:
        traces = client.search_traces(  # type: ignore[attr-defined]
            project_name=project_name,
            filter_string=f'name = "{search_name}"',
            max_results=1,
            wait_for_at_least=1,
            wait_for_timeout=30,
        )
        if traces:
            trace_id: str = traces[0].id
            console.print(f"  Found Opik trace: {search_name} ({trace_id})")
            return trace_id
    except Exception as exc:
        console.print(f"  [yellow]WARN: Opik search timed out for '{search_name}': {exc}[/yellow]")

    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    with open(path) as f:
        data: dict = json.load(f)
    return data
