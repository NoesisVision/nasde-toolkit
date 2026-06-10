---
title: Assessment Criteria & Dimensions
description: How to write the rubric the reviewer scores against — define dimensions, set independent scales, and write score ladders that capture what "good" means to you.
---

The rubric is where NASDE's value lives. The rough `test.sh` answers "did it work?"; the rubric answers "how *good* is it?" — and you're the one who decides what good means. This page is how you write it.

The rubric is two files:

- **`assessment_dimensions.json`** — the axes to score on, defined once for the whole benchmark.
- **`assessment_criteria.md`** — what each score means for *this* task, written per task.

## Defining dimensions

Pick 3–5 axes that reflect what you actually care about. Each dimension declares its own `max_score` — there's no requirement that they sum to 100 or share a scale. Use whatever granularity you can genuinely distinguish.

```json
{
  "dimensions": [
    {
      "name": "domain_modeling",
      "title": "Domain Modeling",
      "max_score": 25,
      "description": "Are weather concepts modeled as value objects, with discount logic in a domain service and zero infrastructure leakage?"
    },
    {
      "name": "test_quality",
      "title": "Test Quality",
      "max_score": 20,
      "description": "Are the tests meaningful (behavior, edge cases) rather than coverage padding?"
    }
  ]
}
```

The `normalized_score` is computed from the actual sum of `max_score` values, so mixed scales (25 here, 20 there) are fine. A dimension's `description` is part of the rubric's fingerprint — change it and you start a fresh scoring cluster, because you've changed what's being measured.

## Writing the score ladder

In `assessment_criteria.md`, spell out — per dimension — what a low score looks like, what a high score looks like, and what to check in between. A **ladder** is the clearest form: concrete descriptions at each rung.

> | Score | Criteria |
> |:---:|---|
> | **0**  | No domain types — raw HTTP responses used directly in domain logic. |
> | **10** | Domain types exist but leak infrastructure (JSON annotations, HTTP codes). |
> | **15** | Clean value objects, but discount logic is *not* a domain service. |
> | **20** | Good modeling and a domain service, but error handling uses infrastructure exceptions. |
> | **25** | Value objects · discount in a domain service · failures via domain patterns · zero infrastructure deps. |

Then add **key checks** — the specific questions the reviewer should answer:

> - Is there a port for weather data in the *domain* layer?
> - Does it use domain types, not `HttpResponseMessage`?
> - Is the discount rule in a domain service, or in the HTTP adapter?

See [A Real Task](/nasde-toolkit/concepts/real-task-example/) for a full worked example across five dimensions.

## How strict should you be?

That's your call, and it's the main lever on signal quality:

- **Very strict** — enumerate a ground-truth structure and exact checks. Best when you know precisely what a correct solution looks like; gives sharp, repeatable scores.
- **Looser** — describe the qualities and leave room for judgment. Better for open-ended tasks where many good solutions exist.

Whatever you choose, write it so a careful human reviewer would score the same way. That's the bar — and [Calibrating the Rubric](/nasde-toolkit/concepts/calibration/) is how you check the judge actually meets it, tightening the wording wherever it drifts from your own grading.

## Tips

- **Score the process, not just the output.** With `include_trajectory` enabled, the reviewer can read the agent's tool-call trace — so a dimension can reward verification discipline or penalize thrashing. See [Configuring the reviewer agent](/nasde-toolkit/guides/running-benchmarks/#configuring-the-reviewer-agent).
- **Edit, then re-score, never silently mix.** Changing a dimension or its `max_score` makes a different benchmark; NASDE fingerprints the rubric so old and new scores never average together. Just re-run `nasde eval`.
- **Start with one task.** Get the rubric right on a single task before scaling — a good ladder is reusable; a vague one multiplies noise.
