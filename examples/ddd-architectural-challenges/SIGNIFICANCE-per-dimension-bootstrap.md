# Per-dimension significance — bootstrap (95% CI)

<!-- Auto-generated 2026-05-28 from on-disk job artifacts (examples/ddd-architectural-challenges/jobs).
     n=5 attempts per configuration (movie repo-tuned: 5 healthy after discarding env/API failures),
     6 judge evals per attempt averaged into one per-attempt score. Unit of resampling = attempt.
     Tasks: Weather = ddd-weather-discount (clean DDD feature); Movie = csharp-movie-rental-anemic (legacy refactor). -->

Percentile bootstrap (40,000 resamples) of the difference in per-attempt mean scores, per quality dimension. A gap is **real** when its 95% CI excludes zero, **noise** when it straddles zero. Scores normalized 0–1. This is the frequentist resampling method described in the post.

## Overall (normalized 0–1)

| Comparison | Task | Δ | 95% CI | Verdict |
|---|---|---:|---|---|
| vanilla → public | Weather | +0.069 | [+0.018, +0.120] | **real** |
| vanilla → repo-tuned | Weather | +0.115 | [+0.073, +0.161] | **real** |
| guided → repo-tuned | Weather | +0.111 | [+0.059, +0.168] | **real** |
| public → repo-tuned | Weather | +0.046 | [+0.003, +0.091] | **real** |
| vanilla → public | Movie | -0.020 | [-0.056, +0.021] | noise |
| vanilla → repo-tuned | Movie | +0.049 | [+0.034, +0.066] | **real** |
| guided → repo-tuned | Movie | +0.047 | [+0.035, +0.062] | **real** |
| public → repo-tuned | Movie | +0.070 | [+0.028, +0.106] | **real** |

## Per dimension

### Weather

| Comparison | Dimension | Δ | 95% CI | Verdict |
|---|---|---:|---|---|
| vanilla → public | Domain Modeling | +0.120 | [+0.067, +0.176] | **real** |
| vanilla → public | Encapsulation | +0.097 | [+0.000, +0.190] | **real** |
| vanilla → public | Architecture | +0.030 | [-0.003, +0.067] | noise |
| vanilla → public | Extensibility | +0.102 | [+0.067, +0.133] | **real** |
| vanilla → public | Test Quality | -0.007 | [-0.123, +0.103] | noise |
| vanilla → repo-tuned | Domain Modeling | +0.155 | [+0.109, +0.205] | **real** |
| vanilla → repo-tuned | Encapsulation | +0.180 | [+0.100, +0.250] | **real** |
| vanilla → repo-tuned | Architecture | +0.050 | [-0.010, +0.097] | noise |
| vanilla → repo-tuned | Extensibility | +0.076 | [+0.004, +0.147] | **real** |
| vanilla → repo-tuned | Test Quality | +0.097 | [+0.000, +0.200] | **real** |
| guided → repo-tuned | Domain Modeling | +0.155 | [+0.105, +0.216] | **real** |
| guided → repo-tuned | Encapsulation | +0.183 | [+0.115, +0.255] | **real** |
| guided → repo-tuned | Architecture | +0.048 | [-0.017, +0.103] | noise |
| guided → repo-tuned | Extensibility | +0.071 | [-0.005, +0.150] | noise |
| guided → repo-tuned | Test Quality | +0.076 | [-0.070, +0.262] | noise |
| public → repo-tuned | Domain Modeling | +0.035 | [+0.003, +0.067] | **real** |
| public → repo-tuned | Encapsulation | +0.083 | [-0.003, +0.163] | noise |
| public → repo-tuned | Architecture | +0.020 | [-0.043, +0.070] | noise |
| public → repo-tuned | Extensibility | -0.027 | [-0.093, +0.040] | noise |
| public → repo-tuned | Test Quality | +0.103 | [-0.003, +0.220] | noise |

### Movie

| Comparison | Dimension | Δ | 95% CI | Verdict |
|---|---|---:|---|---|
| vanilla → public | Domain Modeling | -0.007 | [-0.045, +0.035] | noise |
| vanilla → public | Encapsulation | -0.063 | [-0.148, +0.025] | noise |
| vanilla → public | Architecture | -0.003 | [-0.037, +0.033] | noise |
| vanilla → public | Extensibility | -0.009 | [-0.042, +0.033] | noise |
| vanilla → public | Test Quality | -0.020 | [-0.052, +0.017] | noise |
| vanilla → repo-tuned | Domain Modeling | +0.037 | [+0.016, +0.061] | **real** |
| vanilla → repo-tuned | Encapsulation | +0.078 | [+0.037, +0.127] | **real** |
| vanilla → repo-tuned | Architecture | +0.120 | [+0.098, +0.140] | **real** |
| vanilla → repo-tuned | Extensibility | +0.049 | [+0.024, +0.069] | **real** |
| vanilla → repo-tuned | Test Quality | -0.035 | [-0.067, +0.000] | **real** |
| guided → repo-tuned | Domain Modeling | +0.025 | [+0.000, +0.053] | **real** |
| guided → repo-tuned | Encapsulation | +0.083 | [+0.035, +0.137] | **real** |
| guided → repo-tuned | Architecture | +0.103 | [+0.060, +0.152] | **real** |
| guided → repo-tuned | Extensibility | +0.031 | [+0.009, +0.051] | **real** |
| guided → repo-tuned | Test Quality | -0.005 | [-0.045, +0.030] | noise |
| public → repo-tuned | Domain Modeling | +0.044 | [+0.001, +0.085] | **real** |
| public → repo-tuned | Encapsulation | +0.142 | [+0.047, +0.237] | **real** |
| public → repo-tuned | Architecture | +0.123 | [+0.087, +0.157] | **real** |
| public → repo-tuned | Extensibility | +0.058 | [+0.016, +0.093] | **real** |
| public → repo-tuned | Test Quality | -0.015 | [-0.047, +0.015] | noise |
