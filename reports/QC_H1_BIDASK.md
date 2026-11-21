# QC REPORT — 23-Year Dukascopy H1 Bid/Ask + ECB Official Anchor (Phase B)

Generated UTC: `2026-11-21T09:49:14Z` | Script: `scripts/qc_h1_bidask.py`

## Verdict
- **EURGBP**: `PASS` (147,297 H1 bars, `2003-08-03 17:00:00` -> `2026-11-20 18:00:00`, SHA-256 `5134b1310dafbb56...`)
- **EURUSD**: `PASS` (148,482 H1 bars, `2003-05-04 19:00:00` -> `2026-11-20 18:00:00`, SHA-256 `bb711a279b43cd5a...`)

## EURGBP Detailed Checks
| Check | Result |
|---|---|
| Total H1 Bars | 147,297 |
| Monotonic UTC / Duplicates / NaNs | True / 0 / 0 |
| Bid / Ask OHLC Violations | 0 / 0 |
| Negative Spreads / Non-positive Prices | 0 / 0 |
| Weekend/Holiday Gaps (>4h) / Long (>72h) | 1237 / 4 |
| Spread Median / P95 (pips) | 1.0 / 3.5 |
| Spread London (`08 UTC`) vs Rollover (`20 UTC`) | `1.0` pips vs **`2.6` pips** |
| **ECB Official Cross-Check (`13:00 UTC`, n=5,968d)** | Median Abs Diff = **`6.03` pips**, Daily Return Corr = **`0.8946`** |

## EURUSD Detailed Checks
| Check | Result |
|---|---|
| Total H1 Bars | 148,482 |
| Monotonic UTC / Duplicates / NaNs | True / 0 / 0 |
| Bid / Ask OHLC Violations | 0 / 0 |
| Negative Spreads / Non-positive Prices | 1 / 0 |
| Weekend/Holiday Gaps (>4h) / Long (>72h) | 1250 / 4 |
| Spread Median / P95 (pips) | 0.5 / 2.3 |
| Spread London (`08 UTC`) vs Rollover (`20 UTC`) | `0.5` pips vs **`1.3` pips** |
| **ECB Official Cross-Check (`13:00 UTC`, n=6,033d)** | Median Abs Diff = **`11.5` pips**, Daily Return Corr = **`0.8414`** |
