# Per-dimension significance — Bayesian bootstrap vs bootstrap (95% CI)

<!-- Auto-generated 2026-05-28 from on-disk job artifacts (examples/ddd-architectural-challenges/jobs).
     n=5 attempts per configuration (movie repo-tuned: 5 healthy after discarding env/API failures);
     6 judge evals per attempt averaged into one per-attempt score; unit of resampling = attempt.
     Tasks: Weather = ddd-weather-discount (clean DDD feature); Movie = csharp-movie-rental-anemic (legacy refactor).
     Comparisons are each configuration vs the bare model (vanilla). -->

Same comparisons (each configuration **vs the bare model**), now placing the **Bayesian bootstrap (Rubin)** — Dirichlet(1,…,1) weights instead of resampling with replacement — beside the frequentist bootstrap. For small samples Wolfe's article recommends Bayesian methods; we show both to demonstrate the verdicts don't depend on the choice. On every **Overall** comparison the two agree; per dimension they agree almost everywhere, and the few disagreements are all borderline cases sitting on zero.

## Weather

### Weather — Overall

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.004 | [-0.057, +0.063] noise | [-0.052, +0.059] noise | ✓ |
| public | +0.069 | [+0.019, +0.120] **real** | [+0.023, +0.117] **real** | ✓ |
| repo-tuned | +0.115 | [+0.073, +0.161] **real** | [+0.076, +0.158] **real** | ✓ |

### Weather — Domain Modeling

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | -0.001 | [-0.075, +0.069] noise | [-0.069, +0.062] noise | ✓ |
| public | +0.120 | [+0.067, +0.176] **real** | [+0.073, +0.172] **real** | ✓ |
| repo-tuned | +0.155 | [+0.109, +0.205] **real** | [+0.115, +0.202] **real** | ✓ |

### Weather — Encapsulation

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | -0.003 | [-0.093, +0.075] noise | [-0.088, +0.065] noise | ✓ |
| public | +0.097 | [+0.000, +0.190] **real** | [+0.008, +0.182] **real** | ✓ |
| repo-tuned | +0.180 | [+0.100, +0.250] **real** | [+0.104, +0.239] **real** | ✓ |

### Weather — Architecture

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.002 | [-0.037, +0.040] noise | [-0.034, +0.036] noise | ✓ |
| public | +0.030 | [-0.003, +0.067] noise | [+0.000, +0.064] **real** | ✗ |
| repo-tuned | +0.050 | [-0.010, +0.097] noise | [-0.011, +0.089] noise | ✓ |

### Weather — Extensibility

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.005 | [-0.048, +0.050] noise | [-0.046, +0.044] noise | ✓ |
| public | +0.102 | [+0.067, +0.133] **real** | [+0.067, +0.130] **real** | ✓ |
| repo-tuned | +0.076 | [+0.004, +0.147] **real** | [+0.010, +0.140] **real** | ✓ |

### Weather — Test Quality

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.020 | [-0.164, +0.168] noise | [-0.160, +0.151] noise | ✓ |
| public | -0.007 | [-0.123, +0.103] noise | [-0.117, +0.094] noise | ✓ |
| repo-tuned | +0.097 | [+0.000, +0.200] **real** | [+0.010, +0.193] **real** | ✓ |

## Movie

### Movie — Overall

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.002 | [-0.011, +0.015] noise | [-0.010, +0.014] noise | ✓ |
| public | -0.020 | [-0.056, +0.021] noise | [-0.052, +0.020] noise | ✓ |
| repo-tuned | +0.049 | [+0.034, +0.067] **real** | [+0.036, +0.066] **real** | ✓ |

### Movie — Domain Modeling

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.012 | [-0.013, +0.036] noise | [-0.012, +0.033] noise | ✓ |
| public | -0.007 | [-0.045, +0.035] noise | [-0.042, +0.032] noise | ✓ |
| repo-tuned | +0.037 | [+0.017, +0.060] **real** | [+0.019, +0.059] **real** | ✓ |

### Movie — Encapsulation

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | -0.005 | [-0.038, +0.027] noise | [-0.035, +0.024] noise | ✓ |
| public | -0.063 | [-0.148, +0.025] noise | [-0.140, +0.019] noise | ✓ |
| repo-tuned | +0.078 | [+0.037, +0.127] **real** | [+0.042, +0.124] **real** | ✓ |

### Movie — Architecture

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.017 | [-0.033, +0.060] noise | [-0.030, +0.054] noise | ✓ |
| public | -0.003 | [-0.037, +0.033] noise | [-0.034, +0.031] noise | ✓ |
| repo-tuned | +0.120 | [+0.098, +0.138] **real** | [+0.100, +0.137] **real** | ✓ |

### Movie — Extensibility

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | +0.018 | [-0.000, +0.038] noise | [+0.001, +0.036] **real** | ✗ |
| public | -0.009 | [-0.042, +0.033] noise | [-0.039, +0.032] noise | ✓ |
| repo-tuned | +0.049 | [+0.027, +0.069] **real** | [+0.026, +0.067] **real** | ✓ |

### Movie — Test Quality

| vs vanilla | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---:|---|---|:---:|
| guided | -0.030 | [-0.068, +0.015] noise | [-0.063, +0.012] noise | ✓ |
| public | -0.020 | [-0.052, +0.017] noise | [-0.048, +0.015] noise | ✓ |
| repo-tuned | -0.035 | [-0.067, +0.000] **real** | [-0.063, -0.002] **real** | ✓ |
