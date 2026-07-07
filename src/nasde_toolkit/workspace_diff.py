"""Capture the agent's work from a trial workspace as a unified diff.

Workspace convention (shared with ``nasde calibrate publish``): HEAD is the
task's start state and the agent's work is uncommitted — tracked changes show
up in ``git diff HEAD``, brand-new files as untracked paths. The functions here
turn that state into reviewable artifacts: the full patch (consumed by the
results exporter, the calibration publisher and the evaluator's agent-diff
prompt input) and a compact diffstat.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def capture_patch(workspace: Path) -> str:
    """Full unified diff of the agent's work: tracked changes + untracked files."""
    if not (workspace / ".git").exists():
        console.print(f"  [yellow]no git workspace in {workspace.parent.parent.name}; empty patch[/yellow]")
        return ""
    tracked = _run_git(workspace, ["diff", "HEAD"])
    untracked = _capture_untracked(workspace)
    return tracked + untracked


def capture_diffstat(workspace: Path) -> str:
    """Compact change summary: ``git diff HEAD --stat`` plus untracked paths."""
    if not (workspace / ".git").exists():
        return ""
    stat = _run_git(workspace, ["diff", "HEAD", "--stat"]).rstrip()
    lines = [stat] if stat else []
    lines.extend(f" {path} (new file)" for path in _untracked_paths(workspace))
    return "\n".join(lines)


def _untracked_paths(workspace: Path) -> list[str]:
    listing = _run_git_bytes(workspace, ["ls-files", "--others", "--exclude-standard", "-z"])
    return [raw.decode("utf-8", "surrogateescape") for raw in listing.split(b"\x00") if raw]


def _capture_untracked(workspace: Path) -> str:
    return "".join(_diff_untracked_file(workspace, path) for path in _untracked_paths(workspace))


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
