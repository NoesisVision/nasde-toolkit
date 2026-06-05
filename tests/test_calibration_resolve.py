from __future__ import annotations

import pytest

from nasde_toolkit.calibration_resolve import SystemExitMessage, resolve_sink


def test_resolve_github_https_url_uses_ssh_push() -> None:
    sink = resolve_sink("https://github.com/NoesisVision/nasde-calibration")
    assert sink.platform == "github"
    assert sink.slug == "NoesisVision/nasde-calibration"
    assert sink.push_url == "git@github.com:NoesisVision/nasde-calibration.git"


def test_resolve_self_hosted_host_preserved_in_push_url() -> None:
    sink = resolve_sink("https://gitlab.acme.internal/team/repo")
    assert sink.platform == "gitlab"
    assert sink.push_url == "git@gitlab.acme.internal:team/repo.git"


def test_resolve_gitlab_ssh_url() -> None:
    sink = resolve_sink("git@gitlab.com:noesisvision/nasde-calibration.git")
    assert sink.platform == "gitlab"
    assert sink.slug == "noesisvision/nasde-calibration"
    assert sink.push_url == "git@gitlab.com:noesisvision/nasde-calibration.git"


def test_resolve_bare_slug_requires_platform() -> None:
    with pytest.raises(SystemExitMessage, match="bare slug"):
        resolve_sink("NoesisVision/nasde-calibration")


def test_resolve_bare_slug_with_platform_builds_url() -> None:
    sink = resolve_sink("NoesisVision/nasde-calibration", platform_override="github")
    assert sink.platform == "github"
    assert sink.slug == "NoesisVision/nasde-calibration"
    assert sink.push_url == "git@github.com:NoesisVision/nasde-calibration.git"


def test_resolve_empty_repo_raises() -> None:
    with pytest.raises(SystemExitMessage, match="No calibration sink"):
        resolve_sink("")


def test_resolve_override_wins_over_detected_host() -> None:
    sink = resolve_sink("https://github.com/x/y", platform_override="gitlab")
    assert sink.platform == "gitlab"
