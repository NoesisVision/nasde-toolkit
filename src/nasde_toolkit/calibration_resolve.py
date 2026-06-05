"""Resolve the calibration sink repo into (api slug, push url, platform).

The user may configure ``[calibration] repo`` as a full URL
(``git@gitlab.com:group/repo.git`` / ``https://github.com/owner/repo``) — from
which the platform is auto-detected — or as a bare ``owner/repo`` slug, in which
case ``[calibration] platform`` is required to know the host. See ADR-010.
"""

from __future__ import annotations

from dataclasses import dataclass

from nasde_toolkit.git_platform_backends.detect import GITHUB, GITLAB, detect_platform

_HOSTS = {GITHUB: "github.com", GITLAB: "gitlab.com"}


@dataclass
class ResolvedSink:
    """A calibration sink resolved into everything the publisher needs."""

    slug: str
    push_url: str
    platform: str


def resolve_sink(repo: str, platform_override: str = "") -> ResolvedSink:
    """Resolve a configured repo string into slug + push URL + platform."""
    if not repo:
        raise SystemExitMessage(
            "No calibration sink repo configured. Pass --repo or set [calibration] repo in nasde.toml."
        )
    if _looks_like_url(repo):
        return _resolve_from_url(repo, platform_override)
    return _resolve_from_slug(repo, platform_override)


class SystemExitMessage(SystemExit):
    """A SystemExit carrying a user-facing message (the CLI renders it)."""


def _resolve_from_url(repo: str, platform_override: str) -> ResolvedSink:
    platform = detect_platform(repo, platform_override)
    slug = _slug_from_url(repo)
    return ResolvedSink(slug=slug, push_url=_normalize_push_url(repo), platform=platform)


def _resolve_from_slug(repo: str, platform_override: str) -> ResolvedSink:
    if not platform_override:
        raise SystemExitMessage(
            f"Repo '{repo}' is a bare slug with no host. Set [calibration] platform "
            f"(\"github\" or \"gitlab\") in nasde.toml so the platform can be resolved."
        )
    platform = detect_platform("", platform_override)
    host = _HOSTS[platform]
    return ResolvedSink(slug=repo, push_url=f"git@{host}:{repo}.git", platform=platform)


def _looks_like_url(repo: str) -> bool:
    return "://" in repo or "@" in repo


def _slug_from_url(repo: str) -> str:
    cleaned = repo.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    if "@" in cleaned and "://" not in cleaned:
        return cleaned.split(":", 1)[-1].strip("/")
    without_scheme = cleaned.split("://", 1)[-1]
    return without_scheme.split("/", 1)[-1].strip("/")


def _normalize_push_url(repo: str) -> str:
    cleaned = repo.strip()
    if not cleaned.endswith(".git"):
        cleaned = f"{cleaned}.git"
    return cleaned
