# Security Policy

Thanks for taking the time to help keep **nasde-toolkit** safe for everyone
who uses it. This document describes what we consider a vulnerability, how to
report one, and what to expect in return.

## Supported Versions

nasde-toolkit is maintained by a small team. **Only the latest released
version receives security fixes.** If you're on an older release, the upgrade
path is part of the fix.

| Version | Supported |
|---------|-----------|
| Latest release (see [CHANGELOG.md](CHANGELOG.md)) | ✅ |
| Older tagged releases                            | ❌ |
| `main` branch                                    | Best-effort (dev channel) |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for a suspected vulnerability.
Use one of the following private channels instead:

1. **Preferred — GitHub Security Advisories.**
   Open a private advisory at
   <https://github.com/NoesisVision/nasde-toolkit/security/advisories/new>.
   This gives us a shared workspace to triage the report and coordinate a fix
   without disclosing the issue to the public feed.

2. **Email.**
   If the repo security tab is not available to you, send a report to
   **<szymon@noesis-vision.com>** with the subject prefix
   `[nasde-toolkit security]`.

Please include, to the extent you can:

- A description of the issue and the impact you believe it has.
- Steps to reproduce (a minimal benchmark project or command line helps a lot).
- The nasde-toolkit version (`nasde --version`) and the platform
  (`uname -a`, Python version, container runtime).
- Your suggested severity and any proposed mitigation.

## Response Timeline

Because this project is maintained by one person most weeks, we aim for a
realistic SLA rather than a formal one:

- **Initial acknowledgement:** within **7 calendar days** of receiving a
  report.
- **Triage outcome** (confirmed / not-a-vulnerability / need-more-info):
  within **14 calendar days**.
- **Patch and release:** on a case-by-case basis. Critical and High-severity
  issues that affect the latest release are prioritized above all other work.

If you don't hear back within 7 days, please resend via the other channel —
email can get lost in spam, and GitHub notifications occasionally slip past.

## Scope

### In scope

Issues in **nasde-toolkit itself**, including:

- **CLI handling** — argument parsing, subprocess invocation, command
  injection via task / variant config files (`nasde.toml`, `task.json`,
  `variant.toml`, `harbor_config.json`, `claude_config.json`).
- **Sandbox file injection** — the `sandbox_files` mapping in the
  Configurable{Claude,Codex,Gemini} agents and the way skills / MCP configs
  are materialized inside the agent container.
- **Authentication handling** — OAuth token plumbing for `claude`, `codex`,
  and `gemini` CLIs; `scripts/export_*_oauth_token.sh`; how credentials
  cross the host/sandbox boundary.
- **Evaluator backends** — subprocess invocation of `claude -p` and
  `codex exec`, handling of trial artifacts (`assessment_eval.json`,
  trajectory files), and any path traversal or deserialization risk in
  processing them.
- **Auto-generated Dockerfile / docker-compose** — anything in
  `docker.py:ensure_task_environment()` that could let a crafted `task.json`
  escape the intended build context.
- **Reporting integrations** — Opik upload path, Harbor-span patching,
  anything that could leak secrets into external systems.

### Out of scope / report upstream

- **Vulnerabilities in transitive dependencies** (`harbor`, `opik`,
  `litellm`, etc.). Report these to the upstream project directly. We
  monitor these via `pip-audit` in CI and will upgrade promptly, but fixes
  belong upstream.
- **The `claude`, `codex`, and `gemini` CLIs themselves.** Report to
  Anthropic / OpenAI / Google respectively.
- **Issues that require an attacker to already have `nasde` running
  arbitrary local code.** nasde-toolkit runs trusted benchmark definitions
  on the user's own machine; a malicious `task.json` from an untrusted
  source is out of scope *unless* it can escape the agent sandbox or
  exfiltrate credentials beyond what running the CLI itself would allow.
- **Denial-of-service** against a user's own workstation (a task that
  consumes a lot of CPU is not a security issue).

If you're not sure whether something is in scope, send it anyway — we'd
rather review an out-of-scope report than miss a real one.

## Disclosure Policy

We follow **coordinated disclosure**:

1. You report privately via one of the channels above.
2. We confirm, work on a fix, and agree on a disclosure window with you.
3. Once a patched release is out, we publish a GitHub Security Advisory
   crediting you (unless you'd rather stay anonymous).

We do not have a fixed disclosure clock — how long we need depends on the
fix. We will keep you informed and won't sit on a confirmed issue.

## Credit

Reporters are credited in the resulting GitHub Security Advisory and in
[CHANGELOG.md](CHANGELOG.md) under the `### Security` section, unless you
ask to be left anonymous.

Thanks again.
