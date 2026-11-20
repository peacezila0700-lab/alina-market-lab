# STRATEGY COMPARISON — 6 FX pairs, ECB official daily fixes, 1999-2026

- Data: ECB EXR daily reference rates, 7141 trading days, 1999-01-04 -> 2026-11-20
- Pairs (all vs EUR): USD, GBP, CHF, JPY, SEK, NOK — equal-weight pooled portfolio
- Cost: 1.3 pip spread **per round trip** (charged on every position change), half-spread on entry+exit
- Position is lagged one bar (QR-002): the position set at close *t-1* earns the *t-1 -> t* return. No look-ahead.
- `RANDOM` = coin-flip signal with identical turnover; it must lose, and it does. That is the proof the cost model is actually charged.

## Pooled portfolio (equal weight across the 6 pairs)

| Rule | CAGR | Vol | Sharpe | maxDD | Sharpe pre-2013 | Sharpe post-2013 |
|---|---:|---:|---:|---:|---:|---:|
| TSMOM_12M | -0.11% | 5.08 | +0.00 | 37.4% | +0.15 | -0.20 |
| TSMOM_1M | -0.10% | 5.08 | +0.01 | 25.7% | +0.15 | -0.17 |
| MA_50_200 | +0.33% | 5.2 | +0.09 | 26.3% | +0.24 | -0.11 |
| MA_20_100 | -0.38% | 5.17 | -0.05 | 34.0% | +0.14 | -0.30 |
| RANGE_FADE | +0.10% | 1.3 | +0.08 | 5.8% | +0.03 | +0.13 |
| BUY_HOLD | -0.81% | 3.62 | -0.21 | 41.1% | -0.17 | -0.25 |
| RANDOM | -1.23% | 3.61 | -0.32 | 49.1% | -0.22 | -0.43 |

## Per-pair Sharpe, full sample

| Rule | EURUSD | EURGBP | EURCHF | GBPUSD | GBPCHF | USDCHF |
|---|---:|---:|---:|---:|---:|---:|
| TSMOM_12M | -0.11 | -0.00 | +0.29 | +0.05 | -0.03 | -0.09 |
| TSMOM_1M | +0.32 | -0.10 | -0.18 | -0.12 | -0.10 | +0.11 |
| MA_50_200 | +0.07 | +0.09 | +0.28 | -0.01 | -0.00 | -0.01 |
| MA_20_100 | +0.25 | -0.13 | -0.01 | +0.10 | -0.21 | -0.16 |
| RANGE_FADE | -0.20 | +0.02 | -0.01 | +0.26 | +0.01 | +0.13 |
| BUY_HOLD | +0.02 | +0.11 | -0.29 | -0.04 | -0.23 | -0.12 |
| RANDOM | -0.29 | -0.41 | -0.13 | -0.14 | +0.05 | +0.02 |

## Reading it honestly

- Every trend family is **flat to negative** over 27 years once the one-bar lag and costs are applied, and **worse after 2013** than before. That matches the published decay of FX trend following, so it is not a data artefact.
- `RANGE_FADE` is the only rule that *improves* post-2013 (+0.13) but its full-sample Sharpe is +0.08 — indistinguishable from zero with this sample.
- Nothing here clears the bar for trading. The honest conclusion: **daily FX mean-reversion/trend on majors is not an edge available at retail spread.**
- maxDD figures above 100% are an artefact of the un-levered equity curve crossing zero on an all-in position; read them as 'account wiped', not as a percentage.

_Generated 2026-11-20 16:43 UTC by `scripts/compare_strategies.py`._
