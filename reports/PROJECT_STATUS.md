# ALINA Market Lab — Project Status

Last Updated UTC: `2026-11-21` (`v2.21`) | Active Phase: **Phase C Kill Point (`0/41` Non-Trend Alpha) + Two Audited Defensive Regime Overlays (`EXP-0033` Equity + `EXP-0041` Crypto)**

## 1. Executive Summary & Epistemic Ledger
- **Verified Fact (`Exhaustive Research Closeout — EXP-0001..0042`):**
  - Across **`42` empirical experiments (`EXP-0001..0042`)** and **`45` pre-registered hypotheses (`H01..H45`)**, **`0 / 41`** directional alpha, stock-selection, FX, index-rebalance, SEC-PEAD, bond-timing, or cost-sensitive intraday/overnight anomalies pass ALINA's survivorship-free OOS + permutation + realistic transaction-cost survival bars. Phase D Machine Learning alpha models, Live Trading, and Demo Trading remain **STRICTLY PARKED**, and `AlinaRiskGovernor.mq5` stays locked at `SIG_NONE` / `MODE_PAPER`.
  - Meanwhile, ALINA has proven and integrated **TWO strictly causal, zero-tuning Defensive Regime & Volatility-Management Overlays** into `scripts/risk_radar.py` & `dashboard/alina_today.html`:
    1. **Equities (`EXP-0033`, `2015–2026` Tiingo TR + `BIL`):** `VolTarget12% x RiskMeta(23f) -> BIL Cash` cuts `SPY` MaxDD `-33.70% -> -14.74%`, Sharpe **`+0.816 -> +0.930`**, Calmar **`0.404 -> 0.699`**.
    2. **Crypto (`EXP-0041`, `2015–2026` 11.5y BTC + 7.1y ETH + `EFFR`):** Unoptimized textbook `SMA50_VT25` (`BTC 11.5y`: Sharpe **`+1.665`**, CAGR `+45.3%`, MaxDD **`-33.5%`** vs `-83.4%` B&H, Calmar `1.350`, `1,000` circular shifts **`99.9%` `p=0.001`** passing Bonferroni, `50bp/side = +1.415`; `ETH 7.1y`: `+1.288`, DD `-21.6%`, `99.5%`) and `TrendEns(20..120)_VT25` (`BTC Sh +1.590`, DD `-27.8%`, survives `2-day` delay at `+1.484` `99.7%`). Blending **`85% SPY_VT12 + 15% BTC_TrendEns_VT25`** (`corr = +0.108`) raises Excess Sharpe `+0.736 -> +1.157` (`Calmar 0.693 -> 0.962`) at `-15.38%` MaxDD.
- **Wave `EXP-0036..0042` Findings (All Logged & Verified):**
  - `EXP-0036` (S&P 500 Rebalance `t_eff+1td`): **`NO_EDGE`** (`ADD+5d -0.925%`, `21d L/S -0.139`).
  - `EXP-0037` (SEC PIT PEAD `15,000` events): **`NO_EDGE`** (OOS IC collapsed `-0.0089..+0.0033`, all 4 `21d L/S < 0`).
  - `EXP-0038` (Crypto 6.8y 1h/Funding/DVOL): 1h OFI/Basis died at `4bp` (`-0.31..-3.99`); post-2024 Cash-Carry compressed to `+3.5–3.6%/yr`; `DVOL` throttle underperformed `VT30`; Daily SMA escalated to `EXP-0041`.
  - `EXP-0039` (`DIX/GEX`, `GEM`, `GTAA-6`, `RiskParity`, 26y Sector `Mom12-1`): **`NO_EDGE`** (`GEM OOS +0.358` `15.0%`, `GTAA-6 72.5%`, `RP OOS +0.693` `50.5%`, Sector `L/S -0.035`, `+DIX/GEX` zero lift on 23f Risk Meta `0.7656 -> 0.7633`).
  - `EXP-0040` (Treasury Curve & 408 Auctions): **`NO_EDGE`** (`TLT OOS -0.160`, all curve+SMA negative OOS, auctions `r=-0.0075..-0.0427`).
  - `EXP-0042` (26.8y Overnight `C->O` Drift): **`NO_EDGE`** (`BE = 1.52–2.90 bp/side`, destroyed at `2–5 bp/side`).
- **Operational State:** `scripts/risk_radar.py` reports **`9/9 FRESH` (`overall=HIGH`, `alerts=4`)**, Risk Meta equity `44.6% / BIL 55.4%`, Crypto Trend Overlay (`BTC $59,958 < SMA50 $77,133`) = `0.0% BTC / 100.0% Cash`; **`37/37 pytest` PASSED (`3.00s`)**.

## 2. Workstream Go / No-Go Scorecard
| Workstream | Objective | Status | Decision / Gate |
|---|---|---|---|
| **A1 — SEC PIT + `68` Delisted Audit + PEAD** | `317` active + `68` delisted (`EXP-0026/32/34/37`) + S&P diffs (`EXP-0036`) | **DONE** (`0` leaks) | **REJECT ALPHA PERMANENTLY** |
| **A2 — Risk Meta + Total-Return Overlay** | `23f` Calibrated Risk + `BIL` Cash vs `TLT`/Curve/Auctions (`EXP-0030/31/33/40`) | **DONE** | **GO EQUITY RISK RADAR & `BIL` CASH DEFENSE** |
| **A3 — Form 4, RegSHO, DIX/GEX, ETF Rotation** | `971k` Form 4, `661k` RegSHO (`EXP-0035`), `DIX/GEX` + `GEM/GTAA/RP` (`EXP-0039/42`) | **DONE** | **NO_EDGE / PANEL 9 DESCRIPTIVE ONLY** |
| **B — Microstructure, FX & 11.5y Crypto Trend** | 23y FX, 6.8y 1h/DVOL (`EXP-0038`) + 11.5y Daily Trend+VT25 (`EXP-0041`) | **DONE** | **NO-GO 1H & FX / GO LONG-ONLY CRYPTO TREND OVERLAY** |
| **C — EA KB Batch 6** | `2,174` OSI files, `553` EAs, SQLite KG + FTS5 | **DONE** | **GO COMPLETE** (`integrity=ok`) |
| **D — Daily Risk Radar & Offline Dashboard** | `9/9 FRESH` + Equity Risk Meta + Crypto Trend Monitor + `37/37` tests | **DONE** | **GO LIVE MONITORING** |
