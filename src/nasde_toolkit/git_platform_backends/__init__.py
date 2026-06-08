"""Pluggable git platform backends for nasde rubric calibration (ADR-010).

The backend is auto-detected from the sink repo URL host; an explicit
``platform_override`` resolves self-hosted or ambiguous hosts.
"""

from __future__ import annotations

from nasde_toolkit.git_platform_backends.detect import GITHUB, GITLAB, detect_platform
from nasde_toolkit.git_platform_backends.protocol import (
    GitPlatformBackend,
    PrRef,
    RepoRef,
    ReviewComment,
)

__all__ = [
    "GitPlatformBackend",
    "PrRef",
    "RepoRef",
    "ReviewComment",
    "create_git_backend",
    "detect_platform",
]


def create_git_backend(repo_url: str, platform_override: str = "") -> GitPlatformBackend:
    platform = detect_platform(repo_url, platform_override)
    if platform == GITHUB:
        from nasde_toolkit.git_platform_backends.github_cli import GitHubCliBackend

        return GitHubCliBackend()
    elif platform == GITLAB:
        from nasde_toolkit.git_platform_backends.gitlab_cli import GitLabCliBackend

        return GitLabCliBackend()
    else:
        raise ValueError(f"Unknown git platform: '{platform}'. Supported: 'github', 'gitlab'")
