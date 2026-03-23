"""Configuration parsing for nasde projects.

Reads nasde.toml and task.json files to build a unified configuration
for benchmark runs.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class SourceConfig:
    """Git source for a task's codebase."""

    git: str
    ref: str


@dataclass
class DockerConfig:
    """Docker environment configuration."""

    base_image: str = "ubuntu:22.04"
    build_commands: list[str] = field(default_factory=list)


@dataclass
class EvaluationConfig:
    """Assessment evaluation settings."""

    model: str = "claude-opus-4-6"
    dimensions_file: str = "assessment_dimensions.json"
    max_turns: int = 30
    allowed_tools: list[str] | None = None
    mcp_config: str | None = None
    skills_dir: str | None = None
    append_system_prompt: str | None = None


@dataclass
class ReportingConfig:
    """Reporting platform settings."""

    platform: str = "opik"
    project_name: str = ""


@dataclass
class TaskConfig:
    """Configuration for a single benchmark task."""

    name: str
    path: Path
    source: SourceConfig
    instruction: str = "./instruction.md"
    docker: DockerConfig = field(default_factory=DockerConfig)
    evaluation_script: str = "./tests/test.sh"
    evaluation_timeout: int = 300


@dataclass
class ProjectConfig:
    """Top-level project configuration from nasde.toml."""

    name: str
    version: str = "1.0.0"
    project_dir: Path = field(default_factory=lambda: Path.cwd())
    default_variant: str = "vanilla"
    default_model: str = "claude-sonnet-4-6"
    default_timeout_sec: int = 720
    default_harbor_env: str | None = None
    docker: DockerConfig = field(default_factory=DockerConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    tasks: list[TaskConfig] = field(default_factory=list)


def load_project_config(project_dir: Path | None = None) -> ProjectConfig:
    """Load and merge nasde.toml with task.json files."""
    project_dir = _find_project_dir(project_dir)
    toml_path = project_dir / "nasde.toml"

    if not toml_path.exists():
        raise FileNotFoundError(f"No nasde.toml found in {project_dir}")

    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    config = _parse_toml(raw, project_dir)
    config.tasks = _discover_tasks(project_dir, config.docker)
    return config


def _find_project_dir(start: Path | None) -> Path:
    """Walk up from start to find directory containing nasde.toml."""
    current = start or Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "nasde.toml").exists():
            return parent
    return current


def _parse_toml(raw: dict, project_dir: Path) -> ProjectConfig:
    project = raw.get("project", {})
    defaults = raw.get("defaults", {})
    docker_raw = raw.get("docker", {})
    eval_raw = raw.get("evaluation", {})
    reporting_raw = raw.get("reporting", {})

    return ProjectConfig(
        name=project.get("name", "unnamed"),
        version=project.get("version", "1.0.0"),
        project_dir=project_dir,
        default_variant=defaults.get("variant", "vanilla"),
        default_model=defaults.get("model", "claude-sonnet-4-6"),
        default_timeout_sec=defaults.get("timeout_sec", 720),
        default_harbor_env=defaults.get("harbor_env"),
        docker=DockerConfig(
            base_image=docker_raw.get("base_image", "ubuntu:22.04"),
            build_commands=docker_raw.get("build_commands", []),
        ),
        evaluation=EvaluationConfig(
            model=eval_raw.get("model", "claude-opus-4-6"),
            dimensions_file=eval_raw.get("dimensions_file", "assessment_dimensions.json"),
            max_turns=eval_raw.get("max_turns", 30),
            allowed_tools=eval_raw.get("allowed_tools"),
            mcp_config=eval_raw.get("mcp_config"),
            skills_dir=eval_raw.get("skills_dir"),
            append_system_prompt=eval_raw.get("append_system_prompt"),
        ),
        reporting=ReportingConfig(
            platform=reporting_raw.get("platform", "opik"),
            project_name=reporting_raw.get("project_name", project.get("name", "")),
        ),
    )


def _discover_tasks(project_dir: Path, default_docker: DockerConfig) -> list[TaskConfig]:
    """Find all task directories and load their task.json."""
    tasks_dir = _resolve_tasks_dir(project_dir)
    if not tasks_dir.exists():
        return []

    tasks = []
    for task_path in sorted(tasks_dir.iterdir()):
        task_json_path = task_path / "task.json"
        if not task_json_path.exists():
            continue
        task = _load_task(task_path, task_json_path, default_docker)
        tasks.append(task)

    return tasks


def _resolve_tasks_dir(project_dir: Path) -> Path:
    """Resolve tasks directory — check .nasde/tasks/ first, then tasks/."""
    nasde_tasks = project_dir / ".nasde" / "tasks"
    if nasde_tasks.exists():
        return nasde_tasks
    return project_dir / "tasks"


def _load_task(
    task_path: Path,
    task_json_path: Path,
    default_docker: DockerConfig,
) -> TaskConfig:
    with open(task_json_path) as f:
        raw = json.load(f)

    source_raw = raw.get("source", {})
    docker_raw = raw.get("docker", {})
    eval_raw = raw.get("evaluation", {})

    return TaskConfig(
        name=raw.get("name", task_path.name),
        path=task_path,
        source=SourceConfig(
            git=source_raw.get("git", ""),
            ref=source_raw.get("ref", "HEAD"),
        ),
        instruction=raw.get("instruction", "./instruction.md"),
        docker=DockerConfig(
            base_image=docker_raw.get("base_image", default_docker.base_image),
            build_commands=docker_raw.get("build_commands", default_docker.build_commands),
        ),
        evaluation_script=eval_raw.get("script", "./tests/test.sh"),
        evaluation_timeout=eval_raw.get("timeout_seconds", 300),
    )
