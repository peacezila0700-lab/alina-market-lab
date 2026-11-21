# ALINA Market Lab — Project Status

Last Updated UTC: `2026-11-21` (`v2.19`) | Active Phase: **Phase C Kill Point (Offline Risk/Volatility Engineering, Data Integrity & Monitoring Only)**

## 1. Executive Summary & Epistemic Ledger
- **Verified Fact:** Across **`33` logged empirical experiments (`EXP-0001..0033`)** and **`36` pre-registered hypotheses (`H1..H36`)**, **`0` directional trading or carry/arbitrage rules** clear ALINA's out-of-sample + permutation/bootstrap + realistic transaction-cost survival bars. Phase D Machine Learning alpha models, Live Trading, and Demo Trading remain **STRICTLY PARKED**, and `AlinaRiskGovernor.mq5` stays locked at `SIG_NONE` / `MODE_PAPER`.
- **Verified Fact (`v2.19` Cloud Data Upgrade):** Completed Zero-Key + Tiingo Starter + EODHD Free ingestion and hygiene audit (`35/35 pytest` passing in `1.46s`):
  - Fixed `data/broad/TLT.csv` (`6,121` bars) + `15` dividend-adjusted Tiingo ETFs (`data/etfs_tiingo/`, post-close `2026-11-20` `SPY=689.81`).
  - Restored `320/320` active `data/sec/prices_pit/` + added `30` Tiingo delisted stocks (`SIVBQ`, `FRCB`, `SBNY`, `BBBYQ`, `RADCQ`, `WEWKQ`, `TWTR`, `ATVI`, etc.) + `27` zero-leak SEC delisted PIT firms (`1,030` snapshots, `0` leaks) + `133,957` Form 4 open-market insider P/S transactions (`2025q1..2026q1`) + `1,262` historical S&P 500 constituents (`1996..2026-08-18`).
  - Backfilled `central_bank_rates_daily.csv` `effr` `10,186/10,186` (`0` nulls) via FRED `DFF`, expanded `treasury_auctions.csv` (`11,154` rows `1979–2026`), extended `event_calendar_full.csv` through `2027-12-31` (`FOMC/ECB/BOE/BOJ`), backfilled `deribit_{BTC,ETH}_funding_1h` (`0` gaps) + `DVOL 1h` (`49,632` rows), pulled Binance Vision `2019–2026` (`59,904` perp bars `BTC/ETH/SOL`), pulled `EODHD SET/SET50/SET100.INDX` (`1y` free cap), deduplicated `cot_features.csv` (`0` dups), fixed `HYPOTHESIS_REGISTER.csv` (`H09–H11`), fixed `2` crossed H1 FX spreads (`0` remaining), and audit-flagged `congress_trades.csv` & `CCZ`.
- **Experimental Result — `EXP-0032` (`H35` Survivorship Bias Proof):** Adding `+27` real delisted/bankrupt/M&A US firms (`317 -> 344`) dropped `F_NEG_ACCRUALS` 10bp L/S Sharpe `+0.729 -> +0.579` (`OOS perm 92.5% -> 75.0%`), confirming active-only testing overstated Sharpe by ~`+26%`.
- **Experimental Result — `EXP-0033` (`H36` Total-Return Overlay Parity):** Re-evaluating `EXP-0031` (`2015–2026`, `n=2,943`) on Tiingo dividend-adjusted `adjClose` + tradeable `BIL` T-Bill ETF confirmed `5_VolTarget12_Meta_Cash` (`Sharpe +0.930`, `CAGR +10.11%`, `MaxDD -14.74%`, `Calmar 0.699`) outperforms `SPY Buy & Hold` (`Calmar 0.404`, `MaxDD -33.70%`) and blind `TLT` rotation (`MaxDD -27.00%`, `Calmar 0.336`).
- **Operational Integration (`Workstream D`):** `scripts/risk_radar.py` reports **`8/8 FRESH` (`overall=HIGH`, `VIX=35.89`)** with zero missing-data warnings on 2027 CB calendars or crypto funding archives (`dashboard/alina_today.html` `13 KB`, offline).

## 2. Workstream Go / No-Go Scorecard
| Workstream | Objective | Status | Decision / Gate |
|---|---|---|---|
| **A1 — SEC PIT + Survivorship Audit** | `317` active + `27` delisted US firms (`EXP-0026`, `EXP-0032`) | **DONE** (`0` leaks) | **FAIL_SURVIVORSHIP / MONITOR ONLY** (`+0.729 -> +0.579` w/ delisted) |
| **A2 — Risk Meta-Labeling & Total-Return Overlay** | Calibrated Vol-Onset / TB / `BIL` Cash vs `TLT` (`EXP-0030/0031/0033`) | **DONE** (`35/35` tests) | **GO RISK RADAR & CASH DEFENSE / NO-GO BLIND TLT** |
| **B — Microstructure, FX & Crypto History** | `23y` FX (`0` neg spreads), Deribit `0` gaps + DVOL, Binance Vision `2020–26` | **DONE** (`EXP-0028..0030`) | **RISK-GATE ONLY / NO-GO FX & CRYPTO BASIS** |
| **C — EA KB Batch 6** | `2,174` OSI files, `553` EAs, SQLite KG + FTS5 | **DONE** | **GO COMPLETE** (`integrity=ok`) |
| **D — Daily Risk Radar & Dashboard** | Automated `8/8 FRESH` monitor + calibrated Meta-Labeling UI | **DONE** | **GO LIVE MONITORING** (`Personal Research in Cloud`; Telegram deferred) |
