---
title: Local Repo Benchmarks
description: Build benchmarks from local (private) repositories with an auto-generated Docker environment.
---

You can build benchmarks from local (private) repositories by setting `source.git` to a relative path:

```json
{
  "source": {
    "git": "../..",
    "ref": "abc1234"
  }
}
```

NASDE auto-generates the Docker environment — no custom `Dockerfile` needed. See [`examples/nasde-dev-skill/`](https://github.com/NoesisVision/nasde-toolkit/tree/main/examples/nasde-dev-skill) for a complete example that tests nasde-toolkit itself.

The full `[nasde.source]` reference lives in [variant.toml & task.toml → Local repo benchmarks](/nasde-toolkit/reference/config-formats/#local-repo-benchmarks-nasdesource).
