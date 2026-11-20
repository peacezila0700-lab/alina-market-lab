# H09 — CROSS-SECTIONAL MEAN REVERSION (EXP-0005)

Pre-registered in `docs/PREREG_H09.md` (commit f2ce077) **before any code ran**. Run 2026-11-20T17:03:19Z. k=2 primary, tercile legs, dollar-neutral, weekly, costs charged on lagged turnover, 1000-sim random-selection null.

## P1R_EUR9 — 9 instruments, 1455 weeks (1999-W01 → 2026-W47)

| k weeks | Sharpe | CAGR | vol | maxDD | 2× cost Sharpe | WF windows positive | null mean | null p95 | null_pct |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 **(primary)** | +0.343 | +2.41% | 7.84% | 27.1% | +0.181 | 77.3% | -0.295 | 0.026 | 100.0 |
| 1 | +0.052 | +0.11% | 7.42% | 49.3% | -0.191 | 50.0% | — | — | — |
| 4 | +0.214 | +1.35% | 7.65% | 41.6% | +0.095 | 86.4% | — | — | — |
| 12 | +0.021 | -0.16% | 8.03% | 61.1% | -0.051 | 63.6% | — | — | — |

Equal-weight buy & hold on the same panel: Sharpe **+0.072**, CAGR +0.24%, maxDD 34.9%.

**Criteria (pre-registered):** A1 net sharpe gt 0.35: FAIL · A2 null pct ge 95: PASS · A3 wf positive ge 60pct: PASS · A4 survives 2x cost: FAIL
→ **REJECTED**

Cost sensitivity (post-hoc, **not** part of the verdict): net Sharpe at 0.25x assumed cost = +0.464, 0.5x assumed cost = +0.424, 0.75x assumed cost = +0.383, 1.0x assumed cost = +0.343, 1.5x assumed cost = +0.262, 2.0x assumed cost = +0.181

Walk-forward windows (5y, stepped 1y), net Sharpe:

`2000-2004: +0.13 | 2001-2005: +0.14 | 2002-2006: -0.25 | 2003-2007: -0.14 | 2004-2008: -0.07 | 2005-2009: +0.23 | 2006-2010: +0.13 | 2007-2011: +0.49 | 2008-2012: +0.51 | 2009-2013: +0.88 | 2010-2014: +0.55 | 2011-2015: +0.66 | 2012-2016: +0.71 | 2013-2017: +0.87 | 2014-2018: +0.58 | 2015-2019: +0.62 | 2016-2020: +0.38 | 2017-2021: -0.20 | 2018-2022: -0.17 | 2019-2023: +0.29 | 2020-2024: +0.28 | 2021-2025: +0.35`

## P2_MULTI12 — 12 instruments, 1403 weeks (2000-W01 → 2026-W47)

| k weeks | Sharpe | CAGR | vol | maxDD | 2× cost Sharpe | WF windows positive | null mean | null p95 | null_pct |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 **(primary)** | +0.152 | +1.09% | 19.14% | 251.1% | +0.020 | 57.1% | -0.234 | 0.088 | 98.0 |
| 1 | -0.136 | -4.41% | 19.32% | 630.5% | -0.323 | 47.6% | — | — | — |
| 4 | +0.098 | -0.06% | 20.02% | 233.2% | +0.009 | 52.4% | — | — | — |
| 12 | -0.103 | -4.14% | 20.58% | 387.0% | -0.157 | 47.6% | — | — | — |

Equal-weight buy & hold on the same panel: Sharpe **+0.546**, CAGR +5.83%, maxDD 55.3%.

**Criteria (pre-registered):** A1 net sharpe gt 0.35: FAIL · A2 null pct ge 95: PASS · A3 wf positive ge 60pct: FAIL · A4 survives 2x cost: FAIL
→ **REJECTED**

Cost sensitivity (post-hoc, **not** part of the verdict): net Sharpe at 0.25x assumed cost = +0.251, 0.5x assumed cost = +0.218, 0.75x assumed cost = +0.185, 1.0x assumed cost = +0.152, 1.5x assumed cost = +0.086, 2.0x assumed cost = +0.020

Walk-forward windows (5y, stepped 1y), net Sharpe:

`2001-2005: +0.54 | 2002-2006: +0.60 | 2003-2007: +0.20 | 2004-2008: -0.39 | 2005-2009: -0.38 | 2006-2010: -0.38 | 2007-2011: -0.46 | 2008-2012: -0.46 | 2009-2013: -0.22 | 2010-2014: -0.24 | 2011-2015: -0.42 | 2012-2016: +0.31 | 2013-2017: +0.74 | 2014-2018: +0.66 | 2015-2019: +0.64 | 2016-2020: +0.69 | 2017-2021: +0.31 | 2018-2022: -0.01 | 2019-2023: +0.35 | 2020-2024: +0.46 | 2021-2025: +0.35`

## H09a overall: REJECTED (both panels must pass)

## H09b — single-asset z-fade (secondary)

| Asset | bars | Sharpe | CAGR | 2× cost | WF windows positive | null mean | null_pct | A1 | A2 | A3 | A4 |
|---|---:|---:|---:|---:|---:|---:|---:|:--:|:--:|:--:|:--:|
| AUDUSD ⚠️short | 977 | +0.981 | +6.51% | +0.886 | 0.0% | -0.101 | 99.2 | ✅ | ✅ | ❌ | ✅ |
| EURUSD | 7141 | -0.161 | -1.41% | -0.196 | 40.9% | -0.019 | 20.2 | ❌ | ❌ | ❌ | ❌ |
| GBPUSD | 5973 | +0.085 | +0.35% | -0.007 | 61.1% | -0.123 | 85.8 | ❌ | ❌ | ✅ | ❌ |
| FTSE | 6793 | +0.336 | +3.84% | +0.306 | 90.5% | -0.046 | 98.8 | ❌ | ✅ | ✅ | ✅ |

**AUDUSD** → REJECTED — **short sample (under 12 years of bars), not evidence**.

**EURUSD** → REJECTED.

**GBPUSD** → REJECTED.

**FTSE** → REJECTED.
## What this means

- H09a **failed its pre-registered bar**. Per the pre-registration there is no retuning: no other k, no different tercile, no panel cherry-picking.

- The published literature does find FX/liquidity-provision premia, but they are concentrated in the cross-section of *currency carry and liquidity risk* at institutional cost, not in a 2-week price-reversal rank at retail spread.

- **The verdict turns on cost, and only on cost.** P1R scored +0.343 against a 0.35 bar and +0.181 against a 0.20 bar at doubled cost. The sensitivity table shows it clears both thresholds if the true half-spread is ~0.75× the assumed 0.013%. That is not a rescue — the pre-registered answer is REJECTED — but it is the decision boundary, and it makes T18 (measured spreads from the owner's MT5 export) the single most valuable next action in the project.
- **Descriptive decay:** P1R's rolling 5y Sharpe was strongest 2009–2016 (+0.5 to +0.9) and has fallen to +0.28–0.35 since 2020, consistent with the post-2013 decay seen everywhere else in this project (FX microstructure got faster, spreads got tighter, the slow reversion got arbitraged).
- H09b is reported as secondary evidence only; it does not rescue H09a, and a single-asset fade with a handful of null-passing assets out of a tested cluster is exactly the multiple-testing trap this project exists to avoid.


_Artifacts: `research/artifacts/h09_xs_reversion.json`. Script: `scripts/h09_xs_reversion.py`._
