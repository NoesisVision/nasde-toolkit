# ADR-005: chdir to repo root before Harbor Job execution

**Status:** Accepted
**Date:** 2026-03-16

## Context

Harbor resolves paths from its config relative to the current working directory. The existing `run-benchmark.sh` always runs from the repo root (`cd "$REPO_ROOT"` at the top). Two types of paths depend on this:

1. **Task paths** in `local-registry.json`: `"./evals/ddd-architectural-challenges/tasks/ddd-threshold-discount"`
2. **Agent import path** in `harbor_config.json`: `"evals.claude_custom_agents:ConfigurableClaude"`

When `nasde` is installed as a global tool and invoked from an arbitrary directory, both break.

## Decision

Before creating `Job(config)`, the runner:
1. Walks up from `benchmark_dir` to find the git repository root (`.git` directory)
2. `os.chdir(repo_root)` — so Harbor resolves relative paths correctly
3. `sys.path.insert(0, repo_root)` — so `importlib.import_module("evals.claude_custom_agents")` works
4. Restores original CWD in a `finally` block

```python
saved_cwd = Path.cwd()
if repo_root:
    os.chdir(repo_root)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
try:
    job = Job(JobConfig.model_validate(config_dict))
    return await job.run()
finally:
    os.chdir(saved_cwd)
```

## Consequences

- `nasde` works from any directory as long as `-C` points to a benchmark inside a git repo
- Temporary CWD change is scoped to `_run_job()` — no side effects on other code
- `sys.path` modification is permanent (intentional — agent import paths may be needed later during Harbor's trial execution)
- Alternative considered: rewrite all paths in config to absolute. Rejected because Harbor's `Task` class calls `Path(task_dir).resolve()` internally, and the registry JSON format is shared with other tools
