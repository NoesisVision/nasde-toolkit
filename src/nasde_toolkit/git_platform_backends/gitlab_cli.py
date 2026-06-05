"""GitLab platform backend — shells out to the `glab` CLI (ADR-010).

Encapsulates GitLab's semantic differences from GitHub: Merge Requests (not
PRs), `--source/target-branch` (not `--head/base`), `--description` (not
`--body`), and `notes` (not separate issue/inline comment endpoints). All are
normalized to the shared `ReviewComment` model so the calibration layer stays
platform-unaware.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

from rich.console import Console

from nasde_toolkit.git_platform_backends.protocol import PrRef, ReviewComment

console = Console()


class GitLabCliBackend:
    """Git platform backend driving GitLab via the `glab` CLI."""

    def repo_exists(self, repo: str) -> bool:
        result = self._run(["repo", "view", repo, "--output", "json"], check=False)
        if result.returncode != 0:
            return False
        return bool(_parse_json(result.stdout).get("id"))

    def find_open_pr_for_branch(self, repo: str, head_branch: str) -> PrRef | None:
        result = self._run(
            ["mr", "list", "--repo", repo, "--source-branch", head_branch, "--output", "json"],
            check=True,
        )
        entries = _parse_json_list(result.stdout)
        if not entries:
            return None
        first = entries[0]
        return PrRef(number=int(first["iid"]), url=first["web_url"])

    def create_pr(self, repo: str, head: str, base: str, title: str, body_markdown: str) -> PrRef:
        result = self._run_in_repo_context(
            repo,
            ["mr", "create", "--repo", repo, "--source-branch", head, "--target-branch", base,
             "--title", title, "--description", body_markdown, "--yes"],
        )
        url = _last_url(result.stdout)
        return PrRef(number=_mr_iid_from_url(url), url=url)

    def fetch_pr_comments(self, repo: str, pr_number: int) -> list[ReviewComment]:
        project = quote(repo, safe="")
        result = self._run(
            ["api", "--paginate", f"projects/{project}/merge_requests/{pr_number}/notes"],
            check=True,
        )
        return [_note_comment(raw) for raw in _parse_json_list(result.stdout) if not raw.get("system")]

    def validate_cli_installed(self) -> None:
        if shutil.which("glab") is not None:
            return
        console.print(
            "[red]ERROR: `glab` CLI not found on PATH.[/red]\n"
            "[yellow]Publishing calibration MRs to GitLab requires the GitLab CLI.[/yellow]\n"
            "Install it from https://gitlab.com/gitlab-org/cli, then run `glab auth login`. "
            "For a GitHub sink, set \\[calibration] platform = \"github\" in nasde.toml (requires `gh`)."
        )
        raise SystemExit(1)

    def validate_auth(self) -> None:
        result = self._run(["auth", "status"], check=False)
        if result.returncode == 0:
            return
        console.print(
            "[red]ERROR: not authenticated with GitLab.[/red]\n"
            "[yellow]Run `glab auth login`.[/yellow]"
        )
        raise SystemExit(1)

    def _run(self, args: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(["glab", *args], capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise RuntimeError(f"glab {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def _run_in_repo_context(self, repo: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        context_dir = Path(tempfile.mkdtemp(prefix="nasde_glab_ctx_"))
        try:
            self._init_origin_context(context_dir, repo)
            result = subprocess.run(
                ["glab", *args], cwd=str(context_dir), capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"glab {' '.join(args)} failed: {result.stderr.strip()}")
            return result
        finally:
            shutil.rmtree(context_dir, ignore_errors=True)

    def _init_origin_context(self, context_dir: Path, repo: str) -> None:
        subprocess.run(["git", "-C", str(context_dir), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(context_dir), "remote", "add", "origin", f"git@gitlab.com:{repo}.git"],
            check=True,
        )


def _note_comment(raw: dict) -> ReviewComment:
    position = raw.get("position") or {}
    is_inline = bool(position)
    return ReviewComment(
        body=raw.get("body", ""),
        author=(raw.get("author") or {}).get("username", ""),
        created_at=raw.get("created_at", ""),
        is_inline=is_inline,
        path=position.get("new_path"),
        line=position.get("new_line"),
        diff_hunk=None,
    )


def _last_url(text: str) -> str:
    for token in reversed(text.split()):
        if token.startswith("http"):
            return token.strip()
    return text.strip().splitlines()[-1].strip() if text.strip() else ""


def _mr_iid_from_url(url: str) -> int:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _parse_json(text: str) -> dict:
    text = text.strip()
    if not text:
        return {}
    return json.loads(text)


def _parse_json_list(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    return json.loads(text)
