from __future__ import annotations

import subprocess

import pytest

from nasde_toolkit.git_platform_backends import (
    GitPlatformBackend,
    create_git_backend,
)
from nasde_toolkit.git_platform_backends.detect import detect_platform
from nasde_toolkit.git_platform_backends.github_cli import GitHubCliBackend
from nasde_toolkit.git_platform_backends.gitlab_cli import GitLabCliBackend


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_detect_github_from_https_url() -> None:
    assert detect_platform("https://github.com/NoesisVision/nasde-calibration") == "github"


def test_detect_github_from_scp_url() -> None:
    assert detect_platform("git@github.com:NoesisVision/nasde-calibration.git") == "github"


def test_detect_gitlab_from_scp_url() -> None:
    assert detect_platform("git@gitlab.com:noesisvision/nasde-calibration.git") == "gitlab"


def test_detect_gitlab_from_self_hosted_host() -> None:
    assert detect_platform("https://gitlab.acme.internal/team/repo") == "gitlab"


def test_detect_override_wins_over_host() -> None:
    assert detect_platform("https://github.com/x/y", override="gitlab") == "gitlab"


def test_detect_unknown_host_without_override_raises() -> None:
    with pytest.raises(ValueError, match="Could not detect"):
        detect_platform("https://git.acme.internal/team/repo")


def test_detect_unknown_override_raises() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        detect_platform("https://github.com/x/y", override="bitbucket")


def test_create_backend_github() -> None:
    backend = create_git_backend("https://github.com/NoesisVision/nasde-calibration")
    assert isinstance(backend, GitHubCliBackend)
    assert isinstance(backend, GitPlatformBackend)


def test_create_backend_gitlab() -> None:
    backend = create_git_backend("git@gitlab.com:noesisvision/nasde-calibration.git")
    assert isinstance(backend, GitLabCliBackend)
    assert isinstance(backend, GitPlatformBackend)


def test_create_backend_unrecognized_raises() -> None:
    with pytest.raises(ValueError, match="Could not detect"):
        create_git_backend("https://git.acme.internal/team/repo")


def test_github_validate_cli_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("nasde_toolkit.git_platform_backends.github_cli.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        GitHubCliBackend().validate_cli_installed()
    out = capsys.readouterr().out.lower()
    assert "gh" in out
    assert "cli not found" in out
    assert "install" in out
    assert "cli.github.com" in out


def test_gitlab_validate_cli_fails_with_install_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("nasde_toolkit.git_platform_backends.gitlab_cli.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        GitLabCliBackend().validate_cli_installed()
    out = capsys.readouterr().out.lower()
    assert "glab" in out
    assert "cli not found" in out
    assert "gitlab-org/cli" in out


def test_github_validate_auth_fails_when_not_logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GitHubCliBackend, "_run", lambda self, args, check: _completed(returncode=1))
    with pytest.raises(SystemExit):
        GitHubCliBackend().validate_auth()


def test_github_repo_exists_parses_output_not_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        GitHubCliBackend,
        "_run",
        lambda self, args, check: _completed(stdout='{"name":""}', returncode=0),
    )
    assert GitHubCliBackend().repo_exists("owner/missing") is False


def test_github_repo_exists_true_when_name_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        GitHubCliBackend,
        "_run",
        lambda self, args, check: _completed(stdout='{"name":"nasde-calibration"}', returncode=0),
    )
    assert GitHubCliBackend().repo_exists("NoesisVision/nasde-calibration") is True


def test_github_find_open_pr_returns_none_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GitHubCliBackend, "_run", lambda self, args, check: _completed(stdout="[]"))
    assert GitHubCliBackend().find_open_pr_for_branch("o/r", "calib/x") is None


def test_github_find_open_pr_returns_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        GitHubCliBackend,
        "_run",
        lambda self, args, check: _completed(stdout='[{"number":7,"url":"https://github.com/o/r/pull/7"}]'),
    )
    pr = GitHubCliBackend().find_open_pr_for_branch("o/r", "calib/x")
    assert pr is not None
    assert pr.number == 7
    assert pr.url.endswith("/pull/7")


def test_github_fetch_comments_maps_issue_and_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    issue = '[{"body":"too strict","user":{"login":"sz"},"created_at":"2026-06-05T10:00:00Z"}]'
    inline = (
        '[{"body":"this line is fine","user":{"login":"sz"},"created_at":"2026-06-05T10:01:00Z",'
        '"path":"src/Movie.java","line":42,"diff_hunk":"@@ -1 +1 @@"}]'
    )

    def fake_run(self, args, check):
        if "issues" in args[-1]:
            return _completed(stdout=issue)
        return _completed(stdout=inline)

    monkeypatch.setattr(GitHubCliBackend, "_run", fake_run)
    comments = GitHubCliBackend().fetch_pr_comments("o/r", 7)
    assert len(comments) == 2
    assert comments[0].is_inline is False
    assert comments[0].body == "too strict"
    assert comments[1].is_inline is True
    assert comments[1].path == "src/Movie.java"
    assert comments[1].line == 42


def test_gitlab_fetch_comments_maps_notes_and_skips_system(monkeypatch: pytest.MonkeyPatch) -> None:
    notes = (
        '[{"body":"system note","system":true,"author":{"username":"sz"},"created_at":"t"},'
        '{"body":"human note","system":false,"author":{"username":"sz"},"created_at":"t"},'
        '{"body":"inline","system":false,"author":{"username":"sz"},"created_at":"t",'
        '"position":{"new_path":"a.py","new_line":3}}]'
    )
    monkeypatch.setattr(GitLabCliBackend, "_run", lambda self, args, check: _completed(stdout=notes))
    comments = GitLabCliBackend().fetch_pr_comments("group/repo", 1)
    assert len(comments) == 2
    assert comments[0].body == "human note"
    assert comments[0].is_inline is False
    assert comments[1].is_inline is True
    assert comments[1].path == "a.py"
    assert comments[1].line == 3
