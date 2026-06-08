"""GIT layer for calibration publishing — platform-agnostic (ADR-010).

Transports branches via the `git` binary over ssh/https. Identical for every
platform and not subject to platform API rate limits. Builds the per-(repo,sha)
orphan base branch (a clean snapshot of the agent's start state) and the
per-trial feature branch (start state + the agent's changes applied as a real
commit, so the PR diff shows exactly the agent's work).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()


def remote_branch_exists(repo_url: str, branch: str) -> bool:
    """Whether ``branch`` already exists on the remote (cheap, no platform API)."""
    output = _run_git(Path.cwd(), ["ls-remote", "--heads", repo_url, branch])
    return bool(output.strip())


def ensure_base_branch(repo_url: str, base_branch: str, workspace: Path) -> None:
    """Push an orphan branch holding the agent's start-state snapshot, once.

    The snapshot is ``git archive HEAD`` from the trial workspace — tracked
    files in the pre-agent state. Orphan = no false history relationship between
    different start points; git still deduplicates shared blobs by content.
    """
    if remote_branch_exists(repo_url, base_branch):
        return
    work_dir = Path(tempfile.mkdtemp(prefix="nasde_calib_base_"))
    try:
        _init_seed_repo(work_dir, repo_url)
        _checkout_orphan(work_dir, base_branch)
        _extract_workspace_snapshot(workspace, work_dir)
        _commit_all(work_dir, f"base: start-state snapshot for {base_branch}")
        _push_branch(work_dir, "origin", base_branch)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def push_feature_branch(
    repo_url: str,
    base_branch: str,
    feature_branch: str,
    workspace: Path,
    patch_text: str,
    calibration_files: dict[str, str],
) -> None:
    """Build and push a feature branch = base + agent changes + assessment files.

    The agent's diff (``patch_text``) is applied as a real commit on top of the
    base snapshot, and the assessment artifacts are committed separately under
    ``.calibration/`` so the code diff stays uncluttered.
    """
    work_dir = Path(tempfile.mkdtemp(prefix="nasde_calib_feat_"))
    try:
        _init_seed_repo(work_dir, repo_url)
        _fetch_and_checkout(work_dir, base_branch, feature_branch)
        _apply_agent_patch(work_dir, patch_text)
        _commit_all(work_dir, "agent changes")
        _write_calibration_files(work_dir, calibration_files)
        _commit_all(work_dir, "assessment: calibration artifacts")
        _push_branch(work_dir, "origin", feature_branch)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _init_seed_repo(work_dir: Path, repo_url: str) -> None:
    _run_git(work_dir, ["init", "-q"])
    _run_git(work_dir, ["remote", "add", "origin", repo_url])
    _run_git(work_dir, ["config", "user.email", "calibration@nasde.local"])
    _run_git(work_dir, ["config", "user.name", "nasde calibration"])


def _checkout_orphan(work_dir: Path, branch: str) -> None:
    _run_git(work_dir, ["checkout", "-q", "--orphan", branch])


def _fetch_and_checkout(work_dir: Path, base_branch: str, feature_branch: str) -> None:
    _run_git(work_dir, ["fetch", "-q", "--depth", "1", "origin", base_branch])
    _run_git(work_dir, ["checkout", "-q", "-b", feature_branch, "FETCH_HEAD"])


def _extract_workspace_snapshot(workspace: Path, work_dir: Path) -> None:
    archive = subprocess.run(
        ["git", "-C", str(workspace), "archive", "HEAD"],
        capture_output=True,
        check=False,
    )
    if archive.returncode != 0:
        stderr = archive.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git archive HEAD failed in {workspace}: {stderr}")
    extract = subprocess.run(
        ["tar", "-x", "-C", str(work_dir)],
        input=archive.stdout,
        capture_output=True,
        check=False,
    )
    if extract.returncode != 0:
        stderr = extract.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Extracting start-state snapshot failed: {stderr}")


def _apply_agent_patch(work_dir: Path, patch_text: str) -> None:
    if not patch_text.strip():
        return
    patch_file = work_dir / ".nasde_agent.patch"
    patch_file.write_text(patch_text)
    result = subprocess.run(
        ["git", "-C", str(work_dir), "apply", "--whitespace=nowarn", str(patch_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    patch_file.unlink()
    if result.returncode != 0:
        raise RuntimeError(
            f"git apply of the agent diff failed: {result.stderr.strip()}. "
            "The patch may not align with the base snapshot."
        )


def _write_calibration_files(work_dir: Path, calibration_files: dict[str, str]) -> None:
    calib_dir = work_dir / ".calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)
    for name, content in calibration_files.items():
        (calib_dir / name).write_text(content)


def _commit_all(work_dir: Path, message: str) -> None:
    _run_git(work_dir, ["add", "-A"])
    status = _run_git(work_dir, ["status", "--porcelain"])
    if not status.strip():
        return
    _run_git(work_dir, ["commit", "-q", "-m", message])


def _push_branch(work_dir: Path, remote: str, branch: str) -> None:
    _run_git(work_dir, ["push", "-q", remote, f"HEAD:refs/heads/{branch}"])


def _run_git(work_dir: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(work_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {work_dir}: {result.stderr.strip()}")
    return result.stdout
