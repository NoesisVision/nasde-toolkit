"""Tests for the PyPI update notifier."""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from packaging.version import Version
from rich.console import Console

from nasde_toolkit import update_check


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NASDE_NO_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("NASDE_FORCE_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "update-check.json")
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)


def _make_console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=200)


def _stub_response(version: str) -> bytes:
    return json.dumps({"info": {"version": version}}).encode("utf-8")


class _FakeUrlopen:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeUrlopen:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_skips_when_no_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    with patch("urllib.request.urlopen") as mock_urlopen:
        update_check.maybe_notify_update(_make_console(), current_version="0.3.0")
    mock_urlopen.assert_not_called()


def test_skips_when_no_update_check_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NASDE_NO_UPDATE_CHECK", "1")
    with patch("urllib.request.urlopen") as mock_urlopen:
        update_check.maybe_notify_update(_make_console(), current_version="0.3.0")
    mock_urlopen.assert_not_called()


def test_skips_when_ci_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    with patch("urllib.request.urlopen") as mock_urlopen:
        update_check.maybe_notify_update(_make_console(), current_version="0.3.0")
    mock_urlopen.assert_not_called()


def test_skips_dev_version() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        update_check.maybe_notify_update(
            _make_console(),
            current_version="0.2.2.dev9+gf024b8e7",
        )
    mock_urlopen.assert_not_called()


def test_force_check_overrides_dev_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NASDE_FORCE_UPDATE_CHECK", "1")
    with patch("urllib.request.urlopen", return_value=_FakeUrlopen(_stub_response("0.5.0"))) as mock_urlopen:
        update_check.maybe_notify_update(
            _make_console(),
            current_version="0.2.2.dev9+gf024b8e7",
        )
    mock_urlopen.assert_called_once()


def test_cache_hit_no_newer(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "latest_version": "0.3.0",
            }
        )
    )
    console = _make_console()
    with patch("urllib.request.urlopen") as mock_urlopen:
        update_check.maybe_notify_update(console, current_version="0.3.0")
    mock_urlopen.assert_not_called()
    assert console.file.getvalue() == ""  # type: ignore[union-attr]


def test_cache_hit_newer_known_skips_fetch_but_prints(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "latest_version": "0.4.0",
            }
        )
    )
    console = _make_console()
    with patch("urllib.request.urlopen") as mock_urlopen, patch.object(update_check, "_print_notice") as mock_print:
        update_check.maybe_notify_update(console, current_version="0.3.0")
    mock_urlopen.assert_not_called()
    mock_print.assert_called_once()


def test_cache_miss_fetches_and_writes(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    assert not cache_path.exists()
    with patch("urllib.request.urlopen", return_value=_FakeUrlopen(_stub_response("0.4.0"))):
        update_check.maybe_notify_update(_make_console(), current_version="0.3.0")
    assert cache_path.exists()
    written = json.loads(cache_path.read_text())
    assert written["latest_version"] == "0.4.0"
    assert "checked_at" in written


def test_stale_cache_triggers_refetch(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    stale = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    cache_path.write_text(json.dumps({"checked_at": stale, "latest_version": "0.3.0"}))
    with patch("urllib.request.urlopen", return_value=_FakeUrlopen(_stub_response("0.4.0"))) as mock_urlopen:
        update_check.maybe_notify_update(_make_console(), current_version="0.3.0")
    mock_urlopen.assert_called_once()
    written = json.loads(cache_path.read_text())
    assert written["latest_version"] == "0.4.0"


def test_network_failure_silent() -> None:
    console = _make_console()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        update_check.maybe_notify_update(console, current_version="0.3.0")
    assert console.file.getvalue() == ""  # type: ignore[union-attr]


def test_corrupt_cache_treated_as_miss(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text("{not valid json")
    with patch("urllib.request.urlopen", return_value=_FakeUrlopen(_stub_response("0.4.0"))) as mock_urlopen:
        update_check.maybe_notify_update(_make_console(), current_version="0.3.0")
    mock_urlopen.assert_called_once()


def test_invalid_pypi_payload_silent() -> None:
    console = _make_console()
    bad_response = json.dumps({"info": {"version": "not-a-version"}}).encode("utf-8")
    with patch("urllib.request.urlopen", return_value=_FakeUrlopen(bad_response)):
        update_check.maybe_notify_update(console, current_version="0.3.0")
    assert console.file.getvalue() == ""  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        ("0.3.0", "0.3.1", "patch"),
        ("0.3.0", "0.4.0", "minor"),
        ("0.3.0", "1.0.0", "major"),
        ("0.3.0", "0.3.0", "none"),
        ("0.3.0", "0.2.9", "none"),
        ("1.2.3", "1.2.4", "patch"),
        ("1.2.3", "1.3.0", "minor"),
        ("1.2.3", "2.0.0", "major"),
    ],
)
def test_classify_bump(current: str, latest: str, expected: str) -> None:
    assert update_check._classify_bump(Version(current), Version(latest)) == expected


@pytest.mark.parametrize(
    ("bump", "expected_substring"),
    [
        ("patch", "uv tool upgrade nasde-toolkit"),
        ("minor", "new features"),
        ("major", "breaking changes"),
    ],
)
def test_format_message_includes_key_phrases(bump: str, expected_substring: str) -> None:
    message = update_check._format_message(bump, Version("0.3.0"), Version("0.4.0"))  # type: ignore[arg-type]
    assert expected_substring in message


def test_invalid_current_version_silent() -> None:
    console = _make_console()
    with patch("urllib.request.urlopen") as mock_urlopen:
        update_check.maybe_notify_update(console, current_version="not-a-version")
    mock_urlopen.assert_not_called()
    assert console.file.getvalue() == ""  # type: ignore[union-attr]
