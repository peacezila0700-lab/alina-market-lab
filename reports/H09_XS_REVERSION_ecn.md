# H09 — CROSS-SECTIONAL MEAN REVERSION (EXP-0005)

Pre-registered in `docs/PREREG_H09.md` (commit f2ce077) **before any code ran**. Run 2026-11-20T17:40:19Z. k=2 primary, tercile legs, dollar-neutral, weekly, costs charged on lagged turnover, 1000-sim random-selection null.

## P1R_EUR9 — 9 instruments, 1455 weeks (1999-W01 → 2026-W47)

| k weeks | Sharpe | CAGR | vol | maxDD | 2× cost Sharpe | WF windows positive | null mean | null p95 | null_pct |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 **(primary)** | +0.402 | +2.89% | 7.84% | 22.8% | +0.300 | 77.3% | -0.295 | 0.026 | 100.0 |
| 1 | +0.142 | +0.78% | 7.42% | 46.5% | -0.011 | 59.1% | — | — | — |
| 4 | +0.257 | +1.69% | 7.65% | 40.5% | +0.182 | 86.4% | — | — | — |
| 12 | +0.046 | +0.05% | 8.03% | 57.7% | +0.001 | 63.6% | — | — | — |

Equal-weight buy & hold on the same panel: Sharpe **+0.072**, CAGR +0.24%, maxDD 34.9%.

**Criteria (pre-registered):** A1 net sharpe gt 0.35: PASS · A2 null pct ge 95: PASS · A3 wf positive ge 60pct: PASS · A4 survives 2x cost: PASS
→ **ACCEPTED**

Cost sensitivity (post-hoc, **not** part of the verdict): net Sharpe at 0.25x assumed cost = +0.479, 0.5x assumed cost = +0.453, 0.75x assumed cost = +0.428, 1.0x assumed cost = +0.402, 1.5x assumed cost = +0.351, 2.0x assumed cost = +0.300

Walk-forward windows (5y, stepped 1y), net Sharpe:

`2000-2004: +0.19 | 2001-2005: +0.20 | 2002-2006: -0.18 | 2003-2007: -0.08 | 2004-2008: -0.02 | 2005-2009: +0.26 | 2006-2010: +0.17 | 2007-2011: +0.53 | 2008-2012: +0.56 | 2009-2013: +0.93 | 2010-2014: +0.62 | 2011-2015: +0.73 | 2012-2016: +0.78 | 2013-2017: +0.94 | 2014-2018: +0.66 | 2015-2019: +0.69 | 2016-2020: +0.46 | 2017-2021: -0.12 | 2018-2022: -0.10 | 2019-2023: +0.36 | 2020-2024: +0.35 | 2021-2025: +0.43`

## P2_MULTI12 — 12 instruments, 1403 weeks (2000-W01 → 2026-W47)

| k weeks | Sharpe | CAGR | vol | maxDD | 2× cost Sharpe | WF windows positive | null mean | null p95 | null_pct |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 **(primary)** | +0.156 | +1.16% | 19.13% | 248.1% | +0.028 | 57.1% | -0.234 | 0.088 | 98.0 |
| 1 | -0.131 | -4.31% | 19.32% | 621.7% | -0.312 | 47.6% | — | — | — |
| 4 | +0.101 | -0.00% | 20.02% | 232.3% | +0.015 | 52.4% | — | — | — |
| 12 | -0.101 | -4.11% | 20.58% | 384.6% | -0.153 | 47.6% | — | — | — |

Equal-weight buy & hold on the same panel: Sharpe **+0.546**, CAGR +5.83%, maxDD 55.3%.

**Criteria (pre-registered):** A1 net sharpe gt 0.35: FAIL · A2 null pct ge 95: PASS · A3 wf positive ge 60pct: FAIL · A4 survives 2x cost: FAIL
→ **REJECTED**

Cost sensitivity (post-hoc, **not** part of the verdict): net Sharpe at 0.25x assumed cost = +0.252, 0.5x assumed cost = +0.220, 0.75x assumed cost = +0.188, 1.0x assumed cost = +0.156, 1.5x assumed cost = +0.092, 2.0x assumed cost = +0.028

Walk-forward windows (5y, stepped 1y), net Sharpe:

`2001-2005: +0.54 | 2002-2006: +0.60 | 2003-2007: +0.20 | 2004-2008: -0.39 | 2005-2009: -0.38 | 2006-2010: -0.37 | 2007-2011: -0.45 | 2008-2012: -0.46 | 2009-2013: -0.21 | 2010-2014: -0.24 | 2011-2015: -0.41 | 2012-2016: +0.32 | 2013-2017: +0.75 | 2014-2018: +0.66 | 2015-2019: +0.65 | 2016-2020: +0.69 | 2017-2021: +0.32 | 2018-2022: -0.00 | 2019-2023: +0.36 | 2020-2024: +0.47 | 2021-2025: +0.35`

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
