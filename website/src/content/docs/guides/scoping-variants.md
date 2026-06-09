---
title: Scoping a Variant to Tasks
description: Restrict a repo-specific variant to the tasks it makes sense for with a tasks scope in variant.toml.
---

Some variants only make sense for one task — for example, a skill whose code examples are *tuned to a particular repo's conventions*. Running such a variant against a different codebase produces misleading results. Declare a `tasks` scope in the variant's `variant.toml`:

```toml
agent = "claude"
model = "claude-sonnet-4-6"

# This variant's skill references this repo's value objects, so it should only
# run against that task.
tasks = ["csharp-anemic-to-rich-domain"]
```

The scope is enforced either way you run: with `--all-variants` a scoped variant runs **only** against its declared tasks (others show as `SKIPPED`); with a single `--variant`, asking for a task outside its scope aborts with a clear error rather than running against the wrong repo. Omit `tasks` (the default) for a general-purpose variant that runs everywhere.

The full `tasks` reference lives in [variant.toml & task.toml → Scoping a variant](/nasde-toolkit/reference/config-formats/#scoping-a-variant-to-specific-tasks-tasks).
