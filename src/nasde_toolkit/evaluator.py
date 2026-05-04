"""Post-hoc assessment evaluation via pluggable subprocess backends.

Analyzes AI-generated artifacts from Harbor trials against assessment criteria
and optional ground truth. Scores are written locally and optionally uploaded
to Opik as feedback scores on existing traces.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from nasde_toolkit.config import EvaluationConfig
from nasde_toolkit.evaluator_backends import create_backend

console = Console()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    name: str
    score: int
    max_score: int
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
    console.print(f"  Running {eval_config.backend} evaluation...")

    backend = create_backend(eval_config)
    raw_response = await backend.run_evaluation(
        prompt=prompt,
        workspace_path=workspace_path,
        eval_config=eval_config,
        project_root=project_root,
        trial_dir=trial_dir,
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

    total_max = sum(dim.max_score for dim in evaluation.dimensions)
    console.print(f"  Score: {evaluation.total_score}/{total_max} ({evaluation.normalized_score:.2f})")
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
    _validate_expected_dimensions(dims, dimensions_path)
    return dims


def _validate_expected_dimensions(dims: list[dict] | None, source: Path) -> None:
    if not dims:
        return
    for index, dim in enumerate(dims):
        name = dim.get("name") or f"<dimension #{index}>"
        if "max_score" not in dim:
            raise ValueError(
                f"{source}: dimension '{name}' is missing required field 'max_score'. "
                "Each dimension must declare its own scale (any positive integer)."
            )
        max_score = dim["max_score"]
        if not isinstance(max_score, int) or max_score <= 0:
            raise ValueError(
                f"{source}: dimension '{name}' has invalid max_score={max_score!r}. "
                "max_score must be a positive integer."
            )


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
    scoring_guidance = _format_scoring_guidance(expected_dimensions)
    dimension_constraint = _format_dimension_constraint(expected_dimensions)
    output_schema = _format_output_schema(expected_dimensions)
    dimension_count_rule = _format_dimension_count_rule(expected_dimensions)
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

Score the output on the dimensions defined below. Each dimension has its own
independent scale — use the exact range listed for each one, do NOT assume a
shared scale across dimensions. Follow the rubric EXACTLY — assign the score
that matches the description, not higher.

{scoring_guidance}
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
{output_schema}
```

IMPORTANT:
- Be precise — reference specific files and content you found.
- Do NOT inflate scores. If evidence is missing, score lower.
- Each dimension's `score` must be between 0 and that dimension's `max_score`.
{dimension_constraint}{dimension_count_rule}"""


def _format_scoring_guidance(expected_dimensions: list[dict] | None) -> str:
    if not expected_dimensions:
        return ""
    lines = [f"- `{d['name']}`: 0–{d['max_score']} points" for d in expected_dimensions]
    return "Score ranges per dimension:\n" + "\n".join(lines) + "\n"


def _format_dimension_constraint(expected_dimensions: list[dict] | None) -> str:
    if not expected_dimensions:
        return "- The dimension names must be snake_case and match the criteria headings.\n"
    names = [d["name"] for d in expected_dimensions]
    names_list = ", ".join(f"`{n}`" for n in names)
    return f"- Output EXACTLY these dimension names in this order: {names_list}.\n"


def _format_dimension_count_rule(expected_dimensions: list[dict] | None) -> str:
    if not expected_dimensions:
        return ""
    return f"- Output exactly {len(expected_dimensions)} dimensions.\n"


def _format_output_schema(expected_dimensions: list[dict] | None) -> str:
    if not expected_dimensions:
        return (
            "{\n"
            '  "dimensions": [\n'
            '    {"name": "<dimension_snake_case>", "score": <int>, "max_score": <int>,\n'
            '      "reasoning": "<1-3 sentences with specific evidence references>"}\n'
            "  ],\n"
            '  "total_score": <sum of all dimension scores>,\n'
            '  "normalized_score": <total_score / sum of all max_score values>,\n'
            '  "summary": "<2-3 sentence overall assessment>"\n'
            "}"
        )
    dim_lines = ",\n".join(
        f'    {{"name": "{d["name"]}", "score": <0-{d["max_score"]}>, "max_score": {d["max_score"]},\n'
        f'      "reasoning": "<1-3 sentences with specific evidence references>"}}'
        for d in expected_dimensions
    )
    total_max = sum(d["max_score"] for d in expected_dimensions)
    return (
        "{\n"
        '  "dimensions": [\n'
        f"{dim_lines}\n"
        "  ],\n"
        f'  "total_score": <sum of all dimension scores, max {total_max}>,\n'
        f'  "normalized_score": <total_score / {total_max}>,\n'
        '  "summary": "<2-3 sentence overall assessment>"\n'
        "}"
    )


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

    expected_by_name = {d["name"]: d for d in (expected_dimensions or [])}
    dimensions = [_build_dimension_score(d, expected_by_name) for d in data.get("dimensions", [])]

    _validate_dimensions(dimensions, expected_dimensions)

    total = sum(d.score for d in dimensions)
    total_max = sum(d.max_score for d in dimensions)
    normalized = round(total / total_max, 4) if total_max > 0 else 0.0

    return EvaluationResult(
        task_name="",
        trial_name="",
        agent_name="",
        evaluator_model="",
        timestamp="",
        dimensions=dimensions,
        total_score=total,
        normalized_score=normalized,
        summary=data.get("summary", ""),
    )


def _build_dimension_score(raw: dict, expected_by_name: dict[str, dict]) -> DimensionScore:
    name = raw["name"]
    expected = expected_by_name.get(name, {})
    max_score = int(raw.get("max_score") or expected.get("max_score") or 0)
    if max_score <= 0:
        raise ValueError(
            f"Dimension '{name}' has no usable max_score (evaluator response did not include one "
            "and assessment_dimensions.json did not provide it either)."
        )
    score = max(0, min(max_score, int(raw["score"])))
    return DimensionScore(
        name=name,
        score=score,
        max_score=max_score,
        reasoning=raw.get("reasoning", ""),
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
