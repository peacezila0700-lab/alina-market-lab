# ALINA Market Lab — Project Status

Last Updated UTC: `2026-11-21` (`v2.22`) | Active Phase: **Phase C Kill Point (`0/47` Non-Trend Alpha) + Two Audited Defensive Regime Overlays (`EXP-0033` Equity + `EXP-0041/0043` Multi-Coin Crypto)**

## 1. Executive Summary & Epistemic Ledger
- **Verified Fact (`Exhaustive Research Closeout — EXP-0001..0048`):**
  - Across **`48` empirical experiments (`EXP-0001..0048`)** and **`55` pre-registered hypotheses (`H01..H55`)**, **`0 / 47`** directional alpha, institutional-13F, macro-liquidity, academic-factor, FX, index-rebalance, SEC-PEAD, commodity-COT/EIA, VIX-ETP, or cost-sensitive intraday/overnight anomalies pass ALINA's survivorship-free OOS + permutation + realistic transaction-cost survival bars. Phase D Machine Learning alpha models, Live Trading, and Demo Trading remain **STRICTLY PARKED**, and `AlinaRiskGovernor.mq5` stays locked at `SIG_NONE` / `MODE_PAPER`.
  - Meanwhile, **`v2.22`** validated and strengthened ALINA's **TWO strictly causal, zero-tuning Defensive Regime & Volatility-Management Overlays** integrated into `scripts/risk_radar.py` & `dashboard/alina_today.html`:
    1. **Equities (`EXP-0033`, `2015–2026` Tiingo TR + `BIL`, tested against `Base23+NetLiq` in `EXP-0044`):** `VolTarget12% x RiskMeta(23f) -> BIL Cash` cuts `SPY` MaxDD `-33.70% -> -14.74%`, Sharpe **`+0.816 -> +0.930`**, Calmar **`0.404 -> 0.699`**. Adding Fed Net Liquidity (`WALCL-TGA-RRP`), T10YIE, and 10Y-2Y curve across full `3,830d` WF failed to improve `Base23` (`VolOnset 0.7656 -> 0.7591`; `Base23` stays cleanest).
    2. **Crypto (`EXP-0041` + `EXP-0043`, 11.5y BTC + 7.1y ETH + Survivorship-Free 19-Coin Basket `2018–2026`):** `SMA50_VT25` beats Buy&Hold Sharpe on **`15/19` coins** (including `-96%..-99.7%` fallen majors `FIL -0.099 -> +0.477`, `ICP -0.167 -> +0.298`, `EOS +0.211 -> +0.471`), raises **19-Coin Equal-Weight** Sharpe **`+0.661 -> +1.176`** while cutting MaxDD **`-81.8% -> -19.1%`** (`Calmar 0.320 -> 1.039`, `IS +1.337 | OOS23-26 +0.972`, `30bp +1.015`, **`Shift300 = 99.67%`**), and holds even when stripping out BTC & ETH (`17 Altcoins`: `+0.648 -> +1.088`, DD `-18.5%`, `Shift300 = 98.67%`). `compute_crypto_trend_overlay()` now includes live 19-coin breadth (`>SMA50`).
- **Wave `v2.22` (`EXP-0043..0048`) Open-Data Findings:**
  - `EXP-0043`: 19-coin Trend+VT25 **VALIDATED** (`15/19` coins); Cross-Sectional Crypto Mom (`OOS -0.239/-0.151`) & 4.9y Binance OI/L-S Crowding (**degraded `TrendEns` OOS `+0.368 -> +0.241/-0.788`**) **REJECTED**.
  - `EXP-0044`: US Fed Net Liquidity timing (`SPY OOS +0.587 < +0.675`; `Risk Meta` AUC `-0.0065`) & `SVXY/VXZ/BIL` VIX Term Switch (`OOS -0.299`, `0.0%` shift) **REJECTED**.
  - `EXP-0045`: 20y CFTC Disaggregated Commodity COT (`8,779` rows), EIA Weekly Inventories (`USO -0.114`, `UNG -0.194`), & `19` Country Equity ETFs TR (`Mom12-1 L/S -0.142`, `Rev21d +0.090`) **REJECTED**.
  - `EXP-0046`: 63.2y Ken French Daily Factors (`1963–2026`, `15,918d`): `SMB (-0.100)`, `HML (-0.062)`, `CMA (+0.033)` decayed post-2010; all Factor Momentum rules trailed Static EW (`+0.177`) post-2010 at `10bp` (`-0.052..+0.147`) **REJECTED**.
  - `EXP-0047`: `54` SEC Form 13F bulk zips (`2013q2–2026q3`, `18,466` causal rows across `386` matched active+delisted firms, `$5` investability floor after catching `SIVBQ +8,362%` / `FRCB +700%` OTC penny glitches): all 10 Breadth/HHI/Put-Call strategies failed 95% ticker permutations (`25.5%..90.5%`, `L/S -0.380..+0.276`) **REJECTED**.
  - `EXP-0048`: Wikipedia Daily Attention (`6` assets), 33y CBOE SKEW (`OOS +0.421/+0.484 < +0.652`), and S&P 500 Additions (`5d -0.54%, t=-0.63`) **REJECTED**.

## 2. Workstream Go / No-Go Scorecard
| Workstream | Objective | Status | Decision / Gate |
|---|---|---|---|
| **A1 — SEC PIT + `68` Delisted + 54-Zip SEC 13F** | `EXP-0026/32/34/37/47` (`386` active+delisted, 0 leaks) | **DONE** | **REJECT EQUITY & 13F ALPHA PERMANENTLY** |
| **A2 — `23f` Risk Meta + `BIL` Cash vs NetLiq/Curve** | `EXP-0030/31/33/40/44` (`3,830d` WF) | **DONE** | **GO `Base23` RISK RADAR & `BIL` DEFENSE** |
| **A3 — Form 4, RegSHO, DIX/GEX, FF63y, Country/Comm** | `EXP-0035/39/42/45/46/48` (`1963–2026` tests) | **DONE** | **NO_EDGE / PANEL 9 DESCRIPTIVE ONLY** |
| **B — Microstructure, 4.9y OI/L-S & 19-Coin Crypto Trend** | `EXP-0038/41/43` (`19` coins + `1,796d` UM metrics) | **DONE** | **NO-GO 1H/OI / GO 19-COIN TREND+VT25 OVERLAY** |
| **C — EA KB Batch 6** | `2,174` OSI files, `553` EAs, SQLite KG + FTS5 | **DONE** | **GO COMPLETE** (`integrity=ok`) |
| **D — Daily Risk Radar & Offline Dashboard** | `9/9 FRESH` + `Base23` + 19-Coin Crypto Breadth + `38/38` tests | **DONE** | **GO LIVE MONITORING** |
