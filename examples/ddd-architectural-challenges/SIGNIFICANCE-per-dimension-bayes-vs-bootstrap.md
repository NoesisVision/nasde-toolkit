# Per-dimension significance — Bayesian vs bootstrap (95% CI)

<!-- Auto-generated 2026-05-28 from on-disk job artifacts (examples/ddd-architectural-challenges/jobs).
     n=5 attempts per configuration (movie repo-tuned: 5 healthy after discarding env/API failures),
     6 judge evals per attempt averaged into one per-attempt score. Unit of resampling = attempt.
     Tasks: Weather = ddd-weather-discount (clean DDD feature); Movie = csharp-movie-rental-anemic (legacy refactor). -->

For small samples the linked Wolfe article recommends **Bayesian** methods over the plain bootstrap. We computed a **Bayesian bootstrap (Rubin)** — the Bayesian analogue of the percentile bootstrap, using Dirichlet(1,…,1) weights instead of resampling with replacement — and place it **side by side** with the frequentist bootstrap.

**The point is robustness.** On every overall (aggregate) comparison the two methods give the *same* verdict, so the post's conclusions do not depend on the choice between them. Per dimension they agree almost everywhere; the only four disagreements (marked ✗ below) are all **borderline cases sitting right on zero** — bootstrap calls them "noise" (CI just touches zero, e.g. [−0.003, +0.067]) while the Bayesian bootstrap calls them "real" (CI just clears it, e.g. [+0.001, +0.064]). None of these flip a headline claim; they are exactly the close calls where any method is uncertain, and the disagreement is a hair. (A full Bayesian treatment with an explicit prior is deferred to a separate write-up.)

## Overall (normalized 0–1)

| Comparison | Task | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---|---:|---|---|:---:|
| vanilla → public | Weather | +0.069 | [+0.018, +0.121] **real** | [+0.023, +0.117] **real** | ✓ |
| vanilla → repo-tuned | Weather | +0.115 | [+0.073, +0.161] **real** | [+0.077, +0.158] **real** | ✓ |
| guided → repo-tuned | Weather | +0.111 | [+0.059, +0.168] **real** | [+0.064, +0.164] **real** | ✓ |
| public → repo-tuned | Weather | +0.046 | [+0.003, +0.092] **real** | [+0.007, +0.088] **real** | ✓ |
| vanilla → public | Movie | -0.020 | [-0.056, +0.021] noise | [-0.052, +0.020] noise | ✓ |
| vanilla → repo-tuned | Movie | +0.049 | [+0.034, +0.067] **real** | [+0.036, +0.066] **real** | ✓ |
| guided → repo-tuned | Movie | +0.047 | [+0.035, +0.063] **real** | [+0.036, +0.062] **real** | ✓ |
| public → repo-tuned | Movie | +0.070 | [+0.028, +0.106] **real** | [+0.029, +0.102] **real** | ✓ |

## Per dimension

### Weather

| Comparison | Dimension | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---|---:|---|---|:---:|
| vanilla → public | Domain Modeling | +0.120 | [+0.067, +0.176] **real** | [+0.074, +0.173] **real** | ✓ |
| vanilla → public | Encapsulation | +0.097 | [+0.000, +0.190] **real** | [+0.007, +0.183] **real** | ✓ |
| vanilla → public | Architecture | +0.030 | [-0.003, +0.067] noise | [+0.001, +0.064] **real** | ✗ |
| vanilla → public | Extensibility | +0.102 | [+0.067, +0.133] **real** | [+0.067, +0.130] **real** | ✓ |
| vanilla → public | Test Quality | -0.007 | [-0.123, +0.103] noise | [-0.117, +0.094] noise | ✓ |
| vanilla → repo-tuned | Domain Modeling | +0.155 | [+0.109, +0.205] **real** | [+0.115, +0.202] **real** | ✓ |
| vanilla → repo-tuned | Encapsulation | +0.180 | [+0.100, +0.250] **real** | [+0.103, +0.240] **real** | ✓ |
| vanilla → repo-tuned | Architecture | +0.050 | [-0.010, +0.097] noise | [-0.009, +0.089] noise | ✓ |
| vanilla → repo-tuned | Extensibility | +0.076 | [+0.004, +0.147] **real** | [+0.011, +0.140] **real** | ✓ |
| vanilla → repo-tuned | Test Quality | +0.097 | [+0.000, +0.200] **real** | [+0.010, +0.194] **real** | ✓ |
| guided → repo-tuned | Domain Modeling | +0.155 | [+0.105, +0.214] **real** | [+0.113, +0.213] **real** | ✓ |
| guided → repo-tuned | Encapsulation | +0.183 | [+0.115, +0.255] **real** | [+0.121, +0.251] **real** | ✓ |
| guided → repo-tuned | Architecture | +0.048 | [-0.017, +0.102] noise | [-0.015, +0.095] noise | ✓ |
| guided → repo-tuned | Extensibility | +0.071 | [-0.005, +0.150] noise | [+0.002, +0.144] **real** | ✗ |
| guided → repo-tuned | Test Quality | +0.076 | [-0.069, +0.262] noise | [-0.049, +0.257] noise | ✓ |
| public → repo-tuned | Domain Modeling | +0.035 | [+0.003, +0.067] **real** | [+0.005, +0.063] **real** | ✓ |
| public → repo-tuned | Encapsulation | +0.083 | [-0.003, +0.163] noise | [+0.004, +0.155] **real** | ✗ |
| public → repo-tuned | Architecture | +0.020 | [-0.043, +0.070] noise | [-0.041, +0.061] noise | ✓ |
| public → repo-tuned | Extensibility | -0.027 | [-0.093, +0.040] noise | [-0.090, +0.037] noise | ✓ |
| public → repo-tuned | Test Quality | +0.103 | [-0.003, +0.220] noise | [+0.010, +0.214] **real** | ✗ |

### Movie

| Comparison | Dimension | Δ | Bootstrap 95% CI | Bayes 95% CI | Agree? |
|---|---|---:|---|---|:---:|
| vanilla → public | Domain Modeling | -0.007 | [-0.045, +0.035] noise | [-0.042, +0.032] noise | ✓ |
| vanilla → public | Encapsulation | -0.063 | [-0.148, +0.025] noise | [-0.140, +0.019] noise | ✓ |
| vanilla → public | Architecture | -0.003 | [-0.037, +0.033] noise | [-0.033, +0.031] noise | ✓ |
| vanilla → public | Extensibility | -0.009 | [-0.042, +0.033] noise | [-0.039, +0.031] noise | ✓ |
| vanilla → public | Test Quality | -0.020 | [-0.052, +0.017] noise | [-0.048, +0.015] noise | ✓ |
| vanilla → repo-tuned | Domain Modeling | +0.037 | [+0.016, +0.060] **real** | [+0.019, +0.059] **real** | ✓ |
| vanilla → repo-tuned | Encapsulation | +0.078 | [+0.037, +0.127] **real** | [+0.042, +0.125] **real** | ✓ |
| vanilla → repo-tuned | Architecture | +0.120 | [+0.098, +0.140] **real** | [+0.100, +0.137] **real** | ✓ |
| vanilla → repo-tuned | Extensibility | +0.049 | [+0.027, +0.069] **real** | [+0.027, +0.067] **real** | ✓ |
| vanilla → repo-tuned | Test Quality | -0.035 | [-0.067, +0.000] **real** | [-0.063, -0.003] **real** | ✓ |
| guided → repo-tuned | Domain Modeling | +0.025 | [+0.000, +0.053] **real** | [+0.003, +0.052] **real** | ✓ |
| guided → repo-tuned | Encapsulation | +0.083 | [+0.035, +0.137] **real** | [+0.040, +0.135] **real** | ✓ |
| guided → repo-tuned | Architecture | +0.103 | [+0.060, +0.152] **real** | [+0.066, +0.150] **real** | ✓ |
| guided → repo-tuned | Extensibility | +0.031 | [+0.007, +0.051] **real** | [+0.009, +0.047] **real** | ✓ |
| guided → repo-tuned | Test Quality | -0.005 | [-0.047, +0.030] noise | [-0.044, +0.027] noise | ✓ |
| public → repo-tuned | Domain Modeling | +0.044 | [+0.003, +0.084] **real** | [+0.004, +0.082] **real** | ✓ |
| public → repo-tuned | Encapsulation | +0.142 | [+0.045, +0.237] **real** | [+0.053, +0.227] **real** | ✓ |
| public → repo-tuned | Architecture | +0.123 | [+0.087, +0.157] **real** | [+0.089, +0.153] **real** | ✓ |
| public → repo-tuned | Extensibility | +0.058 | [+0.016, +0.093] **real** | [+0.017, +0.088] **real** | ✓ |
| public → repo-tuned | Test Quality | -0.015 | [-0.047, +0.015] noise | [-0.045, +0.011] noise | ✓ |
