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
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, query
from claude_code_sdk._internal import client as _sdk_client
from claude_code_sdk._internal import message_parser as _mp
from claude_code_sdk.types import AssistantMessage, TextBlock
from rich.console import Console

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


_sdk_client.parse_message = _patched_parse_message

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
) -> list[EvaluationResult]:
    """Evaluate all trials in a job directory."""
    trial_dirs = _collect_trial_dirs(job_dir)

    if not trial_dirs:
        console.print("[yellow]No trial directories found.[/yellow]")
        return []

    results: list[EvaluationResult] = []
    for trial_dir in trial_dirs:
        console.print(f"\n[bold]{'=' * 60}[/bold]")
        console.print(f"[bold]Evaluating: {trial_dir.name}[/bold]")
        console.print(f"[bold]{'=' * 60}[/bold]")

        evaluation = await evaluate_trial(trial_dir, project_root)
        if not evaluation:
            continue

        _write_evaluation_result(trial_dir, evaluation)
        results.append(evaluation)

        if with_opik:
            _upload_to_opik(evaluation, project_name)

    return results


async def evaluate_trial(
    trial_dir: Path,
    project_root: Path,
) -> EvaluationResult | None:
    """Orchestrate assessment evaluation for a single trial."""
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

    prompt = _build_evaluator_prompt(
        instruction, criteria, expected_dimensions, ground_truth,
    )
    console.print(f"  Task: {task_name}")
    console.print(f"  Workspace: {workspace_path}")
    console.print("  Running Claude Code evaluation...")

    raw_response = await _run_claude_code_evaluation(prompt, workspace_path)
    evaluation = _parse_evaluation_response(raw_response, expected_dimensions)

    if not evaluation:
        console.print("  [red]ERROR: Failed to parse evaluation response[/red]")
        return None

    evaluation.task_name = task_name
    evaluation.trial_name = trial_name
    evaluation.agent_name = agent_name
    evaluation.harbor_reward = harbor_reward
    evaluation.duration_sec = duration_sec
    evaluation.evaluator_model = "claude-code-sdk"
    evaluation.timestamp = datetime.now(timezone.utc).isoformat()

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
    return data.get("dimensions", [])


def _resolve_agent_name(trial_dir: Path) -> str:
    config_path = trial_dir / "config.json"
    if config_path.exists():
        config = _load_json(config_path)
        return config.get("agent", {}).get("name", "")
    return ""


def _resolve_task_dir(result: dict, project_root: Path) -> Path:
    task_path = result.get("task_id", {}).get("path", "")
    if task_path:
        return project_root / task_path
    task_name = result.get("task_name", "")
    source = result.get("source", "")
    if source and task_name:
        return project_root / "evals" / source / "tasks" / task_name
    return Path()


def _resolve_task_name(result: dict) -> str:
    return result.get("task_name", "")


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_evaluator_prompt(
    instruction: str,
    criteria: str,
    expected_dimensions: list[dict] | None,
    ground_truth: str = "",
) -> str:
    """Build the evaluation prompt with optional dimension constraints and ground truth."""
    dimension_constraint = _format_dimension_constraint(expected_dimensions)
    ground_truth_section = _format_ground_truth_section(ground_truth)

    return f"""You are an expert evaluator assessing AI-generated artifacts against defined criteria.

## Your task

Analyze the artifacts in the current working directory. These were generated by an AI agent that was given the following task instruction:

<task_instruction>
{instruction}
</task_instruction>

## Evaluation criteria

Score the output on the following dimensions. Each dimension is 0–25 points. Follow the rubric EXACTLY — assign the score that matches the description, not higher.

<criteria>
{criteria}
</criteria>
{ground_truth_section}
## How to evaluate

1. Use `Glob` to discover all output files in the workspace.
2. Use `Read` to examine the content of each output file.
3. Use `Grep` to search for specific patterns or keywords.
4. For each dimension, find concrete evidence before assigning a score.

## Output format

After your analysis, output a single JSON block with your evaluation. The JSON MUST be the last code block in your response:

```json
{{
  "dimensions": [
    {{"name": "<dimension_snake_case>", "score": <0-25>, "max_score": 25, "reasoning": "<1-3 sentences with specific evidence references>"}},
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

Use the following ground truth to evaluate completeness and accuracy. The agent's output should capture these decisions — missing or incorrect decisions should lower the score.

<ground_truth>
{ground_truth}
</ground_truth>
"""


# ---------------------------------------------------------------------------
# Claude Code SDK interaction
# ---------------------------------------------------------------------------


async def _run_claude_code_evaluation(prompt: str, workspace_path: Path) -> str:
    _validate_auth()

    text_parts: list[str] = []
    async for message in query(
        prompt=prompt,
        options=ClaudeCodeOptions(
            allowed_tools=["Read", "Glob", "Grep"],
            cwd=str(workspace_path),
            max_turns=30,
            model="claude-sonnet-4-6",
            env={"CLAUDECODE": ""},
        ),
    ):
        if message is None:
            continue
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)

    return "\n".join(text_parts)


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
        console.print(
            f"  [yellow]WARN: Dimension mismatch — expected {expected_names}, "
            f"got {actual_names}[/yellow]"
        )


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
    client.log_traces_feedback_scores(scores, project_name=project_name)
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
            console.print(f"  Found Opik trace: {search_name} ({traces[0].id})")
            return traces[0].id
    except Exception as exc:
        console.print(f"  [yellow]WARN: Opik search timed out for '{search_name}': {exc}[/yellow]")

    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)
