"""PyPI update notifier for the nasde CLI.

Fetches the latest released version of nasde-toolkit from PyPI and prints a
one-line notice on stderr when the user is running an older release. Notify-only:
never auto-updates and never prompts. Skips silently in CI, non-TTY contexts,
when explicitly disabled, and on dev/pre-release builds.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from packaging.version import InvalidVersion, Version
from platformdirs import user_cache_dir
from rich.console import Console

_PYPI_JSON_URL = "https://pypi.org/pypi/nasde-toolkit/json"
_CHANGELOG_URL = "https://github.com/NoesisVision/nasde-toolkit/blob/main/CHANGELOG.md"
_CACHE_TTL = timedelta(hours=24)
_FETCH_TIMEOUT_SEC = 2.0

_BumpKind = Literal["none", "patch", "minor", "major"]


@dataclass(frozen=True)
class _CacheEntry:
    checked_at: str
    latest_version: str


def maybe_notify_update(console: Console, *, current_version: str) -> None:
    """Display one-line update notice if a newer release is available.

    Never raises. Skips silently when stderr is not a TTY, NASDE_NO_UPDATE_CHECK
    or CI is set, current_version is dev/pre-release, or PyPI is unreachable.
    """
    try:
        if not _should_check(current_version):
            return
        latest = _resolve_latest_version()
        if latest is None:
            return
        try:
            current = Version(current_version)
        except InvalidVersion:
            return
        bump = _classify_bump(current, latest)
        if bump == "none":
            return
        _print_notice(console, bump, current, latest)
    except Exception:
        return


def _should_check(current_version: str) -> bool:
    if os.environ.get("NASDE_NO_UPDATE_CHECK"):
        return False
    if os.environ.get("CI"):
        return False
    if not sys.stderr.isatty():
        return False
    try:
        parsed = Version(current_version)
    except InvalidVersion:
        return False
    return not ((parsed.is_devrelease or parsed.is_prerelease) and not os.environ.get("NASDE_FORCE_UPDATE_CHECK"))


def _resolve_latest_version() -> Version | None:
    cache = _read_cache()
    now = datetime.now(UTC)
    if cache is not None:
        try:
            checked_at = datetime.fromisoformat(cache.checked_at)
            cached_version = Version(cache.latest_version)
        except (ValueError, InvalidVersion):
            cache = None
        else:
            if now - checked_at < _CACHE_TTL:
                return cached_version
    fetched = _fetch_latest_version(_FETCH_TIMEOUT_SEC)
    if fetched is None:
        return None
    _write_cache(_CacheEntry(checked_at=now.isoformat(), latest_version=str(fetched)))
    return fetched


def _fetch_latest_version(timeout: float) -> Version | None:
    try:
        with urllib.request.urlopen(_PYPI_JSON_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    raw = payload.get("info", {}).get("version")
    if not isinstance(raw, str):
        return None
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def _read_cache() -> _CacheEntry | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _CacheEntry(
            checked_at=data["checked_at"],
            latest_version=data["latest_version"],
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def _write_cache(entry: _CacheEntry) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(entry)), encoding="utf-8")
    except OSError:
        return


def _cache_path() -> Path:
    return Path(user_cache_dir("nasde-toolkit", "noesis")) / "update-check.json"


def _classify_bump(current: Version, latest: Version) -> _BumpKind:
    if latest <= current:
        return "none"
    if latest.major > current.major:
        return "major"
    if latest.minor > current.minor:
        return "minor"
    return "patch"


def _print_notice(console: Console, bump: _BumpKind, current: Version, latest: Version) -> None:
    stderr = Console(stderr=True, soft_wrap=True) if not console.stderr else console
    message = _format_message(bump, current, latest)
    stderr.print(message)


def _format_message(bump: _BumpKind, current: Version, latest: Version) -> str:
    upgrade_cmd = "[bold]uv tool upgrade nasde-toolkit[/bold]"
    if bump == "patch":
        return f"Update available: nasde-toolkit {current} → {latest}. Run {upgrade_cmd} to update."
    if bump == "minor":
        return (
            f"Update available: nasde-toolkit {current} → {latest} (new features). "
            f"Changelog: {_CHANGELOG_URL}. Run {upgrade_cmd}."
        )
    return (
        f"[yellow]Major update available[/yellow]: nasde-toolkit {current} → {latest}. "
        f"May contain breaking changes. Review release notes: {_CHANGELOG_URL}."
    )
