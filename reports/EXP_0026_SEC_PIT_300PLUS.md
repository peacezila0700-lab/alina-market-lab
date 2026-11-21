# EXP-0026 — Workstream A1: Point-in-Time SEC Fundamentals Expanded (`317` US Companies)

Generated UTC: `2026-11-21T11:32:15+00:00` | Script: `scripts/exp0026_sec_pit_accruals.py`
Date range: `2015-01-02..2026-11-20` | IS `< 2022-01-01` | OOS `>= 2022-01-01` | Bonferroni bar: `99.0th` pct in BOTH IS & OOS

## 1. Main Results (`10 bp/side` Base Cost, Quarterly Rebalance, Strict `acceptanceDateTime` 16:00 ET Cutoff)
| Factor | Avg Pos | IS Sharpe (pct) | OOS Sharpe (pct) | 5bp ALL | 20bp OOS | LO OOS vs EW | BH FDR (IS/OOS) | Verdict |
|---|---:|---|---|---:|---:|---|---|---|
| `F_NEG_ACCRUALS` | 115.5 | +0.943 (99.0%) | +0.525 (90.0%) | +0.746 | +0.494 | +0.976 vs +0.996 (+4.90%/y) | False/False | **FAIL** |
| `F_CFO_ASSETS` | 115.5 | +0.359 (76.5%) | -0.691 (8.0%) | -0.066 | -0.710 | +0.761 vs +0.996 (-2.13%/y) | False/False | **FAIL** |
| `F_REV_YOY` | 112.1 | +0.237 (76.0%) | +0.512 (88.5%) | +0.382 | +0.492 | +1.044 vs +0.996 (+10.06%/y) | False/False | **FAIL** |
| `F_QUALITY_COMP` | 107.7 | +0.041 (56.5%) | -0.726 (6.0%) | -0.287 | -0.742 | +0.754 vs +0.996 (-2.40%/y) | False/False | **FAIL** |
| `F_SECTOR_NEUT_ACCRUALS` | 115.5 | +0.676 (98.0%) | +0.204 (74.5%) | +0.446 | +0.158 | +1.023 vs +0.996 (+2.79%/y) | False/False | **FAIL** |

## 2. Market-Cap & Market-Regime Sensitivity (`10 bp/side`)
| Factor | Large-Cap IS/OOS | Mid-Cap IS/OOS | Low-VIX (<=22) | High-VIX (>22) | Bull (SPY>SMA200) | Bear (SPY<=SMA200) |
|---|---|---|---|---|---|---|
| `F_NEG_ACCRUALS` | +0.657 / +0.442 | +1.022 / +0.541 | +0.939 | +0.282 | +0.927 | +0.153 |
| `F_CFO_ASSETS` | +0.484 / +0.141 | +0.116 / -1.165 | -0.251 | +0.275 | -0.358 | +0.937 |
| `F_REV_YOY` | +0.366 / +0.557 | +0.139 / +0.517 | +1.039 | -1.016 | +0.502 | -0.109 |
| `F_QUALITY_COMP` | +0.172 / -0.326 | -0.301 / -1.105 | -0.312 | -0.291 | -0.487 | +0.369 |
| `F_SECTOR_NEUT_ACCRUALS` | +0.386 / -0.228 | +1.088 / +0.571 | +0.526 | +0.145 | +0.594 | -0.169 |

## 3. Sector Breakdown (`F_NEG_ACCRUALS` & `F_SECTOR_NEUT_ACCRUALS`, `10 bp/side`)
| Factor | Sector | Firms | IS Sharpe | OOS Sharpe |
|---|---|---:|---:|---:|
| `F_NEG_ACCRUALS` | Technology | 60 | +0.364 | -0.013 |
| `F_NEG_ACCRUALS` | Industrials | 52 | +0.961 | -0.324 |
| `F_NEG_ACCRUALS` | Consumer Discretionary | 48 | -0.170 | +0.644 |
| `F_NEG_ACCRUALS` | Finance | 45 | -0.223 | -0.335 |
| `F_NEG_ACCRUALS` | Health Care | 39 | +0.585 | +0.879 |
| `F_NEG_ACCRUALS` | Utilities | 25 | +0.291 | +1.042 |
| `F_QUALITY_COMP` | Technology | 60 | +0.047 | -0.073 |
| `F_QUALITY_COMP` | Industrials | 52 | -0.093 | -0.708 |
| `F_QUALITY_COMP` | Consumer Discretionary | 48 | -0.632 | -0.292 |
| `F_QUALITY_COMP` | Finance | 45 | -0.003 | -0.179 |
| `F_QUALITY_COMP` | Health Care | 39 | -0.492 | -0.955 |
| `F_QUALITY_COMP` | Utilities | 25 | +0.057 | +0.528 |

## 4. Research Quality Control & Caveats
- **Verified Fact:** Strictly uses `available_from` honoring SEC `acceptanceDateTime` 16:00 ET cutoff + `t+1` close execution; comparative restatements never backdated.
- **Missing Evidence / Survivorship Bias:** Current top-420 Nasdaq active US-GAAP tickers omit delisted/bankrupt companies (`EXP-0026` tests cross-sectional differences across survivors rather than unconditional distressed equity returns).
