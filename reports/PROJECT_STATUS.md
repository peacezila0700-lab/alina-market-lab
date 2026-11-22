# ALINA Market Lab — Project Status

Last Updated UTC: `2026-11-22` (`v2.23`) | Active Phase: **Phase C Kill Point (`0/64` Non-Trend Alpha Across `54` Experiments) + Two Audited Defensive Regime Overlays (`EXP-0033` Equity + `EXP-0041/0043` Multi-Coin Crypto)**

## 1. Executive Summary & Epistemic Ledger
- **Verified Fact (`Exhaustive Research Closeout — EXP-0001..0054`):**
  - Across **`54` empirical experiments (`EXP-0001..0054`)** and **`64` pre-registered hypotheses (`H01..H64`)**, **`0 / 64`** directional alpha, on-chain crypto, macro-surprise, 55-year cross-sectional equity, equity option IV surface, Thai SET50/TFEX intraday, earnings-transcript NLP, SEC XBRL buyback/net-issuance, SEC `8-K` event, 13F institutional, academic-factor, FX, or overnight anomalies survive ALINA's survivorship-free OOS + permutation + transaction-cost survival bars. Phase D Machine Learning alpha models, Live Trading, and Demo Trading remain **STRICTLY PARKED**, and `AlinaRiskGovernor.mq5` stays locked at `SIG_NONE` / `MODE_PAPER`.
  - Meanwhile, ALINA's **TWO strictly causal, zero-tuning Defensive Regime & Volatility-Management Overlays** inside `scripts/risk_radar.py` & `dashboard/alina_today.html` survived **every adversarial challenger in `v2.22` (`EXP-0043/0044`) and `v2.23` (`EXP-0049/0051b`)**:
    1. **Equities (`EXP-0033`, confirmed vs 55y LowVol in `EXP-0051b` & Fed NetLiq in `EXP-0044`):** `VolTarget12% x RiskMeta(23f) -> BIL Cash` cuts `SPY` MaxDD `-33.70% -> -14.74%`, Sharpe **`+0.816 -> +0.930`**, Calmar **`0.404 -> 0.699`**. `2014–2026` S&P 500 `LowVol60_LO_VT12` (`+0.876`) only matched `SPY_VT12 (+0.857)` and trailed `EXP-0033 (+0.930)`.
    2. **Crypto (`EXP-0041` + `EXP-0043`, confirmed vs On-Chain/DeFi/COT in `EXP-0049`):** `SMA50_VT25` delivers **All `+1.713` | OOS `+1.534` | DD `-31.38%` (`Shift300 = 100%`)** on `13.4y` CoinMetrics BTC, **`+1.480`** on `11y` ETH, and **`+1.315`** (`OOS +1.297`) on the survivorship-free 19-coin basket (`15/19` coins beat BuyHold). Zero CoinMetrics MVRV/flow/address, DeFiLlama stablecoin/TVL, Fear&Greed, or CME COT overlays beat `SMA50_VT25_Base`.
- **Wave `v2.23` (`EXP-0049..0054` + `EXP-0054b/c/d` — Complete Public Catalog Audit):**
  - `EXP-0049`: CoinMetrics (`BTC/ETH` on-chain), DeFiLlama Stablecoin/TVL, Crypto Fear&Greed, and CME Crypto COT (`2013–2026`) **REJECTED**.
  - `EXP-0050`: Forex Factory H1 macro surprise drift (`1,911` timed USD clusters `2007–2025`), Daily Surprise EMA (`2008–2025`), and Philly Fed SPF (`2000–2026`) **REJECTED**.
  - `EXP-0051` + `0051b`: `55`-year CRSP-reconciled PIT S&P 500 (`Johnbrick123`, `1971–2026`, `membership_intervals.parquet`) cross-sectional factors (`Mom_12_1`, `FIP`, `Rev_21d`, `LowVol_60d`, `Dist52H`, `LowVol_x_Mom`) decayed post-2006 (`OOS -0.09..+0.12`); S&P 500 Additions drift collapsed `2014–2026` (`21d -0.374% t=-0.68`) **REJECTED**.
  - `EXP-0052`: S&P 500 Equity Options IV Surface (`3.16M` rows -> `678k` daily surface, `2019–2023`, Monthly `21d` & Weekly `5d`) **REJECTED**.
  - `EXP-0053`: Thai `SET50` Daily (`2006–2023` Trend/Basis/OI) & `TFEX S50` 1-Minute Intraday (`2016–2025`, `2,428d`, all 7 strategies negative at `2bp` & `5bp`) **REJECTED** (`54,294` clean 15m bars archived).
  - `EXP-0054` (`0054b/c/d`): Adversarial 4-stage audit killed Earnings Transcripts (`20,681` calls, Calendar-Time `net_tone_21d +0.057`, `OOS -0.187`), SEC XBRL Buybacks (`100%` PIT S&P 500 `796/797` mapped, `806` CIKs, `unsplit_close`: `SecNeut -0.000`, `EW 10bp +0.207`, `20bp -0.316`, `bb/assets +0.010`, `net_share_red +0.034`), SEC `8-K` filings (`808` archive JSONs, `133,850` `8-K`s, `Item 5.02 n=17,846 21d -0.071% t=-1.20`), and 38y Deep Sea Freight PPI (`+45d` lag) **REJECTED**.

## 2. Workstream Go / No-Go Scorecard
| Workstream | Objective | Status | Decision / Gate |
|---|---|---|---|
| **A1 — 55y PIT S&P 500, SEC Buybacks/8-K/13F/PEAD, Transcripts** | `EXP-0026/32/34/37/47/51/52/54` (`796/797` PIT S&P 500, `1971–2026`) | **DONE** | **REJECT EQUITY CROSS-SECTIONAL & FILING ALPHA** |
| **A2 — `23f` Risk Meta + `BIL` Cash vs Macro Surprises/SPF/Freight** | `EXP-0030/31/33/40/44/50/54` (`3,830d` WF) | **DONE** | **GO `Base23` RISK RADAR & `BIL` DEFENSE** |
| **A3 — Form 4, RegSHO, DIX/GEX, FF63y, Country/Comm, Thai SET50/TFEX** | `EXP-0035/39/42/45/46/48/53` (`1963–2026` tests) | **DONE** | **NO_EDGE / PANEL 9 & ARCHIVE ONLY** |
| **B — Microstructure, 4.9y OI/L-S & 13.4y On-Chain/DeFi/COT Crypto** | `EXP-0038/41/43/49` (`BTC 2013–26` + `19` coins) | **DONE** | **NO-GO ON-CHAIN/1H/OI / GO `SMA50_VT25` OVERLAY** |
| **C — EA KB Batch 6** | `2,174` OSI files, `553` EAs, SQLite KG + FTS5 | **DONE** | **GO COMPLETE** (`integrity=ok`) |
| **D — Daily Risk Radar & Offline Dashboard** | `9/9 FRESH` (`VIX 35.89 HIGH`, `Eq 44.6%`, `BTC 0%`, `1/19 >SMA50`) + `39/39` tests | **DONE** | **GO LIVE MONITORING** |
