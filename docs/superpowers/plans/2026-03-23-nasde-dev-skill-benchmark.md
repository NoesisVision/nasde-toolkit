# nasde-dev-skill Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a self-testing benchmark for nasde-toolkit that measures skill value through 4 variant combinations, using local repo as source (first local-repo benchmark example).

**Architecture:** Three prerequisites (fix existing tests, source.git integration with docker-compose override for local paths, nasde-dev skill already cleaned) then benchmark project creation in `examples/nasde-dev-skill/`. For local repos, nasde generates both a Dockerfile (with `COPY . /app`) and a `docker-compose.yaml` override (pointing build context to the repo root). Harbor merges the compose override so `COPY` sees the full repo. 4 variants compose nasde-dev with external Python skills from skills.sh.

**Tech Stack:** Python 3.12, Typer, Harbor, pytest, Docker, skills.sh (python-testing, python-best-practices)

**Spec:** `docs/superpowers/specs/2026-03-20-nasde-dev-skill-benchmark-design.md`

**Key Harbor insight:** Harbor's `DockerEnvironment` uses `environment/` as the default Docker build context (`context_dir=self.environment_dir`). But if an `environment/docker-compose.yaml` exists, Harbor merges it — and relative paths in that compose file resolve relative to the compose file's location. So `build.context: ../../../..` in `environment/docker-compose.yaml` changes the context to the repo root, making `COPY . /app` work for local repos.

---

### Task 0: Fix existing broken tests in test_runner.py

The 4 existing tests in `test_runner.py` are broken — `_build_merged_config()` requires `variant_name` as a positional arg but tests don't pass it.

**Files:**
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Run existing tests to confirm failure**

Run: `uv run pytest tests/test_runner.py -v`
Expected: FAIL with `TypeError: _build_merged_config() missing 1 required positional argument`

- [ ] **Step 2: Fix all 4 test calls by adding `variant_name="vanilla"`**

In `tests/test_runner.py`, add `variant_name="vanilla"` to each of the 4 `_build_merged_config()` calls (lines 60, 72, 85, 99).

- [ ] **Step 3: Run tests to verify fix**

Run: `uv run pytest tests/test_runner.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_runner.py
git commit -m "fix: add missing variant_name arg to test_runner.py tests"
```

---

### Task 1: Fix source.git integration — auto-generate Dockerfile + docker-compose for local repos

Harbor expects `environment/Dockerfile` inside each task directory. When missing, nasde should auto-generate it. For local repos (`source.git` is a filesystem path), we also generate `docker-compose.yaml` that overrides the build context to point to the repo root — this is required because Harbor's default build context is the `environment/` directory, but `COPY . /app` needs the repo root.

**Files:**
- Modify: `src/nasde_toolkit/docker.py`
- Modify: `src/nasde_toolkit/runner.py`
- Create: `tests/test_docker.py`

- [ ] **Step 1: Write tests for `generate_dockerfile` with remote URL (validate existing code)**

```python
# tests/test_docker.py
from __future__ import annotations

from nasde_toolkit.config import DockerConfig, SourceConfig
from nasde_toolkit.docker import generate_dockerfile


def test_generate_dockerfile_remote_url() -> None:
    source = SourceConfig(git="https://github.com/org/repo.git", ref="main")
    docker = DockerConfig(base_image="python:3.12-slim", build_commands=["pip install uv"])
    result = generate_dockerfile(source, docker)
    assert "FROM python:3.12-slim" in result
    assert "git clone https://github.com/org/repo.git" in result
    assert "git checkout main" in result
    assert "RUN pip install uv" in result
```

- [ ] **Step 2: Run test — should pass (existing code)**

Run: `uv run pytest tests/test_docker.py::test_generate_dockerfile_remote_url -v`
Expected: PASS

- [ ] **Step 3: Write failing tests for local path Dockerfile**

```python
# tests/test_docker.py (append)
def test_generate_dockerfile_local_path() -> None:
    source = SourceConfig(git="/tmp/my-repo", ref="abc1234")
    docker = DockerConfig(base_image="python:3.12-slim", build_commands=[])
    result = generate_dockerfile(source, docker)
    assert "COPY . /app" in result
    assert "git checkout abc1234" in result
    assert "git clone" not in result


def test_generate_dockerfile_relative_path() -> None:
    source = SourceConfig(git="../..", ref="7e1a804")
    docker = DockerConfig(base_image="python:3.12-slim", build_commands=["uv sync"])
    result = generate_dockerfile(source, docker)
    assert "COPY . /app" in result
    assert "git checkout 7e1a804" in result
    assert "RUN uv sync" in result
```

- [ ] **Step 4: Run — should fail**

Run: `uv run pytest tests/test_docker.py -v`
Expected: FAIL — existing `generate_dockerfile` uses `git clone` for all paths

- [ ] **Step 5: Implement local path support in `generate_dockerfile`**

Refactor `src/nasde_toolkit/docker.py`: branch on whether `source.git` is a URL or a local path. Local paths use `COPY . /app` + `git checkout`. Remote paths keep the existing `git clone` behavior.

Key changes:
- Add `_is_local_path()` helper
- Split into `_generate_remote_dockerfile()` and `_generate_local_dockerfile()`
- `_generate_local_dockerfile` uses `COPY . /app` (assumes build context is repo root — enforced by the docker-compose override in Step 9)

- [ ] **Step 6: Run tests — should pass**

Run: `uv run pytest tests/test_docker.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 7: Write failing tests for `ensure_task_environment`**

This function generates both Dockerfile AND docker-compose.yaml for local repos.

```python
# tests/test_docker.py (append)
from pathlib import Path

from nasde_toolkit.docker import ensure_task_environment


def test_ensure_task_environment_existing_dockerfile_skips(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "my-task"
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)
    (env_dir / "Dockerfile").write_text("FROM ubuntu:22.04")
    source = SourceConfig(git="https://example.com/repo.git", ref="main")
    docker = DockerConfig()

    ensure_task_environment(task_dir, source, docker)
    assert not (env_dir / "docker-compose.yaml").exists()


def test_ensure_task_environment_generates_for_remote(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "my-task"
    task_dir.mkdir(parents=True)
    source = SourceConfig(git="https://example.com/repo.git", ref="main")
    docker = DockerConfig(base_image="python:3.12-slim", build_commands=[])

    ensure_task_environment(task_dir, source, docker)
    dockerfile_path = task_dir / "environment" / "Dockerfile"
    assert dockerfile_path.exists()
    assert "git clone" in dockerfile_path.read_text()
    assert not (task_dir / "environment" / "docker-compose.yaml").exists()


def test_ensure_task_environment_generates_compose_for_local(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "my-task"
    task_dir.mkdir(parents=True)
    source = SourceConfig(git="../..", ref="abc1234")
    docker = DockerConfig(base_image="python:3.12-slim", build_commands=["uv sync"])

    ensure_task_environment(task_dir, source, docker)

    dockerfile_path = task_dir / "environment" / "Dockerfile"
    assert dockerfile_path.exists()
    assert "COPY . /app" in dockerfile_path.read_text()

    compose_path = task_dir / "environment" / "docker-compose.yaml"
    assert compose_path.exists()
    compose_content = compose_path.read_text()
    assert "context:" in compose_content


def test_ensure_task_environment_compose_context_resolves_to_repo(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    task_dir = project_dir / "tasks" / "my-task"
    task_dir.mkdir(parents=True)
    source = SourceConfig(git="../..", ref="abc1234")
    docker = DockerConfig()

    ensure_task_environment(task_dir, source, docker)

    compose_path = task_dir / "environment" / "docker-compose.yaml"
    compose_content = compose_path.read_text()
    # context path should be relative from environment/ to project_dir/../../
    # environment/ is at tasks/my-task/environment/ → ../../../.. gets to project_dir/../..
    assert "../../../.." in compose_content
```

- [ ] **Step 8: Run — should fail**

Run: `uv run pytest tests/test_docker.py -v -k ensure`
Expected: FAIL — `ensure_task_environment` doesn't exist

- [ ] **Step 9: Implement `ensure_task_environment`**

Add to `src/nasde_toolkit/docker.py`:

```python
def ensure_task_environment(
    task_dir: Path,
    source: SourceConfig,
    docker: DockerConfig,
) -> None:
    """Generate environment/Dockerfile (and docker-compose.yaml for local repos) if missing."""
    env_dir = task_dir / "environment"
    if (env_dir / "Dockerfile").exists():
        return

    env_dir.mkdir(parents=True, exist_ok=True)

    dockerfile_content = generate_dockerfile(source, docker)
    (env_dir / "Dockerfile").write_text(dockerfile_content)
    console.print(f"  [dim]Generated Dockerfile for {task_dir.name}[/dim]")

    if _is_local_path(source.git):
        compose_content = _generate_build_context_compose(task_dir, source.git)
        (env_dir / "docker-compose.yaml").write_text(compose_content)
        console.print(f"  [dim]Generated docker-compose.yaml for local repo build context[/dim]")
```

And the compose generator:

```python
def _generate_build_context_compose(task_dir: Path, git_path: str) -> str:
    """Generate docker-compose.yaml that overrides build context to point to the local repo root.

    Harbor's default build context is environment/. For COPY to see the repo,
    we override context to the resolved repo path, relative from environment/.
    """
    repo_abs = (task_dir / git_path).resolve()
    env_dir = task_dir / "environment"
    context_relative = os.path.relpath(repo_abs, env_dir)

    return dedent(f"""\
        services:
          main:
            build:
              context: {context_relative}
    """)
```

Add `import os` at module top.

- [ ] **Step 10: Run all docker tests**

Run: `uv run pytest tests/test_docker.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 11: Integrate into runner**

Modify `src/nasde_toolkit/runner.py` — in `run_benchmark()`, after variant resolution and before `_build_merged_config()`:

```python
from nasde_toolkit.docker import ensure_task_environment

for task in config.tasks:
    ensure_task_environment(task.path, task.source, config.docker)
```

- [ ] **Step 12: Run full test suite**

Run: `uv run pytest -x -q`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add src/nasde_toolkit/docker.py src/nasde_toolkit/runner.py tests/test_docker.py
git commit -m "feat: auto-generate Dockerfile + docker-compose from source.git

For local repos, generates COPY-based Dockerfile and docker-compose.yaml
that overrides build context to the repo root. Harbor merges the compose
file, so COPY sees the full repository.

Enables benchmarks using source.git: '../..' without custom Dockerfile."
```

---

### Task 2: Download and snapshot external Python skills

Fetch `python-testing` and `python-best-practices` from skills.sh and save as snapshots for deterministic benchmark evaluation.

**Files:**
- Create: `examples/nasde-dev-skill/variants/nasde-dev-with-arch/skills/python-best-practices/SKILL.md`
- Create: `examples/nasde-dev-skill/variants/nasde-dev-with-testing/skills/python-testing/SKILL.md`
- Create: `examples/nasde-dev-skill/variants/nasde-dev-full-stack/skills/python-best-practices/SKILL.md`
- Create: `examples/nasde-dev-skill/variants/nasde-dev-full-stack/skills/python-testing/SKILL.md`

- [ ] **Step 1: Install skills temporarily to get their content**

```bash
npx skills add 0xbigboss/claude-code@python-best-practices -g -y
npx skills add affaan-m/everything-claude-code@python-testing -g -y
```

- [ ] **Step 2: Find and read the installed skill files**

```bash
find ~/.claude -name "SKILL.md" -path "*python-best*" 2>/dev/null
find ~/.claude -name "SKILL.md" -path "*python-testing*" 2>/dev/null
```

- [ ] **Step 3: Create variant directories and copy skill snapshots**

```bash
mkdir -p examples/nasde-dev-skill/variants/nasde-dev-with-arch/skills/{nasde-dev,python-best-practices}
mkdir -p examples/nasde-dev-skill/variants/nasde-dev-with-testing/skills/{nasde-dev,python-testing}
mkdir -p examples/nasde-dev-skill/variants/nasde-dev-full-stack/skills/{nasde-dev,python-best-practices,python-testing}

# Copy snapshots (replace <path> with actual found paths)
cp <python-best-practices-path>/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-with-arch/skills/python-best-practices/SKILL.md
cp <python-best-practices-path>/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-full-stack/skills/python-best-practices/SKILL.md

cp <python-testing-path>/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-with-testing/skills/python-testing/SKILL.md
cp <python-testing-path>/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-full-stack/skills/python-testing/SKILL.md

cp .claude/skills/nasde-dev/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-with-arch/skills/nasde-dev/SKILL.md
cp .claude/skills/nasde-dev/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-with-testing/skills/nasde-dev/SKILL.md
cp .claude/skills/nasde-dev/SKILL.md examples/nasde-dev-skill/variants/nasde-dev-full-stack/skills/nasde-dev/SKILL.md
```

- [ ] **Step 4: Verify YAML frontmatter on all snapshots**

```bash
head -5 examples/nasde-dev-skill/variants/*/skills/*/SKILL.md
```

Each should start with `---` and have `name:` field.

- [ ] **Step 5: Commit**

```bash
git add examples/nasde-dev-skill/variants/*/skills/
git commit -m "feat: snapshot python-testing and python-best-practices skills

Frozen at 2026-03-23 for deterministic benchmark evaluation.
Sources: affaan-m/everything-claude-code@python-testing (1.6K installs),
0xbigboss/claude-code@python-best-practices (802 installs)"
```

---

### Task 3: Create benchmark project scaffold

Create all static benchmark files per the spec.

**Files:**
- Create: `examples/nasde-dev-skill/.gitignore`
- Create: `examples/nasde-dev-skill/nasde.toml`
- Create: `examples/nasde-dev-skill/assessment_dimensions.json`
- Create: `examples/nasde-dev-skill/tasks/add-multi-attempt-support/task.json`
- Create: `examples/nasde-dev-skill/tasks/add-multi-attempt-support/task.toml`
- Create: `examples/nasde-dev-skill/tasks/add-multi-attempt-support/instruction.md`
- Create: `examples/nasde-dev-skill/tasks/add-multi-attempt-support/assessment_criteria.md`
- Create: `examples/nasde-dev-skill/tasks/add-multi-attempt-support/tests/test.sh`
- Create: `examples/nasde-dev-skill/tasks/add-multi-attempt-support/solution/solve.sh`
- Create: `examples/nasde-dev-skill/variants/vanilla/CLAUDE.md`
- Create: `examples/nasde-dev-skill/variants/nasde-dev-with-{arch,testing,full-stack}/CLAUDE.md`

All file contents are specified verbatim in the spec. Copy them exactly.

- [ ] **Step 1: Create .gitignore** — `jobs/` + `tasks/*/environment/` (generated files)

- [ ] **Step 2: Create nasde.toml** — from spec

- [ ] **Step 3: Create assessment_dimensions.json** — from spec (4 × 25 = 100)

- [ ] **Step 4: Create task.json** — from spec (`source.git: "../.."`, no `environment` block)

- [ ] **Step 5: Create task.toml** — from spec

- [ ] **Step 6: Create instruction.md** — from spec

- [ ] **Step 7: Create assessment_criteria.md** — from spec (4 dimensions with rubrics)

- [ ] **Step 8: Create tests/test.sh** — from spec (6 steps), `chmod +x`

- [ ] **Step 9: Create solution/solve.sh** — `git cherry-pick 812b189 --no-commit`, `chmod +x`

- [ ] **Step 10: Create vanilla/CLAUDE.md** — minimal instructions from spec

- [ ] **Step 11: Create shared CLAUDE.md** for the 3 skill variants — from spec

- [ ] **Step 12: Verify directory structure**

```bash
find examples/nasde-dev-skill -type f | sort
```

- [ ] **Step 13: Run full test suite**

Run: `uv run pytest -x -q`
Expected: PASS

- [ ] **Step 14: Commit**

```bash
git add examples/nasde-dev-skill/
git commit -m "feat: add nasde-dev-skill benchmark example

First local-repo benchmark: source.git='../..' references nasde-toolkit itself.
4 variants: vanilla, nasde-dev+arch, nasde-dev+testing, nasde-dev+full-stack.
Task: implement multi-attempt support (commit 812b189)."
```

---

### Task 4: Update documentation (CLAUDE.md, README.md, ARCHITECTURE.md)

Document the source.git integration fix and the local-repo benchmark pattern.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Update CLAUDE.md** — add note that `environment/Dockerfile` is optional (auto-generated from `source.git` + `[docker]`). Add local path note. Verify `--attempts`/`-n` in CLI reference.

- [ ] **Step 2: Update README.md** — add "Local repo benchmarks" section referencing `examples/nasde-dev-skill/`.

- [ ] **Step 3: Update ARCHITECTURE.md** — add Dockerfile auto-generation path to Docker environment flow.

- [ ] **Step 4: Verify doc consistency**

```bash
grep -n "source.git\|environment/Dockerfile\|auto-generat" CLAUDE.md README.md ARCHITECTURE.md
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md ARCHITECTURE.md
git commit -m "docs: add local-repo benchmark pattern and source.git auto-generation"
```

---

### Task 5: Verify end-to-end (solution dry run)

**Files:** None (verification only)

- [ ] **Step 1: Generate environment files and build Docker image**

```bash
cd examples/nasde-dev-skill
uv run python -c "
from nasde_toolkit.config import load_project_config
from nasde_toolkit.docker import ensure_task_environment
config = load_project_config()
for task in config.tasks:
    ensure_task_environment(task.path, task.source, config.docker)
print('Generated OK')
"
```

Verify `tasks/add-multi-attempt-support/environment/Dockerfile` and `docker-compose.yaml` were created.

Then build using the generated compose override's context:

```bash
docker build -t nasde-dev-skill-test \
  -f tasks/add-multi-attempt-support/environment/Dockerfile \
  $(cd tasks/add-multi-attempt-support && python -c "
import yaml
with open('environment/docker-compose.yaml') as f:
    c = yaml.safe_load(f)
print(c['services']['main']['build']['context'])
")
```

Or simpler — let docker compose handle it:

```bash
cd tasks/add-multi-attempt-support
docker compose -f ../../.venv/lib/python3.12/site-packages/harbor/environments/docker/docker-compose-base.yaml \
  -f ../../.venv/lib/python3.12/site-packages/harbor/environments/docker/docker-compose-build.yaml \
  -f environment/docker-compose.yaml build
```

Expected: Image builds successfully.

- [ ] **Step 2: Run solution + test.sh in container**

```bash
docker run --rm \
  -v $(pwd)/tasks/add-multi-attempt-support/solution:/solution \
  -v $(pwd)/tasks/add-multi-attempt-support/tests:/tests \
  nasde-dev-skill-test bash -c "
    mkdir -p /logs/verifier
    bash /solution/solve.sh
    bash /tests/test.sh
    echo 'Reward:' && cat /logs/verifier/reward.txt
  "
```

Expected: All 6 test steps pass, reward.txt = 1.

- [ ] **Step 3: Verify nasde config parses**

```bash
uv run python -c "
from nasde_toolkit.config import load_project_config
from pathlib import Path
config = load_project_config(Path('examples/nasde-dev-skill'))
print(f'Project: {config.name}')
print(f'Tasks: {[t.name for t in config.tasks]}')
print(f'Source: {config.tasks[0].source.git} @ {config.tasks[0].source.ref}')
"
```

Expected: Parses OK, source.git="../..".

- [ ] **Step 4: Full test suite**

Run: `uv run pytest -x -q`
Expected: PASS

- [ ] **Step 5: Push**

```bash
git push
```

---

### Task 6 (optional): Full benchmark dry run with Harbor

Requires Docker daemon and ANTHROPIC_API_KEY/CLAUDE_CODE_OAUTH_TOKEN.

- [ ] **Step 1: Run vanilla without eval**

```bash
source scripts/export_oauth_token.sh
nasde run --variant vanilla --tasks add-multi-attempt-support --without-eval \
  -C examples/nasde-dev-skill
```

Expected: Harbor trial completes, reward 1.0.

- [ ] **Step 2: Run with eval**

```bash
nasde run --variant vanilla --tasks add-multi-attempt-support \
  -C examples/nasde-dev-skill
```

Expected: Assessment scores for all 4 dimensions.

- [ ] **Step 3: Run all variants with Opik**

```bash
for variant in vanilla nasde-dev-with-arch nasde-dev-with-testing nasde-dev-full-stack; do
  nasde run --variant $variant --tasks add-multi-attempt-support \
    --with-opik -C examples/nasde-dev-skill
done
```

Expected: 4 traces in Opik with differentiated scores.

- [ ] **Step 4: Critical log analysis**

Inspect for each run:
- Harbor trial log — errors, warnings, timeout
- Docker build output — local path handling, compose merge
- Assessment evaluator log — scoring rationale differentiates variants
- Agent transcript — evidence of skill usage (ran pytest, checked --help, updated docs)
- test.sh output — all 6 steps pass
