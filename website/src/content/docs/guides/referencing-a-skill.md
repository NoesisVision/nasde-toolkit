---
title: Referencing a Skill
description: Point a variant at a skill's source path with [[skill]] instead of copying it into the variant directory.
---

If a variant just needs to test one skill, point at its source path instead of copying it into `variants/<v>/skills/`. Add a `[[skill]]` array to the variant's `variant.toml`:

```toml
agent = "claude"
model = "claude-sonnet-4-6"

[[skill]]
path = "../../../src/plugins/my-plugin/skills/my-skill"
ref  = "abc1234"   # optional, same semantics as [nasde.source]
```

The **whole** skill directory (including `references/`) is staged into the sandbox — no copy under `variants/`. The legacy `variants/<v>/skills/<name>/` copy path still works unchanged (and now also carries `references/`, which it previously dropped).

The full `[[skill]]` reference lives in [variant.toml & task.toml → Referencing a skill](/nasde-toolkit/reference/config-formats/#referencing-a-skill-instead-of-copying-it-skill).
