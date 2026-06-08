"""Git platform backend protocol — the interface for PR/MR review platforms.

Separates PLATFORM operations (repo existence, PR creation, comment fetching —
done via the platform's CLI, varying per platform) from GIT operations (branch
pushing — done via the git binary, identical everywhere). See ADR-010.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RepoRef:
    """A resolved sink repository on a git platform."""

    slug: str
    url: str


@dataclass
class PrRef:
    """A Pull Request (GitHub) or Merge Request (GitLab)."""

    number: int
    url: str


@dataclass
class ReviewComment:
    """A single human comment on a PR/MR, normalized across platforms.

    Inline comments carry ``path``/``line``/``diff_hunk`` (anchored to a line of
    the diff); issue-level comments leave those ``None`` and set ``is_inline``
    to ``False``.
    """

    body: str
    author: str
    created_at: str
    is_inline: bool
    path: str | None = None
    line: int | None = None
    diff_hunk: str | None = None


@runtime_checkable
class GitPlatformBackend(Protocol):
    """Interface for CLI-based git platform backends (GitHub `gh`, GitLab `glab`).

    Each backend shells out to the platform's CLI, which holds the user's auth
    in its own keyring and handles pagination/retry/rate-limit backoff. The
    backend never handles tokens itself. Repository creation is intentionally
    absent — the sink repo must already exist (pushing a branch to it creates
    refs ad-hoc).
    """

    def repo_exists(self, repo: str) -> bool: ...

    def find_open_pr_for_branch(self, repo: str, head_branch: str) -> PrRef | None: ...

    def create_pr(self, repo: str, head: str, base: str, title: str, body_markdown: str) -> PrRef: ...

    def fetch_pr_comments(self, repo: str, pr_number: int) -> list[ReviewComment]: ...

    def validate_cli_installed(self) -> None: ...

    def validate_auth(self) -> None: ...
