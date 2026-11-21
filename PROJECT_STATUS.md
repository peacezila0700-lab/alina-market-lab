# ALINA Market Lab — Project Status

Last Updated UTC: `2026-11-21` (`v2.20`) | Active Phase: **Phase C Kill Point (Offline Risk/Volatility Engineering, Data Integrity & Monitoring Only)**

## 1. Executive Summary & Epistemic Ledger
- **Verified Fact:** Across **`35` logged empirical experiments (`EXP-0001..0035`)** and **`38` pre-registered hypotheses (`H1..H38`)**, **`0` directional trading, factor, or carry/arbitrage rules** clear ALINA's out-of-sample + permutation/bootstrap + realistic transaction-cost survival bars. Phase D Machine Learning alpha models, Live Trading, and Demo Trading remain **STRICTLY PARKED**, and `AlinaRiskGovernor.mq5` stays locked at `SIG_NONE` / `MODE_PAPER`.
- **Verified Fact (`v2.20` Delisted Expansion, Form 4 & FINRA RegSHO Continuation):**
  - Expanded Tiingo US delisted prices (`data/stocks_delisted_tiingo/`) from `30` to **`70` clean US delisted stocks** (`SPLS/CA/EMC/WRK/NFX` quarantined for ticker reuse or `<100` rows; `90/500` Tiingo monthly symbols used, `410` left).
  - Resolved **`41/41`** remaining delisted SEC EDGAR CIKs (`40` via SEC DERA `sub.txt` + `CTRA->858470`), raising `data/sec/pit_fundamentals_delisted.csv` from `27` to **`68` delisted firms (`2,372` PIT snapshots, `leaks=0`)**.
  - Pulled `2018q1..2024q4` SEC Form 3/4/5 (`28` quarters) and merged with `2025q1..2026q1` into `data/sec/insider_form4_2018_2026q1.csv.gz` (**`971,831` `P/S` open-market trades across `8,826` tickers**).
  - Audited FINRA free `otcMarket/equityShortInterest` API (proved it only serves `2018-09-14 Other OTC`; removed stale `finra_short_interest_latest5k.csv.gz`), and migrated to public **FINRA RegSHO Consolidated NMS Daily Short Volume** (`CNMSshvolYYYYMMDD.txt`), ingesting **`1,984` trading days (`2019-01-02..2026-11-20`)** into `finra_regsho_market_daily.csv` and **`661,677` rows across `375` active + delisted stocks** into `finra_regsho_universe_daily.csv.gz`.
- **Experimental Result — `EXP-0034` (`H37` Monotonic Survivorship Collapse):** Expanding delisted coverage `0 -> +27 -> +68` (`317 -> 344 -> 385` firms) collapsed `F_NEG_ACCRUALS` 10bp L/S Sharpe **`+0.729 -> +0.579 -> +0.453`** (`OOS perm 92.5% -> 75.0% -> 73.5%`; `-37.9%`), with `528` distressed/delisted firm-quarters entering the Long leg vs `332` Short. `F_SECTOR_NEUT_ACCRUALS` OOS collapsed `+0.227 -> +0.011 -> -0.064` (`48.5%` coinflip). Accounting accrual alpha is **permanently rejected**.
- **Experimental Result — `EXP-0035` (`H38` Causal Form 4 & RegSHO Evaluation):** Strict causal (`filing_date + 1td` / `regsho_date + 1td`) testing across `384` survivorship-free firms (`316` active + `68` delisted) found **zero reliable alpha**: all Form 4 signals picked `[neg]` IS (mega-cap routine selling vs distressed buying) and failed OOS ticker permutations (`72.5–86.5%` < `95%`), while `REGSHO_EXEMPT_RATIO_20D` depended heavily on 2020 COVID (`+3.40` Sharpe, with `2021/2022/2024` all negative `-0.40/-0.53/-1.00`; OOS tie-broken `+0.335`, perm `89.0%`). Adding RegSHO to Walk-Forward Risk Meta degraded `TailStress AUC` (`0.6624 -> 0.6347`, `-0.0277`). RegSHO stays strictly as **descriptive Risk Radar Panel 9** (not an ML predictor or signal).
- **Operational Integration (`Workstream D`):** `scripts/risk_radar.py` reports **`9/9 FRESH` (`overall=HIGH`, `VIX=35.89`, `alerts=4`)** including Panel 9 (`equity_short_insider_breadth`: RegSHO market short ratio `0.4612`, `z60=-2.02`, `12,414` NMS symbols, through `2026-11-20`); `36/36 pytest` passing (`3.10s`).

## 2. Workstream Go / No-Go Scorecard
| Workstream | Objective | Status | Decision / Gate |
|---|---|---|---|
| **A1 — SEC PIT + `68` Delisted Audit** | `317` active + `68` delisted US firms (`EXP-0026`, `EXP-0032`, `EXP-0034`) | **DONE** (`0` leaks) | **FAIL_SURVIVORSHIP / REJECT ALPHA** (`+0.729 -> +0.453`, perm `73.5%`) |
| **A2 — Risk Meta & Total-Return Overlay** | Calibrated Vol-Onset / TB / `BIL` Cash vs `TLT` (`EXP-0030/0031/0033`) | **DONE** (`36/36` tests) | **GO RISK RADAR & CASH DEFENSE / NO-GO BLIND TLT** |
| **A3 — Causal Form 4 & FINRA RegSHO** | `971k` Form 4 (`2018–26`) + `661k` RegSHO (`2019–26`, `EXP-0035`) | **DONE** (`+1td` lag) | **NO_EDGE / PANEL 9 MONITORING ONLY** (degrades WF Risk AUC `-0.028`) |
| **B — Microstructure, FX & Crypto History** | `23y` FX (`0` neg spreads), Deribit `0` gaps + DVOL, Binance Vision `2020–26` | **DONE** (`EXP-0028..0030`) | **RISK-GATE ONLY / NO-GO FX & CRYPTO BASIS** |
| **C — EA KB Batch 6** | `2,174` OSI files, `553` EAs, SQLite KG + FTS5 | **DONE** | **GO COMPLETE** (`integrity=ok`) |
| **D — Daily Risk Radar & Dashboard** | Automated `9/9 FRESH` monitor + calibrated Meta-Labeling UI | **DONE** | **GO LIVE MONITORING** (`Personal Research in Cloud`; Telegram deferred) |
