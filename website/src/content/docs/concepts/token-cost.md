---
title: Token & Cost
description: The raw token, cost, and quality signals NASDE records per trial — and why it compares models as a Pareto front, not a single efficiency ratio.
---

A passing test tells you the agent *can* do the task. It doesn't tell you what that capability **costs**. NASDE records, for every trial, how many tokens the agent burned and what that would cost in dollars.

## The raw signals

NASDE records the raw quality, token, and cost signals you need to compare agents and models:

- **token usage** — total input + output tokens for the run (price-independent; a measure of how much the model "thinks" to reach a given quality).
- **cost (USD)** — what those tokens cost at catalog rates. The number that matters when you're choosing a model for a budget.

These appear in three places: the `nasde run` summary prints a per-`(agent, model, effort)` table (trials, score, tokens, $cost — with an inter-trial `±std` on cost and tokens once a group has 2+ trials, a bare value at n=1); `assessment_summary.json` carries them per trial; and `results-export` copies them into `metrics.json`.

## Quality vs. cost: the Pareto frontier

This is the comparison that actually drives a model choice. NASDE measures quality and cost **independently** so you can see the *trade-off* — which model gives you the best quality for your budget — instead of collapsing it into one number that hides the picture.

Why not a single "efficiency" ratio (quality per dollar)? Because that ratio has an arbitrary zero — a score of 0 means an empty rubric, which no real run reaches — so the same data can re-order which model "wins" just by shifting where you put that zero. The trade-off is shift-invariant; a single ratio is not.

So NASDE plots the raw signals as a **Pareto frontier** (quality vs. cost, and quality vs. tokens). Models on the frontier are the best available trade-offs; a model above it is overpaying for its quality, one below it is buying cheap quality. *You* pick the point on the frontier that matches your budget and quality bar.

![Quality vs cost across models and skill variants: one shared cost panel plus a per-provider token panel](../../../assets/benchmark/pareto.png)

A real example from a skill×model matrix. **Left panel — quality vs. cost (USD), all providers together**, because dollars are a fair common unit. Color is the provider, marker shape is the variant (circle = vanilla, square = with the skill), and a line links a model's variants. The shaded region is the most attractive corner (high quality, low cost). **The two right panels are quality vs. tokens, one per provider** — token counts use each provider's native tokenizer and are *not* comparable across providers, so they never share a panel. Reading the left panel, `gpt-5.4` and `sonnet-4-6` sit cheap-but-lower, `opus-4-8` buys the top score at the highest cost — which one "wins" depends entirely on where your budget and quality bar fall.

The Pareto comparison and the chart generator live in the `nasde-benchmark-runner` skill.

## A mean is never reported bare

The summary table shows `Score` as `mean ±std` across trials — the standard deviation between repeated runs (agent noise: the agent writes different code each time). A single trial reads `mean (n=1)`, an explicit single-run flag rather than a fake `±0.00`, and the `Trials` column is the sample size. The other noise source — the judge scoring the *same* code differently — is per-trial, so it lives in `metrics.json` (`score_eval_std`, `score_eval_n`, `single_eval`). Keeping the two apart is the point: is a gap bigger than the run-to-run wobble, or just noise? (Bootstrap/Bayesian significance testing is a separate, offline step — this surfaces the spread and `n` that make a mean honest.)

## How cost is computed — "as if every run were the first"

The full input volume (prompt tokens, cache included) is billed at the full catalog rate, with *no* cache discount, and the model's reasoning tokens are counted as output. This is deliberate: the prompt-token count is fixed for a task, but the cache hit rate drifts with run order and timing — so billing the full volume keeps cost **deterministic and comparable across runs**, not a function of how warm your cache happened to be.

## Where pricing comes from

Rates live in a small, versioned `pricing.toml` bundled with NASDE, each model stamped with the date and source it came from. A model entry looks like:

```toml
[models."your-model-id"]
input_per_1m = 3.0
output_per_1m = 15.0
as_of = "2026-06-08"
source = "https://…"
```

A model that isn't in the catalog still gets token metrics — only its `cost_usd` is left blank (with a warning), never a wrong number.

:::note[Editing the catalog]
The catalog is **bundled into the package**, so editing it depends on how you installed NASDE. From a source checkout (`uv sync`) you can edit `src/nasde_toolkit/pricing.toml` directly. After a PyPI install (`uv tool install` / pipx) the file lives inside an isolated environment and any edit is overwritten on the next upgrade — so for now, adding a model or correcting a rate means contributing it upstream or running from source. A per-project / per-user pricing override is a planned improvement.
:::

:::caution[Confirm rates before quoting costs]
The bundled catalog is a convenience, not a billing authority — re-check against the provider's current rate card before publishing any dollar figure.
:::
