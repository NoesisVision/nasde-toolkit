"""Installer for NASDE authoring skills bundled into the wheel."""

from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from pathlib import Path

import typer
from rich.console import Console


def install_bundled_skills(
    console: Console,
    scope: str,
    target_dir: Path | None,
    force: bool,
) -> None:
    resolved_target = _resolve_target_dir(scope=scope, target_dir=target_dir)
    resolved_target.mkdir(parents=True, exist_ok=True)

    bundled_root = _bundled_skills_root()
    skill_dirs = [p for p in bundled_root.iterdir() if p.is_dir() and p.name.startswith("nasde-benchmark-")]
    if not skill_dirs:
        console.print("[red]ERROR: no bundled skills found — reinstall nasde from a recent release.[/red]")
        raise typer.Exit(1)

    installed: list[str] = []
    skipped: list[str] = []
    for skill_src in sorted(skill_dirs):
        skill_dst = resolved_target / skill_src.name
        if skill_dst.exists() and not force:
            skipped.append(skill_src.name)
            continue
        if skill_dst.exists():
            shutil.rmtree(skill_dst)
        shutil.copytree(skill_src, skill_dst)
        installed.append(skill_src.name)

    _print_summary(console, resolved_target, installed, skipped, force)


def _bundled_skills_root() -> Path:
    resources = files("nasde_toolkit").joinpath("_bundled_skills")
    with as_file(resources) as path:
        bundled = Path(path)
    if bundled.is_dir():
        return bundled
    editable_fallback = Path(__file__).resolve().parents[2] / ".claude" / "skills"
    if editable_fallback.is_dir():
        return editable_fallback
    return bundled


def _resolve_target_dir(scope: str, target_dir: Path | None) -> Path:
    if target_dir is not None:
        return target_dir.expanduser().resolve()
    if scope == "user":
        return (Path.home() / ".claude" / "skills").resolve()
    if scope == "project":
        return (Path.cwd() / ".claude" / "skills").resolve()
    raise typer.BadParameter(f"scope must be 'user' or 'project', got: {scope!r}")


def _print_summary(
    console: Console,
    target: Path,
    installed: list[str],
    skipped: list[str],
    force: bool,
) -> None:
    if installed:
        console.print(f"[green]✓ Installed {len(installed)} skill(s) to {target}:[/green]")
        for name in installed:
            console.print(f"  • {name}")
    if skipped:
        console.print(f"[yellow]Skipped {len(skipped)} existing skill(s) — rerun with --force to overwrite:[/yellow]")
        for name in skipped:
            console.print(f"  • {name}")
    if not installed and not skipped:
        console.print("[yellow]No skills were installed or skipped.[/yellow]")
    if installed:
        console.print("\n[dim]Skills are picked up automatically by Claude Code on the next session start.[/dim]")
