"""GitHub platform backend — shells out to the `gh` CLI (ADR-010)."""

from __future__ import annotations

import json
import shutil
import subprocess

from rich.console import Console

from nasde_toolkit.git_platform_backends.protocol import PrRef, ReviewComment

console = Console()


class GitHubCliBackend:
    """Git platform backend driving GitHub via the `gh` CLI.

    `gh` holds the user's auth in its keyring and handles pagination/retry/
    rate-limit backoff. Note: `gh repo view` exits 0 even for a missing repo, so
    existence is determined by parsing output, not the exit code.
    """

    def repo_exists(self, repo: str) -> bool:
        result = self._run(["repo", "view", repo, "--json", "name"], check=False)
        if result.returncode != 0:
            return False
        return bool(_parse_json(result.stdout).get("name"))

    def find_open_pr_for_branch(self, repo: str, head_branch: str) -> PrRef | None:
        result = self._run(
            ["pr", "list", "--repo", repo, "--head", head_branch, "--state", "all", "--json", "number,url"],
            check=True,
        )
        entries = _parse_json_list(result.stdout)
        if not entries:
            return None
        first = entries[0]
        return PrRef(number=int(first["number"]), url=first["url"])

    def create_pr(self, repo: str, head: str, base: str, title: str, body_markdown: str) -> PrRef:
        result = self._run(
            ["pr", "create", "--repo", repo, "--head", head, "--base", base,
             "--title", title, "--body", body_markdown],
            check=True,
        )
        url = _last_url(result.stdout)
        number = _pr_number_from_url(url)
        if not url or number == 0:
            raise RuntimeError(f"gh pr create succeeded but no PR URL was parsed from output: {result.stdout!r}")
        return PrRef(number=number, url=url)

    def fetch_pr_comments(self, repo: str, pr_number: int) -> list[ReviewComment]:
        issue_level = self._fetch_issue_comments(repo, pr_number)
        inline = self._fetch_inline_comments(repo, pr_number)
        return issue_level + inline

    def validate_cli_installed(self) -> None:
        if shutil.which("gh") is not None:
            return
        console.print(
            "[red]ERROR: `gh` CLI not found on PATH.[/red]\n"
            "[yellow]Publishing calibration PRs to GitHub requires the GitHub CLI.[/yellow]\n"
            "Install it from https://cli.github.com, then run `gh auth login`. "
            "For a GitLab sink, set \\[calibration] platform = \"gitlab\" in nasde.toml (requires `glab`)."
        )
        raise SystemExit(1)

    def validate_auth(self) -> None:
        result = self._run(["auth", "status"], check=False)
        if result.returncode == 0:
            return
        console.print(
            "[red]ERROR: not authenticated with GitHub.[/red]\n"
            "[yellow]Run `gh auth login` (scope `repo` is enough for private PR review).[/yellow]"
        )
        raise SystemExit(1)

    def _fetch_issue_comments(self, repo: str, pr_number: int) -> list[ReviewComment]:
        result = self._run(
            ["api", "--paginate", "--slurp", f"repos/{repo}/issues/{pr_number}/comments"],
            check=True,
        )
        return [_issue_comment(raw) for raw in _flatten_slurped(result.stdout)]

    def _fetch_inline_comments(self, repo: str, pr_number: int) -> list[ReviewComment]:
        result = self._run(
            ["api", "--paginate", "--slurp", f"repos/{repo}/pulls/{pr_number}/comments"],
            check=True,
        )
        return [_inline_comment(raw) for raw in _flatten_slurped(result.stdout)]

    def _run(self, args: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
        return result


def _issue_comment(raw: dict) -> ReviewComment:
    return ReviewComment(
        body=raw.get("body", ""),
        author=(raw.get("user") or {}).get("login", ""),
        created_at=raw.get("created_at", ""),
        is_inline=False,
    )


def _inline_comment(raw: dict) -> ReviewComment:
    return ReviewComment(
        body=raw.get("body", ""),
        author=(raw.get("user") or {}).get("login", ""),
        created_at=raw.get("created_at", ""),
        is_inline=True,
        path=raw.get("path"),
        line=raw.get("line"),
        diff_hunk=raw.get("diff_hunk"),
    )


def _pr_number_from_url(url: str) -> int:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _last_url(text: str) -> str:
    for token in reversed(text.split()):
        if token.startswith("http"):
            return token.strip()
    return ""


def _flatten_slurped(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    pages = json.loads(text)
    flattened: list[dict] = []
    for page in pages:
        flattened.extend(page)
    return flattened


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
