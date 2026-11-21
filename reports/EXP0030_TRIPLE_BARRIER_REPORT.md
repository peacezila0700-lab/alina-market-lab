# EXP-0030 (`H33`): Path-Dependent Triple-Barrier Risk & Volatility Meta-Labeling Audit

**Date (UTC):** `2026-11-21`  
**Experiment / Hypothesis ID:** `EXP-0030` / `H33` (`scripts/exp0030_triple_barrier_risk_meta.py`, `research/artifacts/exp0030_triple_barrier.json`)  
**Phase Gate Status:** **`PHASE_C_KILL_POINT_ACTIVE_OFFLINE_ONLY`** — Phase D ML and Live/Demo automated trading remain **STRICTLY PARKED**.  
**Pre-Registered Objective:** Test whether path-dependent Triple-Barrier meta-labeling (López de Prado *AFML* Ch. 3 formulation adapted strictly to **non-directional risk/cost-shock gating**, without searching for directional price alpha or tuning hyperparameters on OOS) beats naive causal baselines across:
1. **Track A (`SPY` Daily, `2011-04-05 -> 2026-09-16`):** Predicting stop/stress barrier hits with stationary macro + vol-term-structure + HAR features under strict `Purge=21d + Embargo=10d = 31d` separation, Platt calibration, `200` circular-shift null tests, and explicit `5 bp` / `10 bp` transaction + `Fed + 50 bp` leverage-borrow costs.
2. **Track B (`EURGBP H1` Dukascopy Bid/Ask, `2003-08-06 -> 2026-11-20`, `147,217` clean bars):** Predicting `6h` intraday liquidity/volatility shocks (`spread >= 3.0 pips` OR `6h excursion >= 1.50 * sigma_6h`) under strict `Purge=6h + Embargo=6h = 12h` separation, real measured Dukascopy Bid/Ask quotes, `0.70 pip` RT commission, `0.30 pip` RT slippage, and `BoE-ECB` swap (`3x` Wed) minus `0.25 pip/night` retail markup.

---

## 1. Epistemic Summary & Headline Verdict

| Track & Target | OOS AUC | OOS PR-AUC (Lift) | OOS BSS | OOS ECE | 5-Fold Purged WF AUC (`2015–26`) | Null Perm `p` | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| **Track A1 (`SPY`): `TB_VolNorm` (`-2.0s` hit before `+2.5s`)** | `0.6432` | `0.1480` (`1.91x`) | `+0.0235` | `0.0376` | **`0.4685`** (`BSS -0.1091`) | `0.120` OOS / **`0.680` WF** | **FAIL** (Directional barrier race collapses to coin flip) |
| **Track A2 (`SPY`): `TB_CapitalDD5` (`-5%` hit before `+5%`)** | `0.5932` | `0.1813` (`1.23x`) | `+0.0303` | `0.0892` | **`0.5419`** (`BSS -0.0383`) | `0.215` OOS / **`0.210` WF** | **FAIL** (Worse than `HAR` baseline `0.6111` OOS) |
| **Track A3 (`SPY`): `TB_NonDirStress` (`-5%` DD OR `RV21 > 20%`)** | `0.6164` | `0.2401` (`1.57x`) | **`+0.1984`** | `0.1428` | **`0.6641`** (`BSS +0.0837, ECE 0.0393`) | `0.180` OOS / **`0.000` WF** | **MIXED / WF-PASS** (Significant multi-cycle stress separation; tail-CVaR compression `-12.8%`) |
| **Track B (`EURGBP H1`): Combined `6h` Risk Shock** | **`0.8545`** | `0.8100` (`2.17x`) | **`+0.3940`** | **`0.0433`** | *Chrono OOS (`n=36,705`)* | **`0.000`** (`p99=0.8175`) | **RISK-GATE PASS / TRADING FAIL** (Shock cut `34.9% -> 16.1%`; net FX still `-2.102 pips/trade`) |
| **Track B Ablation: `Clock_Only` (`sin/cos hr, dow`)** | `0.8567` | `0.8199` (`2.20x`) | `+0.3508` | `0.1107` | *Chrono OOS (`n=36,705`)* | — | **EXPOSED**: `90%+` of Track B raw AUC is deterministic rollover-entry clock |
| **Track B Ablation: `State_Only_NoClock` (spread/ATR/OFR)** | **`0.6692`** | `0.4886` (`1.31x`) | **`+0.0603`** | `0.0994` | *Chrono OOS (`6h non-overlap=0.6530`)* | **`0.000`** (`p99=0.6418`) | **STATE-SIGNAL CONFIRMED** (Genuine non-clock spread/vol predictability) |

### Key Scientific Discovery from `EXP-0030`
1. **Why Directional Triple-Barrier Labeling Fails While Non-Directional Volatility/Drawdown Labeling Succeeds:**  
   When a Triple-Barrier label encodes **which barrier touches first** (`A1: -2.0*sigma` before `+2.5*sigma`, or `A2: -5%` before `+5%`), it implicitly turns the target into a **directional path race** (`sign(path)`). Across `2015–2026` 5-fold Purged WF (`N=2,943`), `HGBC_Platt_Combined` collapses to **`AUC = 0.4685` (`perm_p = 0.680`)** on `TB_VolNorm` and **`AUC = 0.5419` (`perm_p = 0.210`)** on `TB_CapitalDD5` — empirically confirming ALINA's core `EXP-0001..0029` finding that **equity direction/first-passage races cannot be reliably timed**.  
   By contrast, removing the directional race (`A3: TB_NonDirStress`, touching `-5%` drawdown OR breaching `20%` realized volatility within `21d`) restores full-cycle 5-fold Purged WF significance (**`AUC = 0.6641`, `PR-AUC = 0.4585 [1.819x]`, `BSS = +0.0837`, `ECE = 0.0393`, `perm_p = 0.000`** vs `null_p99 = 0.6389`), matching our Task 3 `target_vol_onset` (`0.6882`) and `target_tail_stress` (`0.6966`) results.
2. **Diurnal Schedule vs State-Dependent Risk Decomposition on `23y` FX (`Track B`):**  
   A naive `Avoid_Rollover_20_23_UTC` filter *worsened* `6h` shock exposure (`39.3%` vs `34.9%` unfiltered) because trades entered at `15:00–19:00 UTC` walk straight into Dukascopy's `21:00–22:00 UTC` rollover widening inside `[t+1..t+6]`. An explicit ablation exposed that `Clock_Only` captures `AUC = 0.8567` from predicting whether the next `6h` window intersects rollover, while `State_Only_NoClock` (spread level, `72h` spread z-score, `ATR` ratio, `OFR FSI`) delivers genuine non-calendar skill (**`OOS AUC = 0.6692`, `BSS = +0.0603`, `perm_p = 0.000`**), and `Combined_HGBC_Platt` achieves the best probability calibration (**`ECE = 0.0433`, `BSS = +0.3940`**). Yet even inside the gated lowest-risk 70% cohort, **net FX expectancy remains `-2.102 pips/trade`**, keeping Phase C Kill Point firmly locked.

---

## 2. Leakage, Temporal Integrity & Canary Verification

* **[Verified Fact — Track A Chronological Splits]:**
  * `IS`: `2011-04-05 -> 2018-11-13` (`n = 1,917`)
  * `VALID`: `2019-01-02 -> 2022-11-15` (`n = 977`, includes COVID crash + 2022 rate bear)
  * `OOS`: `2023-01-03 -> 2026-09-16` (`n = 929`, calm/bull regime, low stress base rate `7.75%–15.29%`)
  * `Purge + Embargo`: `21d + 10d = 31` trading days; programmatic assertion verified actual gaps **`is_to_valid = 32` bars** and **`valid_to_oos = 32` bars** (`purged_gap_assertion_passed = True`).
* **[Verified Fact — Shuffled-Label Canary Check]:** Fitting `HGBC` on `5` randomly shuffled IS target seeds (`995..999`) produced **`OOS AUC = 0.4877`** (`canary_expected_near_0_50 = True`), confirming zero label or macro-alignment leakage.
* **[Verified Fact — Track B Chronological Splits (`EURGBP H1` `147,217` bars)]:**
  * `IS`: `2003-08-06 -> 2015-12-31` (`n = 79,330`)
  * `VALID`: `2016-01-04 -> 2020-12-31` (`n = 31,158`)
  * `OOS`: `2021-01-04 -> 2026-11-20` (`n = 36,705`)
  * `Purge + Embargo`: `6h + 6h = 12` H1 bars between `IS -> VALID` and `VALID -> OOS`; all macro daily covariates (`BoE-ECB`, `OFR FSI`) explicitly lagged `t-1` day (`shift(1)`).

---

## 3. Track A Detailed Empirical Results (`SPY` Daily Triple-Barrier)

### 3.1 Classification Metrics Across Targets & Feature Sets

| Target | Model (`Platt` on `VALID`) | `IS` AUC | `VALID` AUC | `OOS` AUC (`2023–26`) | `OOS` PR (Lift) | `OOS` BSS | `OOS` ECE | `OOS` Perm `p` | `5-Fold WF` AUC (Perm `p`) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`A1: TB_VolNorm`** (`8.4%` IS / `11.4%` VAL / `7.8%` OOS) | `HGBC_Platt_Combined` | `0.9677` | `0.6699` | `0.6432` | `0.1480` (`1.91x`) | `+0.0235` | `0.0376` | `0.120` | **`0.4685`** (`0.680`) |
| `A1: TB_VolNorm` | `LogReg_Platt_Combined` | `0.8202` | `0.7082` | `0.5604` | `0.1110` (`1.43x`) | `-0.0667` | `0.0799` | `0.335` | — |
| `A1: TB_VolNorm` | `HGBC_Platt_MacroVol_NoPrice` | `0.9607` | `0.5903` | `0.5327` | `0.0805` (`1.04x`) | `+0.0041` | `0.0277` | `0.385` | — |
| `A1: TB_VolNorm` | `HAR_Persistence_Baseline` | `0.6844` | `0.7040` | `0.6039` | `0.2226` (`2.87x`) | `-0.0360` | `0.0761` | `0.215` | — |
| **`A2: TB_CapitalDD5`** (`15.5%` / `25.3%` / `14.8%`) | `HGBC_Platt_Combined` | `0.9497` | `0.5457` | `0.5932` | `0.1813` (`1.23x`) | `+0.0303` | `0.0892` | `0.215` | **`0.5419`** (`0.210`) |
| `A2: TB_CapitalDD5` | `LogReg_Platt_Combined` | `0.7654` | `0.5636` | `0.5912` | `0.1635` (`1.11x`) | `+0.0015` | `0.1101` | `0.130` | — |
| `A2: TB_CapitalDD5` | `HGBC_Platt_MacroVol_NoPrice` | `0.9471` | `0.5522` | `0.6010` | `0.1790` (`1.21x`) | `+0.0392` | `0.0826` | `0.180` | — |
| `A2: TB_CapitalDD5` | `HAR_Persistence_Baseline` | `0.6857` | `0.5883` | **`0.6111`** | `0.1957` (`1.33x`) | `+0.0183` | `0.0967` | `0.070` | — |
| **`A3: TB_NonDirStress`** (`18.8%` / `39.4%` / `15.3%`) | `HGBC_Platt_Combined` | `0.9580` | `0.7034` | **`0.6164`** | `0.2401` (`1.57x`) | **`+0.1984`** | `0.1428` | `0.180` | **`0.6641`** (`0.000`) |
| `A3: TB_NonDirStress` | `LogReg_Platt_Combined` | `0.8160` | `0.6523` | `0.6156` | `0.2173` (`1.42x`) | `+0.0601` | `0.2174` | `0.105` | — |
| `A3: TB_NonDirStress` | `HGBC_Platt_MacroVol_NoPrice` | `0.9518` | **`0.7196`** | `0.5885` | `0.2241` (`1.47x`) | `+0.1976` | `0.1316` | `0.215` | — |
| `A3: TB_NonDirStress` | `HAR_Persistence_Baseline` | `0.7426` | `0.6952` | `0.6029` | `0.2492` (`1.63x`) | `+0.1504` | `0.1693` | `0.145` | — |

**Diagnostic Notes:**
* Notice how `IS` `HGBC` (`0.95–0.97`) overfits vs `LogReg` (`0.77–0.82`), and in calm `OOS (2023–26)` (`~44` 21d blocks, low base rate), **single-split OOS AUC confidence intervals are wide** (`null_p99 ~ 0.70–0.77`), so none of the single-split `2023–26` AUCs reach `perm_p < 0.05`.
* Only when evaluated across the full `11.7-year` multi-regime `5-Fold Purged WF` (`2015–2026`, `n=2,943`) does `TB_NonDirStress` (`AUC = 0.6641, PR = 0.4585 [1.819x], BSS = +0.0837, ECE = 0.0393, perm_p = 0.000`) separate cleanly from the directional barrier races (`0.4685` and `0.5419`, both `perm_p >= 0.21`).

### 3.2 Causal Portfolio Utility — Gross vs Net (`5 bp` + `Fed+50 bp` Borrow & `10 bp` Stress)

**`VALID (2019-01-02 -> 2022-11-15)` — COVID Crash & 2022 Rate Bear:**

| Strategy (`t-1` causal weights) | Gross Sh | Net `5 bp` Sh | `10 bp` Stress Sh | Ann Ret (`Net 5bp`) | MaxDD (`Net`) | Calmar | `CVaR95` | Avg Exp | Tx Drag | Borrow Drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `1_Buy_And_Hold` | `+0.644` | `+0.644` | `+0.644` | `+14.63%` | `-34.10%` | `0.429` | `-355.6 bp` | `1.000` | `0.0 bp/y` | `0.0 bp/y` |
| `2_Causal_VolTarget_12pct_Baseline` | `+0.740` | `+0.700` | `+0.669` | `+9.31%` | `-16.31%` | `0.571` | `-218.0 bp` | `0.837` | `36.9 bp/y` | `16.3 bp/y` |
| `3_TB_DD5_MetaOnly_HGBC` | `+0.672` | `+0.668` | `+0.663` | `+13.46%` | `-30.03%` | `0.448` | `-315.0 bp` | `0.920` | `9.4 bp/y` | `0.0 bp/y` |
| `4_VolTarget_Plus_TB_VolNorm_HGBC` | `+0.744` | `+0.703` | `+0.670` | `+9.27%` | `-15.52%` | **`0.597`** | `-215.3 bp` | `0.826` | `39.8 bp/y` | `14.4 bp/y` |
| `5_VolTarget_Plus_TB_CapitalDD5_HGBC` | `+0.744` | **`+0.705`** | **`+0.671`** | `+8.60%` | **`-15.17%`** | `0.567` | `-199.8 bp` | `0.774` | `37.6 bp/y` | `10.9 bp/y` |
| `6_VolTarget_Plus_TB_NonDirStress_HGBC` | `+0.730` | `+0.679` | `+0.634` | `+7.82%` | `-16.04%` | `0.488` | **`-190.1 bp`** | `0.750` | `48.4 bp/y` | `10.9 bp/y` |

**`OOS (2023-01-03 -> 2026-09-16)` — Low-Stress Equity Bull:**

| Strategy (`t-1` causal weights) | Gross Sh | Net `5 bp` Sh | `10 bp` Stress Sh | Ann Ret (`Net 5bp`) | MaxDD (`Net`) | Calmar | `CVaR95` | Avg Exp | Tx Drag | Borrow Drag | Shift Pct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `1_Buy_And_Hold` | `+1.303` | `+1.303` | `+1.303` | `+19.54%` | `-19.00%` | `1.029` | `-205.2 bp` | `1.000` | `0.0` | `0.0` | `100.0%` |
| `2_Causal_VolTarget_12pct_Baseline` | `+1.102` | `+1.030` | `+0.994` | `+13.36%` | `-15.18%` | `0.880` | `-193.2 bp` | `0.981` | `42.3` | `51.1` | `15.0%` |
| `3_TB_DD5_MetaOnly_HGBC` | `+1.318` | `+1.311` | `+1.303` | `+18.15%` | `-17.59%` | `1.032` | `-189.5 bp` | `0.945` | `10.1` | `0.0` | `75.5%` |
| `4_VolTarget_Plus_TB_VolNorm_HGBC` | `+1.127` | `+1.054` | `+1.018` | `+13.59%` | `-14.62%` | `0.930` | `-191.3 bp` | `0.980` | `42.6` | `50.9` | `21.0%` |
| `5_VolTarget_Plus_TB_CapitalDD5_HGBC` | `+1.107` | `+1.036` | `+0.997` | `+12.66%` | `-14.27%` | `0.887` | **`-182.1 bp`** | `0.932` | `44.4` | `42.1` | `18.5%` |
| `6_VolTarget_Plus_TB_NonDirStress_HGBC` | `+1.049` | `+0.967` | `+0.922` | `+11.94%` | **`-13.95%`** | `0.856` | `-186.2 bp` | `0.950` | `50.4` | `50.5` | `14.5%` |

**Interpretation:** Even with explicit `5 bp` turnover and `Fed + 50 bp` financing drag (`~93–101 bp/yr` combined drag during 5% Fed rates in `2023–26` when Vol-Targeting leverages above `1.0x`), adding calibrated risk meta-throttles consistently compresses OOS `MaxDD` (`-19.00% -> -13.95% / -14.27%`) and `CVaR95` (`-205.2 bp -> -182.1 / -186.2 bp`), and in `2019–22` slashed COVID/2022 `CVaR95` from `-355.6 bp` to **`-190.1 bp` (`-46.5%`)**. Crucially, **zero overlays clear the `95%` circular-shift Sharpe bar** (`14.5%–75.5%`), proving these tools belong strictly to **risk & tail-loss engineering, not alpha generation**.

---

## 4. Track B Detailed Empirical Results (`EURGBP H1` `23y` Bid/Ask Intraday)

### 4.1 Classification & Diurnal vs State Ablation (`OOS 2021-01-04 -> 2026-11-20`, `n=36,705`, base rate `37.35%`)

| Model / Ablation | `ROC-AUC` | `PR-AUC` (`Lift`) | `Brier` | `BSS` | `ECE` | `Mean Pred` | Non-Overlap `6h` Null Perm `p` (`p99`) |
|---|---:|---:|---:|---:|---:|---:|---|
| **`Combined_HGBC_Platt`** (Clock + Spread/ATR + Macro) | **`0.8545`** | `0.8100` (`2.169x`) | **`0.1441`** | **`+0.3940`** | **`0.0433`** | `0.3302` | **`0.000`** (`obs=0.8678`, `p99=0.8175`) |
| `Clock_Only_Ablation` (`sin_hr, cos_hr, is_rollover, dow`) | `0.8567` | `0.8199` (`2.195x`) | `0.1533` | `+0.3508` | `0.1107` | `0.3209` | — *(deterministic diurnal rollover schedule)* |
| **`State_Only_NoClock_Platt`** (spread, `z72`, `ATR`, `OFR FSI`, `BoE-ECB`) | **`0.6692`** | `0.4886` (`1.308x`) | `0.2234` | **`+0.0603`** | `0.0994` | `0.3203` | **`0.000`** (`obs=0.6530`, `p99=0.6418`) |
| `Simple_Linear_Baseline` (`is_rollover, spread, sigma_6h`) | `0.5362` | `0.4129` (`1.105x`) | `0.2440` | `-0.0330` | `0.1067` | `0.2706` | — |

### 4.2 Non-Overlapping `6h` Execution Cost Survival (`OOS 2021–2026`, `n=6,118` brackets)
Symmetric execution bracket (`SL = TP = 1.0 * sigma_6h`, `H = 6h`, Dukascopy measured Bid/Ask + `0.70p` RT comm + `0.30p` RT slip + `BoE-ECB` swap minus `0.25p` retail markup):

| Execution Gating Cohort | `N` Trades | Shock Rate | Gross Mean (`pips`) | Net Mean (`pips`) | Cost Drag (`pips/trade`) |
|---|---:|---:|---:|---:|---:|
| `Always_Execute_Unfiltered` | `6,118` | `34.86%` | `-0.531 p` | `-2.738 p` | `2.206 p` |
| `Avoid_Rollover_20_23_UTC` *(entry-hour only)* | `5,256` | `39.29%` | `-0.665 p` | `-2.759 p` | `2.094 p` |
| **`MetaLabel_Risk_Gated_70pct_VALID`** (`p <= q70_VALID`) | `4,331` | **`16.05%`** | `-0.256 p` | **`-2.102 p`** | **`1.846 p`** |
| `High_Risk_Blocked_Cohort` (`p > q70_VALID`) | `1,787` | **`80.47%`** | `-1.200 p` | **`-4.280 p`** | **`3.080 p`** |

**Interpretation:**
* Blocking the top 30% highest-risk windows (`1,787` trades suffering `80.47%` shock rate and `3.080 pips/trade` cost drag!) cuts shock frequency in half (`34.86% -> 16.05%`) and trims per-trade friction (`2.206 -> 1.846 pips`, `-16.3%`).
* **Phase C Kill Point Confirmation:** Even after removing the worst 30% of intraday liquidity windows, `Net Mean = -2.102 pips/trade` remains deeply negative (`Gross -0.256 p`, `Cost Drag 1.846 p`). Meta-labeling reduces execution waste — it **never manufactures directional FX alpha**.

---

## 5. Governance Decision
- **Pre-Registered Rule (`EXP-0030 / H33`):** Reject directional/path-first-passage Triple-Barrier labeling (`TB_VolNorm` WF `0.4685`, `TB_CapitalDD5` WF `0.5419`) and reject any positive-expectancy FX execution claim (`EURGBP` Net `-2.102 p < 0`).
- **Accepted Risk-Engineering Rule:** Retain **non-directional volatility/drawdown stress meta-labeling** (`TB_NonDirStress` WF `0.6641`, matching Task 3 `target_vol_onset` `0.6882` / `target_tail_stress` `0.6966`) and **horizon-aware rollover + spread/ATR shock gating** (`State_Only` `0.6692`) strictly for **offline risk calibration, execution-cost guarding, and Risk Radar (`Workstream D`) research**.
- **Phase Gate:** **Phase C Kill Point stays LOCKED.** `AlinaRiskGovernor.mq5` stays `SIG_NONE` / `MODE_PAPER`; Phase D ML remains parked.
