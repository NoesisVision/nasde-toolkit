"""Project scaffolding for nasde init."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

console = Console()

NASDE_TOML_TEMPLATE = """\
[project]
name = "{name}"
version = "1.0.0"

[defaults]
variant = "vanilla"

[docker]
base_image = "ubuntu:22.04"
build_commands = []

[evaluation]
model = "claude-sonnet-4-6"
dimensions_file = "assessment_dimensions.json"

[reporting]
platform = "opik"
project_name = "{name}"
"""

ASSESSMENT_DIMENSIONS_TEMPLATE = """\
{
  "_comment": "Independent per-dimension max_score. See docs/adr/008.",
  "dimensions": [
    {
      "name": "domain_modeling",
      "title": "Domain Modeling",
      "max_score": 20,
      "description": "Correct use of DDD building blocks or simpler patterns as appropriate for domain complexity"
    },
    {
      "name": "architecture_compliance",
      "title": "Architecture Compliance",
      "max_score": 10,
      "description": "Respecting layer boundaries, project conventions, separation of concerns"
    },
    {
      "name": "extensibility",
      "title": "Extensibility",
      "max_score": 5,
      "description": "OCP, Strategy/Policy patterns, ease of adding similar features"
    },
    {
      "name": "test_quality",
      "title": "Test Quality",
      "max_score": 15,
      "description": "Coverage, isolation from externals, edge cases, test conventions"
    }
  ]
}
"""

TASK_TOML_TEMPLATE = """\
version = "1.0"

[task]
name = "nasde/{task_name}"
description = "Describe the task."

[agent]
timeout_sec = 1800

[environment]
memory_mb = 4096

[verifier]
timeout_sec = 300

[nasde.source]
git = ""
ref = "HEAD"
"""

VARIANT_CLAUDE_MD_TEMPLATE = """\
# Agent Instructions

## Approach

1. Explore the existing codebase before writing any code.
2. Follow existing architectural patterns and conventions.
3. Write tests that match the style of existing test files.
"""

VARIANT_TOML_TEMPLATE = """\
agent = "claude"
model = "claude-sonnet-4-6"
"""

GITIGNORE_TEMPLATE = """\
jobs/
"""

GITATTRIBUTES_TEMPLATE = """\
# Critical: files executed inside benchmark sandboxes (Linux containers via
# Docker / Daytona / Modal / etc.) MUST be LF. CRLF on a shebang line causes
# `bash: required file not found` because the kernel reads `#!/bin/bash\\r`.
* text=auto eol=lf

*.sh        text eol=lf
*.bash      text eol=lf
Dockerfile  text eol=lf
*.dockerfile text eol=lf
docker-compose.yaml text eol=lf
docker-compose.yml  text eol=lf
*.toml      text eol=lf
*.yaml      text eol=lf
*.yml       text eol=lf
*.json      text eol=lf
*.md        text eol=lf
*.py        text eol=lf

# PowerShell / Windows batch keep CRLF.
*.ps1       text eol=crlf
*.psd1      text eol=crlf
*.psm1      text eol=crlf
*.bat       text eol=crlf
*.cmd       text eol=crlf

# Binary assets — never touch line endings.
*.png       binary
*.jpg       binary
*.jpeg      binary
*.gif       binary
*.ico       binary
*.pdf       binary
*.zip       binary
*.gz        binary
*.tar       binary
*.tgz       binary
*.whl       binary
*.so        binary
*.dll       binary
*.exe       binary
"""


def create_project(project_dir: Path, name: str) -> None:
    """Scaffold a new evaluation project structure."""
    tasks_dir = project_dir / "tasks"
    variants_dir = project_dir / "variants" / "vanilla"
    jobs_dir = project_dir / "jobs"

    _write_if_missing(project_dir / "nasde.toml", NASDE_TOML_TEMPLATE.format(name=name))
    _write_if_missing(project_dir / "assessment_dimensions.json", ASSESSMENT_DIMENSIONS_TEMPLATE)
    _write_if_missing(project_dir / ".gitignore", GITIGNORE_TEMPLATE)
    _write_if_missing(project_dir / ".gitattributes", GITATTRIBUTES_TEMPLATE)

    tasks_dir.mkdir(parents=True, exist_ok=True)
    variants_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    _write_if_missing(variants_dir / "variant.toml", VARIANT_TOML_TEMPLATE)
    _write_if_missing(variants_dir / "CLAUDE.md", VARIANT_CLAUDE_MD_TEMPLATE)

    example_task_dir = tasks_dir / "example-task"
    example_task_dir.mkdir(parents=True, exist_ok=True)
    (example_task_dir / "tests").mkdir(parents=True, exist_ok=True)

    _write_if_missing(
        example_task_dir / "task.toml",
        TASK_TOML_TEMPLATE.format(task_name="example-task"),
    )
    instruction_content = (
        "# Task: Example\n\n"
        "## Context\n\nDescribe the codebase context.\n\n"
        "## Requirement\n\nDescribe what the agent should do.\n"
    )
    _write_if_missing(
        example_task_dir / "instruction.md",
        instruction_content,
    )
    _write_if_missing(
        example_task_dir / "assessment_criteria.md",
        "# Assessment Criteria\n\nDefine scoring dimensions here.\n",
    )
    _write_if_missing(
        example_task_dir / "tests" / "test.sh",
        "#!/bin/bash\n# Verification script\necho 1 > /logs/verifier/reward.txt\n",
    )

    console.print(f"[green]Project scaffolded at[/green] {project_dir}")
    console.print("  nasde.toml")
    console.print("  assessment_dimensions.json")
    console.print("  tasks/example-task/")
    console.print("  variants/vanilla/variant.toml")
    console.print("  variants/vanilla/CLAUDE.md")


def _write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        console.print(f"  [yellow]Skipping[/yellow] {path.name} (already exists)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")
