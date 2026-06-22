"""Publish trial diffs + assessments as PRs/MRs for rubric calibration (ADR-010).

For each trial: ensure a per-(repo,sha) orphan base branch holding the agent's
start-state codebase, push a feature branch with the agent's diff applied as a
real commit (so the PR diff is exactly the agent's work) plus the assessment
artifacts under .calibration/, and open a Pull/Merge Request whose description
renders the per-dimension judge scores. Idempotent (re-runs skip existing PRs)
and throttled (sequential, sleeps between content-creating calls).

The GIT layer (push) and the PLATFORM layer (PR/comments) are separated: see
git_ops.py and git_platform_backends/. This module never shells out to gh/glab
directly — it drives a GitPlatformBackend chosen by URL auto-detection.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

from nasde_toolkit.evaluator import (
    AssessmentSummary,
    EvaluatorGroupSummary,
    _aggregate_evaluations,
    _load_json,
    _load_raw_evaluations,
)
from nasde_toolkit.git_platform_backends import create_git_backend
from nasde_toolkit.git_platform_backends.git_ops import (
    ensure_base_branch,
    push_feature_branch,
)
from nasde_toolkit.git_platform_backends.protocol import GitPlatformBackend, PrRef, ReviewComment
from nasde_toolkit.pricing import load_pricing_layered
from nasde_toolkit.results_exporter import (
    _build_metrics,
    _capture_patch,
    _expand_to_trials,
)

console = Console()


@dataclass
class PublishedTrial:
    """Outcome of publishing one trial as a PR/MR."""

    label: str
    base_branch: str
    feature_branch: str
    pr_number: int
    pr_url: str
    created: bool


@dataclass
class PublishSummary:
    """Outcome of a publish run."""

    published: list[PublishedTrial] = field(default_factory=list)
    skipped: list[PublishedTrial] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class TrialComments:
    """Comments pulled from one trial's PR/MR, for the calibration orchestrator."""

    label: str
    pr_number: int
    pr_url: str
    comments: list[ReviewComment] = field(default_factory=list)


def publish_trials(
    paths: list[Path],
    repo: str,
    repo_url: str,
    base_branch: str = "main",
    platform_override: str = "",
    throttle_sec: float = 2.0,
    project_root: Path | None = None,
) -> PublishSummary:
    """Publish the given job/trial paths as PRs/MRs on the sink repo."""
    backend = _preflight(repo, repo_url, platform_override)
    trials = _expand_to_trials(paths)
    summary = PublishSummary()
    for index, (_, trial_dir) in enumerate(trials):
        if index > 0:
            time.sleep(throttle_sec)
        _publish_one_trial(trial_dir, backend, repo, repo_url, base_branch, project_root, summary)
    _print_publish_summary(summary, repo)
    return summary


def pull_trial_comments(
    paths: list[Path],
    repo: str,
    repo_url: str,
    platform_override: str = "",
) -> list[TrialComments]:
    """Pull PR/MR comments for the given trials into a platform-neutral structure."""
    backend = create_git_backend(repo_url, platform_override)
    backend.validate_cli_installed()
    backend.validate_auth()
    trials = _expand_to_trials(paths)
    collected: list[TrialComments] = []
    for _, trial_dir in trials:
        comments = _pull_one_trial_comments(trial_dir, backend, repo)
        if comments is not None:
            collected.append(comments)
    return collected


def _preflight(repo: str, repo_url: str, platform_override: str) -> GitPlatformBackend:
    backend = create_git_backend(repo_url, platform_override)
    backend.validate_cli_installed()
    backend.validate_auth()
    if not backend.repo_exists(repo):
        console.print(
            f"[red]ERROR: sink repo '{repo}' does not exist or is not accessible.[/red]\n"
            "[yellow]Create it manually (repo creation is out of scope) or fix [calibration] repo "
            "in nasde.toml.[/yellow]"
        )
        raise SystemExit(1)
    return backend


def _publish_one_trial(
    trial_dir: Path,
    backend: GitPlatformBackend,
    repo: str,
    repo_url: str,
    base_branch: str,
    project_root: Path | None,
    summary: PublishSummary,
) -> None:
    label = trial_dir.name
    try:
        repo_slug, short_sha = _base_key(trial_dir)
        base = _base_branch_name(repo_slug, short_sha)
        feature = _feature_branch_name(repo_slug, short_sha, trial_dir.name)
        existing = backend.find_open_pr_for_branch(repo, feature)
        if existing is not None:
            _record_skip(summary, label, base, feature, existing)
            return
        created = _open_pr_for_trial(trial_dir, backend, repo, repo_url, base, feature, project_root)
        summary.published.append(PublishedTrial(label, base, feature, created.number, created.url, created=True))
        console.print(f"  [green]published: {label} → {created.url}[/green]")
    except Exception as error:
        console.print(f"  [red]FAIL: {label} — {error}[/red]")
        summary.failed.append(label)


def _open_pr_for_trial(
    trial_dir: Path,
    backend: GitPlatformBackend,
    repo: str,
    repo_url: str,
    base: str,
    feature: str,
    project_root: Path | None,
) -> PrRef:
    workspace = trial_dir / "artifacts" / "workspace"
    metrics = _build_metrics(trial_dir, load_pricing_layered(project_root))
    summary = _summarize_trial(trial_dir)
    title = _pr_title(trial_dir, summary)
    body = _render_pr_body(summary, metrics)
    ensure_base_branch(repo_url, base, workspace)
    patch_text = _capture_patch(workspace)
    files = _calibration_files(trial_dir, metrics, project_root)
    push_feature_branch(repo_url, base, feature, workspace, patch_text, files)
    return backend.create_pr(repo, head=feature, base=base, title=title, body_markdown=body)


def _summarize_trial(trial_dir: Path) -> AssessmentSummary:
    evaluations = _load_raw_evaluations(trial_dir)
    if not evaluations:
        return AssessmentSummary(
            task_name=trial_dir.name,
            trial_name=trial_dir.name,
            agent_name="",
            groups=[],
        )
    return _aggregate_evaluations(evaluations)


def _pull_one_trial_comments(
    trial_dir: Path,
    backend: GitPlatformBackend,
    repo: str,
) -> TrialComments | None:
    repo_slug, short_sha = _base_key(trial_dir)
    feature = _feature_branch_name(repo_slug, short_sha, trial_dir.name)
    pr = backend.find_open_pr_for_branch(repo, feature)
    if pr is None:
        console.print(f"  [yellow]no PR for {trial_dir.name} (branch {feature}); skipping.[/yellow]")
        return None
    comments = backend.fetch_pr_comments(repo, pr.number)
    return TrialComments(label=trial_dir.name, pr_number=pr.number, pr_url=pr.url, comments=comments)


def _calibration_files(trial_dir: Path, metrics: dict, project_root: Path | None) -> dict[str, str]:
    files: dict[str, str] = {}
    _add_task_context_files(files, trial_dir, project_root)
    for assessment in sorted(trial_dir.glob("assessment_eval_*.json")):
        files[assessment.name] = assessment.read_text(encoding="utf-8")
    summary_path = trial_dir / "assessment_summary.json"
    if summary_path.exists():
        files["assessment_summary.json"] = summary_path.read_text(encoding="utf-8")
    files["metrics.json"] = json.dumps(metrics, indent=2)
    return files


def _add_task_context_files(files: dict[str, str], trial_dir: Path, project_root: Path | None) -> None:
    task_dir = _resolve_task_dir(trial_dir, project_root)
    if task_dir is None:
        return
    for name in ("instruction.md", "assessment_criteria.md"):
        source = task_dir / name
        if source.exists():
            files[name] = source.read_text(encoding="utf-8")
    dimensions = task_dir.parent.parent / "assessment_dimensions.json"
    if dimensions.exists():
        files["assessment_dimensions.json"] = dimensions.read_text(encoding="utf-8")


def _resolve_task_dir(trial_dir: Path, project_root: Path | None) -> Path | None:
    if project_root is None:
        return None
    result = _load_json(trial_dir / "result.json")
    task_name = str(result.get("task_name", ""))
    source = str(result.get("source", ""))
    if not task_name:
        return None
    candidates = [
        project_root / "tasks" / task_name,
        project_root / "evals" / source / "tasks" / task_name,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _base_key(trial_dir: Path) -> tuple[str, str]:
    workspace = trial_dir / "artifacts" / "workspace"
    origin = _workspace_origin(workspace)
    short_sha = _workspace_short_sha(workspace)
    return _slug_from_origin(origin), short_sha


def _workspace_origin(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _workspace_short_sha(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    if not sha:
        raise RuntimeError(f"Could not read HEAD sha from workspace {workspace}")
    return sha


def _slug_from_origin(origin: str) -> str:
    cleaned = origin.strip()
    if not cleaned:
        raise RuntimeError(
            "Trial workspace has no git origin remote — cannot derive a base-branch key. "
            "The workspace .git must point at the source repo."
        )
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    if "@" in cleaned and "://" not in cleaned:
        cleaned = cleaned.split(":", 1)[-1]
    else:
        cleaned = cleaned.split("://", 1)[-1]
        cleaned = cleaned.split("/", 1)[-1] if "/" in cleaned else cleaned
    slug = cleaned.strip("/").replace("/", "-")
    if not slug:
        raise RuntimeError(f"Could not derive a repo slug from origin '{origin}'.")
    return slug


def _base_branch_name(repo_slug: str, short_sha: str) -> str:
    return f"base/{repo_slug}-{short_sha}"


def _feature_branch_name(repo_slug: str, short_sha: str, trial_name: str) -> str:
    return f"calib/{repo_slug}-{short_sha}/{trial_name}"


def _pr_title(trial_dir: Path, summary: AssessmentSummary) -> str:
    dominant = _dominant_group(summary)
    score = f"{dominant.normalized_score_mean:.2f}" if dominant else "n/a"
    return f"[{summary.task_name}] {summary.agent_name} — score {score} ({trial_dir.name})"


def _render_pr_body(summary: AssessmentSummary, metrics: dict) -> str:
    dominant = _dominant_group(summary)
    lines = [
        f"## Assessment — {summary.task_name}",
        "",
        f"- **Agent:** {summary.agent_name}",
        f"- **Model:** {metrics.get('model_name', '') or 'n/a'}",
        f"- **Trial:** {summary.trial_name}",
        f"- **Harbor reward:** {metrics.get('harbor_reward', 0.0)}",
        "",
    ]
    if dominant is None:
        lines.append("_No assessment evaluations found for this trial._")
        return "\n".join(lines)
    lines.extend(_dimension_table(dominant))
    lines.append("")
    lines.append(
        f"**Normalized score:** {dominant.normalized_score_mean:.4f} "
        f"± {dominant.normalized_score_std:.4f} (n={dominant.n}, {dominant.evaluator_model})"
    )
    lines.extend(_reasoning_section(summary))
    lines.extend(_how_to_calibrate())
    return "\n".join(lines)


def _dimension_table(group: EvaluatorGroupSummary) -> list[str]:
    rows = [
        "| Dimension | Mean ± Std | Max | n |",
        "|-----------|-----------|-----|---|",
    ]
    for dim in group.dimensions:
        rows.append(f"| {dim.name} | {dim.mean:.2f} ± {dim.std:.2f} | {dim.max_score} | {group.n} |")
    return rows


def _reasoning_section(summary: AssessmentSummary) -> list[str]:
    return [
        "",
        "<details><summary>Judge reasoning (raw)</summary>",
        "",
        "See `.calibration/assessment_eval_*.json` on this branch for the full "
        "per-dimension reasoning behind each score.",
        "",
        "</details>",
    ]


def _how_to_calibrate() -> list[str]:
    return [
        "",
        "---",
        "",
        "### How to calibrate",
        "",
        "Review the diff. Where a dimension's score disagrees with how *you* would "
        "judge this code, **comment inline on the relevant line** — e.g. "
        '_"this score should be higher: the model is not anemic here because…"_. '
        "Those comments are pulled back into rubric tuning by "
        "`nasde calibrate pull-comments`.",
    ]


def _dominant_group(summary: AssessmentSummary) -> EvaluatorGroupSummary | None:
    for group in summary.groups:
        if group.dominant:
            return group
    return summary.groups[0] if summary.groups else None


def _record_skip(
    summary: PublishSummary,
    label: str,
    base: str,
    feature: str,
    existing: PrRef,
) -> None:
    summary.skipped.append(PublishedTrial(label, base, feature, existing.number, existing.url, created=False))
    console.print(f"  [dim]skip (PR exists): {label} → {existing.url}[/dim]")


def _print_publish_summary(summary: PublishSummary, repo: str) -> None:
    table = Table(title=f"Calibration publish → {repo}")
    table.add_column("Outcome", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[green]published[/green]", str(len(summary.published)))
    table.add_row("[dim]skipped[/dim]", str(len(summary.skipped)))
    table.add_row("[red]failed[/red]", str(len(summary.failed)))
    console.print(table)
