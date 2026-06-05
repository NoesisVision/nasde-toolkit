# ADR-010: Git platform integration via auto-detected pluggable CLI backends

**Status:** Accepted
**Date:** 2026-06-05

## Context

The rubric-calibration feature (`nasde calibrate`) publishes each trial's agent diff and
LLM-as-a-Judge assessment as a Pull Request to a private "sink" repository, so a human can review
the diff with full code navigation, comment inline, and feed those comments back into rubric
tuning. This requires `nasde` to talk to a git hosting platform.

The operations split cleanly into two disjoint classes:

- **GIT** — pushing branches (the orphan base branch carrying the start-state codebase, and the
  per-trial feature branch carrying the agent's changes). This goes through the `git` binary over
  ssh/https. It is **platform-agnostic** (identical for GitHub/GitLab/Bitbucket) and does **not**
  count against any platform API rate limit.
- **PLATFORM** — four API operations that the `git` binary cannot perform: does the repo exist,
  does a PR already exist for a branch (idempotency), create a PR, fetch PR comments (issue-level
  plus inline review comments carrying `path`/`line`/`diff_hunk`).

Three constraints shaped the decision:

1. **Two platforms are required up front.** Clients are split between GitHub and GitLab (the latter
   common in enterprise/self-hosted setups), so the design must support both, not just GitHub.
2. **GitHub enforces secondary rate limits on content creation** (PRs, comments) with `Retry-After`
   semantics — a real concern when publishing many trials.
3. **`gh` returns exit code 0 even for a non-existent repo** (verified: `gh repo view <missing>`
   exits 0 and prints `Could not resolve to a Repository`). So existence checks must parse output,
   not trust the exit code. `gh auth status` does exit non-zero when not authenticated, so auth
   validation can rely on the exit code.

Repository **creation** is deliberately out of MVP scope: pushing a branch to an existing repo
creates the ref ad-hoc, so the sink repo only needs to exist (the client creates it once). This
removes the need for `admin:org`/repo-creation permissions and the public/private distinction.

The repo already has the load-bearing precedents this decision builds on:

- `evaluator_backends/` — a `@runtime_checkable Protocol` (`EvaluatorBackend`) with a
  `create_backend()` factory that lazily imports the chosen implementation. Backends spawn the
  user's CLI (`claude`, `codex`) as a subprocess and rely on the CLI's own authentication.
- ADR-002 — **all dependencies are core, no optional extras**; the Agent SDK was deliberately
  dropped in favor of subprocess-to-CLI so that the CLI binary is a runtime prerequisite, not a
  Python dependency, and the user's existing auth is reused.
- ADR-001 / ADR-004 — thin integration layer; delegating to a third-party CLI is an established
  pattern (`nasde harbor`, `nasde opik`).
- `docker.py` — the existing pattern for GIT operations: `subprocess.run(["git", ...],
  capture_output=True, text=True)`, check `returncode`, raise `RuntimeError` with the stderr tail.

## Decision

### Separate the GIT and PLATFORM layers

GIT operations live in a single platform-agnostic module (`git_platform_backends/git_ops.py`),
**not** behind the Protocol — there is no per-platform variance in `git push` / `git ls-remote`.
PLATFORM operations live behind a `GitPlatformBackend` Protocol. When GitLab support lands, the
push layer is untouched and only the platform backend is added.

### `GitPlatformBackend` Protocol + neutral models

Mirrors `EvaluatorBackend` (`@runtime_checkable Protocol`):

```
repo_exists(repo) -> bool                                   # parse OUTPUT (gh exits 0 for missing repo)
find_open_pr_for_branch(repo, head_branch) -> PrRef | None  # idempotency, keyed on head-branch name
create_pr(repo, head, base, title, body_markdown) -> PrRef
fetch_pr_comments(repo, pr_number) -> list[ReviewComment]   # issue-level + inline (path/line/diff_hunk)
validate_cli_installed() -> None
validate_auth() -> None
```

`@dataclass` models `RepoRef` / `PrRef` / `ReviewComment(body, path, line, diff_hunk, author,
created_at, is_inline)` keep the calibration layer **platform-unaware** — it consumes a neutral
`ReviewComment` regardless of source. There is no `ensure_repo` (creation out of scope) and no
`private` flag (we open PRs in the repo as given).

### Two CLI backends from the start: `gh` and `glab`

Both delegate auth to the CLI's keyring (zero token handling on our side) and let the CLI handle
pagination/retry/`Retry-After`. `gh api .../pulls/{n}/comments --paginate` is the escape hatch for
rich inline review comments; `glab` reaches the same data via `glab api .../merge_requests/{n}/notes`.
GitLab's semantic differences (MR≠PR, `opened`≠`open`, `--description`≠`--body`,
`--source/target-branch`≠`--head/base`, `position.new_path/new_line`≠`path/line/diff_hunk`) are
encapsulated inside `gitlab_cli.py` and normalized to the shared `ReviewComment`.

### Auto-detect the platform from the repo URL (not a config field)

The backend is **inferred** from the sink repo URL in `[calibration].repo`: host `github.com`
(or `git@github.com:`) → `gh`; host `gitlab.com` or any host containing `gitlab` → `glab`. A
self-hosted or otherwise ambiguous host is resolved by an optional `[calibration].platform =
"github" | "gitlab"` override. `create_git_backend(repo_url, platform_override)` does the detection
then the `if/elif/raise ValueError(...)` factory dispatch (mirroring
`evaluator_backends/__init__.py`). This eliminates the "backend set to GitHub but repo is on GitLab"
class of misconfiguration that a standalone `backend` field would allow.

### Preflight before any work

In order: (1) detect platform from URL + override; (2) `validate_cli_installed()` —
`shutil.which("gh"|"glab")`, and on failure a precise message (we know the platform, so we name the
right CLI + its install URL + the override hint), `raise SystemExit(1)` — mirroring
`claude_subprocess.py:51`; (3) `validate_auth()` — `gh|glab auth status` exit code; (4)
`repo_exists()` — **parsing output**, with a clear "repo does not exist; create it manually
(creation is out of MVP scope)" error. Token scope is **not** checked up front (it varies per
platform and parsing it is brittle) — a too-narrow scope surfaces as a 403/404 from the API, which
is caught and translated to "check your token scope (`gh auth refresh -s repo`)".

### Module structure (mirrors `evaluator_backends/`)

```
src/nasde_toolkit/git_platform_backends/
  __init__.py        # create_git_backend(repo_url, platform_override) — detect + factory
  protocol.py        # @runtime_checkable GitPlatformBackend + @dataclass RepoRef/PrRef/ReviewComment
  detect.py          # detect_platform(repo_url) -> "github"|"gitlab"; self-hosted + override
  github_cli.py      # GitHubCliBackend (subprocess gh + gh api escape hatch)
  gitlab_cli.py      # GitLabCliBackend (subprocess glab) — MR/notes/position -> ReviewComment
  git_ops.py         # GIT layer — push/ls-remote; subprocess git (docker.py pattern); not behind Protocol
```

## Alternatives considered

- **HTTP API via a per-platform library (PyGithub / python-gitlab / httpx + REST).** Rejected. It
  collides with ADR-002: per-platform client libraries as core dependencies bloat the dependency
  tree (the repo already manages CVE churn in transitive deps), and as optional extras they are
  forbidden by ADR-002. It also regresses the auth UX (an env-var token vs. the CLI's existing
  keyring) and forces us to write the rate-limit / `Retry-After` / pagination handling that `gh` and
  `glab` provide for free.
- **Pure git-native (no platform API).** Rejected as a whole-solution: fetching comments and
  checking PR existence (idempotency) are impossible without the API, and GitHub cannot create a PR
  via push. Git-native is, however, **adopted for the GIT layer** (push).
- **`gh` subprocess with no abstraction.** Rejected. GitLab is a stated, present requirement — the
  abstraction is not speculative. The cost is asymmetric: adding the abstraction later (after the
  calibration layer has bound itself to `gh`-shaped JSON) is far higher than adding it now.
- **A `backend = "github-cli"` config field.** Rejected in favor of URL auto-detection, which
  removes the backend≠host misconfiguration class.

## Consequences

- **Prerequisites:** `git` on PATH (already required by `docker.py`), the platform's CLI (`gh` or
  `glab`), and a completed `gh|glab auth login`. This is the same class of prerequisite as the
  evaluator's `claude`/`codex` CLI requirement (ADR-002) — consistent, not novel.
- **Zero new paradigm.** The structure is a recycling of `evaluator_backends/`, familiar to any
  reviewer of this repo.
- **GitLab ships in the MVP** as one additional backend file behind the same Protocol; the push
  layer and call sites are untouched. Bitbucket, if needed, can be an `httpx`-based backend behind
  the *same* Protocol — the Protocol does not mandate that a backend be a CLI.
- **Push does not count against platform API rate limits;** content creation relies on the CLI's
  built-in throttling, with an additional soft-throttle between PR creations when publishing a batch.
- **Trade-off:** ~5-6 small files up front, justified by the present (not hypothetical) two-platform
  requirement.
- Open (recommendations, to confirm during implementation): sync vs. async platform operations
  (recommend sync — operations are infrequent); whether `git_ops` shares a `_run_git` helper with
  `docker.py` or duplicates the pattern (recommend a separate module — distinct responsibilities).

## References

- ADR-001 (thin integration layer), ADR-002 (all deps core / CLI-not-SDK), ADR-004 (pass-through
  CLI delegation).
- `evaluator_backends/protocol.py`, `evaluator_backends/__init__.py` — the Protocol + factory pattern.
- `docker.py` — the GIT-as-subprocess pattern (worktree staging, stderr-tail `RuntimeError`).
- `claude_subprocess.py:51` — the prerequisite-not-found error message pattern.
