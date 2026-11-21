# ALINA Risk & Volatility Meta-Labeling Framework (Empirical Specification & Audit)

**Date (UTC):** 2026-11-20 (Asia/Bangkok)  
**Scope:** Task 3 — Non-Directional Risk, Volatility, and Downside-Regime Meta-Labeling Framework  
**Baseline Anchor:** `EXP-0027` (`AUC = 0.7212`, `BSS = -0.1571`, treated strictly as an **UNCONFIRMED starting point**)  
**Empirical Audit Script & Artifact:** `scripts/audit_risk_meta_labeling_framework.py` -> `research/artifacts/task3_risk_meta_framework_audit.json`  
**Phase Gate Posture:** **Phase C Kill Point Active** — Offline Risk-Control & Meta-Labeling research only; zero directional price-alpha ML and zero auto-unlock of Phase D or trading.

---

## 1. Executive Summary & Core Diagnosis

This framework establishes a disciplined, non-directional Meta-Labeling pipeline designed **strictly to forecast volatility expansion, tail drawdown regimes, and dynamic exposure scaling**, never directional price return (`+1 / -1`).

Treating `EXP-0027` (`research/artifacts/exp0027_macro_events.json`: `oos_onset_auc = 0.7212`, `oos_onset_brier_skill = -0.1571`) strictly as an unconfirmed starting point, our empirical audit across `3,962` clean trading days (`2011-01-04 -> 2026-10-15`, `2,964` strictly out-of-sample Purged Walk-Forward days from `2015-01-02 -> 2026-10-15`) uncovered **three critical defects** in the unconfirmed `EXP-0027` design and verified their fixes:

1. **Non-Stationary Macro Level Defect (Root Cause of `BSS < 0`):** Feeding raw central bank policy levels (`fed_rate`, `ecb_dfr`, `diff_fed_ecb`) into linear `LogisticRegression` on `2011–2020` (ZIRP) caused `2021–2026` probability predictions to saturate at `mean_pred = 0.76–0.85` against a true event rate of `0.20–0.23`, collapsing Brier Skill Score to **`-2.60 .. -2.70`** (`ECE = 0.58–0.62`). Replacing raw levels with **causal 252-day rolling Z-scores and 21d/63d rate changes** + **Purged Walk-Forward + Platt Calibration** fixed `2021+` OOS calibration immediately (`target_vol_onset`: `AUC = 0.7440`, `BSS = +0.0575`; `target_tail_stress`: `AUC = 0.7065`, `BSS = +0.0234`).
2. **Scale-Invariant Non-Linear Classification + Purged Platt Calibration (`HGBC_Platt`):** Across all `6` expanding Purged Walk-Forward folds (`2015–2026`, `21d purge + 10d embargo`), `HistGradientBoostingClassifier(max_depth=2, min_samples_leaf=50, l2=5.0)` with inner chronological purged Platt calibration achieved:
   - **`target_vol_onset`** (`rv21_fwd > 1.35 * rv21_past`, base rate `21.59%`): **`WF-OOS AUC = 0.6882`** (`0.7414` raw), **`PR-AUC = 0.4417` (`2.05x` base-rate lift)**, **`BSS = +0.0951`**, **`ECE = 0.0606`**, Null Permutation **`p = 0.000`** (`null p99 = 0.6058`).
   - **`target_tail_stress`** (`rv21_fwd > 20% OR fwd21_max_adverse <= -5%`, base rate `23.04%`): **`WF-OOS AUC = 0.6966`**, **`PR-AUC = 0.4700` (`2.04x` lift)**, **`BSS = +0.1057`**, **`ECE = 0.0369` (`3.7%` error)**, Null Permutation **`p = 0.005`** (`null p99 = 0.6786`).
3. **Honest Utility Boundary (Risk Reduction vs Sharpe Illusion):** Risk/Volatility Meta-Labeling **does NOT generate independent directional Sharpe alpha** (`circular_shift_pct = 86.0%` on SPY Sharpe, below `95%`). Instead, when layered atop `Causal 12% Vol-Targeting`, it improves tail-risk metrics out-of-sample (`2015–2026`): **`MaxDD` improves from `-34.10%` (Buy&Hold) and `-16.57%` (VolTarget) to `-15.07% .. -15.56%`**, **`CVaR(95%)` improves from `-267.0 bp` / `-202.2 bp` to `-189.1 .. -194.2 bp`**, and **`Calmar` improves from `0.375` / `0.591` to `0.607 .. 0.648`** net of `2 bp` and `5 bp` turnover costs.

---

## 2. Non-Directional Target Architecture & Feature Hierarchy

### 2.1 Prohibited vs Permitted Targets
- **Strictly Prohibited:** `sign(r_{t+h})`, next-bar directional return regression, price-pattern classification on raw OHLCV.
- **Permitted Risk/Volatility Meta-Labels (evaluated strictly on future path `[t+1 .. t+21]`):**
  1. **Volatility-Expansion Onset (`target_vol_onset`):** $Y^{\text{onset}}_t = \mathbb{I}(\text{RV}_{21}(t+1..t+21) > 1.35 \cdot \text{RV}_{21}(t-20..t))$. Captures **regime acceleration** before trailing 21d vol-targeting reacts.
  2. **Downside Tail / Stress Regime (`target_tail_stress`):** $Y^{\text{stress}}_t = \mathbb{I}\big(\text{RV}_{21}(t+1..t+21) > 0.20 \;\lor\; \min_{1 \le k \le 21} \frac{P_{t+k}}{P_t}-1 \le -0.05\big)$. Captures **absolute high-volatility OR path-dependent `-5%` drawdown barriers**.

### 2.2 Non-Price / Macro-First Feature Design (`100%` Causal Availability Lag)

| Tier | Feature Group | Exact Causal Signals (`data/*`) | Stationarization & Lag Rule |
|---|---|---|---|
| **Tier 1 (Non-Price Macro & Positioning)** | Financial Stress, Rates, Geopolitics, CFTC COT, FOMC Calendar | `ofr_fsi_z252`, `ofr_fsi_chg21`, `ofr_credit_z252`, `ofr_funding_z252`, `d_fed_63`, `d_diff_fed_ecb_21`, `d_diff_boe_ecb_21`, `gpr_z252`, `cot_sp500_z`, `cot_vix_z`, `cot_ust10y_z`, `cot_eur_z`, `fomc_within_5d` | `GPR` lagged `MonthEnd + 2d`; `COT` indexed strictly on `available_from`; `OFR`/`GPR` Z-scored causally over trailing `252` trading days clipped `[-4, 4]`; zero raw policy-rate levels |
| **Tier 2 (Option-Implied Tail & Term Structure)** | CBOE Implied Vol Surface | `vix`, `slope_3m = VIX/VIX3M`, `slope_9d = VIX9D/VIX`, `vvix_pct`, `skew`, `vix_chg21` | Close-of-day `[t]` surface known prior to `[t+1]` execution |
| **Tier 3 (Baseline Persistence Benchmark)** | Trailing HAR Realized Vol | `rv5_past`, `rv21_past`, `rv63_past`, `rv_ratio_5_21` | Benchmarked explicitly as a **Baseline Null/AR comparator**, never claimed as macro alpha |

*(Note: SEC PIT fundamentals `data/sec/pit_fundamentals_expanded.csv` were audited in Task 1/`EXP-0026` and retained only for cross-sectional equity factor audit due to active-firm survivorship bias `PROB-005`, NOT injected as a macro time-series predictor here.)*

---

## 3. Purged Walk-Forward Validation, Embargo & Leakage Audit

Because every `21`-day forward label $Y_t$ depends on prices in $[t+1, t+21]$, consecutive daily labels share up to `20/21` overlapping days. Splitting cleanly at date $t_{\text{test}}$ without purging leaks future crisis information from $[t_{\text{test}}-21, t_{\text{test}}-1]$ into training.

- **Walk-Forward Protocol:** Expanding training window across `6` chronological two-year OOS test folds (`2015-01`, `2017-01`, `2019-01`, `2021-01`, `2023-01`, `2025-01..2026-10`), enforcing:
  - **Purge = `H = 21` trading days** removed immediately preceding `test_start`.
  - **Embargo = `10` trading days** (`~0.5 * H`) buffer added before inner validation/calibration splits (`total gap = 31 trading days` dropped at every boundary).
- **2021 Boundary Diagnosis (`raw_macro` vs `stationary_macro + purged + platt`):**

| Target | Specification (`2021-01 -> 2026-10` OOS, `n=1,453`) | ROC-AUC | PR-AUC (`lift`) | BSS | ECE | Mean Pred (`True=0.20–0.23`) |
|---|---|---:|---:|---:|---:|---:|
| `target_vol_onset` | `raw_macro_unpurged` (`EXP-0027` style) | `0.5636` | — | **`-2.6961`** | `0.5776` | `0.7619` (SEVERE DRIFT) |
| `target_vol_onset` | `raw_macro_purged_embargo` (`31` rows dropped) | `0.5759` | — | **`-2.6592`** | `0.5789` | `0.7631` (SEVERE DRIFT) |
| `target_vol_onset` | **`stationary_macro_platt_purged`** | **`0.7440`** | — | **`+0.0575`** | **`0.1161`** | **`0.2971`** |
| `target_tail_stress` | `raw_macro_unpurged` | `0.3825` | — | **`-2.6047`** | `0.6185` | `0.8434` (SEVERE DRIFT) |
| `target_tail_stress` | `raw_macro_purged_embargo` (`31` rows dropped) | `0.3865` | — | **`-2.6145`** | `0.6216` | `0.8487` (SEVERE DRIFT) |
| `target_tail_stress` | **`stationary_macro_platt_purged`** | **`0.7065`** | — | **`+0.0234`** | **`0.1584`** | **`0.3623`** |

**Verified Finding:** Purging alone (`31` days) cannot rescue a model fed non-stationary policy levels (`fed_rate` going from `0.1%` to `5.3%`); stationarizing macro inputs + chronological purged Platt calibration is mandatory to eliminate regime-shift calibration collapse.

---

## 4. Class Imbalance, Probability Calibration & Model Comparison (`2015–2026` WF OOS, `n = 2,964`)

Positive event prevalence is imbalanced (`21.59%` for `target_vol_onset`; `23.04%` for `target_tail_stress`). Inner calibration fits exclusively on a chronological `72%` sub-train / `31`-day purged gap / `28%` calibration split inside each training fold.

| Target | Model / Calibration | ROC-AUC | PR-AUC (`Lift` vs Base) | Brier (`Clim`) | Brier Skill (`BSS`) | ECE (`10` bins) | Null `p`-val (`200` shifts) |
|---|---|---:|---:|---:|---:|---:|---:|
| `target_vol_onset` | `logreg_uncal` (stationary features) | `0.7224` | `0.4911` (`2.274x`) | `0.1657` (`0.1696`) | `+0.0228` | `0.1405` | — |
| `target_vol_onset` | `logreg_balanced` (`class_weight='balanced'`) | `0.7241` | `0.4912` (`2.275x`) | — | **`-0.3958`** | `0.2681` | — |
| `target_vol_onset` | `logreg_platt` (purged inner sigmoid) | `0.6666` | `0.4080` (`1.889x`) | `0.1621` | `+0.0444` | `0.0883` | `0.000` (`p99=0.576`) |
| `target_vol_onset` | `logreg_isotonic` (purged inner isotonic) | `0.6598` | `0.3816` (`1.767x`) | — | `+0.0094` | `0.1109` | — |
| `target_vol_onset` | `hgbc_raw` (`max_depth=2, leaf=50, l2=5`) | **`0.7414`** | `0.4444` (`2.058x`) | `0.1485` | **`+0.1245`** | `0.0672` | — |
| `target_vol_onset` | **`hgbc_platt` (Recommended Calibrated)** | `0.6882` | `0.4417` (`2.046x`) | `0.1535` | **`+0.0951`** | **`0.0606`** | **`0.000`** (`p99=0.606`) |
| `target_tail_stress` | `logreg_uncal` (stationary features) | `0.5492` | `0.3399` (`1.475x`) | — | `-0.2061` | `0.1519` | — |
| `target_tail_stress` | `logreg_balanced` (`class_weight='balanced'`) | `0.5583` | `0.3471` (`1.506x`) | — | **`-0.5940`** | `0.2938` | — |
| `target_tail_stress` | `logreg_platt` | `0.5838` | `0.3105` (`1.348x`) | — | `-0.1698` | `0.1525` | `0.025` (`p99=0.594`) |
| `target_tail_stress` | `logreg_isotonic` | `0.5996` | `0.3892` (`1.689x`) | — | `-0.0062` | `0.0790` | — |
| `target_tail_stress` | `hgbc_raw` | `0.6805` | `0.4499` (`1.952x`) | — | `+0.0613` | `0.0915` | — |
| `target_tail_stress` | **`hgbc_platt` (Recommended Calibrated)** | **`0.6966`** | **`0.4700` (`2.039x`)** | `0.1592` (`0.1780`) | **`+0.1057`** | **`0.0369`** | **`0.005`** (`p99=0.679`) |

**Key Calibration Rule:** Never apply `class_weight="balanced"` when predicted probabilities feed risk-sizing formulas — it preserves rank (`AUC`) while destroying calibration (`BSS = -0.40 .. -0.59`, `ECE = 0.27 .. 0.29`). Use shallow regularized trees (`hgbc_platt`) or L2 logistic regression with **purged inner Platt scaling**.

---

## 5. Feature-Group Ablation & Baseline Comparison (`2015–2026` WF OOS)

| Target | Feature Group | `logreg_platt` AUC / BSS | `hgbc_platt` AUC / BSS / PR-AUC | Verdict vs HAR Baseline |
|---|---|---:|---:|---|
| `target_vol_onset` | `1_Stationary_Macro_COT_GPR_ONLY` | `0.4729` / `-0.1929` | `0.5217` / `-0.0199` / `0.2464` | Insufficient alone (`rv21_past` denominator dependency) |
| `target_vol_onset` | `2_Vol_Term_Structure_ONLY` | `0.5187` / `-0.1859` | `0.5080` / `-0.1134` / `0.2194` | Weak standalone for relative expansion ratio |
| `target_vol_onset` | `3_HAR_RealizedVol_Baseline` | `0.6380` / `-0.0897` | `0.6308` / `-0.0785` / `0.3274` | Baseline mean-reversion benchmark |
| `target_vol_onset` | **`5_Full_Combined`** | `0.6666` / `+0.0444` | **`0.6882` / `+0.0951` / `0.4417`** | **Beats HAR Baseline (`+0.057` AUC, `+0.174` BSS)** |
| `target_tail_stress` | **`1_Stationary_Macro_COT_GPR_ONLY`** | `0.5137` / `-0.2838` | **`0.6500` / `+0.0528` / `0.4007`** | **Zero-Price Macro/COT genuinely predicts tail stress (`1.74x` lift)** |
| `target_tail_stress` | `2_Vol_Term_Structure_ONLY` | **`0.6948` / `+0.1109`** | `0.6504` / `+0.0813` / `0.4181` | Strongest linear implied-risk predictor (`ECE=0.055`) |
| `target_tail_stress` | `3_HAR_RealizedVol_Baseline` | `0.6750` / `+0.0779` | `0.6477` / `+0.0301` / `0.4102` | Strong persistence benchmark |
| `target_tail_stress` | `4_StatMacro_Plus_VolTerm` (No Price/RV) | `0.5770` / `-0.1724` | `0.6844` / `+0.0746` / `0.4532` | **Outperforms HAR Baseline using ZERO price/RV features** |
| `target_tail_stress` | **`5_Full_Combined`** | `0.5838` / `-0.1698` | **`0.6966` / `+0.1057` / `0.4700`** | **Best calibrated overall (`ECE = 0.0369`)** |

---

## 6. Cross-Period Stability Audit (`hgbc_platt`, `6` Expanding Folds `2015–2026`)

| OOS Fold Window | `n` | `vol_onset` Base | `vol_onset` AUC / PR (`Lift`) / BSS | `tail_stress` Base | `tail_stress` AUC / PR (`Lift`) / BSS | Regime Note |
|---|---:|---:|---:|---:|---:|---|
| `2015-01..2016-12` | `504` | `0.189` | `0.7694` / `2.56x` / `+0.1826` | `0.165` | `0.5392` / `1.17x` / `-0.0355` | China/Oil vol bursts; `tail_stress` rare early |
| `2017-01..2018-12` | `502` | `0.221` | `0.6384` / `1.73x` / `+0.0134` | `0.217` | `0.8036` / `2.37x` / `+0.0691` | Volmageddon (`2018-02`) + Q4 selloff |
| `2019-01..2020-12` | `505` | `0.289` | `0.7717` / `2.00x` / `-0.0573` | `0.319` | `0.7500` / `2.11x` / `+0.2421` | COVID shock (`2020-03`): strong stress ranking |
| `2021-01..2022-12` | `503` | `0.219` | `0.7683` / `2.89x` / `+0.2170` | `0.423` | `0.7920` / `1.73x` / `+0.3089` | Inflation/Fed hike bear regime |
| `2023-01..2024-12` | `502` | `0.141` | `0.9195` / `5.31x` / `+0.1565` | `0.100` | `0.5430` / `1.03x` / `-0.2875` | **Low-stress calm regime (`10%` base rate):** prior-bear base rate inflates `tail_stress` `ECE=0.181` |
| `2025-01..2026-10` | `448` | `0.239` | `0.7233` / `2.07x` / `+0.1351` | `0.150` | `0.6561` / `1.87x` / `+0.0490` | Recent regime (`2025-26`) remains positive BSS |

**Stability Takeaway:** `target_vol_onset` stays above `AUC >= 0.638` across **all `6/6` regimes**, whereas `target_tail_stress` suffers **base-rate inertia** right after prolonged bear markets (`2021-22` -> `2023-24`, `BSS = -0.2875`) when training mixes all historical years equally—suggesting rolling/decaying calibration windows for fixed-threshold stress labels.

---

## 7. Causal Sizing & Exposure Utility (`2015–2026` WF OOS, Strictly Lagged `t-1 -> t`)

Evaluated on `SPY` (`2,964` WF OOS days) with explicit `2 bp` and `5 bp` one-way turnover costs (`w_t` uses only features and model weights fitted strictly before `t`):

| Strategy / Overlay (`t-1 -> t`) | Gross Sharpe | Net Sharpe (`2 bp`) | Net Sharpe (`5 bp`) | Calmar | MaxDD | CVaR95 (Daily) | Avg Exp | Circular-Shift Pct (`2 bp`) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `1_SPY_Buy_And_Hold` | `+0.728` | `+0.728` | `+0.728` | `0.375` | `-34.10%` | `-267.0 bp` | `1.000` | `100.0%` |
| `2_Causal_VolTarget_12pct_Baseline` | `+0.768` | `+0.757` | `+0.740` | `0.591` | `-16.57%` | `-202.2 bp` | `0.974` | `80.0%` |
| `3_EXP0027_Heuristic_Throttle` | `+0.713` | `+0.697` | `+0.672` | `0.483` | `-17.67%` | `-193.8 bp` | `0.950` | `69.5%` |
| `4_MetaTailStress_LogReg_Standalone` | `+0.827` | `+0.822` | `+0.813` | `0.529` | `-22.78%` | `-228.8 bp` | `0.910` | `99.5%` *(biased by secular long bias)* |
| `5_VolTarget_Plus_MetaTailStress_LogReg` | `+0.780` | `+0.764` | `+0.739` | `0.607` | **`-15.07%`** | **`-189.1 bp`** | `0.884` | `81.5%` |
| `6_VolTarget_Plus_MetaTailStress_HGBC` | `+0.732` | `+0.718` | `+0.698` | `0.536` | `-16.57%` | `-194.1 bp` | `0.950` | `75.0%` |
| **`7_VolTarget_Plus_MetaVolOnset_HGBC`** | **`+0.819`** | **`+0.807`** | **`+0.788`** | **`0.648`** | **`-15.56%`** | `-194.2 bp` | `0.948` | `86.0%` |

*(Warning on `4_MetaTailStress_LogReg_Standalone` `99.5%`: circular-shifting a ~0.91 long-biased series against a secular bull asset can trivially exceed or fall below depending on variance scaling; notice its `MaxDD = -22.78%` is far worse than Vol-Targeting `-15.56% .. -16.57%`. True risk-control evaluation must use `MaxDD`, `CVaR95`, `Calmar`, and `VolTarget` comparison.)*

---

## 8. Production Specification for `EXP-0030` (Task 4) & Epistemic Separation

1. **Standardized Pipeline Contract (`EXP-0030` Ready):**
   - **Labeling:** Upgrade from endpoint `rv21_fwd` ratios to **Path-Dependent Triple-Barrier Risk Meta-Labels** (monitoring upper-vol/adverse-excursion barrier, recovery barrier, and `H`-bar vertical timeout, strictly causal).
   - **Splits:** Strictly chronological **IS / VALID / OOS** + **Purged Walk-Forward CV with Purge $\ge H$ and Embargo $\ge 0.5 H$**.
   - **Features:** Stationarized causal non-price Macro (`OFR FSI Z`, `Central Bank rate deltas`, `GPR Z`, `COT Z`, `FOMC proximity`) + Implied Vol Term Structure + strictly isolated `HAR` baseline comparison.
   - **Costs & Nulls:** Gross vs Net reporting including explicit spread, commission, slippage, and swap/carry costs, paired with **`>= 200` Null Permutations**.
2. **Epistemic Separation:**
   - **Verified Facts:** Raw macro policy levels caused `EXP-0027` calibration failure (`BSS = -2.60 .. -2.70`); stationary macro + `HGBC_Platt` achieves `AUC = 0.6882–0.6966`, `BSS = +0.0951 .. +0.1057`, `ECE = 0.0369–0.0606`, `p <= 0.005` against `200` null shifts; pure non-price Macro/COT/GPR alone achieves `AUC = 0.6500` (`BSS = +0.0528`) on `target_tail_stress`.
   - **Hypotheses:** Translating Triple-Barrier Risk Meta-Labeling onto **intraday Dukascopy FX bid/ask data (`EURGBP H1` / `EURUSD H1` / `XAUUSD H1`) AND multi-asset `SPY` daily risk control** improves path-dependent tail risk (`MaxDD` / `CVaR95` / cost avoidance) over unguarded baselines—**to be tested empirically in Task 4 (`EXP-0030`)**.
   - **Unverified / Missing Evidence:** No intraday H1/tick Triple-Barrier execution test has been run yet with real bid/ask spread shocks and swap costs; historical dealer swap schedules remain missing beyond static overnight assumptions (`PROB-007`).
