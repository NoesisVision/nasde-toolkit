# Per-dimension significance — bootstrap (95% CI)

<!-- Auto-generated 2026-05-28 from on-disk job artifacts (examples/ddd-architectural-challenges/jobs).
     n=5 attempts per configuration (movie repo-tuned: 5 healthy after discarding env/API failures);
     6 judge evals per attempt averaged into one per-attempt score; unit of resampling = attempt.
     Tasks: Weather = ddd-weather-discount (clean DDD feature); Movie = csharp-movie-rental-anemic (legacy refactor).
     Comparisons are each configuration vs the bare model (vanilla). -->

Each configuration compared **against the bare model (vanilla)**, per quality dimension, split by task. A gap is **real** when its 95% CI (percentile bootstrap, 40,000 resamples on per-attempt means) excludes zero; **noise** when it straddles zero. Scores normalized 0–1.

## Weather

### Weather — Overall

![Weather Overall forest](../assets/forest_weather_overall.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.004 | [-0.057, +0.063] | noise |
| public | +0.069 | [+0.019, +0.120] | **real** |
| repo-tuned | +0.115 | [+0.073, +0.161] | **real** |

### Weather — Domain Modeling

![Weather Domain Modeling forest](../assets/forest_weather_domain_modeling.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | -0.001 | [-0.075, +0.069] | noise |
| public | +0.120 | [+0.067, +0.176] | **real** |
| repo-tuned | +0.155 | [+0.109, +0.205] | **real** |

### Weather — Encapsulation

![Weather Encapsulation forest](../assets/forest_weather_encapsulation.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | -0.003 | [-0.093, +0.075] | noise |
| public | +0.097 | [+0.000, +0.190] | **real** |
| repo-tuned | +0.180 | [+0.100, +0.250] | **real** |

### Weather — Architecture

![Weather Architecture forest](../assets/forest_weather_architecture_compliance.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.002 | [-0.037, +0.040] | noise |
| public | +0.030 | [-0.003, +0.067] | noise |
| repo-tuned | +0.050 | [-0.010, +0.097] | noise |

### Weather — Extensibility

![Weather Extensibility forest](../assets/forest_weather_extensibility.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.005 | [-0.048, +0.050] | noise |
| public | +0.102 | [+0.067, +0.133] | **real** |
| repo-tuned | +0.076 | [+0.004, +0.147] | **real** |

### Weather — Test Quality

![Weather Test Quality forest](../assets/forest_weather_test_quality.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.020 | [-0.164, +0.168] | noise |
| public | -0.007 | [-0.123, +0.103] | noise |
| repo-tuned | +0.097 | [+0.000, +0.200] | **real** |

## Movie

### Movie — Overall

![Movie Overall forest](../assets/forest_movie_overall.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.002 | [-0.011, +0.015] | noise |
| public | -0.020 | [-0.056, +0.021] | noise |
| repo-tuned | +0.049 | [+0.034, +0.067] | **real** |

### Movie — Domain Modeling

![Movie Domain Modeling forest](../assets/forest_movie_domain_modeling.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.012 | [-0.013, +0.036] | noise |
| public | -0.007 | [-0.045, +0.035] | noise |
| repo-tuned | +0.037 | [+0.017, +0.060] | **real** |

### Movie — Encapsulation

![Movie Encapsulation forest](../assets/forest_movie_encapsulation.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | -0.005 | [-0.038, +0.027] | noise |
| public | -0.063 | [-0.148, +0.025] | noise |
| repo-tuned | +0.078 | [+0.037, +0.127] | **real** |

### Movie — Architecture

![Movie Architecture forest](../assets/forest_movie_architecture_compliance.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.017 | [-0.033, +0.060] | noise |
| public | -0.003 | [-0.037, +0.033] | noise |
| repo-tuned | +0.120 | [+0.098, +0.138] | **real** |

### Movie — Extensibility

![Movie Extensibility forest](../assets/forest_movie_extensibility.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | +0.018 | [-0.000, +0.038] | noise |
| public | -0.009 | [-0.042, +0.033] | noise |
| repo-tuned | +0.049 | [+0.027, +0.069] | **real** |

### Movie — Test Quality

![Movie Test Quality forest](../assets/forest_movie_test_quality.png)

| vs vanilla | Δ | 95% CI | Verdict |
|---|---:|---|---|
| guided | -0.030 | [-0.068, +0.015] | noise |
| public | -0.020 | [-0.052, +0.017] | noise |
| repo-tuned | -0.035 | [-0.067, +0.000] | **real** |
