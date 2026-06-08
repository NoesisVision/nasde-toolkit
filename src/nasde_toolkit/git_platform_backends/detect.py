"""Platform auto-detection from a sink repository URL (ADR-010).

The platform (github/gitlab) is inferred from the repo URL host so there is no
separate config field to drift out of sync with the URL. An explicit override
resolves self-hosted or otherwise ambiguous hosts.
"""

from __future__ import annotations

GITHUB = "github"
GITLAB = "gitlab"
SUPPORTED_PLATFORMS = (GITHUB, GITLAB)


def detect_platform(repo_url: str, override: str = "") -> str:
    """Return ``"github"`` or ``"gitlab"`` for a sink repo URL/slug.

    An ``override`` (from ``[calibration] platform``) wins over host detection.
    Raises ``ValueError`` when the host is unrecognized and no override is given.
    """
    if override:
        return _validate_override(override)
    host = _extract_host(repo_url)
    labels = host.split(".")
    if any("gitlab" in label for label in labels):
        return GITLAB
    if any("github" in label for label in labels):
        return GITHUB
    raise ValueError(
        f"Could not detect a git platform from repo '{repo_url}'. "
        f"Set [calibration] platform to one of {SUPPORTED_PLATFORMS} in nasde.toml."
    )


def _validate_override(override: str) -> str:
    normalized = override.strip().lower()
    if normalized not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unknown [calibration] platform '{override}'. Supported: {SUPPORTED_PLATFORMS}.")
    return normalized


def _extract_host(repo_url: str) -> str:
    scp_like = _scp_like_host(repo_url)
    if scp_like:
        return scp_like
    stripped = _strip_scheme(repo_url)
    return stripped.split("/", 1)[0].lower()


def _scp_like_host(repo_url: str) -> str:
    if "://" in repo_url or "@" not in repo_url:
        return ""
    after_user = repo_url.split("@", 1)[1]
    return after_user.split(":", 1)[0].lower()


def _strip_scheme(repo_url: str) -> str:
    without_scheme = repo_url.split("://", 1)[-1]
    if "@" in without_scheme.split("/", 1)[0]:
        return without_scheme.split("@", 1)[1]
    return without_scheme
