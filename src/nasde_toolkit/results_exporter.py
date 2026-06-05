"""Export the essence of trial artifacts to a plain destination directory.

EXPERIMENTAL. Scans Harbor trial artifacts (not the best-effort EXPERIMENT_LOG.md)
and copies their analytic essence into a flat per-trial layout under a destination
directory the user controls (iCloud, Dropbox, a git repo, anywhere). The destination
is a plain filesystem path; this module never talks to a cloud provider.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from nasde_toolkit.evaluator import (
    _collect_trial_dirs,
    _compute_duration_sec,
    _load_json,
    _resolve_agent_name,
    _resolve_task_name,
)

console = Console()


@dataclass
class ExportSummary:
    """Outcome of an export run."""

    exported: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def export_results(paths: list[Path], dest: Path, include_trajectory: bool = True) -> ExportSummary:
    """Export trial artifacts from the given job and/or trial paths into dest."""
    dest.mkdir(parents=True, exist_ok=True)
    trials = _expand_to_trials(paths)
    summary = ExportSummary()
    for job_name, trial_dir in trials:
        _export_one_trial(job_name, trial_dir, dest, include_trajectory, summary)
    _print_summary(summary, dest)
    return summary


def _expand_to_trials(paths: list[Path]) -> list[tuple[str, Path]]:
    trials: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for path in paths:
        kind = _classify_path(path)
        if kind == "trial":
            _append_trial(trials, seen, path.parent.name, path)
        elif kind == "job":
            for trial_dir in _collect_trial_dirs(path):
                _append_trial(trials, seen, path.name, trial_dir)
        else:
            console.print(
                f"[yellow]SKIP: {path} is neither a job nor a trial directory "
                f"(no result.json here or in children).[/yellow]"
            )
    return trials


def _append_trial(
    trials: list[tuple[str, Path]],
    seen: set[Path],
    job_name: str,
    trial_dir: Path,
) -> None:
    if trial_dir in seen:
        return
    seen.add(trial_dir)
    trials.append((job_name, trial_dir))


def _classify_path(path: Path) -> str | None:
    if not path.is_dir():
        return None
    if _has_trial_children(path):
        return "job"
    if _is_trial_result(path):
        return "trial"
    if _collect_trial_dirs(path):
        console.print(
            f"[yellow]SKIP: {path} looks like a jobs/ root (its children are job dirs, not "
            f"trials) — pass specific jobs (e.g. jobs/*/) or a single job/trial dir.[/yellow]"
        )
    elif (path / "result.json").exists():
        console.print(
            f"[yellow]SKIP: {path} has a result.json but no trial_name and no trial-shaped "
            f"children — ambiguous, not exporting.[/yellow]"
        )
    return None


def _has_trial_children(path: Path) -> bool:
    return any(_is_trial_result(child) for child in _collect_trial_dirs(path))


def _is_trial_result(path: Path) -> bool:
    result_path = path / "result.json"
    if not result_path.exists():
        return False
    return bool(_load_json(result_path).get("trial_name"))


def _export_one_trial(
    job_name: str,
    trial_dir: Path,
    dest: Path,
    include_trajectory: bool,
    summary: ExportSummary,
) -> None:
    out_dir = dest / f"{job_name}__{trial_dir.name}"
    label = out_dir.name
    existed = out_dir.exists()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_metrics(trial_dir, out_dir)
        copied = _copy_assessment_files(trial_dir, out_dir)
        _copy_verifier_files(trial_dir, out_dir)
        if include_trajectory and not (out_dir / "trajectory.json").exists():
            _copy_trajectory(trial_dir, out_dir)
        if not (out_dir / "changes.patch").exists():
            _write_patch(trial_dir, out_dir)
    except Exception as error:
        if not existed:
            shutil.rmtree(out_dir, ignore_errors=True)
        console.print(f"  [red]FAIL: {label} — {error}[/red]")
        summary.failed.append(label)
        return
    if copied > 0 or not existed:
        console.print(f"  [green]exported: {label}[/green]")
        summary.exported.append(label)
    else:
        console.print(f"  [dim]skip (up to date): {label}[/dim]")
        summary.skipped.append(label)


def _write_metrics(trial_dir: Path, out_dir: Path) -> None:
    metrics = _build_metrics(trial_dir)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))


def _build_metrics(trial_dir: Path) -> dict:
    result = _load_json(trial_dir / "result.json")
    return {
        "trial_name": result.get("trial_name", trial_dir.name),
        "task_name": _resolve_task_name(result),
        "agent_name": _resolve_agent_name(trial_dir),
        "model_name": _resolve_model_name(trial_dir),
        "source": result.get("source", ""),
        "started_at": result.get("started_at", ""),
        "finished_at": result.get("finished_at", ""),
        "duration_sec": _compute_duration_sec(result),
        "harbor_reward": _resolve_harbor_reward(result),
        "exception_info": result.get("exception_info"),
    }


def _resolve_harbor_reward(result: dict) -> float:
    rewards = (result.get("verifier_result") or {}).get("rewards", {})
    reward: float = rewards.get("reward", 0.0)
    return reward


def _resolve_model_name(trial_dir: Path) -> str:
    config_path = trial_dir / "config.json"
    if not config_path.exists():
        return ""
    config = _load_json(config_path)
    model: str = config.get("agent", {}).get("model_name", "")
    return model


def _copy_assessment_files(trial_dir: Path, out_dir: Path) -> int:
    copied = 0
    numbered = sorted(trial_dir.glob("assessment_eval_*.json"))
    for assessment in numbered:
        dest_file = out_dir / assessment.name
        if not dest_file.exists():
            shutil.copy2(assessment, dest_file)
            copied += 1
    if not numbered:
        copied += _copy_legacy_bare_assessment(trial_dir, out_dir)
    summary_src = trial_dir / "assessment_summary.json"
    if summary_src.exists():
        shutil.copy2(summary_src, out_dir / "assessment_summary.json")
    return copied


def _copy_legacy_bare_assessment(trial_dir: Path, out_dir: Path) -> int:
    bare = trial_dir / "assessment_eval.json"
    dest_file = out_dir / "assessment_eval_1.json"
    if not bare.exists() or dest_file.exists():
        return 0
    shutil.copy2(bare, dest_file)
    console.print(
        f"  [yellow]legacy bare assessment_eval.json in {trial_dir.name} — exported as "
        f"assessment_eval_1.json; run `nasde migrate-evals` to normalize.[/yellow]"
    )
    return 1


def _copy_verifier_files(trial_dir: Path, out_dir: Path) -> None:
    verifier_dir = trial_dir / "verifier"
    stdout_path = verifier_dir / "test-stdout.txt"
    reward_path = verifier_dir / "reward.txt"
    if stdout_path.exists():
        shutil.copy2(stdout_path, out_dir / "verifier_stdout.txt")
    if reward_path.exists():
        shutil.copy2(reward_path, out_dir / "reward.txt")


def _copy_trajectory(trial_dir: Path, out_dir: Path) -> None:
    trajectory_path = trial_dir / "agent" / "trajectory.json"
    if trajectory_path.exists():
        shutil.copy2(trajectory_path, out_dir / "trajectory.json")


def _write_patch(trial_dir: Path, out_dir: Path) -> None:
    workspace = trial_dir / "artifacts" / "workspace"
    patch = _capture_patch(workspace)
    (out_dir / "changes.patch").write_text(patch)


def _capture_patch(workspace: Path) -> str:
    if not (workspace / ".git").exists():
        console.print(f"  [yellow]no git workspace in {workspace.parent.parent.name}; empty patch[/yellow]")
        return ""
    tracked = _run_git(workspace, ["diff", "HEAD"])
    untracked = _capture_untracked(workspace)
    return tracked + untracked


def _capture_untracked(workspace: Path) -> str:
    listing = _run_git_bytes(workspace, ["ls-files", "--others", "--exclude-standard", "-z"])
    chunks: list[str] = []
    for raw_path in listing.split(b"\x00"):
        if raw_path:
            relative_path = raw_path.decode("utf-8", "surrogateescape")
            chunks.append(_diff_untracked_file(workspace, relative_path))
    return "".join(chunks)


def _diff_untracked_file(workspace: Path, relative_path: str) -> str:
    return _run_git(
        workspace,
        ["diff", "--no-index", "--", "/dev/null", relative_path],
        accept_diff_exit=True,
    )


def _run_git(workspace: Path, args: list[str], accept_diff_exit: bool = False) -> str:
    completed = subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 and not (accept_diff_exit and completed.returncode == 1):
        raise RuntimeError(f"git {' '.join(args)} failed in {workspace}: {completed.stderr.strip()}")
    return completed.stdout


def _run_git_bytes(workspace: Path, args: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {workspace}: {stderr}")
    return completed.stdout


def _print_summary(summary: ExportSummary, dest: Path) -> None:
    from rich.table import Table

    table = Table(title=f"Results export → {dest}")
    table.add_column("Outcome", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[green]exported[/green]", str(len(summary.exported)))
    table.add_row("[dim]skipped[/dim]", str(len(summary.skipped)))
    table.add_row("[red]failed[/red]", str(len(summary.failed)))
    console.print(table)
