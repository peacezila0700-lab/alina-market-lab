# ALINA EA Knowledge Base — Batch 6 Provenance & Risk Architecture Report

**Date (UTC):** 2026-11-20 (Asia/Bangkok)  
**Scope:** Task 2 — Targeted Batch 6 Expansion of `data/ea_kb/alina_ea_kb.sqlite` from Verified, Explicitly Licensed Open-Source GitHub Repositories  
**Status:** `COMPLETE` (SQLite `PRAGMA integrity_check == ok`, `7/7` workstream tests passing, zero Batch 1–5 historical records modified or deleted)  
**Key Script & Artifacts:**  
- Script: `scripts/build_ea_kb_batch6.py`  
- Database: `data/ea_kb/alina_ea_kb.sqlite` (Pre-Batch 6 backup verified intact prior to update)  
- Stats & Audit Logs: `data/ea_kb/KB_STATS_BATCH6.json`, `data/ea_kb/batch6_provenance_audit.json`  
- Local Verified Source Mirror: `data/ea_kb/sources_batch6/` (`74` files across `10` repositories)

---

## 1. Executive Summary & Database Delta (Verified Facts)

Batch 6 addresses the exact structural blind spots identified in `RESEARCH_ANALYSIS_EXP0001_0029.md`: whereas Batches 1–5 (`2,100` files) were heavily concentrated in raw MQL4/5 scripts where only `49.9%` of local EAs implemented a hard Stop Loss and only `5.7%` implemented a Daily Drawdown Guard, **Batch 6 selectively ingests `74` verified source files (`35,593` lines, `1.37 MB`) strictly focused on Risk Management, Position Sizing, Kalman/Volatility Regime Modeling, Engine Protections, and Execution Controls.**

| Table / Metric | Pre-Batch 6 (v2.16) | Batch 6 Added | Post-Batch 6 Total | Verification |
|---|---:|---:|---:|---|
| `source_files` | `2,100` | `+74` | **`2,174`** | All `2,174` `local_path` verified on disk |
| `ea_master` | `499` | `+54` | **`553`** | `EA-B6-0001..0054` (`Confirmed`, Level 1) |
| `github_repos` | `75` | `+10` | **`85`** | `100%` OSI-licensed (`MIT`, `Apache-2.0`, `GPL-3.0`) |
| `developers` | `197` | `+5` | **`202`** | Linked via `authored_by` KG edges |
| `duplicates` | `1,322` | `+10` | **`1,332`** | `7` excluded Jesse mirrors + `3` MT4↔MT5 ports |
| `kg_edges` | — | — | **`5,503`** | Includes `implements_risk_control`, `belongs_to_repo`, `fork_or_modified` |
| `kb_fts` | — | — | **`2,477`** | Full-text FTS5 indexed (`RAG-SRC_B6_*`) |
| `PRAGMA integrity_check` | `ok` | — | **`ok`** | `tests/test_workstreams.py` `7/7 PASS` |

### Platform Breakdown (Batch 6 Only)
- `Python_ML4T` (`stefan-jansen/machine-learning-for-trading`): `18` files (`19,388` lines, `762,331` B)
- `Python_Freqtrade` (`freqtrade/freqtrade` + `freqtrade-strategies`): `15` files (`4,122` lines, `165,813` B)
- `cTrader_CSharp` (`spotware/ctrader-algo-samples`): `13` files (`1,031` lines, `40,034` B)
- `Python_Jesse` (`jesse-ai/example-strategies`): `11` files (`903` lines, `32,646` B)
- `Python_Quantopian` (`zipline`, `empyrical`, `pyfolio`): `9` files (`4,746` lines, `150,882` B)
- `MQL_Include` (`EarnForex/AutoTrading-Scheduler` `.mqh`): `4` files (`4,504` lines, `181,452` B)
- `MT4` (`AutoTrading Scheduler.mq4`, `Spread.mq4`): `2` files (`434` lines, `17,841` B)
- `MT5` (`AutoTrading Scheduler.mq5`, `Spread.mq5`): `2` files (`465` lines, `18,130` B)

---

## 2. Repository Provenance Registry & Exclusion Audit

Every Batch 6 repository was queried live against the GitHub REST API at runtime, pinned to an exact 40-character commit SHA, checked for an explicit OSI SPDX license (`MIT`, `Apache-2.0`, `GPL-3.0`), and hashed (`SHA-256`) directly from saved bytes.

### 2.1 Confirmed Batch 6 Repositories (`10/10` Verified)

| Repository | Owner / Org | SPDX License | Branch | Pinned Commit SHA | Commit Date (UTC) | Stars | Files Ingested (`ea_master`) | Primary Knowledge Cluster |
|---|---|---|---|---|---|---:|---:|---|
| `stefan-jansen/machine-learning-for-trading` | `stefan-jansen` | `MIT` | `main` | `fe08097f3ef4...` | `2026-11-16` | `21,929` | `18` (`10`) | Risk Mgmt (VaR/CVaR, Exits, MAE/MFE, Kelly, HRP, Stress, Drift), Kalman/GARCH/HAR/HMM, FX Barrier Labels & Costs |
| `quantopian/zipline` | `quantopian` | `Apache-2.0` | `master` | `014f1fc3399a...` | `2020-12-03` | `20,261` | `4` (`4`) | Multi-Asset OLMAR & Pipeline Portfolio Execution Architecture |
| `quantopian/empyrical` | `quantopian` | `Apache-2.0` | `master` | `40f61b4f22b3...` | `2020-11-17` | `1,521` | `2` (`0`) | Tail Risk, Sortino, Calmar, MaxDD, Downside Risk, Attribution |
| `quantopian/pyfolio` | `quantopian` | `Apache-2.0` | `master` | `4b901f6d73ec...` | `2020-10-12` | `6,440` | `3` (`0`) | Drawdown Duration, Round-Trip Trade Audit, Capacity/Slippage Limits |
| `freqtrade/freqtrade` | `freqtrade` | `GPL-3.0` | `develop` | `a025e7fb3be5...` | `2026-11-19` | `57,119` | `7` (`6`) | `IProtection` Guards (`MaxDrawdown`, `StoplossGuard`, `CooldownPeriod`, `LowProfitPairs`), `IStrategy` Lifecycle, `Wallets` |
| `freqtrade/freqtrade-strategies` | `freqtrade` | `GPL-3.0` | `main` | `f3340ce11fa2...` | `2026-08-29` | `5,672` | `8` (`8`) | `BreakEven`, `FixedRiskRewardLoss`, `CustomStoplossWithPSAR`, `AlmgrenChrissStrategy`, `TWAPStrategy`, `InformativeSample` |
| `jesse-ai/example-strategies` | `jesse-ai` | `MIT` | `master` | `7c91e0a37ba3...` | `2026-05-03` | `181` | `11` (`11`) | `TurtleRules` ATR Unit Sizing & Pyramiding, `Donchian`, `DUAL_THRUST`, `IFR2`, `KDJstrategy`, etc. |
| `spotware/ctrader-algo-samples` | `spotware` | `MIT` | `main` | `0bcec493f9c0...` | `2025-11-12` | `144` | `13` (`13`) | `SampleBreakEven`, `SampleSARTrailingStop`, `StopTriggerMethodSample`, `PartialClose`, `CustomFitnessFunctions`, `BarClosed` |
| `EarnForex/AutoTrading-Scheduler` | `EarnForex` | `Apache-2.0` | `master` | `a7e6dd333022...` | `2025-10-28` | `57` | `6` (`2`) | Weekly Session/News AutoTrading Enforcement & Flatten Guard (MT4 & MT5) |
| `EarnForex/Spread` | `EarnForex` | `Apache-2.0` | `main` | `39135ed73e16...` | `2022-02-23` | `6` | `2` (`0`) | Real-Time Spread Cost Monitor (MT4 & MT5) |

### 2.2 Explicit Provenance Exclusion & Deduplication Audit

1. **Unlicensed Repository Excluded (`quantopian/research_public`):**  
   - **Fact:** GitHub API returns `license: None` (`UNSPECIFIED`) for `quantopian/research_public` (`2,906` stars, commit `e183ecd093`), and neither the repository root nor inspected files (`drafts/kelly/kelly_kalman_pairs.py`) carry a `LICENSE` file or OSI license header.  
   - **Action:** **Strictly excluded** from `source_files`, `ea_master`, and `Confirmed` KB records (`data/ea_kb/KB_STATS_BATCH6.json` logs this under `excluded_unlicensed_audit`). Quantopian Kalman/Pairs/Risk functionality was sourced exclusively from OSI-licensed `stefan-jansen/machine-learning-for-trading` (`MIT`) and `quantopian/zipline`/`empyrical`/`pyfolio` (`Apache-2.0`).
2. **Jesse Legacy Mirror Duplicates Excluded (`7` files):**  
   - **Fact:** `jesse-ai/example-strategies` contains a legacy `example-strategies-master/` folder mirroring root strategy folders (`Donchian`, `TurtleRules`, `IFR2`, `RSI2`, `SMACrossover`, `SimpleBollinger`, `TradingView_RSI`) with `SequenceMatcher` similarity ranging from **`0.8292` to `0.9926`**.  
   - **Action:** Only the `11` canonical root strategies were ingested into `source_files` and `ea_master`; all `7` mirror duplicates were excluded from primary tables and documented in `duplicates` (`DUP_B6_1323..1329`, `near_duplicate_excluded`).
3. **EarnForex Cross-Platform MT4↔MT5 Ports Logged (`3` pairs):**  
   - `AutoTrading Scheduler.mq4` ↔ `.mq5` (`0.9535` similarity, `DUP_B6_1330`), `AutoTrading Scheduler.mqh` MT4↔MT5 (`0.9019`, `DUP_B6_1331`), `Spread.mq4` ↔ `.mq5` (`0.8446`, `DUP_B6_1332`), linked via `fork_or_modified` edges in `kg_edges`.
4. **Pre-Existing Batches 1–2 URL-Normalized Duplicate Audit (`98` cases detected, non-destructive):**  
   - Cross-checking `urllib.parse.unquote(source_url)` across pre-existing Batches 1–2 identified **`98` duplicate URL pairs** (e.g., `EarnForex/PositionSizer` URL-encoded `Position%20Sizer` in Batch 1 vs space-encoded `Position Sizer` in Batch 2, and `geraked/metatrader5` re-ingested across Batch 1 `SRC-0099..` and Batch 2 `SRC-1235..`). Per standing constraint, **zero prior records were deleted or overwritten**; all `98` detections are recorded in `KB_STATS_BATCH6.json` (`preexisting_url_encoding_duplicates_detected`).

---

## 3. Extracted Risk Management & Trading Logic Synthesis

Across all `74` Batch 6 files, automated AST/regex inspection + manual source verification extracted the following control coverage:

| Extracted Risk / Logic Control | Batch 6 Files Implementing | Representative Verified Sources |
|---|---:|---|
| `PositionSizing` (ATR/Kelly/HRP/MAE-MFE/Custom Stake) | `49` (`66.2%`) | `04_kelly_criterion.py`, `06_hierarchical_risk_parity.py`, `03_position_sizing_mae_mfe.py`, `TurtleRules/__init__.py` |
| `HardSL` / Dynamic SL (`custom_stoploss`, ATR stop, `ModifyPosition`) | `38` (`51.4%`) | `FixedRiskRewardLoss.py`, `CustomStoplossWithPSAR.py`, `IStrategy` (`interface.py`), `15_risk_management.py` |
| `SpreadOrSlippageCost` / Impact / Trigger Controls | `33` (`44.6%`) | `AlmgrenChrissStrategy.py`, `TWAPStrategy.py`, `StopTriggerMethodSample.cs`, `16_costs.py`, `pyfolio/capacity.py`, `Spread.mq5` |
| `VolatilityOrRegime` (Kalman, GARCH, HAR, HMM, VIX/Vol) | `24` (`32.4%`) | `04_kalman_filter.py`, `08_garch_volatility.py`, `09_har_rough_volatility.py`, `11_hmm_regimes.py` |
| `TrailingStop` / Dynamic Exit Path | `25` (`33.8%`) | `CustomStoplossWithPSAR.py`, `SampleSARTrailingStop.cs`, `02_exit_strategies.py` |
| `PartialOrBasketExit` / Custom Exit | `22` (`29.7%`) | `PartialCloseSample.cs`, `CloseProfitablePositions.cs`, `Strategy001_custom_exit.py` |
| `DrawdownGuard` / Global Circuit Breakers | `15` (`20.3%`) | `max_drawdown_protection.py`, `04_circuit_breakers.py`, `10_safety_risk_demo.py`, `CustomFitnessFunctions.cs` |
| `CooldownOrLock` (Post-Loss / Low-Profit Lockouts) | `7` (`9.5%`) | `stoploss_guard.py`, `cooldown_period.py`, `low_profit_pairs.py`, `iprotection.py` |
| `VaR_CVaR_RiskMetrics` (Tail Risk / Kupiec / QLIKE) | `6` (`8.1%`) | `01_var_cvar.py`, `empyrical/stats.py`, `pyfolio/timeseries.py` |
| `BreakEven` (Zero-loss / Offset SL Transfer) | `5` (`6.8%`) | `SampleBreakEven.cs`, `BreakEven.py`, `FixedRiskRewardLoss.py` |
| `ScheduleOrMarketClose` (Session / Anti-Repaint Bar Close) | `9` (`12.2%`) | `AutoTrading Scheduler.mq5`, `CloseAllOnMarketCloseSample.cs`, `BarClosedExample.cs` |

### Key Architectural Takeaways Relevant to ALINA Research

1. **Non-Predictive Risk Sizing & Tail Controls (`stefan-jansen`, `empyrical`, `pyfolio`):**
   - `01_var_cvar.py` implements Historical, Parametric, Cornish-Fisher, and Student-t CVaR alongside **Kupiec POF backtesting** and **QLIKE asymmetric volatility loss** (penalizing volatility under-prediction harder than over-prediction—directly matching ALINA's asymmetric risk objective).
   - `04_kelly_criterion.py` proves empirically why raw continuous Kelly sizing (`f* = mu / sigma^2`) is unusable without fractional shrinkage and drawdown ruin constraints due to expected-return (`mu`) estimation error—directly validating why ALINA avoids directional return chasing in favor of volatility-target / downside-risk scaling.
   - `04_kalman_filter.py` demonstrates **forward-scheduled MLE refitting (`schedule_from_refits`)** so hyper-parameters (`process_var`, `obs_var`) never read future observations, solving look-ahead bias in dynamic state-space estimation.
   - `case_studies/fx_pairs/15_risk_management.py` explicitly separates **cost-sensitivity sweeps** from strategy selection ranking to avoid selecting strategies solely because they were evaluated under gentler cost assumptions, and isolates **path-dependent stop losses** from endpoint return evaluation.

2. **Decoupled Engine-Level Risk Protections (`freqtrade`, `EarnForex`):**
   - Unlike Batch 1–5 MQL EAs that mix signal logic and risk checks inside monolithic `OnTick()` loops (`94.3%` lacking daily drawdown guards), Freqtrade enforces engine-level `IProtection` hooks (`MaxDrawdown`, `StoplossGuard`, `CooldownPeriod`, `LowProfitPairs`) completely decoupled from strategy alpha signals (`IStrategy`).
   - `AlmgrenChrissStrategy.py` and `TWAPStrategy.py` embed **execution slicing and temporary/permanent market impact (`eta`, `gamma`, `lambda`)** inside `adjust_trade_position()`, complementing ALINA's rollover spread-shock findings in `EXP-0028`/`EXP-0029`.
   - `EarnForex/AutoTrading-Scheduler` adds strict **24h weekly schedule & pre-close flatten controls** (`WaitForNoPositions`, `DefaultClosePos`, `ALLOWDENY_ALLOW/DENY`), providing an execution-window filter aligned with avoiding the `22:00 UTC` FX rollover spike (`EXP-0028`).

3. **Execution & Anti-Repaint Safety (`spotware/ctrader-algo-samples`, `jesse-ai`):**
   - `StopTriggerMethodSample.cs` highlights spread-spike protection via `StopTriggerMethod` (`Trade` vs `Opposite` vs `DoubleTrade`), preventing false stop-outs during illiquid bid-ask widening—a direct parallel to ALINA's `EXP-0028` Dukascopy bid-ask rollover audit.
   - `BarClosedExample.cs` enforces strictly closed-bar event processing (`OnBarClosed`), preventing intrabar look-ahead/repainting.
   - `CustomFitnessFunctions.cs` demonstrates replacing raw Net Profit optimization with custom penalized risk fitness (`GetFitness`), matching ALINA's `PROB-009` multi-objective sanity posture.
   - `TurtleRules/__init__.py` demonstrates clean Python `risk_to_qty` ATR unit sizing (`1%` equity risk per `2 * ATR(20)`) with a hard `4`-unit pyramiding ceiling.

---

## 4. Direct Mapping to Tasks 3 & 4 (Risk/Volatility Meta-Labeling & `EXP-0030`)

| Batch 6 Module | Extracted Concept | Application in Task 3 & Task 4 (`EXP-0030`) |
|---|---|---|
| `case_studies/fx_pairs/02_labels.py` & `19_risk_management/02_exit_strategies.py` | Path-dependent Triple-Barrier & asymmetric exit labeling | Replaces single-horizon endpoint binary (`rv21_fwd > 1.35 * rv21_past`) in `EXP-0027` with clean **Risk-Event / Volatility-Drawdown Triple-Barrier labels** |
| `09_model_based_features/04_kalman_filter.py` & `01_var_cvar.py` | Causal forward refitting & QLIKE asymmetric loss | Ensures all scalers, volatility baselines, and probability calibrators fit strictly on past purged windows |
| `19_risk_management/03_position_sizing_mae_mfe.py` & `17_portfolio_construction/04_kelly_criterion.py` | Probability-to-Exposure Sizing | Maps calibrated risk probabilities `P(risk_event)` to **causal exposure throttling** (`w_meta`) rather than directional long/short timing |
| `freqtrade/plugins/protections/*` & `EarnForex/AutoTrading-Scheduler` | Decoupled circuit-breaker & cooldown overlays | Provides operational architecture for translating `EXP-0030` risk-regime states into discrete exposure/cooldown states (offline simulation only under Phase C freeze) |

---

## 5. Epistemic Classification

- **Verified Facts:**
  - All `74` Batch 6 files (`35,593` lines) were fetched via live GitHub REST API pinned to exact 40-char commit SHAs from `10` verified OSI-licensed repositories (`MIT`, `Apache-2.0`, `GPL-3.0`), saved to `data/ea_kb/sources_batch6/`, SHA-256 hashed, AST/regex parsed for dependencies, indexed in `alina_ea_kb.sqlite` (`2,174` total `source_files`, `553` `ea_master`, `PRAGMA integrity_check == ok`), and verified by `tests/test_workstreams.py` (`7/7 PASS`).
  - `quantopian/research_public` was verified via GitHub API to have `license=None` and was strictly excluded from `Confirmed` records.
  - `7` duplicate mirror strategies in `jesse-ai/example-strategies/example-strategies-master/` were detected (`0.8292–0.9926` similarity) and excluded from primary strategy tables, and `98` pre-existing URL-encoded/duplicate pairs in Batches 1–2 were audited without altering historical rows.
- **Architectural Hypotheses:**
  - Decoupling risk/exposure guards (`MaxDrawdown`, `AutoTrading-Scheduler`, probability-weighted vol targeting) from directional alpha signals reduces tail drawdown compared to static `100%` exposure, **subject to empirical verification in Task 3 and `EXP-0030`**.
- **Unverified / Missing Evidence:**
  - None of the `54` newly cataloged `ea_master` strategies/cBots from Freqtrade, Jesse, Zipline, or cTrader have been backtested on ALINA's Dukascopy/SPY/crypto data; they remain **Level 1 static source verified only** (`source_available=1`, `evidence_level=1`), and Batch 6 does NOT validate directional profitability of any strategy included in those external repos.
