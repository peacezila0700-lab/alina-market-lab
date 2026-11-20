# H09 — CROSS-SECTIONAL MEAN REVERSION (EXP-0005)

Pre-registered in `docs/PREREG_H09.md` (commit f2ce077) **before any code ran**. Run 2026-11-20T17:40:59Z. k=2 primary, tercile legs, dollar-neutral, weekly, costs charged on lagged turnover, 1000-sim random-selection null.

## P1R_EUR9 — 9 instruments, 1455 weeks (1999-W01 → 2026-W47)

| k weeks | Sharpe | CAGR | vol | maxDD | 2× cost Sharpe | WF windows positive | null mean | null p95 | null_pct |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 **(primary)** | +0.358 | +2.53% | 7.84% | 26.0% | +0.211 | 77.3% | -0.295 | 0.026 | 100.0 |
| 1 | +0.075 | +0.28% | 7.42% | 48.6% | -0.144 | 54.5% | — | — | — |
| 4 | +0.225 | +1.43% | 7.65% | 41.3% | +0.116 | 86.4% | — | — | — |
| 12 | +0.027 | -0.11% | 8.03% | 60.3% | -0.038 | 63.6% | — | — | — |

Equal-weight buy & hold on the same panel: Sharpe **+0.072**, CAGR +0.24%, maxDD 34.9%.

**Criteria (pre-registered):** A1 net sharpe gt 0.35: PASS · A2 null pct ge 95: PASS · A3 wf positive ge 60pct: PASS · A4 survives 2x cost: PASS
→ **ACCEPTED**

Cost sensitivity (post-hoc, **not** part of the verdict): net Sharpe at 0.25x assumed cost = +0.468, 0.5x assumed cost = +0.431, 0.75x assumed cost = +0.395, 1.0x assumed cost = +0.358, 1.5x assumed cost = +0.285, 2.0x assumed cost = +0.211

Walk-forward windows (5y, stepped 1y), net Sharpe:

`2000-2004: +0.15 | 2001-2005: +0.15 | 2002-2006: -0.23 | 2003-2007: -0.13 | 2004-2008: -0.06 | 2005-2009: +0.23 | 2006-2010: +0.14 | 2007-2011: +0.50 | 2008-2012: +0.52 | 2009-2013: +0.89 | 2010-2014: +0.57 | 2011-2015: +0.68 | 2012-2016: +0.72 | 2013-2017: +0.89 | 2014-2018: +0.60 | 2015-2019: +0.64 | 2016-2020: +0.40 | 2017-2021: -0.18 | 2018-2022: -0.15 | 2019-2023: +0.31 | 2020-2024: +0.29 | 2021-2025: +0.37`

## P2_MULTI12 — 12 instruments, 1403 weeks (2000-W01 → 2026-W47)

| k weeks | Sharpe | CAGR | vol | maxDD | 2× cost Sharpe | WF windows positive | null mean | null p95 | null_pct |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 **(primary)** | +0.154 | +1.13% | 19.13% | 249.3% | +0.025 | 57.1% | -0.234 | 0.088 | 98.0 |
| 1 | -0.133 | -4.35% | 19.32% | 625.2% | -0.317 | 47.6% | — | — | — |
| 4 | +0.100 | -0.03% | 20.02% | 232.7% | +0.012 | 52.4% | — | — | — |
| 12 | -0.102 | -4.12% | 20.58% | 385.6% | -0.155 | 47.6% | — | — | — |

Equal-weight buy & hold on the same panel: Sharpe **+0.546**, CAGR +5.83%, maxDD 55.3%.

**Criteria (pre-registered):** A1 net sharpe gt 0.35: FAIL · A2 null pct ge 95: PASS · A3 wf positive ge 60pct: FAIL · A4 survives 2x cost: FAIL
→ **REJECTED**

Cost sensitivity (post-hoc, **not** part of the verdict): net Sharpe at 0.25x assumed cost = +0.251, 0.5x assumed cost = +0.219, 0.75x assumed cost = +0.187, 1.0x assumed cost = +0.154, 1.5x assumed cost = +0.090, 2.0x assumed cost = +0.025

Walk-forward windows (5y, stepped 1y), net Sharpe:

`2001-2005: +0.54 | 2002-2006: +0.60 | 2003-2007: +0.20 | 2004-2008: -0.39 | 2005-2009: -0.38 | 2006-2010: -0.38 | 2007-2011: -0.45 | 2008-2012: -0.46 | 2009-2013: -0.21 | 2010-2014: -0.24 | 2011-2015: -0.42 | 2012-2016: +0.31 | 2013-2017: +0.75 | 2014-2018: +0.66 | 2015-2019: +0.64 | 2016-2020: +0.69 | 2017-2021: +0.31 | 2018-2022: -0.00 | 2019-2023: +0.35 | 2020-2024: +0.46 | 2021-2025: +0.35`

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
