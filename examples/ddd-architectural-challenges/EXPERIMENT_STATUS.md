# Status końcowy eksperymentu tactical-ddd

_2026-05-25. Twarde dane per atempt (hasze, tokeny, czas, wymiary) → `EXPERIMENT_LOG.md`.
Ten plik = werdykt._

**Pytanie:** czy skill DDD (publiczny + dostrojony do repo) poprawia jakość kodu, na
dwóch zadaniach — **weather** (dodanie feature do czystego DDD) i **movie** (refactor
anemic→rich, legacy). 5 wymiarów oceny. Szum sędziego ≈ 0.02–0.05 (norm).

**Konfiguracja pomiaru:** każdy wariant = **3 atempty (runy agenta) × 3 ewaluacje = 9
ocen**. Aktywacja skilla weryfikowana w trajektorii (`inv≥1`); wariant ze skillem,
który się nie uruchomił, nie liczy się jako skill.

---

## WYNIKI (mediana znormalizowana, n=3×3)

### WEATHER — skill i dostrojenie wyraźnie pomagają ✅
| wariant | mediana |
|---|---|
| **repo-tuned** | **0.92** |
| public skill | 0.85 |
| vanilla | 0.79 |

Każdy krok ~0.06–0.07, **ponad szum** → porządek realny: dostrojony > publiczny >
goły model. Na tym zadaniu zarówno sam skill, jak i jego dostrojenie do repo dają
mierzalny przeskok.

### MOVIE — skill pomaga, dostrojenie nie wygrywa ⚖️
| wariant | mediana |
|---|---|
| repo-tuned (po naprawie) | 0.62 |
| public skill | 0.60 |
| guided | 0.58 |
| vanilla | 0.56 |

Porządek monotoniczny, ale kroki ~0.02 (rząd szumu) → sąsiednie pary to **remisy**.
Skill ≈ ręczne wskazówki ≈ siebie nawzajem; wszystkie ponad goły model. Repo-tuned
NIE bije publicznego (w przeciwieństwie do weather). Jedyna realna przewaga tuned to
naprawiona architektura — owoc pętli „zmierz→diagnozuj→popraw" (tuned startował od
najgorszego wyniku, naprawa konkretnego defektu podniosła go do peletonu).

---

## DEKOMPOZYCJA WARIANCJI (σ sędziego vs σ agenta)
σ_eval = szum sędziego (ten sam kod oceniony 3×). σ_agent = szum agenta, wyizolowany
przez odjęcie (między-atemptowa − σ_eval²/E). Znormalizowane 0–1.

| wariant | mediana | σ_eval | σ_agent |
|---|---|---|---|
| movie vanilla | 0.56 | 0.038 | 0 |
| movie guided | 0.58 | 0.024 | 0 |
| movie public | 0.60 | 0.051 | 0.025 |
| movie tuned | 0.62 | 0.033 | 0 |
| weather vanilla | 0.79 | 0.037 | 0.026 |
| weather public | 0.85 | 0.016 | 0.036 |
| weather tuned | 0.92 | 0.013 | 0.023 |

**Wnioski:** (1) oba szumy są tego samego rzędu (0.01–0.05) — każdy trzeba zbijać
powtórzeniami na swoim poziomie (więcej ewaluacji ↓σ_eval, więcej atemptów ↓σ_agent).
(2) σ_agent czasem wychodzi 0 — to nie „agent deterministyczny", lecz „rozrzut między
atemptami mniejszy niż szum sędziego, nieizolowalny nawet przy 9 pomiarach". (3) Na
weather σ sędziego jest najmniejsze przy najwyższych wynikach (tuned 0.013) — sędzia
bardzo pewny. To formalnie uzasadnia werdykty: kroki ~0.02 (movie) = remis, ~0.06
(weather) = realny efekt.

---

## NARRACJA (oś = pętla dostrajania, przekaz zniuansowany)
- **weather:** dostrojony skill wygrywa wyraźnie (0.92 > 0.85 > 0.79).
- **movie:** dostrojenie samo z siebie nie wygrywa (tuned ≈ public); źle zrobione
  potrafi zaszkodzić — pętla „zmierz → zdiagnozuj → popraw" to ratuje.
- **wniosek:** mierz, nie zgaduj. Bez twardej tezy „bez tuningu nie działa" — dane jej
  nie bronią (na movie skill publiczny ≈ dostrojony).
