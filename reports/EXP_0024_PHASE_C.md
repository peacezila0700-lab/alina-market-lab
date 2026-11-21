# EXP-0024 / EXP-0025 — Phase C 23-Year Dukascopy Bid/Ask FX Validation Suite

Generated UTC: `2026-11-21T09:51:25Z` | Script: `scripts/exp0024_eurgbp_phase_c.py`
Splits: `IS <= 2021-12-31` | `VALID 2022-01-01..2026-05-19` | `OOS_LOCKED 2026-05-20..2026-11-20`

## 1. Primary Instrument: EURGBP (23 Years, 147,297 H1 Bid/Ask Bars, Dukascopy Measured Cost)
| Rule | Split | Trades | Net Exp (pips) | Swap 0.35 Bound | PF | Win% | 95% Month-CI | Random Null Pct |
|---|---|---:|---:|---:|---:|---:|---|---|
| `H26_LIMIT_OU` | IS | 1826 | -1.8 | -2.21 | 0.89 | 56.3 | [-3.24, -0.45] | 39.7 |
| `H26_LIMIT_OU` | VALID | 386 | -0.48 | -1.04 | 0.96 | 53.9 | [-2.87, 1.84] | - |
| `H26_LIMIT_OU` | OOS | 30 | -4.28 | -5.32 | 0.67 | 43.3 | [-9.34, 3.63] | - |
| `H26_LIMIT_OU` | ALL | 2242 | -1.6 | -2.05 | 0.9 | 55.7 | [-2.79, -0.37] | - |
| `H26_MKT_COMPARE` | IS | 1981 | -2.64 | -3.05 | 0.84 | 55.2 | [-3.99, -1.33] | 13.0 |
| `H26_MKT_COMPARE` | VALID | 432 | -1.09 | -1.66 | 0.92 | 53.2 | [-3.29, 1.27] | - |
| `H26_MKT_COMPARE` | OOS | 33 | -4.27 | -5.22 | 0.67 | 42.4 | [-9.32, 3.75] | - |
| `H26_MKT_COMPARE` | ALL | 2446 | -2.38 | -2.83 | 0.85 | 54.7 | [-3.55, -1.16] | - |
| `H27_LONDON_FIX_REVERT` | IS | 2522 | -2.25 | -2.25 | 0.57 | 39.0 | [-2.7, -1.76] | 3.7 |
| `H27_LONDON_FIX_REVERT` | VALID | 611 | -2.25 | -2.25 | 0.49 | 36.0 | [-3.01, -1.45] | - |
| `H27_LONDON_FIX_REVERT` | OOS | 69 | -1.81 | -1.81 | 0.37 | 29.0 | [-2.74, -1.1] | - |
| `H27_LONDON_FIX_REVERT` | ALL | 3202 | -2.24 | -2.24 | 0.56 | 38.2 | [-2.62, -1.83] | - |
| `H28_REGIME_GUARDED` | IS | 1326 | -1.84 | -2.29 | 0.88 | 53.4 | [-3.35, -0.2] | 42.7 |
| `H28_REGIME_GUARDED` | VALID | 265 | 1.08 | 0.45 | 1.09 | 53.6 | [-1.56, 3.31] | - |
| `H28_REGIME_GUARDED` | OOS | 26 | -4.93 | -6.0 | 0.62 | 42.3 | [-12.08, 5.53] | - |
| `H28_REGIME_GUARDED` | ALL | 1617 | -1.41 | -1.9 | 0.9 | 53.2 | [-2.78, -0.12] | - |
| `H28_H1_SCALP_BASELINE` | IS | 3453 | -3.58 | -3.59 | 0.45 | 52.0 | [-4.01, -3.13] | 0.0 |
| `H28_H1_SCALP_BASELINE` | VALID | 778 | -2.42 | -2.45 | 0.56 | 54.8 | [-3.33, -1.61] | - |
| `H28_H1_SCALP_BASELINE` | OOS | 65 | -2.14 | -2.18 | 0.55 | 52.3 | [-3.22, 0.13] | - |
| `H28_H1_SCALP_BASELINE` | ALL | 4296 | -3.35 | -3.37 | 0.47 | 52.5 | [-3.77, -2.95] | - |

## 2. Multi-Broker Cost Matrix Across Full 23-Year Sample (incl. 0.15 pip/night swap)
| Pair | Rule | Dukascopy Measured | IC Markets Raw ECN | Exness Raw | Exness Standard |
|---|---|---:|---:|---:|---:|
| EURGBP | `H26_LIMIT_OU` | -1.79 (n=2242) | -1.52 | -1.42 | -1.81 |
| EURGBP | `H26_MKT_COMPARE` | -2.58 (n=2446) | -2.35 | -2.25 | -2.64 |
| EURGBP | `H27_LONDON_FIX_REVERT` | -2.24 (n=3202) | -1.16 | -1.06 | -1.45 |
| EURGBP | `H28_REGIME_GUARDED` | -1.62 (n=1617) | -1.39 | -1.29 | -1.68 |
| EURGBP | `H28_H1_SCALP_BASELINE` | -3.35 (n=4296) | -3.17 | -3.07 | -3.46 |
| EURUSD | `H26_LIMIT_OU` | -2.87 (n=2663) | -2.89 | -2.89 | -3.1 |
| EURUSD | `H26_MKT_COMPARE` | -3.49 (n=2866) | -3.55 | -3.55 | -3.76 |
| EURUSD | `H27_LONDON_FIX_REVERT` | -1.99 (n=3338) | -1.59 | -1.59 | -1.8 |
| EURUSD | `H28_REGIME_GUARDED` | -2.41 (n=1892) | -2.45 | -2.45 | -2.66 |
| EURUSD | `H28_H1_SCALP_BASELINE` | -5.87 (n=4415) | -5.96 | -5.96 | -6.17 |

## 3. Control Instrument: EURUSD (23 Years, 148,482 H1 Bid/Ask Bars, Dukascopy Measured)
| Rule | IS Exp (n) | VALID Exp (n) | OOS_LOCKED Exp (n) | ALL Exp (PF) |
|---|---|---|---|---|
| `H26_LIMIT_OU` | -3.71 (2131) | 0.32 (477) | 7.7 (55) | -2.75 (PF 0.86) |
| `H26_MKT_COMPARE` | -4.86 (2281) | 1.93 (528) | 6.92 (57) | -3.38 (PF 0.83) |
| `H27_LONDON_FIX_REVERT` | -2.24 (2617) | -1.03 (658) | -1.3 (63) | -1.99 (PF 0.76) |
| `H28_REGIME_GUARDED` | -3.25 (1523) | 0.82 (322) | 7.68 (47) | -2.29 (PF 0.87) |
| `H28_H1_SCALP_BASELINE` | -6.31 (3531) | -4.25 (801) | -2.58 (83) | -5.86 (PF 0.33) |
