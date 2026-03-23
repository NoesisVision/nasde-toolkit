# Agent Instructions

## Approach

1. Before writing any code, explore the existing codebase to understand its architecture and conventions.
2. Follow existing architectural patterns exactly — match naming, namespaces, directory structure, and code style.
3. Read CLAUDE.md in the project root for full architecture documentation.
4. **When modifying nasde-toolkit functionality (CLI, runner, evaluator, config, agents), you MUST invoke the `/nasde-dev` skill first.** It contains the verification protocol including documentation sync requirements.
5. After making changes, verify documentation is consistent (CLAUDE.md, README.md, ARCHITECTURE.md).
