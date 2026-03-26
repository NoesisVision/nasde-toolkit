"""ASCII art banner for nasde CLI with Noesis brand colors."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from nasde_toolkit import __version__

GREEN = "#1B5E20"
GREEN_LIGHT = "#2E7D32"
BLUE = "#1565C0"
BLUE_LIGHT = "#1E88E5"
ACCENT = "#4CAF50"

_INDENT = "  "
_LOGO_LINES = [
    f"{_INDENT}                         __",
    f"{_INDENT}   ____  ____ _________ / /__",
    f"{_INDENT}  / __ \\/ __ `/ ___/ __  / _ \\",
    f"{_INDENT} / / / / /_/ (__  ) /_/ /  __/",
    f"{_INDENT}/_/ /_/\\__,_/____/\\__,_/\\___/",
]

_LINE_STYLES: list[list[tuple[str, str]]] = [
    [(GREEN, "full")],
    [(GREEN, "full")],
    [(GREEN_LIGHT, "full")],
    [(BLUE, "full")],
    [(BLUE_LIGHT, "full")],
]


def _render_logo() -> Text:
    text = Text()
    for i, line in enumerate(_LOGO_LINES):
        color = _LINE_STYLES[i][0][0]
        text.append(line, style=f"bold {color}")
        if i < len(_LOGO_LINES) - 1:
            text.append("\n")
    return text


def _render_tagline() -> Text:
    text = Text()
    text.append(f"{_INDENT}Noesis ", style=f"bold {GREEN}")
    text.append("Agentic Software Development Evals", style=f"{BLUE_LIGHT}")
    return text


def _render_version_line() -> Text:
    text = Text()
    text.append(f"{_INDENT}v{__version__}", style=f"bold {ACCENT}")
    return text


_banner_suppressed = False


def suppress_banner() -> None:
    global _banner_suppressed  # noqa: PLW0603
    _banner_suppressed = True


def is_banner_suppressed() -> bool:
    if _banner_suppressed:
        return True
    import os

    return os.environ.get("NASDE_NO_BANNER", "").strip() not in ("", "0", "false")


def print_banner(console: Console | None = None) -> None:
    if is_banner_suppressed():
        return
    c = console or Console()
    c.print()
    c.print(_render_logo())
    c.print()
    c.print(_render_tagline())
    c.print(_render_version_line())
    c.print()
