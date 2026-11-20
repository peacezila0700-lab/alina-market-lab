# RESEARCH — D1 descriptive statistics

Generated: 2026-11-20T15:24:20+00:00
Script: `scripts/descriptive_d1.py` · Data: `*_D1_clean.csv` (canonical, Sunday bars removed)

## Findings (status)

1. **Range behaviour — SUPPORTED.** EURGBP sits within ±2% of its 200dMA 65.7% of days vs 41.0% for EURUSD; Hurst 0.358 vs 0.5.
2. **Mean reversion speed — SUPPORTED.** Deviation half-life MA50 13.7d (EURGBP) vs 20.8d (EURUSD).
3. **Variance ratio < 1 — SUPPORTED** for EURGBP at 5/20/60 days (0.882/0.736/0.516).
4. **Tradeable edge from z-score — INCONCLUSIVE.** See bucket table: gross vs net columns differ by the cost assumption, and overlapping windows inflate t-stats. Requires the Stage 6/7 protocol before any claim.
5. **Day-of-week effect — WEAK/INCONCLUSIVE.** Small n per bucket, no multiple-testing correction.

## What this does NOT prove

- that a strategy makes money: no entry/exit rules, no slippage, no swap, no position sizing
- out-of-sample performance: everything above is in-sample over one 10-year window
- that the effect survives regime change: see subperiod table

> **Scope:** descriptive only. No strategy, no backtest, no OOS. Forward-return cells are **in-sample** and windows **overlap** (h-day horizon shifted daily), so t-stats are optimistic. Treat as hypothesis generation, not evidence of edge.

## EURGBP

- sample: **2592** bars, 2016-11-21 → 2026-11-20 (10.0 years)
- annualised vol: **6.45%** · skew 0.396 · kurtosis 8.26
- return autocorr (1,2,3,5,10): [-0.0433, -0.0121, -0.0305, 0.0034, -0.0445]
- Hurst (last 1500 bars): **0.358** (<0.5 = mean reverting)
- variance ratio VR(5)=0.882 · VR(20)=0.736 · VR(60)=0.516 (<1 = mean reverting)
- half-life of deviation: MA50 = **13.7d**, MA200 = 31.5d
- share of days within ±2% of MA200: **65.7%**
- volatility clustering (|r| autocorr): 0.176

| z-bucket | horizon | n | gross pips | net @0.9 | net @1.5 | win% | sd | t |
|---|---|---|---|---|---|---|---|---|
| [-9,-2) | 5d | 49 | 20.4 | 19.5 | 18.9 | 59.2 | 71.4 | 2.0 |
| [-9,-2) | 10d | 49 | 31.4 | 30.5 | 29.9 | 51.0 | 89.6 | 2.45 |
| [-9,-2) | 20d | 49 | -3.7 | -4.6 | -5.2 | 44.9 | 104.7 | -0.25 |
| [-2,-1) | 5d | 276 | 10.4 | 9.5 | 8.9 | 54.7 | 73.9 | 2.34 |
| [-2,-1) | 10d | 271 | 17.7 | 16.8 | 16.2 | 54.6 | 111.7 | 2.61 |
| [-2,-1) | 20d | 261 | 17.3 | 16.4 | 15.8 | 53.6 | 166.2 | 1.69 |
| [-1,1) | 5d | 1869 | -1.4 | -2.3 | -2.9 | 46.9 | 67.3 | -0.91 |
| [-1,1) | 10d | 1869 | -2.7 | -3.6 | -4.2 | 46.5 | 88.6 | -1.32 |
| [-1,1) | 20d | 1869 | 1.3 | 0.4 | -0.2 | 47.1 | 120.9 | 0.48 |
| [1,2) | 5d | 274 | -1.3 | -2.2 | -2.8 | 49.6 | 72.2 | -0.3 |
| [1,2) | 10d | 274 | 7.6 | 6.7 | 6.1 | 54.0 | 126.2 | 1.0 |
| [1,2) | 20d | 274 | 10.4 | 9.5 | 8.9 | 52.6 | 144.5 | 1.2 |
| [2,9) | 5d | 70 | -25.2 | -26.1 | -26.7 | 38.6 | 173.8 | -1.21 |
| [2,9) | 10d | 70 | -77.9 | -78.8 | -79.4 | 32.9 | 207.5 | -3.14 |
| [2,9) | 20d | 70 | -189.1 | -190.0 | -190.6 | 22.9 | 200.8 | -7.88 |

### stability of `z<-2, 20d` across subperiods (in-sample)

| period | n | mean pips | win% |
|---|---|---|---|
| 2016-11→2019-12 | 11 | -44.8 | 27.0 |
| 2020-01→2022-12 | 4 | -27.9 | 50.0 |
| 2023-01→2026-11 | 15 | 7.6 | 53.0 |

### mean D1 move by weekday (pips)

| weekday | n | mean pips |
|---|---|---|
| Mon | 520 | -0.7 |
| Tue | 522 | 1.4 |
| Wed | 521 | -3.1 |
| Thu | 518 | -0.1 |
| Fri | 510 | 2.1 |

## EURUSD

- sample: **2592** bars, 2016-11-21 → 2026-11-20 (10.0 years)
- annualised vol: **7.13%** · skew 0.075 · kurtosis 5.16
- return autocorr (1,2,3,5,10): [-0.0079, -0.0158, -0.0258, 0.0166, -0.0132]
- Hurst (last 1500 bars): **0.5** (<0.5 = mean reverting)
- variance ratio VR(5)=0.948 · VR(20)=0.852 · VR(60)=0.948 (<1 = mean reverting)
- half-life of deviation: MA50 = **20.8d**, MA200 = 81.0d
- share of days within ±2% of MA200: **41.0%**
- volatility clustering (|r| autocorr): 0.096

| z-bucket | horizon | n | gross pips | net @0.9 | net @1.5 | win% | sd | t |
|---|---|---|---|---|---|---|---|---|
| [-9,-2) | 5d | 40 | 56.8 | 55.9 | 55.3 | 65.0 | 105.8 | 3.4 |
| [-9,-2) | 10d | 40 | 42.5 | 41.6 | 41.0 | 62.5 | 134.2 | 2.0 |
| [-9,-2) | 20d | 40 | 48.9 | 48.0 | 47.4 | 52.5 | 151.3 | 2.04 |
| [-2,-1) | 5d | 331 | 4.4 | 3.5 | 2.9 | 53.5 | 102.3 | 0.78 |
| [-2,-1) | 10d | 328 | 8.6 | 7.7 | 7.1 | 51.5 | 138.0 | 1.12 |
| [-2,-1) | 20d | 322 | -27.6 | -28.5 | -29.1 | 42.5 | 185.8 | -2.66 |
| [-1,1) | 5d | 1737 | -3.5 | -4.4 | -5.0 | 47.3 | 107.8 | -1.34 |
| [-1,1) | 10d | 1735 | -7.6 | -8.5 | -9.1 | 47.0 | 147.6 | -2.13 |
| [-1,1) | 20d | 1731 | -4.0 | -4.9 | -5.5 | 47.3 | 205.8 | -0.81 |
| [1,2) | 5d | 338 | 12.6 | 11.7 | 11.1 | 54.1 | 120.9 | 1.91 |
| [1,2) | 10d | 338 | 35.4 | 34.5 | 33.9 | 59.2 | 167.1 | 3.9 |
| [1,2) | 20d | 338 | 51.2 | 50.3 | 49.7 | 57.7 | 230.1 | 4.09 |
| [2,9) | 5d | 92 | -7.2 | -8.1 | -8.7 | 47.8 | 89.3 | -0.77 |
| [2,9) | 10d | 92 | -0.7 | -1.6 | -2.2 | 48.9 | 120.8 | -0.05 |
| [2,9) | 20d | 92 | 61.4 | 60.5 | 59.9 | 60.9 | 182.3 | 3.23 |

### stability of `z<-2, 20d` across subperiods (in-sample)

| period | n | mean pips | win% |
|---|---|---|---|
| 2016-11→2019-12 | 17 | -74.1 | 24.0 |
| 2020-01→2022-12 | 10 | 237.9 | 100.0 |
| 2023-01→2026-11 | 6 | -54.4 | 0.0 |

### mean D1 move by weekday (pips)

| weekday | n | mean pips |
|---|---|---|
| Mon | 520 | 0.1 |
| Tue | 521 | 0.8 |
| Wed | 521 | -0.0 |
| Thu | 518 | -1.1 |
| Fri | 511 | 0.9 |
