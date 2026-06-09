---
title: Verifying Opik Results
description: A small Python snippet to confirm feedback scores landed in Opik after a --with-opik run.
---

```python
import urllib.request, json

req = urllib.request.Request(
    "https://www.comet.com/opik/api/v1/private/traces?project_name=<PROJECT>&limit=1",
    headers={
        "authorization": "<OPIK_API_KEY>",
        "Comet-Workspace": "<WORKSPACE>",
    },
)
resp = json.loads(urllib.request.urlopen(req).read())
scores = resp["content"][0].get("feedback_scores", [])
for s in sorted(scores, key=lambda x: x["name"]):
    print(f"  {s['name']}: {s['value']}")
```

Expected feedback scores after a full run with `--with-opik`:

- `arch_<dimension>` (e.g. `arch_domain_modeling`) — normalized 0.0-1.0
- `arch_total` — overall architecture score
- `reward` — Harbor rough-test result (0.0 or 1.0)
- `duration_sec` — trial duration
