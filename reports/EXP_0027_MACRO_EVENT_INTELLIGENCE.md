# EXP-0027 — Workstream A2: Macro, Central Bank & Volatility Event Intelligence

Generated UTC: `2026-11-21T11:32:16+00:00` | IS `< 2021-01-01` | OOS `>= 2021-01-01`

## 1. Directional Prediction (OOS Ridge Regression + Circular-Shift Null, 2 bp cost)
| Target | OOS Corr | OOS Net Sharpe | Circular-Shift Pct | Verdict |
|---|---:|---:|---:|---|
| SPY 5d Forward Return | +0.0638 | +0.153 | 40.0% | **FAIL** |
| SPY 21d Forward Return | +0.0935 | +0.821 | 90.5% | **FAIL** |
| EURGBP 5d Forward Return | +0.0883 | -0.423 | 24.0% | **FAIL** |

## 2. Volatility Prediction (Strictly Out-of-Sample `>= 2021-01-01`)
- **Forward 21d Realized Vol `R²` (OOS):** `-0.0210` | **Pearson Corr:** `+0.4271`
- **Vol-Expansion Onset (`RV21_fwd > 1.35 * RV21_past`) OOS `AUC`:** `0.7212` | **Brier Skill Score:** `-0.1571`

| Central Bank Event | Events | `|Move|` Ratio vs Normal Day | Mean Signed Move (bp) |
|---|---:|---:|---:|
| FOMC Decision Day (SPY) | 132 | 1.187x | +7.78 |
| BoE Rate Change Day (EURGBP) | 26 | 1.573x | +29.29 |
| ECB Rate Change Day (EURGBP) | 30 | 0.724x | -10.03 |

## 3. Regime Classification
| Regime | Days | SPY Ann Vol (%) | Forward 21d Median (%) |
|---|---:|---:|---:|
| Normal Term Structure (slope_3m <= 1.0) | 3982 | 13.56% | +1.47% |
| Inverted Stress (slope_3m > 1.0) | 330 | 38.12% | +3.41% |
| High Financial Stress (OFR FSI > 0) | 1036 | 26.36% | +2.79% |
| Low Financial Stress (OFR FSI <= 0) | 3276 | 12.9% | +1.29% |

## 4. Risk-Sizing & Exposure Control (2 bp turnover cost)
| Strategy | Avg Exp | IS Sharpe | OOS Sharpe | ALL Sharpe | IS MaxDD | OOS MaxDD |
|---|---:|---:|---:|---:|---:|---:|
| `SPY_Buy_And_Hold` | 1.0 | +0.737 | +0.705 | +0.726 | -34.1% | -25.36% |
| `Causal_Vol_Targeting_12pct` | 0.974 | +0.769 | +0.683 | +0.739 | -16.57% | -16.18% |
| `VolTarget_Plus_MacroStress_Throttle` | 0.94 | +0.694 | +0.607 | +0.663 | -15.17% | -17.67% |
